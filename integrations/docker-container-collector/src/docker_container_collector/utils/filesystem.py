import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def copy_file_from_container(container_id: str, source_path: Path, destination_path: Path)  -> None:
    """Copy a file from a Docker container to the host.

    Args:
        container_id (str): ID of the Docker container.
        source_path (Path): Path of the file inside the container.
        destination_path (Path): Path on the host where the file will be copied.

    Returns:
        None
    """
    logger.info(f"Copying file {source_path} from container {container_id} to {destination_path}.")
    try:
        copy = subprocess.run(["docker", "cp", f"{container_id}:{source_path}", destination_path], capture_output=True)
        if copy.returncode == 0:
            logger.info(f"Copied file {source_path} from container {container_id} successfully.")
        else:
            raise Exception(f"Failed to copy file {source_path} from container {container_id}. "
                            f"Return code: {copy.returncode}. Error: {copy.stderr.decode().strip()}")
    except Exception as e:
        try:
            result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container_id],
                                    capture_output=True,
                                    text=True)
            if result.returncode != 0 or result.stdout.strip().lower() != "true":
                raise Exception(f"Failed to copy file {source_path} from container because container {container_id} "
                                "is not running anymore.")
            else:
                raise Exception(f"Failed to copy file {source_path} from container {container_id}. Error: {e}")
        except Exception as _:
            raise Exception(f"Failed to copy file {source_path} from container {container_id}. Error: {e}") from e

def load_file_types(file_path: Path) -> dict:
    """Loads file types and their headers from a JSON configuration file.

    Args:
        file_path (Path): Path to the JSON file containing file types and headers.
    Returns:
        dict: Dictionary mapping file types to their headers.
    """
    logger.info(f"Loading file types from {file_path}.")
    file_types = dict()
    try:
        with open(file_path) as f:
            file_types = json.load(f)
        logger.info(f"Loaded {len(file_types)} file types from {file_path}.")
    except Exception as e:
        raise Exception(f"Failed to load file types from {file_path}. Error: {e}") from e
    return file_types

def load_known_file_hashes(file_path: Path) -> set[str]:
    """Reads known file hashes from the specified file.

    Args:
        file_path (Path): Path to the file where known hashes are stored.
    Returns:
        set[str]: Set of known file hashes.
    """
    logger.info(f"Loading known file hashes from {file_path}.")
    known_hashes = set()
    try:
        with open(file_path) as f:
            file_hashes = json.load(f)
        for hashes in file_hashes.values():
            known_hashes.update(hashes)
        logger.info(f"Loaded {len(known_hashes)} known file hashes from {file_path}.")
    except Exception as e:
        raise Exception(f"Failed to read known file hashes from {file_path}. Error: {e}") from e
    return known_hashes

def save_new_known_file_hashes(file_path: Path, new_hashes: list[str], timestamp: str) -> None:
    """Saves new known file hashes to the specified file.

    Args:
        file_path (Path): Path to the file where known hashes are stored.
        new_hashes (list[str]): List of new file hashes to be added.
        timestamp (str): Timestamp of when the hashes were added.
    """
    logger.info(f"Saving new known file hashes to {file_path}.")
    try:
        with open(file_path, 'a') as f:
            file_hashes = json.load(f)
        file_hashes[timestamp] = new_hashes
        with open(file_path, 'w') as f:
            json.dump(file_hashes, f, indent=4)
        logger.info(f"Saved {len(new_hashes)} new known file hashes to {file_path}.")
    except Exception as e:
        raise Exception(f"Failed to save new known file hashes to {file_path}. Error: {e}") from e

def save_changed_objects_to_cache(new_cached_objects: list[dict], cache_file: Path) -> None:
    """Saves changed objects to cache.

    Args:
        changed_objects (ChangedObjectsList): List of changed objects to be cached.
    """
    logger.info(f"Saving {len(new_cached_objects)} changed objects to cache {cache_file}.")
    try:
        if not cache_file.exists():
            with open(cache_file, 'w') as f:
                json.dump([], f, indent=4)
        with open(cache_file) as f:
            cache = json.load(f)
        cache.extend(new_cached_objects)
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=4)
        logger.info(f"Saved {len(new_cached_objects)} changed objects to cache {cache_file}.")
    except Exception as e:
        raise Exception(f"Failed to save changed objects to cache {cache_file}. Error: {e}") from e

def save_scan_results(scan_results, directory: Path, timestamp) -> None:
    """Saves scan results to a JSON file.

    Args:
        scan_results (ScanResultsList): List of scan results to be saved.
    """
    logger.info(f"Saving scan results to {directory / f'scan_results_{timestamp}.json'}.")
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
    try:
        results_to_save = [result.__dict__ for result in scan_results.get()]
        with open(directory / f'scan_results_{timestamp}.json', 'w') as f:
            json.dump(results_to_save, f, indent=4)
        logger.info(f"Saved {len(results_to_save)} scan results to scan_results_{timestamp}.json.")
    except Exception as e:
        raise Exception(
            "Failed to save scan results to "
            f"{directory / f'scan_results_{timestamp}.json'}. Error: {e}"
        ) from e
