import unittest
from unittest.mock import patch, mock_open
import docker_container_collector


class TestFilterOutKnownFiles(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.open", new_callable=mock_open, read_data='{}')
    def test_no_known_hashes(self, mock_open_fn, mock_logger):
        # ITEMS_TO_SCAN contains items with sha256 hashes
        docker_container_collector.ITEMS_TO_SCAN = [
            {"file_path": "/app/a", "sha256": "abc"},
            {"file_path": "/app/b", "sha256": "def"},
        ]

        docker_container_collector.filter_out_known_files()

        # Should not filter anything
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)

        mock_logger.info.assert_any_call(
            "Found 2 files to scan after filtering already scanned files."
        )

    @patch("docker_container_collector.logger")
    @patch(
        "docker_container_collector.open",
        new_callable=mock_open,
        read_data='{"2025-01-01": ["abc"]}'
    )
    def test_one_known_hash(self, mock_open_fn, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"file_path": "/app/a", "sha256": "abc"},
            {"file_path": "/app/b", "sha256": "def"},
        ]

        docker_container_collector.filter_out_known_files()

        # "abc" should be filtered out
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]["sha256"], "def")

        mock_logger.info.assert_any_call(
            "Found 1 files to scan after filtering already scanned files."
        )

    @patch("docker_container_collector.logger")
    @patch(
        "docker_container_collector.open",
        new_callable=mock_open,
        read_data='{"2025-01-01": ["abc"], "2025-01-02": ["def"]}'
    )
    def test_multiple_dates_combined(self, mock_open_fn, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"file_path": "/app/a", "sha256": "abc"},
            {"file_path": "/app/b", "sha256": "def"},
            {"file_path": "/app/c", "sha256": "xyz"},
        ]

        docker_container_collector.filter_out_known_files()

        # Only "xyz" remains
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]["sha256"], "xyz")

        mock_logger.info.assert_any_call(
            "Found 1 files to scan after filtering already scanned files."
        )

    @patch("docker_container_collector.logger")
    def test_open_raises_exception(self, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [{"file_path": "/app/a", "sha256": "abc"}]

        # open() fails → the function should raise
        with self.assertRaises(Exception):
            with patch("docker_container_collector.open", side_effect=Exception("read error")):
                docker_container_collector.filter_out_known_files()

if __name__ == "__main__":
    unittest.main()