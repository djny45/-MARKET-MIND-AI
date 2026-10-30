import unittest
from app.workflow import execute_workflow, NODE_TYPES

class WorkflowTests(unittest.TestCase):
 def test_indicator_nodes_registered(self):
  for kind in ("sma","ema","rsi","macd","bollinger","returns","volatility"):
   self.assertIn(kind,NODE_TYPES)
 def test_branching_dag_executes(self):
  nodes=[
   {"id":"feed","type":"market_input","data":{"values":[100,102,101,105,108,107,111,115,114,118,120,121,119,123,126]}},
   {"id":"rsi","type":"rsi","data":{"period":5}},
   {"id":"macd","type":"macd","data":{}},
  ]
  edges=[{"source":"feed","target":"rsi"},{"source":"feed","target":"macd"}]
  out=execute_workflow(nodes,edges,{})
  self.assertEqual(out["status"],"completed")
  self.assertEqual(len(out["results"]["rsi"]["series"]),14)
  self.assertIn("histogram",out["results"]["macd"])
 def test_cycle_rejected(self):
  nodes=[{"id":"a","type":"market_input","data":{"values":[1,2]}},{"id":"b","type":"sma","data":{}}]
  with self.assertRaisesRegex(ValueError,"cycle"):
   execute_workflow(nodes,[{"source":"a","target":"b"},{"source":"b","target":"a"}],{})
 def test_unknown_node_rejected(self):
  with self.assertRaisesRegex(ValueError,"Unsupported"):
   execute_workflow([{"id":"x","type":"unknown","data":{}}],[],{"data":[1,2]})
if __name__=="__main__": unittest.main()
