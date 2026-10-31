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
  self.assertIn("histogram",out["results"]["macd"])\n  self.assertEqual(out["performance"]["node_count"],3)\n  self.assertEqual(out["execution_layers"],[["feed"],["rsi","macd"]])
 def test_parallel_independent_nodes_preserve_results(self):\n  nodes=[\n   {"id":"feed","type":"market_input","data":{"values":[10,11,12,13,14,15]}},\n   {"id":"sma","type":"sma","data":{"period":2}},\n   {"id":"ema","type":"ema","data":{"period":2}},\n  ]\n  edges=[{"source":"feed","target":"sma"},{"source":"feed","target":"ema"}]\n  sequential=execute_workflow(nodes,edges,{},max_workers=1)\n  concurrent=execute_workflow(nodes,edges,{},max_workers=4)\n  self.assertEqual(sequential["results"],concurrent["results"])\n  self.assertTrue(concurrent["performance"]["parallelism_used"])\n  self.assertEqual(concurrent["execution_layers"],[["feed"],["sma","ema"]])\n def test_invalid_worker_limit_rejected(self):\n  with self.assertRaisesRegex(ValueError,"max_workers"):\n   execute_workflow([{"id":"x","type":"market_input","data":{"values":[1,2]}}],[],{},max_workers=0)\n def test_cycle_rejected(self):
  nodes=[{"id":"a","type":"market_input","data":{"values":[1,2]}},{"id":"b","type":"sma","data":{}}]
  with self.assertRaisesRegex(ValueError,"cycle"):
   execute_workflow(nodes,[{"source":"a","target":"b"},{"source":"b","target":"a"}],{})
 def test_unknown_node_rejected(self):
  with self.assertRaisesRegex(ValueError,"Unsupported"):
   execute_workflow([{"id":"x","type":"unknown","data":{}}],[],{"data":[1,2]})
if __name__=="__main__": unittest.main()
