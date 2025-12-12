import unittest
from unittest.mock import patch, mock_open
import docker_container_collector

class TestFilterOutFilesWithSpecificTypes(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    @patch("docker_container_collector.open", new_callable=mock_open, read_data=b"\x00\x11\x22\x33\x44")
    def test_no_file_types_match(self, mock_file, mock_get_path, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/a"},
            {"container_id": "c2", "file_path": "/b"},
        ]

        # FILE HEADER: "0011223344" — should match NONE of your registered FILE_TYPES
        mock_get_path.side_effect = ["/tmp/a", "/tmp/b"]

        docker_container_collector.filter_out_files_with_specific_types()

        # All items remain
        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        mock_logger.info.assert_any_call(
            f"Found 2 files to scan after filtering out specific file types."
        )

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    def test_single_file_filtered(self, mock_get_path, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/bin/sh"},
        ]
        docker_container_collector.FILTER_OUT_FILE_TYPES = ["ELF"]
        docker_container_collector.FILE_TYPES = {
            "ELF": ["7F454C46"],  # ELF file header in hex
        }

        # Pick a known file type header that exists in FILE_TYPES and should be filtered
        # For example assume:
        # FILE_TYPES = {"ELF": ["7F454C46"], ...}
        # and FILTER_OUT_FILE_TYPES = ["ELF"]
        elf_header = bytes.fromhex(docker_container_collector.FILE_TYPES["ELF"][0])

        mock_get_path.return_value = "/tmp/sh"

        with patch("docker_container_collector.open", mock_open(read_data=elf_header)):
            docker_container_collector.filter_out_files_with_specific_types()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 0)
        mock_logger.info.assert_any_call(
            "Filtering out file /bin/sh from container c1 due to file type ELF."
        )

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.get_file_path_in_diff_directory")
    def test_mixed_files(self, mock_get_path, mock_logger):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/keep1"},
            {"container_id": "c1", "file_path": "/drop1"},
            {"container_id": "c1", "file_path": "/keep2"},
        ]
        docker_container_collector.FILTER_OUT_FILE_TYPES = ["ELF"]
        docker_container_collector.FILE_TYPES = {
            "ELF": ["7F454C46"],  # ELF file header in hex
        }

        # Map: keep1 = no match, drop1 = ELF, keep2 = no match
        no_match_header = b"\x01\x02\x03\x04\x05"
        elf_header = bytes.fromhex(docker_container_collector.FILE_TYPES["ELF"][0])

        mock_get_path.side_effect = ["/tmp/k1", "/tmp/d1", "/tmp/k2"]

        def mock_file_open(path, mode):
            if path == "/tmp/k1":
                return mock_open(read_data=no_match_header)()
            if path == "/tmp/d1":
                return mock_open(read_data=elf_header)()
            if path == "/tmp/k2":
                return mock_open(read_data=no_match_header)()
            raise RuntimeError("unexpected path")

        with patch("docker_container_collector.open", mock_file_open):
            docker_container_collector.filter_out_files_with_specific_types()

        self.assertEqual(len(docker_container_collector.ITEMS_TO_SCAN), 2)
        self.assertEqual(
            [item["file_path"] for item in docker_container_collector.ITEMS_TO_SCAN],
            ["/keep1", "/keep2"]
        )

        mock_logger.info.assert_any_call(
            f"Found 2 files to scan after filtering out specific file types."
        )

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/f")
    @patch("docker_container_collector.logger")
    def test_open_raises_exception(self, mock_logger, mock_get_path):
        docker_container_collector.ITEMS_TO_SCAN = [
            {"container_id": "c1", "file_path": "/crash"},
        ]

        with self.assertRaises(Exception):
            with patch("docker_container_collector.open", side_effect=Exception("IO fail")):
                docker_container_collector.filter_out_files_with_specific_types()

if __name__ == "__main__":
    unittest.main()