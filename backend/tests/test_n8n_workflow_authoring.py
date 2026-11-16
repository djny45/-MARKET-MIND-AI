import json, os, tempfile, unittest
from unittest.mock import patch
from app.n8n_workflow_authoring import generate_n8n_workflow

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
            self.assertEqual(result["status"],"validation_rejected")
            self.assertFalse(result["validation"]["structurally_valid"])
    def test_model_active_flag_is_forced_off(self):
        response={"status":"completed","summary":json.dumps(export(active=True))}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{"MARKET_MIND_DB":os.path.join(tmp,"db.sqlite")}):
            result=generate_n8n_workflow("agent","Research intake","Create a manual research intake workflow.",synthesize=lambda _:response)
            self.assertEqual(result["status"],"queued_for_review")
            self.assertFalse(result["workflow_activation"])

if __name__=="__main__": unittest.main()