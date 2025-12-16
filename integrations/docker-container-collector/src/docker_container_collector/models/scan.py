import logging
from dataclasses import dataclass
from pathlib import Path

from thunderstormAPI.thunderstorm import ThunderstormAPI  # ty:ignore[unresolved-import]

from docker_container_collector.utils import connection, filesystem

from .changed_objects import ChangedObjectsList

logger = logging.getLogger(__name__)


@dataclass
class ScanResults:
    hash: str
    timestamp_object: str
    timestamp_scan: str
    matches: dict

class ScanResultsList:
    def __init__(self):
        self.scan_results: list[ScanResults] = []

    def add(self, scan_result: ScanResults):
        self.scan_results.append(scan_result)

    def get(self) -> list[ScanResults]:
        return self.scan_results

def scan_changed_objects(changed_objects: ChangedObjectsList,
                         host: str,
                         port: int,
                         known_hashes_file: Path,
                         cache_file: Path,
                         timestamp_scan: str) -> ScanResultsList:
    """ Scans each changed object using THOR Thunderstorm.

    Args:
        changed_objects (ChangedObjectsList): List of changed objects.
        scanner_command (list[str]): Command to run the external scanner.

    Returns:
        ScanResultsList: List of scan results.
    """
    logger.info("Starting scan of changed objects.")
    list_of_scan_results = ScanResultsList()
    new_known_file_hashes = list[str]()
    changed_objects_to_cache = ChangedObjectsList()
    for obj in changed_objects.get():
        thunderstorm = ThunderstormAPI(host=host, port=port, source=obj.container_id)
        try:
            if not connection.check_connection(host,port):
                raise ConnectionError(f"Cannot connect to Thunderstorm instance. Check if it is running properly. "
                                      f"Host: {host}, Port: {port}")
            matches = thunderstorm.scan(str(obj.file_path_after_copy))
            if obj.hash is None:
                raise ValueError(f'File hash is None for file {obj.file_path_after_copy}.')
            scan_results = ScanResults(hash=obj.hash,
                                       timestamp_object=obj.timestamp,
                                       timestamp_scan=timestamp_scan,
                                       matches=matches)
            list_of_scan_results.add(scan_results)
            new_known_file_hashes.append(obj.hash)
            logger.info(f"Scanned file {obj.file_path_after_copy}.")
        except Exception as e:
            changed_objects_to_cache.add(obj)
            raise Exception(f"Failed to scan file {obj.file_path_after_copy}. Error: {e}") from e
    if new_known_file_hashes:
        try:
            filesystem.save_new_known_file_hashes(known_hashes_file,new_known_file_hashes,timestamp_scan)
        except Exception as e:
            logger.warning(f"Failed to save new known file hashes to {known_hashes_file}. Error: {e}")
    if changed_objects_to_cache.get():
        try:
            filesystem.save_changed_objects_to_cache(changed_objects_to_cache.to_list_of_dicts(), cache_file)
        except Exception as e:
            logger.warning(f"Failed to save changed objects to cache {cache_file}. Error: {e}")
    return list_of_scan_results
