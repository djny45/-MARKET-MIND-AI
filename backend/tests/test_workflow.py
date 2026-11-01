import unittest
from unittest.mock import patch

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
        self.assertTrue(tasks["feed"]["assigned_worker"].endswith("Analyst 016"))
        self.assertEqual(tasks["feed"]["assigned_worker_id"], "worker_016")
        self.assertEqual(tasks["feed"]["worker_department"], "data_quality")
        self.assertEqual(tasks["feed"]["intelligence_core"], "shared_central_intelligence")
        self.assertEqual(tasks["feed"]["execution_mode"], "deterministic_analytical_handler")
        self.assertEqual(tasks["sma"]["assigned_worker"], "Trend Analyst")
        self.assertEqual(tasks["sma"]["worker_department"], "technical_analysis")
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

    def test_independent_failure_isolated_and_downstream_skipped(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [1, 2, 3]}},
            {"id": "good", "type": "sma", "data": {"period": 2}},
            {"id": "bad", "type": "ema", "data": {"period": 2}},
            {"id": "blocked", "type": "research_summary", "data": {}},
        ]
        edges = [
            {"source": "feed", "target": "good"},
            {"source": "feed", "target": "bad"},
            {"source": "bad", "target": "blocked"},
        ]
        from app import workflow
        original = workflow._run_node

        def fail_ema(kind, payload, params):
            if kind == "ema":
                raise RuntimeError("simulated isolated failure")
            return original(kind, payload, params)

        with patch("app.workflow._run_node", side_effect=fail_ema):
            out = execute_workflow(nodes, edges, {}, max_workers=2)
        tasks = {task["node_id"]: task for task in out["tasks"]}
        self.assertEqual(out["status"], "completed_with_errors")
        self.assertEqual(tasks["good"]["status"], "completed")
        self.assertEqual(tasks["bad"]["status"], "failed")
        self.assertEqual(tasks["bad"]["attempts"], 1)
        self.assertEqual(tasks["blocked"]["status"], "skipped")
        self.assertEqual(tasks["blocked"]["blocked_by"], ["bad"])
        self.assertEqual(out["aggregation"]["completed_count"], 2)
        self.assertEqual(out["aggregation"]["failed_count"], 1)
        self.assertEqual(out["aggregation"]["skipped_count"], 1)

    def test_failed_task_retries_are_bounded(self):
        nodes = [{"id": "feed", "type": "market_input", "data": {"values": [1, 2, 3]}}]
        from app import workflow
        with patch("app.workflow._run_node", side_effect=RuntimeError("temporary")) as mocked:
            out = execute_workflow(nodes, [], {}, max_retries=2)
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(out["tasks"][0]["status"], "failed")
        self.assertEqual(out["tasks"][0]["attempts"], 3)
        self.assertEqual(out["aggregation"]["failed_count"], 1)

    def test_checkpoint_callback_runs_after_each_completed_layer(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [1, 2, 3]}},
            {"id": "sma", "type": "sma", "data": {"period": 2}},
            {"id": "ema", "type": "ema", "data": {"period": 2}},
        ]
        edges = [
            {"source": "feed", "target": "sma"},
            {"source": "feed", "target": "ema"},
        ]
        snapshots = []
        out = execute_workflow(nodes, edges, {}, max_workers=2, checkpoint_callback=snapshots.append)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0]["completed_node_ids"], ["feed"])
        self.assertEqual(snapshots[0]["completed_layers"], 1)
        self.assertCountEqual(snapshots[1]["completed_node_ids"], ["feed", "sma", "ema"])
        self.assertEqual(out["aggregation"]["completed_count"], 3)

    def test_resume_restores_completed_nodes_and_runs_only_pending_tasks(self):
        nodes = [
            {"id": "feed", "type": "market_input", "data": {"values": [1, 2, 3]}},
            {"id": "sma", "type": "sma", "data": {"period": 2}},
        ]
        edges = [{"source": "feed", "target": "sma"}]
        checkpoint = {
            "completed_node_ids": ["feed"],
            "results": {"feed": {"values": [1, 2, 3]}},
            "tasks": {"feed": {
                "task_id": "task:feed", "node_id": "feed", "node_type": "market_input",
                "assigned_worker": "workflow-engine", "dependency_ids": [],
                "layer": 0, "status": "completed", "attempts": 1, "duration_ns": 10,
                "queue_wait_ns": 0, "result_key": "feed",
            }},
            "completed_layers": 1,
        }
        from app import workflow
        original = workflow._run_node
        called = []
        def track(kind, payload, params):
            called.append(kind)
            return original(kind, payload, params)
        with patch("app.workflow._run_node", side_effect=track):
            out = execute_workflow(nodes, edges, {}, initial_checkpoint=checkpoint)
        self.assertEqual(called, ["sma"])
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["aggregation"]["completed_count"], 2)
        self.assertEqual(out["results"]["feed"], {"values": [1, 2, 3]})

    def test_invalid_retry_limit_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_retries"):
            execute_workflow(
                [{"id": "x", "type": "market_input", "data": {"values": [1, 2]}}],
                [], {}, max_retries=4,
            )

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
