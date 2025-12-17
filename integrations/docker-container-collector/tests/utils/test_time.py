from datetime import datetime
from unittest.mock import patch

from docker_container_collector.utils.time import get_current_timestamp  # ty:ignore[unresolved-import]


def test_get_current_timestamp():
    fixed_dt = datetime(2025, 12, 17, 12, 34, 56, 789000)
    with patch("docker_container_collector.utils.time.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_dt
        mock_datetime.now.isoformat = datetime.isoformat
        timestamp = get_current_timestamp()
    # Prüfen, dass der Timestamp dem fixen Datum entspricht
    assert timestamp.startswith("2025-12-17T12-34-56-789000")
