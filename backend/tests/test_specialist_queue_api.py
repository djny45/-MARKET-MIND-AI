import unittest
from unittest.mock import patch
from fastapi import BackgroundTasks

from app.main import SpecialistResearchQueueRequest, route_and_queue_research


class SpecialistQueueApiTests(unittest.TestCase):
    def test_route_queue_creates_one_task_per_selected_specialist(self):
        request = SpecialistResearchQueueRequest(
            brief="Compare bitcoin crypto correlation, volatility risk, and historical data validation",
            data={"returns": [0.01, -0.02, 0.005]},
            max_specialists=3,
        )
        background_tasks = BackgroundTasks()

        def fake_enqueue(worker_id, brief, data):
            return {
                "task_id": "task-" + worker_id,
                "worker_id": worker_id,
                "agent_id": worker_id,
                "status": "queued",
            }

        with patch("app.main.enqueue_research_task", side_effect=fake_enqueue):
            result = route_and_queue_research(request, background_tasks)

        selected = result["routing"]["candidates"]
        self.assertEqual(result["queued_count"], len(selected))
        self.assertEqual(len(result["tasks"]), len(selected))
        self.assertEqual(len(background_tasks.tasks), len(selected))
        self.assertEqual(
            [task["routing_score"] for task in result["tasks"]],
            [candidate["routing_score"] for candidate in selected],
        )
        self.assertEqual(
            [task["task_id"] for task in result["tasks"]],
            ["task-" + candidate["worker_id"] for candidate in selected],
        )
        self.assertTrue(all(task.kwargs == {} for task in background_tasks.tasks))

    def test_route_queue_empty_match_returns_no_fake_tasks(self):
        request = SpecialistResearchQueueRequest(
            brief="Please discuss gardening and houseplants only",
            max_specialists=3,
        )
        background_tasks = BackgroundTasks()
        with patch("app.main.enqueue_research_task") as enqueue:
            result = route_and_queue_research(request, background_tasks)
        self.assertEqual(result["queued_count"], 0)
        self.assertEqual(result["tasks"], [])
        self.assertEqual(background_tasks.tasks, [])
        enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
