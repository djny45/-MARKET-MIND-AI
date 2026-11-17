import json, os, tempfile, unittest
from unittest.mock import patch
import httpx
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.n8n_reviewer_security import authenticate_reviewer, require_role, import_approved_workflow, get_import_record

class ReviewerAuthTests(unittest.TestCase):
    def test_authentication_uses_configured_identity_and_roles(self):
        token="r"*48
        with patch.dict(os.environ,{"N8N_REVIEWER_TOKENS_JSON":json.dumps({"reviewer-a":{"token":token,"roles":["reviewer"]}})}):
            principal=authenticate_reviewer(HTTPAuthorizationCredentials(scheme="Bearer",credentials=token))
            self.assertEqual(principal.reviewer_id,"reviewer-a")
            self.assertIn("reviewer",principal.roles)
    def test_missing_or_invalid_token_rejected(self):
        with patch.dict(os.environ,{"N8N_REVIEWER_TOKENS_JSON":json.dumps({"reviewer-a":{"token":"x"*48,"roles":["reviewer"]}})}):
            with self.assertRaises(HTTPException) as err: authenticate_reviewer(None)
            self.assertEqual(err.exception.status_code,401)
    def test_import_role_is_separate(self):
        with self.assertRaises(HTTPException) as err: require_role(type("P",(),{"roles":frozenset({"reviewer"})})(),"importer")
        self.assertEqual(err.exception.status_code,403)

class N8NImportTests(unittest.TestCase):
    def _approved_draft(self, path):
        from app.n8n_workflow_lifecycle import submit_agent_workflow_draft, record_agent_workflow_review
        workflow={"name":"Manual import test","active":False,"nodes":[{"id":"1","name":"Manual Trigger","type":"n8n-nodes-base.manualTrigger","typeVersion":1,"parameters":{}}],"connections":{}}
        with patch.dict(os.environ,{"MARKET_MIND_DB":path}):
            draft=submit_agent_workflow_draft("agent","Manual import test",workflow)
            record_agent_workflow_review(draft["draft_id"],"reviewer-a","approve","approved")
        return draft["draft_id"]
    def test_approved_workflow_imports_and_remote_inactive_state_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"n8n.sqlite"); draft_id=self._approved_draft(db)
            calls=[]
            def handler(request):
                calls.append((request.method,request.url.path,json.loads(request.content) if request.content else None))
                if request.method=="POST":
                    self.assertNotIn("active",json.loads(request.content))
                    return httpx.Response(201,json={"id":"remote-42","name":"Manual import test"})
                return httpx.Response(200,json={"id":"remote-42","name":"Manual import test","active":False})
            client=httpx.Client(transport=httpx.MockTransport(handler))
            env={"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret-test-key"}
            with patch.dict(os.environ,env):
                result=import_approved_workflow(draft_id,"importer-a",client=client)
                self.assertEqual(result["status"],"imported_inactive")
                self.assertTrue(result["active_state_verified"])
                self.assertEqual([c[0] for c in calls],["POST","GET"])
                self.assertFalse(result["workflow_activation"]); self.assertFalse(result["workflow_execution"])
                self.assertEqual(get_import_record(draft_id)["status"],"imported_inactive")
                with self.assertRaises(HTTPException) as err: import_approved_workflow(draft_id,"importer-a",client=client)
                self.assertEqual(err.exception.status_code,409)
            client.close()
    def test_unapproved_workflow_never_calls_n8n(self):
        from app.n8n_workflow_lifecycle import submit_agent_workflow_draft
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"n8n.sqlite")
            workflow={"name":"Pending","active":False,"nodes":[{"id":"1","name":"Manual Trigger","type":"n8n-nodes-base.manualTrigger","typeVersion":1,"parameters":{}}],"connections":{}}
            with patch.dict(os.environ,{"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret"}):
                draft=submit_agent_workflow_draft("agent","Pending",workflow)
                with self.assertRaises(HTTPException) as err: import_approved_workflow(draft["draft_id"],"importer")
                self.assertEqual(err.exception.status_code,409)
    def test_unexpected_active_remote_workflow_is_deactivated_and_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"active.sqlite"); draft_id=self._approved_draft(db)
            calls=[]
            def handler(request):
                calls.append((request.method,request.url.path))
                if request.method=="POST" and request.url.path.endswith("/workflows"): return httpx.Response(201,json={"id":"remote-44","name":"Manual import test"})
                if request.method=="GET": return httpx.Response(200,json={"id":"remote-44","name":"Manual import test","active":True if len(calls)<4 else False})
                if request.method=="POST" and request.url.path.endswith("/deactivate"): return httpx.Response(204)
                return httpx.Response(404)
            client=httpx.Client(transport=httpx.MockTransport(handler))
            with patch.dict(os.environ,{"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret"}):
                result=import_approved_workflow(draft_id,"importer-a",client=client)
                self.assertEqual(result["status"],"imported_inactive")
                self.assertIn(("POST","/api/v1/workflows/remote-44/deactivate"),calls)
                self.assertFalse(any(path.endswith("/activate") or "/executions" in path for _,path in calls))
            client.close()
    def test_missing_remote_active_false_is_not_reported_as_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"n8n.sqlite"); draft_id=self._approved_draft(db)
            def handler(request):
                if request.method=="POST": return httpx.Response(201,json={"id":"remote-43"})
                return httpx.Response(200,json={"id":"remote-43"})
            client=httpx.Client(transport=httpx.MockTransport(handler))
            with patch.dict(os.environ,{"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret"}):
                with self.assertRaises(HTTPException) as err: import_approved_workflow(draft_id,"importer-a",client=client)
                self.assertEqual(err.exception.status_code,502)
                self.assertEqual(get_import_record(draft_id)["status"],"imported_inactive_state_unverified")
            client.close()


    def test_timeout_records_unknown_outcome_and_blocks_automatic_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"timeout.sqlite")
            draft_id=self._approved_draft(db)
            calls=[]
            def handler(request):
                calls.append(request.method)
                raise httpx.ReadTimeout("simulated response timeout",request=request)

            client=httpx.Client(transport=httpx.MockTransport(handler))
            env={"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret-test-key"}
            try:
                with patch.dict(os.environ,env):
                    with self.assertRaises(HTTPException) as err:
                        import_approved_workflow(draft_id,"importer-a",client=client)
                    self.assertEqual(err.exception.status_code,502)
                    record=get_import_record(draft_id)
                    self.assertEqual(record["status"],"outcome_unknown")
                    self.assertEqual(record["error_code"],"ReadTimeout")
                    with self.assertRaises(HTTPException) as retry:
                        import_approved_workflow(draft_id,"importer-a",client=client)
                    self.assertEqual(retry.exception.status_code,409)
                self.assertEqual(calls,["POST"])
            finally:
                client.close()

    def test_concurrent_import_attempts_are_serialized_and_only_one_reaches_n8n(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"concurrent.sqlite")
            draft_id=self._approved_draft(db)
            post_started=threading.Event()
            release_post=threading.Event()
            calls=[]
            def handler(request):
                calls.append((request.method,request.url.path))
                if request.method=="POST":
                    post_started.set()
                    if not release_post.wait(timeout=5):
                        raise TimeoutError("test did not release mocked n8n request")
                    return httpx.Response(201,json={"id":"remote-concurrent","name":"Manual import test"})
                return httpx.Response(200,json={"id":"remote-concurrent","name":"Manual import test","active":False})

            client=httpx.Client(transport=httpx.MockTransport(handler))
            env={"MARKET_MIND_DB":db,"N8N_BASE_URL":"https://n8n.example.test","N8N_API_KEY":"secret-test-key"}
            try:
                with patch.dict(os.environ,env):
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        first=pool.submit(import_approved_workflow,draft_id,"importer-a",client=client)
                        self.assertTrue(post_started.wait(timeout=5),"first import never reached n8n")
                        with self.assertRaises(HTTPException) as err:
                            import_approved_workflow(draft_id,"importer-b",client=client)
                        self.assertEqual(err.exception.status_code,409)
                        release_post.set()
                        result=first.result(timeout=5)
                    self.assertEqual(result["status"],"imported_inactive")
                    self.assertEqual([method for method,_ in calls],["POST","GET"])
                    self.assertEqual(get_import_record(draft_id)["status"],"imported_inactive")
            finally:
                release_post.set()
                client.close()

if __name__=="__main__": unittest.main()