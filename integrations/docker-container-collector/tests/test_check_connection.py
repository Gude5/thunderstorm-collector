import unittest
from unittest.mock import patch, MagicMock
import docker_container_collector

class TestCheckConnection(unittest.TestCase):

    @patch("docker_container_collector.socket.socket")
    def test_connection_success(self, mock_socket_cls):
        """Test that check_connection returns True when socket.connect() succeeds."""
        mock_sock = MagicMock()
        mock_socket_cls.return_value = mock_sock

        result = docker_container_collector.check_connection(host="127.0.0.1", port=9999, timeout=5)

        self.assertTrue(result)

        # socket called with AF_INET, SOCK_STREAM
        mock_socket_cls.assert_called_once()

        # timeout set
        mock_sock.settimeout.assert_called_once_with(5)

        # connect called
        mock_sock.connect.assert_called_once_with(("127.0.0.1", 9999))

        # socket closed
        mock_sock.close.assert_called_once()

    @patch("docker_container_collector.socket.socket")
    def test_connection_failure(self, mock_socket_cls):
        """Test that check_connection returns False when socket.connect() raises exception."""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("connection failed")
        mock_socket_cls.return_value = mock_sock

        result = docker_container_collector.check_connection(host="127.0.0.1", port=9999, timeout=5)

        self.assertFalse(result)

        # socket created
        mock_socket_cls.assert_called_once()

        # timeout set
        mock_sock.settimeout.assert_called_once_with(5)

        # connect attempted
        mock_sock.connect.assert_called_once_with(("127.0.0.1", 9999))

        # should NOT close the socket because connection failed before else-block
        mock_sock.close.assert_not_called()

if __name__ == "__main__":
    unittest.main()