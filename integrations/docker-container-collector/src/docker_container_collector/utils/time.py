from datetime import datetime


def get_current_timestamp() -> str:
    """Returns the current timestamp as a string.

    Returns:
        str: Current timestamp in ISO 8601 format.
    """
    return datetime.now().isoformat()
