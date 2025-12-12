import unittest
from unittest.mock import patch
import docker_container_collector


class TestFilterOutBigFiles(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.os.path.getsize")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    def test_all_files_small(self, mock_get_path, mock_getsize, mock_logger):
        """ Tests that no files are filtered out when all files are below the size limit."""
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/a"},
            {"container_id": "c2", "file_path": "/app/b"},
        ]
        docker_container_collector.MAX_FILE_SIZE = 1024 # 1 KB

        # All files smaller than MAX_FILE_SIZE
        mock_get_path.side_effect = ["/tmp/a", "/tmp/b"]
        mock_getsize.side_effect = [docker_container_collector.MAX_FILE_SIZE - 1, docker_container_collector.MAX_FILE_SIZE - 10]

        docker_container_collector.filter_out_big_files()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        mock_logger.info.assert_any_call(
            f"Found 2 files to scan after filtering out files bigger than {docker_container_collector.MAX_FILE_SIZE} bytes."
        )

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.os.path.getsize")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    def test_one_file_too_large(self, mock_get_path, mock_getsize, mock_logger):
        """ Tests that a file larger than the size limit is filtered out."""
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/a"},
            {"container_id": "c1", "file_path": "/app/b"},
        ]
        docker_container_collector.MAX_FILE_SIZE = 1024 # 1 KB

        mock_get_path.side_effect = ["/tmp/a", "/tmp/b"]
        mock_getsize.side_effect = [docker_container_collector.MAX_FILE_SIZE - 1, docker_container_collector.MAX_FILE_SIZE + 500]

        docker_container_collector.filter_out_big_files()

        # Only first file should remain
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]["file_path"], "/app/a")

        mock_logger.info.assert_any_call(
            f'Filtering out file /app/b from container c1 due to size {docker_container_collector.MAX_FILE_SIZE + 500} bytes exceeding limit of {docker_container_collector.MAX_FILE_SIZE} bytes.'
        )

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.os.path.getsize")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    def test_mixed_sizes(self, mock_get_path, mock_getsize, mock_logger):
        """ Tests that only files larger than the size limit are filtered out."""
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/small"},
            {"container_id": "c1", "file_path": "/app/large1"},
            {"container_id": "c1", "file_path": "/app/large2"},
            {"container_id": "c1", "file_path": "/app/small2"},
        ]
        docker_container_collector.MAX_FILE_SIZE = 1024 # 1 KB

        mock_get_path.side_effect = [
            "/tmp/small",
            "/tmp/large1",
            "/tmp/large2",
            "/tmp/small2",
        ]

        mock_getsize.side_effect = [
            docker_container_collector.MAX_FILE_SIZE - 100,       # keep
            docker_container_collector.MAX_FILE_SIZE + 1,         # drop
            docker_container_collector.MAX_FILE_SIZE + 5000,      # drop
            docker_container_collector.MAX_FILE_SIZE - 10         # keep
        ]

        docker_container_collector.filter_out_big_files()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        remaining_paths = [item["file_path"] for item in docker_container_collector.ITEMS_TO_SCAN]
        self.assertEqual(remaining_paths, ["/app/small", "/app/small2"])

        mock_logger.info.assert_any_call(
            f"Found 2 files to scan after filtering out files bigger than {docker_container_collector.MAX_FILE_SIZE} bytes."
        )

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/f")
    @patch("docker_container_collector.logger")
    def test_getsize_raises_exception(self, mock_logger, mock_get_path):
        """ Tests that an exception during os.path.getsize is handled gracefully."""
        docker_container_collector.ITEMS_TO_SCAN = [{"container_id": "c1", "file_path": "/app/crash"}]
        docker_container_collector.MAX_FILE_SIZE = 1024 # 1 KB

        with self.assertRaises(Exception):
            with patch("docker_container_collector.os.path.getsize", side_effect=Exception("read error")):
                docker_container_collector.filter_out_big_files()

if __name__ == "__main__":
    unittest.main()