import unittest
from unittest.mock import patch, MagicMock
from docker_container_collector import copy_file_from_container

class TestCopyFileFromContainer(unittest.TestCase):

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/fakepath")
    @patch("docker_container_collector.os.makedirs")
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_file_copied_successfully(self, mock_logger, mock_subprocess, mock_exists, mock_makedirs, mock_get_path):
        """ Tests that a file is copied successfully from the container."""
        item = {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11'}
        
        # subprocess.run returns success
        mock_subprocess.return_value = MagicMock(returncode=0)

        copy_file_from_container(item)

        mock_logger.info.assert_any_call('Copied file /app/file1 from container c1 successfully.')

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/fakepath")
    @patch("docker_container_collector.os.makedirs")
    @patch("docker_container_collector.os.path.exists", return_value=False)
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_directories_created_if_missing(self, mock_logger, mock_subprocess, mock_exists, mock_makedirs, mock_get_path):
        """ Tests that necessary directories are created if they do not exist."""
        item = {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11'}
        mock_subprocess.return_value = MagicMock(returncode=0)

        copy_file_from_container(item)

        self.assertEqual(mock_makedirs.call_count, 2)  # GLOBAL_CHANGED_FILES_DIRECTORY + DIFF_DIRECTORY
        mock_logger.info.assert_any_call('Copied file /app/file1 from container c1 successfully.')

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/fakepath")
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_copy_fails_returncode_nonzero(self, mock_logger, mock_subprocess, mock_exists, mock_get_path):
        """ Tests that an error is logged if the copy command fails with non-zero return code."""
        item = {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11'}
        mock_subprocess.return_value = MagicMock(returncode=1)  # cp fails

        copy_file_from_container(item)

        mock_logger.error.assert_any_call('Failed to copy file /app/file1 from container c1. Return code: 1')

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/fakepath")
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_copy_raises_exception_container_not_running(self, mock_logger, mock_subprocess, mock_exists, mock_get_path):
        """ Tests that an error is logged if the container is not running."""
        item = {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11'}
        
        # First cp raises Exception
        def side_effect_cp(args, **kwargs):
            if args[0] == 'docker' and args[1] == 'cp':
                raise Exception("cp failed")
            elif args[1] == 'inspect':
                return MagicMock(returncode=1, stdout='')  # container not running
        mock_subprocess.side_effect = side_effect_cp

        copy_file_from_container(item)

        mock_logger.error.assert_any_call(
            'Failed to copy file /app/file1 from container because container c1 is not running anymore.'
        )

    @patch("docker_container_collector.get_file_path_in_diff_directory", return_value="/tmp/fakepath")
    @patch("docker_container_collector.os.path.exists", return_value=True)
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_copy_raises_exception_container_running(self, mock_logger, mock_subprocess, mock_exists, mock_get_path):
        """ Tests that an error is logged if the copy command raises an exception while container is running."""
        item = {'container_id': 'c1', 'file_path': '/app/file1', 'change_type': 'A', 'timestamp': '2025-12-11'}
        
        def side_effect_cp(args, **kwargs):
            if args[1] == 'cp':
                raise Exception("cp failed")
            elif args[1] == 'inspect':
                return MagicMock(returncode=0, stdout='true\n')  # container running
        mock_subprocess.side_effect = side_effect_cp

        copy_file_from_container(item)

        mock_logger.error.assert_any_call(
            'Failed to copy file /app/file1 from container c1. Error: cp failed'
        )

if __name__ == "__main__":
    unittest.main()