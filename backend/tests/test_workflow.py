import unittest

from app.workflow import NODE_TYPES, execute_workflow


class WorkflowTests(unittest.TestCase):
    def test_indicator_nodes_registered(self):
        for kind in ("sma", "ema", "rsi", "macd", "bollinger", "returns", "volatility"):
            self.assertIn(kind, NODE_TYPES)

    def test_branching_dag_executes(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [100, 102, 101, 105, 108, 107, 111, 115, 114, 118, 120, 121, 119, 123, 126]}},
            {"id": "rsi", "type": "rsi", "data": {"period": 5}},
            {"id": "macd", "type": "macd", "data": {}},
        ]
        edges = [{"source": "feed", "target": "rsi"}, {"source": "feed", "target": "macd"}]
        out = execute_workflow(nodes, edges, {})
        self.assertEqual(out["status"], "completed")
        self.assertEqual(len(out["results"]["rsi"]["series"]), 14)
        self.assertIn("histogram", out["results"]["macd"])
        self.assertEqual(out["performance"]["node_count"], 3)
        self.assertEqual(out["execution_layers"], [["feed"], ["rsi", "macd"]])

    def test_parallel_independent_nodes_preserve_results(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [10, 11, 12, 13, 14, 15]}},
            {"id": "sma", "type": "sma", "data": {"period": 2}},
            {"id": "ema", "type": "ema", "data": {"period": 2}},
        ]
        edges = [{"source": "feed", "target": "sma"}, {"source": "feed", "target": "ema"}]
        sequential = execute_workflow(nodes, edges, {}, max_workers=1)
        concurrent = execute_workflow(nodes, edges, {}, max_workers=4)
        self.assertEqual(sequential["results"], concurrent["results"])
        self.assertTrue(concurrent["performance"]["parallelism_used"])
        self.assertEqual(concurrent["execution_layers"], [["feed"], ["sma", "ema"]])

    def test_task_orchestration_tracks_assignments_dependencies_and_aggregation(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [10, 11, 12, 13]}},
            {"id": "sma", "type": "sma", "data": {"period": 2, "category": "worker", "label": "Trend Analyst"}},
            {"id": "summary", "type": "research_summary", "data": {}},
        ]
        edges = [
            {"source": "feed", "target": "sma"},
            {"source": "sma", "target": "summary"},
        ]
        out = execute_workflow(nodes, edges, {})
        tasks = {task["node_id"]: task for task in out["tasks"]}
        self.assertEqual(tasks["feed"]["assigned_worker"], "workflow-engine")
        self.assertEqual(tasks["sma"]["assigned_worker"], "Trend Analyst")
        self.assertEqual(tasks["sma"]["dependency_ids"], ["feed"])
        self.assertEqual(tasks["summary"]["dependency_ids"], ["sma"])
        self.assertTrue(all(task["status"] == "completed" for task in tasks.values()))
        self.assertTrue(all(task["duration_ns"] >= 0 for task in tasks.values()))
        self.assertTrue(all(task["queue_wait_ns"] >= 0 for task in tasks.values()))
        self.assertTrue(all(task["start_offset_ns"] >= 0 for task in tasks.values()))
        self.assertTrue(all(task["completion_offset_ns"] >= task["start_offset_ns"] for task in tasks.values()))
        self.assertEqual(out["aggregation"]["task_count"], 3)
        self.assertEqual(out["aggregation"]["completed_count"], 3)
        self.assertEqual(out["aggregation"]["failed_count"], 0)
        self.assertEqual(out["aggregation"]["result_count"], 3)

    def test_invalid_worker_limit_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_workers"):
            execute_workflow(
                [{"id": "x", "type": "market_input", "data": {"values": [1, 2]}}],
                [],
                {},
                max_workers=0,
            )

    def test_cycle_rejected(self):
        nodes = [
            {"id": "a", "type": "market_input", "data": {"values": [1, 2]}},
            {"id": "b", "type": "sma", "data": {}},
        ]
        with self.assertRaisesRegex(ValueError, "cycle"):
            execute_workflow(nodes, [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}], {})

    def test_unknown_node_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            execute_workflow([{"id": "x", "type": "unknown", "data": {}}], [], {"data": [1, 2]})


if __name__ == "__main__":
    unittest.main()
