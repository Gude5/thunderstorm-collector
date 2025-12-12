import unittest
from unittest.mock import patch, MagicMock
import docker_container_collector


class TestScanFilesInBatch(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.check_connection", return_value=True)
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.ThunderstormAPI")
    def test_batch_scan_success(
        self, mock_thunderstorm_cls, mock_get_path, mock_check_conn, mock_logger
    ):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "h1"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "h2"},
        ]
        docker_container_collector.SCAN_RESULTS = []

        # map file paths
        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]

        # mock Thunderstorm
        mock_th = MagicMock()
        mock_th.scan_multi.return_value = [["ok1"], ["ok2"]]
        mock_thunderstorm_cls.return_value = mock_th

        file_hashes, files_to_cache = docker_container_collector.scan_files_in_batch()

        # Verify results
        self.assertEqual(file_hashes, ["h1", "h2"])
        self.assertEqual(files_to_cache, [])

        # SCAN_RESULTS updated
        self.assertEqual(len(docker_container_collector.SCAN_RESULTS), 1)
        self.assertEqual(len(docker_container_collector.SCAN_RESULTS[0]["scan_results"]), 2)

        mock_logger.info.assert_any_call("Scanned 2 files in batch.")
        mock_logger.info.assert_any_call(
            "Scan results not mapped to individual files when scanning in batch mode."
        )


    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.check_connection", return_value=False)
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.ThunderstormAPI")
    def test_batch_scan_connection_fails(
        self, mock_thunderstorm_cls, mock_get_path, mock_check_conn, mock_logger
    ):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "h1"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "h2"},
        ]
        docker_container_collector.SCAN_RESULTS = []

        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]

        mock_th = MagicMock()
        mock_th.scan_multi.return_value = [["ok1"], ["ok2"]]
        mock_thunderstorm_cls.return_value = mock_th

        file_hashes, files_to_cache = docker_container_collector.scan_files_in_batch()

        # No files scanned → all should be cached
        self.assertEqual(file_hashes, ["h1", "h2"])
        self.assertEqual(len(files_to_cache), 2)

        mock_logger.error.assert_called_once()
        mock_logger.info.assert_any_call("Adding file h1 to cache to scan it later.")
        mock_logger.info.assert_any_call("Adding file h2 to cache to scan it later.")


    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.check_connection", return_value=True)
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.ThunderstormAPI")
    def test_batch_scan_raises_exception(
        self, mock_thunderstorm_cls, mock_get_path, mock_check_conn, mock_logger
    ):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "h1"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "h2"},
        ]
        docker_container_collector.SCAN_RESULTS = []

        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]

        mock_th = MagicMock()
        # scan_multi raises an error
        mock_th.scan_multi.side_effect = Exception("batch error")
        mock_thunderstorm_cls.return_value = mock_th

        file_hashes, files_to_cache = docker_container_collector.scan_files_in_batch()

        # No successful scan → everything goes into cache
        self.assertEqual(file_hashes, ["h1", "h2"])
        self.assertEqual(len(files_to_cache), 2)

        mock_logger.error.assert_any_call(
            "Error scanning files in batch. Error: batch error"
        )
        mock_logger.info.assert_any_call("Adding file h1 to cache to scan it later.")
        mock_logger.info.assert_any_call("Adding file h2 to cache to scan it later.")

if __name__ == '__main__':
    unittest.main()