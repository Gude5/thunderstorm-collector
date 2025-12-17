from unittest.mock import MagicMock, patch

import pytest  # ty:ignore[unresolved-import]

from docker_container_collector.services import docker_container_collector  # ty:ignore[unresolved-import]


@pytest.fixture
def tmp_paths(tmp_path):
    return {
        "cache_file": tmp_path / "cache.json",
        "store_dir": tmp_path / "store",
        "known_hashes": tmp_path / "known.json",
        "file_types": tmp_path / "filetypes.json",
        "scan_results": tmp_path / "scan_results"
    }

def test_run_docker_container_collector_happy_path(tmp_paths):
    timestamp = "2025-12-17"
    file_types_of_no_interest = set()
    host = "127.0.0.1"
    port = 1234
    max_file_size = 100
    skip_known_hashes = False
    delete_files_after_scan = True

    # Mocks für alle externen Aufrufe
    with patch("docker_container_collector.services.docker_container_collector.containers."
               "get_list_of_running_containers") as mock_containers, \
         patch("docker_container_collector.services.docker_container_collector."
               "changed_objects.get_new_changed_objects") as mock_new_changed, \
         patch("docker_container_collector.services.docker_container_collector."
               "changed_objects.add_cached_changed_objects") as mock_add_cached, \
         patch("docker_container_collector.services.docker_container_collector."
               "filesystem.load_known_file_hashes", return_value=set()), \
         patch("docker_container_collector.services.docker_container_collector."
               "filesystem.load_file_types", return_value={}), \
         patch("docker_container_collector.services.docker_container_collector."
               "changed_objects.filter_changed_objects") as mock_filter, \
         patch("docker_container_collector.services.docker_container_collector."
               "scan.scan_changed_objects") as mock_scan, \
         patch("docker_container_collector.services.docker_container_collector."
               "filesystem.save_scan_results") as mock_save_scan:

        mock_containers.return_value.get_length.return_value = 1
        mock_new_changed.return_value = MagicMock()
        mock_add_cached.return_value = MagicMock()
        mock_filter.return_value = MagicMock()
        mock_scan.return_value = MagicMock()

        docker_container_collector.run_docker_container_collector(
            timestamp=timestamp,
            cache_file_path=tmp_paths["cache_file"],
            store_directory=tmp_paths["store_dir"],
            max_file_size=max_file_size,
            skip_known_hashes=skip_known_hashes,
            known_hashes_file_path=tmp_paths["known_hashes"],
            file_types_file_path=tmp_paths["file_types"],
            file_types_of_no_interest=file_types_of_no_interest,
            host=host,
            port=port,
            scan_results_directory=tmp_paths["scan_results"],
            delete_files_after_scan=delete_files_after_scan
        )

        # Prüfen, dass alle zentralen Schritte aufgerufen wurden
        mock_containers.assert_called_once()
        mock_new_changed.assert_called_once()
        mock_add_cached.assert_called_once()
        mock_filter.assert_called_once()
        mock_scan.assert_called_once()
        mock_save_scan.assert_called_once()
