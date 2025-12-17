from unittest.mock import MagicMock, patch

from docker_container_collector.utils.connection import check_connection  # ty:ignore[unresolved-import]


def test_check_connection_success():
    mock_sock = MagicMock()
    with patch("docker_container_collector.utils.connection.socket.socket", return_value=mock_sock):
        result = check_connection("127.0.0.1", 1234)
    mock_sock.connect.assert_called_once_with(("127.0.0.1", 1234))
    mock_sock.close.assert_called_once()
    assert result is True

def test_check_connection_failure():
    mock_sock = MagicMock()
    mock_sock.connect.side_effect = Exception("Connection failed")

    with patch("docker_container_collector.utils.connection.socket.socket", return_value=mock_sock):
        result = check_connection("127.0.0.1", 1234)
    mock_sock.connect.assert_called_once_with(("127.0.0.1", 1234))
    mock_sock.close.assert_not_called()
    assert result is False
