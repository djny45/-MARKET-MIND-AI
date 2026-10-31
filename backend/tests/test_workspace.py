import os, tempfile, unittest
from app import workspace
class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.old=os.environ.get("MARKET_MIND_DB")
  os.environ["MARKET_MIND_DB"]=os.path.join(self.tmp.name,"test.db")
 def tearDown(self):
  if self.old is None: os.environ.pop("MARKET_MIND_DB",None)
  else: os.environ["MARKET_MIND_DB"]=self.old
  self.tmp.cleanup()
 def test_save_get_update_delete(self):
  saved=workspace.save_workflow("Test","desc",[{"id":"n1","type":"market_input"}],[])
  loaded=workspace.get_workflow(saved["id"])
  self.assertEqual(loaded["nodes"][0]["id"],"n1")
  updated=workspace.save_workflow("Renamed","updated",[],[],saved["id"])
  self.assertEqual(updated["id"],saved["id"])
  self.assertEqual(workspace.list_workflows()[0]["title"],"Renamed")
  self.assertTrue(workspace.delete_workflow(saved["id"]))
  self.assertIsNone(workspace.get_workflow(saved["id"]))
 def test_execution_history_persists_and_lists_replay_payloads(self):
  request={"nodes":[{"id":"feed","type":"market_input"}],"edges":[],"inputs":{"data":[1,2,3]}}
  result={"status":"completed","results":{"feed":{"values":[1,2,3]}}}
  saved=workspace.save_execution("run-1",request,result,"completed")
  loaded=workspace.get_execution("run-1")
  self.assertEqual(loaded["request"],request)
  self.assertEqual(loaded["result"],result)
  self.assertEqual(loaded["status"],"completed")
  self.assertEqual(workspace.list_executions()[0]["id"],"run-1")
  child=workspace.save_execution("run-2",request,result,"completed","run-1")
  self.assertEqual(workspace.get_execution(child["id"])["parent_run_id"],"run-1")
 def test_execution_history_rejects_non_finite_payload(self):
  with self.assertRaises(ValueError):
   workspace.save_execution("bad",{"value":float("nan")},{},"failed")
 def test_checkpoint_updates_are_persisted_with_run_record(self):
  request={"nodes":[{"id":"a","type":"market_input"}],"edges":[],"inputs":{"data":[1,2]}}
  workspace.create_execution("checkpoint-run",request)
  snapshot={"completed_node_ids":["a"],"results":{"a":{"values":[1,2]}},"completed_layers":1}
  workspace.update_execution_checkpoint("checkpoint-run",snapshot,"running")
  loaded=workspace.get_execution("checkpoint-run")
  self.assertEqual(loaded["status"],"running")
  self.assertEqual(loaded["checkpoint"]["completed_node_ids"],["a"])
  self.assertEqual(loaded["checkpoint"]["results"]["a"]["values"],[1,2])
 def test_graph_limits(self):
  with self.assertRaises(ValueError):
   workspace.save_workflow("Too big","",[{}]*251,[])
 def test_non_finite_rejected(self):
  with self.assertRaises(ValueError):
   workspace.save_workflow("Bad","",[{"x":float("nan")}],[])
if __name__=="__main__": unittest.main()
