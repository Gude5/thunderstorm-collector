import unittest
from unittest.mock import patch, MagicMock
import docker_container_collector

class TestScanFilesSeparately(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.check_connection", return_value=True)
    @patch("docker_container_collector.ThunderstormAPI")
    def test_all_files_scanned_successfully(self, mock_thunderstorm_cls, mock_check_conn, mock_get_path, mock_logger):
        # Setup
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "hash1", "timestamp": "2025-12-11"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "hash2", "timestamp": "2025-12-11"}
        ]
        docker_container_collector.SCAN_RESULTS = []
        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]
        mock_thunderstorm = MagicMock()
        mock_thunderstorm.scan.side_effect = [{"result": "ok1"}, {"result": "ok2"}]
        mock_thunderstorm_cls.return_value = mock_thunderstorm

        file_hashes, files_to_cache = docker_container_collector.scan_files_separately()

        # All files scanned
        self.assertEqual(file_hashes, ["hash1", "hash2"])
        self.assertEqual(files_to_cache, [])
        self.assertEqual(len(docker_container_collector.SCAN_RESULTS), 2)
        mock_logger.info.assert_any_call("Scanned file /tmp/f1.")
        mock_logger.info.assert_any_call("Scanned file /tmp/f2.")

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.check_connection", return_value=True)
    @patch("docker_container_collector.ThunderstormAPI")
    def test_some_files_fail_during_scan(self, mock_thunderstorm_cls, mock_check_conn, mock_get_path, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "hash1", "timestamp": "2025-12-11"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "hash2", "timestamp": "2025-12-11"}
        ]
        docker_container_collector.SCAN_RESULTS = []
        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]
        mock_thunderstorm = MagicMock()
        # First file scans OK, second raises Exception
        mock_thunderstorm.scan.side_effect = [{"result": "ok1"}, Exception("scan fail")]
        mock_thunderstorm_cls.return_value = mock_thunderstorm

        file_hashes, files_to_cache = docker_container_collector.scan_files_separately()

        self.assertEqual(file_hashes, ["hash1"])
        self.assertEqual(len(files_to_cache), 1)
        self.assertEqual(files_to_cache[0]["sha256"], "hash2")
        mock_logger.error.assert_any_call("Error scanning file /tmp/f2. Error: scan fail")
        mock_logger.info.assert_any_call("Adding file hash2 to cache to scan it later.")

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.check_connection", return_value=False)
    @patch("docker_container_collector.ThunderstormAPI")
    def test_cannot_connect_to_thunderstorm(self, mock_thunderstorm_cls, mock_check_conn, mock_get_path, mock_logger):
        docker_container_collector.THUNDERSTORM_HOST = "localhost"
        docker_container_collector.THUNDERSTORM_PORT = 1234
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/app/f1", "sha256": "hash1", "timestamp": "2025-12-11"},
            {"container_id": "c1", "file_path": "/app/f2", "sha256": "hash2", "timestamp": "2025-12-11"}
        ]
        docker_container_collector.SCAN_RESULTS = []
        mock_get_path.side_effect = ["/tmp/f1", "/tmp/f2"]
        mock_thunderstorm = MagicMock()
        mock_thunderstorm_cls.return_value = mock_thunderstorm

        file_hashes, files_to_cache = docker_container_collector.scan_files_separately()

        # All files added to cache because connection fails
        self.assertEqual(file_hashes, [])
        self.assertEqual(len(files_to_cache), 2)
        mock_logger.error.assert_any_call(
            "Error scanning file /tmp/f1. Error: Cannot connect to Thunderstorm instance. Check if it is running properly. Host: localhost, Port: 1234"
        )
        mock_logger.info.assert_any_call("Adding file hash1 to cache to scan it later.")
        mock_logger.info.assert_any_call("Adding file hash2 to cache to scan it later.")

if __name__ == '__main__':
    unittest.main()