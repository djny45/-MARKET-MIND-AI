import json, os, tempfile, unittest
from unittest.mock import patch
from fastapi.security import HTTPAuthorizationCredentials
from app.n8n_workflow_authoring import generate_n8n_workflow
from app import main as api

AUTH_TOKEN = "reviewer-token-for-authoring-tests-000000000000000000000000"
AUTH_ENV = {"N8N_REVIEWER_TOKENS_JSON": json.dumps({"human-reviewer": {"token": AUTH_TOKEN, "roles": ["reviewer"]}})}
AUTH = HTTPAuthorizationCredentials(scheme="Bearer", credentials=AUTH_TOKEN)

def export(active=False):
    return {"name":"Generated intake","active":active,
      "nodes":[{"id":"a","name":"Manual Trigger","type":"n8n-nodes-base.manualTrigger","typeVersion":1,"parameters":{}},
               {"id":"b","name":"Normalize","type":"n8n-nodes-base.set","typeVersion":3,"parameters":{}}],
      "connections":{"Manual Trigger":{"main":[[{"node":"Normalize","type":"main","index":0}]]}}}

class WorkflowGenerationTests(unittest.TestCase):
    def test_core_generation_validates_and_queues(self):
        response={"status":"completed","core_id":"shared_central_intelligence","provider":"ollama_local","model":"phi3","summary":json.dumps(export())}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"db.sqlite")}):
            result=generate_n8n_workflow("agent","Research intake","Create a manual research intake workflow.",synthesize=lambda _:response)
            self.assertEqual(result["status"],"queued_for_review")
            self.assertEqual(result["generation"]["core_id"],"shared_central_intelligence")
            self.assertTrue(result["human_review_required"])
            self.assertFalse(result["auto_approval"])
            self.assertFalse(result["workflow_execution"])
    def test_unconfigured_core_does_not_queue(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"db.sqlite")}):
            result=generate_n8n_workflow("agent","Research intake","Create a manual research intake workflow.",synthesize=lambda _:{"status":"not_configured"})
            self.assertEqual(result["status"],"not_configured")
    def test_invalid_model_output_is_not_queued(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"db.sqlite")}):
            result=generate_n8n_workflow("agent","Research intake","Create a manual research intake workflow.",synthesize=lambda _:{"status":"completed","summary":"not json"})
            self.assertEqual(result["status"],"generation_invalid_output")
    def test_api_generate_to_validate_and_human_review_integration(self):
        response={"status":"completed","core_id":"shared_central_intelligence","provider":"ollama_local","model":"phi3","summary":json.dumps(export())}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"integration.db"), **AUTH_ENV}):
            real_generate=generate_n8n_workflow
            with patch.object(api,"generate_n8n_workflow",side_effect=lambda agent,title,brief: real_generate(agent,title,brief,synthesize=lambda _:response)):
                generated=api.generate_n8n_workflow_draft(api.N8NWorkflowGenerateRequest(agent_id="api-author",title="API intake",brief="Create a manual research intake workflow."))
            self.assertEqual(generated["status"],"queued_for_review")
            pending=api.list_n8n_workflow_drafts(status="pending_human_review", credentials=AUTH)
            self.assertEqual(len(pending["drafts"]),1)
            reviewed=api.review_n8n_workflow_draft(generated["draft_id"],api.N8NWorkflowReviewRequest(decision="approve",review_note="Reviewed generated nodes."), credentials=AUTH)
            self.assertEqual(reviewed["status"],"approved")
            stored=api.read_n8n_workflow_draft(generated["draft_id"], credentials=AUTH)
            self.assertEqual(stored["status"],"approved")
            self.assertEqual(stored["review"]["decision"],"approve")
            self.assertFalse(stored["workflow_execution"])

    def test_restricted_authoring_rejects_external_side_effect_nodes(self):
        unsafe=export()
        unsafe["nodes"][1]["type"]="n8n-nodes-base.executeCommand"
        response={"status":"completed","summary":json.dumps(unsafe)}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"unsafe.db")}):
            result=generate_n8n_workflow("agent","Unsafe","Create a command workflow.",synthesize=lambda _:response)
            self.assertEqual(result["status"],"validation_rejected")
            self.assertIn("allowlist", " ".join(result["validation"]["errors"]))
    def test_active_model_output_is_rejected(self):
        response={"status":"completed","summary":json.dumps(export(active=True))}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"db.sqlite")}):
            result=generate_n8n_workflow("agent","Research intake","Create a manual research intake workflow.",synthesize=lambda _:response)
            self.assertEqual(result["status"],"validation_rejected")
            self.assertFalse(result["validation"]["structurally_valid"])

if __name__=="__main__": unittest.main()