import unittest
from unittest.mock import patch, MagicMock
from docker_container_collector import process_container, DIFF, DATE

class TestProcessContainer(unittest.TestCase):

    def setUp(self):
        global DIFF
        DIFF.clear()  

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.subprocess.run")
    def test_container_with_changes(self, mock_run, mock_logger):
        """ Tests that a container with file changes is processed correctly."""
        container = {"ID": "abc123", "Image": "alpine"}
        mock_run.return_value = MagicMock(stdout="A /app/file1\nC /app/file2")

        process_container(container)

        self.assertEqual(len(DIFF), 2)
        self.assertEqual(DIFF[0], {
            'container_id': "abc123",
            'change_type': "A",
            'file_path': "/app/file1",
            'timestamp': DATE
        })
        self.assertEqual(DIFF[1]['change_type'], "C")

        calls = [call.args[0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any("Processing container abc123" in c for c in calls))
        self.assertTrue(any("Found file" in c for c in calls))

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.subprocess.run")
    def test_container_no_changes(self, mock_run, mock_logger):
        """ Tests that a container with no file changes is handled correctly."""
        container = {"ID": "abc123", "Image": "alpine"}
        mock_run.return_value = MagicMock(stdout="")

        process_container(container)

        self.assertEqual(DIFF, [])

        mock_logger.info.assert_any_call("No changes detected in container abc123.")

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.subprocess.run", side_effect=Exception("Docker diff failed"))
    def test_subprocess_exception(self, mock_run, mock_logger):
        """ Tests that an exception during subprocess.run is handled gracefully."""
        container = {"ID": "abc123", "Image": "alpine"}

        with self.assertRaises(Exception) as context:
            process_container(container)

        self.assertIn("Docker diff failed", str(context.exception))

    def test_missing_container_keys(self):
        container = {"ID": "abc123"}
        with self.assertRaises(KeyError):
            process_container(container)


if __name__ == "__main__":
    unittest.main()
