import unittest
from unittest.mock import patch, MagicMock
import docker_container_collector

class TestFilterOutDeletedItemsAndNonFiles(unittest.TestCase):

    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_all_items_are_files_and_modified(self, mock_logger, mock_run):
        # Setup DIFF with added and modified items
        docker_container_collector.DIFF = [
            {'container_id': 'c1', 'change_type': 'A', 'file_path': '/app/file1', 'timestamp': '2025-12-11'},
            {'container_id': 'c1', 'change_type': 'C', 'file_path': '/app/file2', 'timestamp': '2025-12-11'}
        ]
        docker_container_collector.ITEMS_TO_SCAN = []

        # Mock subprocess.run to indicate all items exist as files
        mock_run.return_value = MagicMock(returncode = 0)

        docker_container_collector.filter_out_deleted_items_and_non_files()

        # ITEMS_TO_SCAN should include both items
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]['file_path'], '/app/file1')

        # Check that logger reports the final count
        mock_logger.info.assert_any_call('Found 2 changes of type "modified" or "added" across all containers.')

    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_deleted_items_filtered_out(self, mock_logger, mock_run):
        # Setup DIFF with one deleted item and one modified
        docker_container_collector.DIFF = [
            {'container_id': 'c1', 'change_type': 'D', 'file_path': '/app/file_deleted', 'timestamp': '2025-12-11'},
            {'container_id': 'c1', 'change_type': 'C', 'file_path': '/app/file2', 'timestamp': '2025-12-11'}
        ]
        docker_container_collector.ITEMS_TO_SCAN = []

        mock_run.return_value = MagicMock(returncode=0)

        docker_container_collector.filter_out_deleted_items_and_non_files()

        # Deleted item should be excluded
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]['file_path'], '/app/file2')

        # Logger should report filtered deleted item
        mock_logger.info.assert_any_call('Filtering out deleted item /app/file_deleted in container c1.')

    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_non_file_items_filtered_out(self, mock_logger, mock_run):
        # Setup DIFF with one added item that is not a file
        docker_container_collector.DIFF = [
            {'container_id': 'c1', 'change_type': 'A', 'file_path': '/app/not_a_file', 'timestamp': '2025-12-11'}
        ]
        docker_container_collector.ITEMS_TO_SCAN = []

        # Mock subprocess.run to indicate the item does not exist as a file
        mock_run.return_value = MagicMock(returncode=1)

        docker_container_collector.filter_out_deleted_items_and_non_files()

        # ITEMS_TO_SCAN should remain empty
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 0)

        # Logger should report filtered non-file item
        mock_logger.info.assert_any_call('Filtering out non-file item /app/not_a_file in container c1.')

    @patch("docker_container_collector.subprocess.run", side_effect=Exception("Docker exec failed"))
    @patch("docker_container_collector.logger")
    def test_subprocess_exception(self, mock_logger, mock_run):
        # Setup DIFF with one added item
        docker_container_collector.DIFF = [
            {'container_id': 'c1', 'change_type': 'A', 'file_path': '/app/file1', 'timestamp': '2025-12-11'}
        ]
        docker_container_collector.ITEMS_TO_SCAN = []

        # Expect subprocess.run exception to propagate
        with self.assertRaises(Exception) as context:
            docker_container_collector.filter_out_deleted_items_and_non_files()

        self.assertIn("Docker exec failed", str(context.exception))

if __name__ == "__main__":
    unittest.main()