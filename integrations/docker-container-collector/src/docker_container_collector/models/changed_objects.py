import hashlib
import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from docker_container_collector.utils import filesystem

from .containers import DockerContainer, DockerContainersList

logger = logging.getLogger(__name__)

@dataclass
class ChangedObject:
    container_id: str
    file_path: Path
    change_type: str
    timestamp: str
    from_cache: bool = False
    file_path_after_copy: Optional[Path] = None  # noqa: UP045
    hash: Optional[str] = None  # noqa: UP045
    file_size: Optional[int] = None  # noqa: UP045

    def set_file_path_after_copy(self, directory: Path):
        self.file_path_after_copy = directory / str(uuid.uuid4())

    def to_dict(self) -> dict:
        return {
            "container_id": self.container_id,
            "file_path": str(self.file_path),
            "change_type": self.change_type,
            "timestamp": self.timestamp,
            "from_cache": self.from_cache,
            "file_path_after_copy": str(self.file_path_after_copy) if self.file_path_after_copy else None,
            "hash": self.hash,
            "file_size": self.file_size
        }

    def set_hash(self):
        with open(str(self.file_path_after_copy), 'rb') as f:
            self.hash = hashlib.sha256(f.read()).hexdigest()

    def set_file_size(self):
        self.file_size = os.path.getsize(str(self.file_path_after_copy))

    def is_not_deleted(self) -> bool:
        return self.change_type != "D"

    def is_file(self) -> bool:
        result = subprocess.run(
            ["docker", "exec", self.container_id, "test", "-f", str(self.file_path)],
            capture_output=True
        ).returncode == 0
        return result

    def is_duplicate_of(self, other: "ChangedObject") -> bool:
        return self.hash == other.hash

    def is_too_big(self, max_size: int) -> bool:
        if self.file_size is None:
            return False
        return self.file_size > max_size

    def has_known_hash(self, known_hashes: set[str]) -> bool:
        return self.hash in known_hashes

    def has_file_type_of_no_interest(self, file_types: dict, file_types_of_no_interest: set) -> bool:
        with open(str(self.file_path_after_copy), 'rb') as f:
            file_header = f.read(20).hex().upper()
        for file_type, headers in file_types.items():
            for header in headers:
                if file_header.startswith(header):
                    if file_type in file_types_of_no_interest:
                        return True
        return False

class ChangedObjectsList:
    def __init__(self):
        self.changed_objects: list[ChangedObject] = []

    def add(self, changed_object: ChangedObject):
        self.changed_objects.append(changed_object)

    def add_multi(self, changed_objects: list[ChangedObject]):
        self.changed_objects.extend(changed_objects)

    def get(self) -> list[ChangedObject]:
        return self.changed_objects

    def remove(self, changed_object: ChangedObject):
        self.changed_objects.remove(changed_object)

    def remove_multi(self, changed_objects: list[ChangedObject]):
        for obj in changed_objects:
            self.changed_objects.remove(obj)

    def get_length(self) -> int:
        return len(self.changed_objects)

    def to_list_of_dicts(self) -> list[dict]:
        return [obj.to_dict() for obj in self.changed_objects]

    def remove_deleted(self):
        self.changed_objects = [obj for obj in self.changed_objects if obj.is_not_deleted()]

    def remove_objects_with_duplicate_hashes(self):
        unique_hashes = set()
        unique_objects = []
        for obj in self.changed_objects:
            if obj.hash not in unique_hashes:
                unique_hashes.add(obj.hash)
                unique_objects.append(obj)
        self.changed_objects = unique_objects

    def remove_non_files_objects(self):
        self.changed_objects = [obj for obj in self.changed_objects if obj.is_file()]

    def remove_too_big_objects(self, max_size: int):
        if max_size <= 0:
            return
        self.changed_objects = [obj for obj in self.changed_objects if not obj.is_too_big(max_size)]

    def remove_objects_with_known_hashes(self, known_hashes: set[str]):
        self.changed_objects = [obj for obj in self.changed_objects if not obj.has_known_hash(known_hashes)]

    def remove_objects_with_file_types_of_no_interest(self, file_types: dict, file_types_of_no_interest: set[str]):
        self.changed_objects = [obj for obj in self.changed_objects
                                if not obj.has_file_type_of_no_interest(file_types, file_types_of_no_interest)]


def get_new_changed_objects(running_containers: DockerContainersList, timestamp: str) -> ChangedObjectsList:
    """ Processes each running Docker container to find changed files.

    Args:
        running_containers (DockerContainersList): List of running Docker containers.
    """
    logger.info("Retrieving new changed objects from running containers.")
    changed_objects = ChangedObjectsList()
    for container in running_containers.get():
        changed_objects.add_multi(get_changed_objects_from_container(container,timestamp).get())
    return changed_objects

def get_changed_objects_from_container(container: DockerContainer, timestamp: str) -> ChangedObjectsList:
    """ Processes a single Docker container to find changed files.
        Initializes list of changed files (DIFF) detected in the container. Each change is represented as a dictionary
        including container ID, change type, file path, and timestamp.

    Args:
        container (DockerContainer): A DockerContainer object representing a Docker container.
    """
    changed_objects = ChangedObjectsList()
    logger.info(f"Processing container {container.id}, image: {container.image}.")
    # docker diff has no --format option, so we need to parse its output manually
    result = subprocess.run(['docker', 'diff', container.id, ],capture_output=True,text=True)
    changes = result.stdout.strip().splitlines()
    if not changes:
        logger.info(f"No changes detected in container {container.id}.")
        return changed_objects
    for change in changes:
        change_type = change[0]
        file_path = change[2:]
        logger.info(f"Found file: container ID: {container.id}, file path: {file_path}, change type: {change_type}")
        changed_objects.add(ChangedObject(container_id=container.id,
                                           change_type=change_type,
                                           file_path=Path(file_path),
                                           timestamp=timestamp))
    return changed_objects

def get_cached_changed_objects(cache_file: Path) -> ChangedObjectsList:
    """ Reads cached changed objects from a JSON file.

    Args:
        cache_file (Path): Path to the cache file.

    Returns:
        ChangedObjectsList: List of cached changed objects.
    """
    logger.info(f"Loading cached changed objects from {cache_file}.")
    changed_objects = ChangedObjectsList()
    if not cache_file.exists():
        logger.info(f"Cache file {cache_file} does not exist. No cached changed objects to load.")
        return changed_objects
    try:
        with open(cache_file) as f:
            cached_data = json.load(f)
            changed_objects.add_multi(cached_data)
    except Exception as e:
        raise Exception(f"Failed to read cached changed objects from {cache_file}. Error: {e}") from e
    return changed_objects

def add_cached_changed_objects(changed_objects: ChangedObjectsList,
                              cache_file: Path) -> ChangedObjectsList:
    """ Adds cached changed objects to the current list.
    Args:
        changed_objects (ChangedObjectsList): Current list of changed objects.
        cache_file (Path): Path to the cache file.
    Returns:
        ChangedObjectsList: Updated list of changed objects.
    """
    logger.info("Adding cached changed objects to the current list.")
    try:
        cached_changed_objects = get_cached_changed_objects(cache_file)
    except Exception as e:
        raise Exception(f"Failed to load cached changed objects from {cache_file}. Continue without cached objects. "
                       f"Error: {e}") from e
    for obj in cached_changed_objects.get():
        obj.from_cache = True
    changed_objects.add_multi(cached_changed_objects.get())
    logger.info(f"Added {cached_changed_objects.get_length()} cached changed objects.")
    return changed_objects

def filter_changed_objects(changed_objects: ChangedObjectsList,
                           store_directory: Path,
                           max_file_size: int,
                           skip_known_hashes: bool,
                           known_hashes: set[str],
                           file_types: dict,
                           file_types_of_no_interest: set[str]) -> ChangedObjectsList:
    """ Applies a series of filters to the list of changed objects.

    Args:
        changed_objects (ChangedObjectsList): List of changed objects.
        store_directory (Path): Directory for storing copied files.
        max_file_size (int): Maximum file size in bytes.
        skip_known_hashes (bool): Whether to skip objects with known hashes.
        known_hashes (set[str]): Set of known file hashes.
        file_types (dict): Dictionary of file types and their headers.
        file_types_of_no_interest (set[str]): Set of file types to exclude.

    Returns:
        ChangedObjectsList: Filtered list of changed objects.
    """
    logger.info("Filtering changed objects.")
    # tests possible before copying files
    changed_objects.remove_deleted()
    logger.info(f"Removed deleted objects. Remaining objects: {changed_objects.get_length()}.")
    changed_objects.remove_non_files_objects()
    logger.info(f"Removed non-file objects. Remaining objects: {changed_objects.get_length()}.")
    for obj in changed_objects.get():
        obj.set_file_path_after_copy(store_directory)
        logger.info(f"Set file path after copy for file {obj.file_path} from "
                    f"container {obj.container_id} to {obj.file_path_after_copy}.")
        if obj.is_not_deleted():
            if obj.file_path_after_copy is None:
                logger.info(f"File path after copy is not set for file {obj.file_path} from "
                            f"container {obj.container_id}. Skipping copy.")
                continue
            try:
                filesystem.copy_file_from_container(obj.container_id, obj.file_path, obj.file_path_after_copy)
            except Exception as e:
                logger.warning(f"Failed to copy file {obj.file_path} from container {obj.container_id}. Error: {e}")
                continue
            obj.set_hash()
            obj.set_file_size()
    # further tests after copying files
    changed_objects.remove_objects_with_duplicate_hashes()
    logger.info(f"Removed duplicate objects. Remaining objects: {changed_objects.get_length()}.")
    # optional tests (add conditions later)
    if max_file_size > 0:
        changed_objects.remove_too_big_objects(max_file_size)
        logger.info(f"Removed too big objects. Maximal file size: {max_file_size}. "
                    f"Remaining objects: {changed_objects.get_length()}.")
    if skip_known_hashes:
        changed_objects.remove_objects_with_known_hashes(known_hashes)
    logger.info(f"Removed objects with known hashes. Remaining objects: {changed_objects.get_length()}.")
    if file_types_of_no_interest:
        changed_objects.remove_objects_with_file_types_of_no_interest(file_types, file_types_of_no_interest)
    logger.info(f"Removed objects with file types of no interest. Remaining objects: {changed_objects.get_length()}.")
    return changed_objects
