import unittest
from unittest.mock import patch, mock_open, MagicMock
from docker_container_collector import save_file_hashes, HASH_FILE, DATE


class TestSaveFileHashes(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.json.dump")
    @patch("docker_container_collector.json.load")
    @patch("docker_container_collector.open", new_callable=mock_open)
    @patch("docker_container_collector.os.path.exists", return_value=True)
    def test_save_file_hashes_when_hash_file_exists(
        self, mock_exists, mock_open_file, mock_json_load, mock_json_dump, mock_logger
    ):
        """ Tests that file hashes are saved correctly when the hash file exists. """
        # Existing JSON content
        mock_json_load.return_value = {"2024-01-01": ["oldhash"]}

        save_file_hashes(["hash1", "hash2"])

        # Should read existing file
        mock_open_file.assert_any_call(HASH_FILE, 'r')
        
        # Should write updated JSON
        mock_open_file.assert_any_call(HASH_FILE, 'w')

        # json.dump called with merged dict
        expected_dict = {
            "2024-01-01": ["oldhash"],
            DATE: ["hash1", "hash2"]
        }
        mock_json_dump.assert_called_once_with(expected_dict, mock_open_file(), indent=4)

        mock_logger.info.assert_any_call(f"Saved scanned file hashes to {HASH_FILE}.")


    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.json.dump")
    @patch("docker_container_collector.open", new_callable=mock_open)
    @patch("docker_container_collector.os.path.exists", return_value=False)
    def test_save_file_hashes_when_hash_file_does_not_exist(
        self, mock_exists, mock_open_file, mock_json_dump, mock_logger
    ):
        """ Tests that file hashes are saved correctly when the hash file does not exist. """
        save_file_hashes(["h1"])

        # Should NOT try to read file
        mock_open_file.assert_any_call(HASH_FILE, 'w')

        expected_dict = {DATE: ["h1"]}
        mock_json_dump.assert_called_once_with(expected_dict, mock_open_file(), indent=4)

        mock_logger.info.assert_any_call(f"Saved scanned file hashes to {HASH_FILE}.")


    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.json.dump")
    @patch("docker_container_collector.open", new_callable=mock_open)
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.json.load", return_value={})
    def test_save_file_hashes_empty_list(
        self, mock_json_load, mock_exists, mock_open_file, mock_json_dump, mock_logger
    ):
        """ Tests that saving an empty list of file hashes is handled correctly. """
        save_file_hashes([])

        expected_dict = {DATE: []}
        mock_json_dump.assert_called_once_with(expected_dict, mock_open_file(), indent=4)

        mock_logger.info.assert_any_call("No new file hashes to save.")

if __name__ == "__main__":
    unittest.main()