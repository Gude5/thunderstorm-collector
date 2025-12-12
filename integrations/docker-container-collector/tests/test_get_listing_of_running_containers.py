import unittest
from unittest.mock import patch, MagicMock
import json
from docker_container_collector import get_listing_of_running_containers


class TestGetListingOfRunningContainers(unittest.TestCase):
    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_positive_multiple_containers(self, mock_logger, mock_run):
        """ Tests that multiple running containers are listed correctly."""
        containers = [
            {"ID": "1a2b3c", "Image": "alpine"},
            {"ID": "4d5e6f", "Image": "ubuntu"},
        ]
        stdout = "\n".join(json.dumps(c) for c in containers)
        mock_run.return_value = MagicMock(stdout=stdout)
        result = get_listing_of_running_containers()
        self.assertEqual(result, containers)
        mock_logger.info.assert_called_once()

    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_positive_single_container(self, mock_logger, mock_run):
        """ Tests that a single running container is listed correctly."""
        container = {"ID": "123", "Image": "nginx"}
        mock_run.return_value = MagicMock(stdout=json.dumps(container))
        result = get_listing_of_running_containers()
        self.assertEqual(result, [container])
        mock_logger.info.assert_called_once()

    @patch("docker_container_collector.subprocess.run")
    @patch("docker_container_collector.logger")
    def test_positive_no_containers(self, mock_logger, mock_run):
        """ Tests that no running containers returns an empty list."""
        mock_run.return_value = MagicMock(stdout="")
        result = get_listing_of_running_containers()
        self.assertEqual(result, [])
        mock_logger.info.assert_called_once()

    @patch("docker_container_collector.subprocess.run", side_effect=Exception("Docker error"))
    @patch("docker_container_collector.logger")
    def test_negative_docker_exception(self, mock_logger, mock_run):
        """ Tests that a Docker exception is handled gracefully."""
        result = get_listing_of_running_containers()
        mock_logger.error.assert_called_once() 
        mock_logger.info.assert_called_once_with("Found 0 running containers.")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
