import unittest
from unittest.mock import patch, mock_open
import docker_container_collector


class TestReadFileTypeConfig(unittest.TestCase):

    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.open", new_callable=mock_open, read_data=
        """
        50 4B 03 04;ZIP
        # This is a comment
        25 50 44 46;PDF
        deadbeef;NewType
        """
    )
    def test_read_config_file_exists(self, mock_open_file, mock_exists, mock_logger):
        docker_container_collector.FILE_TYPES = {
            "PNG": ["89504E47"],
            "PDF": ["25504446"]
        }

        docker_container_collector.read_file_type_config()

        # expected:
        # - ZIP added
        # - PDF gets additional header because name matches existing type (case insensitive)
        # - NewType added

        expected = {
            "PNG": ["89504E47"],
            "PDF": ["25504446", "25504446"],  # duplicate allowed per your implementation
            "ZIP": ["504B0304"],
            "NewType": ["DEADBEEF"]
        }

        self.assertEqual({k: v for k, v in docker_container_collector.FILE_TYPES.items()}, expected)

        mock_logger.info.assert_any_call(f"Loaded file type configuration from {docker_container_collector.FILE_TYPE_CONFIG_FILE}.")


    @patch("docker_container_collector.logger")
    @patch("docker_container_collector.os.path.exists", return_value=False)
    def test_read_config_file_missing(self, mock_exists, mock_logger):
        docker_container_collector.FILE_TYPES = {
            "PNG": ["89504E47"],
            "PDF": ["25504446"]
        }
        docker_container_collector.read_file_type_config()

        # FILE_TYPES should remain unchanged since the file does not exist
        self.assertEqual(docker_container_collector.FILE_TYPES, {
            "PNG": ["89504E47"],
            "PDF": ["25504446"]
        })

        mock_logger.warning.assert_any_call(
            f"File type configuration file {docker_container_collector.FILE_TYPE_CONFIG_FILE} not found."
        )

if __name__ == "__main__":
    unittest.main()