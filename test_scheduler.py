import unittest
from scheduler import DAGScheduler, TaskStatus
from brain import Task, TaskGraph

class TestScheduler(unittest.TestCase):
    def test_basic_dag(self):
        tasks = [
            Task(id="1", branch="b1", instruction="i1", dependencies=[]),
            Task(id="2", branch="b2", instruction="i2", dependencies=["1"]),
        ]
        graph = TaskGraph(tasks=tasks)
        scheduler = DAGScheduler(graph)

        self.assertEqual(scheduler.get_ready_tasks(), ["1"])
        scheduler.mark_running("1", "sess1")
        self.assertEqual(scheduler.get_ready_tasks(), [])

        scheduler.mark_completed("1")
        self.assertEqual(scheduler.get_ready_tasks(), ["2"])

        scheduler.mark_completed("2")
        self.assertTrue(scheduler.is_finished())

if __name__ == "__main__":
    unittest.main()
