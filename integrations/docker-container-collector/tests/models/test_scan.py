from unittest.mock import MagicMock, patch

import pytest  # ty:ignore[unresolved-import]

from docker_container_collector.models.changed_objects import (  # ty:ignore[unresolved-import]
    ChangedObject,
    ChangedObjectsList,
)
from docker_container_collector.models.scan import ScanResultsList, scan_changed_objects  # ty:ignore[unresolved-import]


@pytest.fixture
def sample_changed_object(tmp_path):
    obj = ChangedObject(
        container_id="c1",
        file_path=tmp_path / "file.txt",
        change_type="M",
        timestamp="2025-12-17",
        file_path_after_copy=tmp_path / "copy.txt",
        hash="hash1"
    )
    obj.file_path_after_copy.write_text("content")
    return obj

@pytest.fixture
def changed_objects_list(sample_changed_object):
    lst = ChangedObjectsList()
    lst.add(sample_changed_object)
    return lst

def test_scan_changed_objects_success(changed_objects_list, tmp_path):
    host = "127.0.0.1"
    port = 1234
    known_hashes_file = tmp_path / "known.json"
    cache_file = tmp_path / "cache.json"
    timestamp_scan = "2025-12-17"
    delete_files_after_scan = True

    with patch("docker_container_collector.models.scan.ThunderstormAPI") as mock_ts_api, \
         patch("docker_container_collector.models.scan.connection.check_connection", return_value=True), \
         patch("docker_container_collector.models.scan.filesystem.delete_file") as mock_delete, \
         patch("docker_container_collector.models.scan.filesystem.save_new_known_file_hashes") as mock_save_hashes, \
         patch("docker_container_collector.models.scan.filesystem.save_changed_objects_to_cache") as mock_save_cache:

        mock_ts_instance = MagicMock()
        mock_ts_instance.scan.return_value = {}
        mock_ts_api.return_value = mock_ts_instance

        results: ScanResultsList = scan_changed_objects(
            changed_objects=changed_objects_list,
            host=host,
            port=port,
            known_hashes_file=known_hashes_file,
            cache_file=cache_file,
            timestamp_scan=timestamp_scan,
            delete_files_after_scan=delete_files_after_scan
        )

    assert results.get()
    assert results.get()[0].hash == "hash1"
    assert results.get()[0].timestamp_scan == timestamp_scan

    mock_delete.assert_called_once_with(changed_objects_list.get()[0].file_path_after_copy)

    mock_save_hashes.assert_called_once()

    mock_save_cache.assert_not_called()

def test_scan_changed_objects_connection_error(changed_objects_list, tmp_path):
    host = "127.0.0.1"
    port = 1234
    known_hashes_file = tmp_path / "known.json"
    cache_file = tmp_path / "cache.json"
    timestamp_scan = "2025-12-17"
    delete_files_after_scan = True

    with patch("docker_container_collector.models.scan.ThunderstormAPI") as mock_ts_api, \
         patch("docker_container_collector.models.scan.connection.check_connection", return_value=False):

        mock_ts_instance = MagicMock()
        mock_ts_api.return_value = mock_ts_instance

        with pytest.raises(Exception, match="Cannot connect to Thunderstorm instance"):
            scan_changed_objects(
                changed_objects=changed_objects_list,
                host=host,
                port=port,
                known_hashes_file=known_hashes_file,
                cache_file=cache_file,
                timestamp_scan=timestamp_scan,
                delete_files_after_scan=delete_files_after_scan
            )

def test_scan_changed_objects_file_hash_none(changed_objects_list, tmp_path):
    changed_objects_list.get()[0].hash = None
    host = "127.0.0.1"
    port = 1234
    known_hashes_file = tmp_path / "known.json"
    cache_file = tmp_path / "cache.json"
    timestamp_scan = "2025-12-17"
    delete_files_after_scan = True

    with patch("docker_container_collector.models.scan.ThunderstormAPI") as mock_ts_api, \
         patch("docker_container_collector.models.scan.connection.check_connection", return_value=True):

        mock_ts_instance = MagicMock()
        mock_ts_instance.scan.return_value = {}
        mock_ts_api.return_value = mock_ts_instance

        with pytest.raises(Exception, match="File hash is None"):
            scan_changed_objects(
                changed_objects=changed_objects_list,
                host=host,
                port=port,
                known_hashes_file=known_hashes_file,
                cache_file=cache_file,
                timestamp_scan=timestamp_scan,
                delete_files_after_scan=delete_files_after_scan
            )
