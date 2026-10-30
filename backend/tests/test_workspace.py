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
 def test_graph_limits(self):
  with self.assertRaises(ValueError):
   workspace.save_workflow("Too big","",[{}]*251,[])
 def test_non_finite_rejected(self):
  with self.assertRaises(ValueError):
   workspace.save_workflow("Bad","",[{"x":float("nan")}],[])
if __name__=="__main__": unittest.main()
