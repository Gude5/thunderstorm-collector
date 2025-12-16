import logging
from pathlib import Path

from docker_container_collector.models import changed_objects, containers, scan
from docker_container_collector.utils import filesystem

logger = logging.getLogger(__name__)

def run_docker_container_collector(timestamp: str,
                                   cache_file_path: Path,
                                   store_directory: Path,
                                   max_file_size: int,
                                   skip_known_hashes: bool,
                                   known_hashes_file_path: Path,
                                   file_types_file_path: Path,
                                   file_types_of_no_interest: set,
                                   host: str,
                                   port: int,
                                   scan_results_directory: Path
                                   ) -> None:
    """Runs the Docker Container Collector service.

    Args:
        timestamp (str): Current timestamp.
        cache_file_path (Path): Path to the cache file.
        store_directory (Path): Directory to store copied files.
        max_file_size (int): Maximum file size to process.
        skip_known_hashes (bool): Whether to skip known file hashes.
        known_hashes_file_path (Path): Path to the known file hashes file.
        file_types_file_path (Path): Path to the file types configuration file.
        file_types_of_no_interest (set): Set of file types to exclude.
        host (str): Host of the external scanner.
        port (int): Port of the external scanner.
        scan_results_directory (Path): Directory to store scan results.
    Returns:
        None
    """
    logger.info("Starting Docker Container Collector service.")
    try:
        list_of_running_containers = containers.get_list_of_running_containers()
    except Exception as e:
        logger.warning(f"Failed to get list of running Docker containers. Error: {e}")
        list_of_running_containers = containers.DockerContainersList()
    if list_of_running_containers.get_length() > 0:
        list_of_new_changed_objects = changed_objects.get_new_changed_objects(
                                                                            running_containers=list_of_running_containers,
                                                                            timestamp=timestamp)
    else:
        list_of_new_changed_objects = changed_objects.ChangedObjectsList()
    try:
        list_of_changed_objects = changed_objects.add_cached_changed_objects(
                                                                            changed_objects=list_of_new_changed_objects,
                                                                            cache_file=cache_file_path)
    except Exception as e:
        logger.warning(f"Failed to add cached changed objects. Continue without cached objects. Error: {e}")
        list_of_changed_objects = list_of_new_changed_objects
    try:
        list_of_known_file_hashes = filesystem.load_known_file_hashes(file_path=known_hashes_file_path)
    except Exception as e:
        logger.warning(f"Failed to load known file hashes from {known_hashes_file_path}. "
                      f"Continue without known hashes. Error: {e}")
        list_of_known_file_hashes = set()
    try:
        directory_of_file_types = filesystem.load_file_types(file_path=file_types_file_path)
    except Exception as e:
        logger.warning(f"Failed to load file types from {file_types_file_path}. "
                        f"Continue without file types. Error: {e}")
        directory_of_file_types = {}
    filtered_list_of_changed_objects = changed_objects.filter_changed_objects(changed_objects=list_of_changed_objects,
                           store_directory=store_directory,
                           max_file_size=max_file_size,
                           skip_known_hashes=skip_known_hashes,
                           known_hashes=list_of_known_file_hashes,
                           file_types=directory_of_file_types,
                           file_types_of_no_interest=file_types_of_no_interest)
    try:
        scan_results = scan.scan_changed_objects(changed_objects=filtered_list_of_changed_objects,
                                                host=host,
                                                port=port,
                                                known_hashes_file=known_hashes_file_path,
                                                cache_file=cache_file_path,
                                                timestamp_scan=timestamp)
    except Exception as e:
        raise Exception(f"Failed to scan changed objects. Error: {e}") from e
    try:
        filesystem.save_scan_results(scan_results, scan_results_directory, timestamp)
    except Exception as e:
        logger.warning(f"Failed to save scan results to {scan_results_directory}. Error: {e}")
    logger.info("Docker Container Collector service completed.")
