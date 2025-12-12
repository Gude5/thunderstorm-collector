import unittest
from unittest.mock import patch, mock_open, MagicMock
import docker_container_collector


class TestFilterOutDuplicates(unittest.TestCase):

    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.open", new_callable=mock_open, read_data=b"content1")
    @patch("docker_container_collector.logger")
    def test_no_duplicates(self, mock_logger, mock_open_fn, mock_get_path):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/file1"}
        ]

        mock_get_path.return_value = "/tmp/f1"

        docker_container_collector.filter_out_duplicates()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertIn("sha256", docker_container_collector.ITEMS_TO_SCAN[0])
        mock_logger.info.assert_any_call("Found 1 unique files after removing duplicates.")

    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.open", new_callable=mock_open)
    @patch("docker_container_collector.logger")
    def test_two_unique_files(self, mock_logger, mock_open_fn, mock_get_path):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/file1"},
            {"container_id": "c1", "file_path": "/app/file2"},
        ]

        mock_open_fn.side_effect = [
            mock_open(read_data=b"abc").return_value,
            mock_open(read_data=b"xyz").return_value
        ]

        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]

        docker_container_collector.filter_out_duplicates()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        self.assertNotEqual(docker_container_collector.ITEMS_TO_SCAN[0]["sha256"], docker_container_collector.ITEMS_TO_SCAN[1]["sha256"])
        mock_logger.info.assert_any_call("Found 2 unique files after removing duplicates.")

    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.open", new_callable=mock_open)
    @patch("docker_container_collector.logger")
    def test_duplicate_files_filtered_out(self, mock_logger, mock_open_fn, mock_get_path):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/file1"},
            {"container_id": "c1", "file_path": "/app/file2"},
        ]

        mock_open_fn.side_effect = [
            mock_open(read_data=b"samecontent").return_value,
            mock_open(read_data=b"samecontent").return_value
        ]

        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]

        docker_container_collector.filter_out_duplicates()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        mock_logger.info.assert_any_call('Filtering out duplicate file /app/file2 from container c1.')
        mock_logger.info.assert_any_call("Found 1 unique files after removing duplicates.")

    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.logger")
    def test_open_raises_exception(self, mock_logger, mock_get_path):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/file1"},
        ]

        mock_get_path.return_value = "/tmp/f1"

        with self.assertRaises(Exception):
            with patch("docker_container_collector.open", side_effect=Exception("read error")):
                docker_container_collector.filter_out_duplicates()

if __name__ == "__main__":
    unittest.main()