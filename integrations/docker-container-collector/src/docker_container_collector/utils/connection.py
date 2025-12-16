import socket


def check_connection(host,port,timeout=2) -> bool:
    """ Checks if a connection to the Thunderstorm instance can be established.

    Args:
        host (str): Thunderstorm host address.
        port (int): Thunderstorm port number.
        timeout (int): Connection timeout in seconds.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
       sock.connect((host,port))
    except Exception:
       return False
    else:
       sock.close()
       return True
