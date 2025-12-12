import unittest
from unittest.mock import patch, mock_open, MagicMock
import docker_container_collector

class TestAddCachedFiles(unittest.TestCase):

    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open)
    @patch("docker_container_collector.json.load")
    def test_cache_file_exists(self, mock_logger, mock_json_load, mock_open, mock_exists):
        """ Tests that cached files are added to ITEMS_TO_SCAN when the cache file exists.
        """
        docker_container_collector.ITEMS_TO_SCAN = []
        # Mock the JSON load to return a list of cached items
        mock_open.return_value = MagicMock()
        mock_json_load.return_value = [
            {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11', 'sha256': 'abc123'}
        ]
        docker_container_collector.add_cached_files()

        # ITEMS_TO_SCAN should now contain the cached item
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 1)
        self.assertEqual(docker_container_collector.ITEMS_TO_SCAN[0]['file_path'], "/app/file1")

        # Logger should be called with correct message
        mock_logger.info.assert_any_call('Added 1 cached files to the list of files to scan.')

    @patch("docker_container_collector.os.path.exists", return_value=False)
    @patch("docker_container_collector.logger")
    def test_cache_file_missing(self, mock_logger, mock_exists):
        """ Tests that no files are added when the cache file does not exist.
        """
        docker_container_collector.ITEMS_TO_SCAN = []

        docker_container_collector.add_cached_files()

        # ITEMS_TO_SCAN should remain empty
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 0)

        # Logger should indicate no cache file
        mock_logger.info.assert_any_call('No cache file found. Skipping adding cached files.')

if __name__ == "__main__":
    unittest.main()