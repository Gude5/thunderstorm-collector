import hashlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest  # ty:ignore[unresolved-import]

from docker_container_collector.models.changed_objects import (  # ty:ignore[unresolved-import]
    ChangedObject,
    ChangedObjectsList,
    add_cached_changed_objects,
    filter_changed_objects,
    get_cached_changed_objects,
    get_changed_objects_from_container,
    get_new_changed_objects,
)
from docker_container_collector.models.containers import (  # ty:ignore[unresolved-import]
    DockerContainer,
    DockerContainersList,
)


@pytest.fixture
def temp_file(tmp_path: Path):
    f = tmp_path / "test.txt"
    f.write_text("test content")
    return f

@pytest.fixture
def changed_obj(temp_file: Any):
    return ChangedObject(container_id="c1", file_path=temp_file, change_type="C", timestamp="2025-12-17")

@pytest.fixture
def container():
    return DockerContainer(id="c1", image="img1", name="container1", status="up")

# Tests for ChangedObject

def test_to_dict(changed_obj: ChangedObject, tmp_path: Path):
    changed_obj.set_file_path_after_copy(tmp_path)
    d = changed_obj.to_dict()
    assert d["container_id"] == changed_obj.container_id
    assert d["file_path"] == str(changed_obj.file_path)
    assert d["file_path_after_copy"] == str(changed_obj.file_path_after_copy)

def test_set_file_path_after_copy(changed_obj: ChangedObject, tmp_path: Path):
    changed_obj.set_file_path_after_copy(tmp_path)
    assert changed_obj.file_path_after_copy is not None
    assert tmp_path in changed_obj.file_path_after_copy.parents

def test_set_hash_and_file_size(changed_obj: ChangedObject, tmp_path: Path):
    changed_obj.set_file_path_after_copy(tmp_path)
    dest = changed_obj.file_path_after_copy
    dest.write_text("test content")
    changed_obj.set_hash()
    changed_obj.set_file_size()
    expected_hash = hashlib.sha256(b"test content").hexdigest()
    assert changed_obj.hash == expected_hash
    assert changed_obj.file_size == len("test content")

def test_is_not_deleted(changed_obj: ChangedObject):
    assert changed_obj.is_not_deleted() is True
    changed_obj.change_type = "D"
    assert changed_obj.is_not_deleted() is False

def test_is_file(changed_obj: ChangedObject):
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        assert changed_obj.is_file() is True
        mock_run.assert_called_once_with(
            ["docker", "exec", changed_obj.container_id, "test", "-f", str(changed_obj.file_path)],
            capture_output=True
        )
    mock_result.returncode = 1
    with patch("subprocess.run", return_value=mock_result):
        assert changed_obj.is_file() is False

def test_is_duplicate_of(changed_obj: ChangedObject):
    other = ChangedObject(container_id="c2", file_path=changed_obj.file_path,
                          change_type="M", timestamp="2025-12-17")
    changed_obj.hash = "hash1"
    other.hash = "hash1"
    assert changed_obj.is_duplicate_of(other) is True
    other.hash = "hash2"
    assert changed_obj.is_duplicate_of(other) is False

def test_is_too_big(changed_obj: ChangedObject):
    changed_obj.file_size = 10
    assert changed_obj.is_too_big(5) is True
    assert changed_obj.is_too_big(15) is False
    changed_obj.file_size = None
    assert changed_obj.is_too_big(5) is False

def test_has_known_hash(changed_obj: ChangedObject):
    changed_obj.hash = "abc"
    known = {"abc", "def"}
    assert changed_obj.has_known_hash(known) is True
    assert changed_obj.has_known_hash({"xyz"}) is False

def test_has_file_type_of_no_interest(changed_obj: ChangedObject, tmp_path: Path):
    changed_obj.set_file_path_after_copy(tmp_path)
    dest = changed_obj.file_path_after_copy
    dest.write_bytes(bytes.fromhex("FFD8FFE00000000000"))
    file_types = {"jpg": ["FFD8FF"]}
    assert changed_obj.has_file_type_of_no_interest(file_types, {"jpg"}) is True
    assert changed_obj.has_file_type_of_no_interest(file_types, {"png"}) is False

# Tests for ChangedObjectsList

def test_add_and_get():
    lst = ChangedObjectsList()
    obj = ChangedObject("c1", Path("a.txt"), "M", "ts")
    lst.add(obj)
    assert lst.get_length() == 1
    assert lst.get()[0] == obj

def test_add_and_remove_multi():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    lst.add_multi([obj1, obj2])
    assert lst.get_length() == 2
    lst.remove_multi([obj1,obj2])
    assert lst.get_length() == 0

def test_to_list_of_dicts():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    lst.add_multi([obj1, obj2])
    dicts = lst.to_list_of_dicts()
    assert isinstance(dicts, list)
    assert len(dicts) == 2
    assert dicts[0]["container_id"] == "c1"
    assert dicts[1]["container_id"] == "c2"

def test_remove_deleted():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "D", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    lst.add_multi([obj1, obj2])
    lst.remove_deleted()
    assert lst.get_length() == 1
    assert lst.get()[0] == obj2

def test_remove_objects_with_duplicate_hashes():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    obj1.hash = "h1"
    obj2.hash = "h1"
    lst.add_multi([obj1, obj2])
    lst.remove_objects_with_duplicate_hashes()
    assert lst.get_length() == 1

def test_remove_non_files_objects():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("dir"), "M", "ts")
    lst.add_multi([obj1, obj2])
    with patch.object(ChangedObject, 'is_file', side_effect=[True, False]):
        lst.remove_non_files_objects()
    assert lst.get_length() == 1
    assert lst.get()[0] == obj1

def test_remove_too_big_objects():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    obj1.file_size = 10
    obj2.file_size = 5
    lst.add_multi([obj1, obj2])
    lst.remove_too_big_objects(7)
    assert lst.get_length() == 1
    assert lst.get()[0] == obj2

def test_remove_objects_with_known_hashes():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.txt"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    obj1.hash = "h1"
    obj2.hash = "h2"
    lst.add_multi([obj1, obj2])
    lst.remove_objects_with_known_hashes({"h1"})
    assert lst.get_length() == 1
    assert lst.get()[0] == obj2

def test_remove_objects_with_file_types_of_no_interest():
    lst = ChangedObjectsList()
    obj1 = ChangedObject("c1", Path("a.jpg"), "M", "ts")
    obj2 = ChangedObject("c2", Path("b.txt"), "M", "ts")
    lst.add_multi([obj1, obj2])
    with patch.object(ChangedObject, 'has_file_type_of_no_interest', side_effect=[True, False]):
        lst.remove_objects_with_file_types_of_no_interest({"jpg": ["FFD8FF"]}, {"jpg"})
    assert lst.get_length() == 1
    assert lst.get()[0] == obj2

def test_get_changed_objects_from_container(container):
    mock_result = MagicMock()
    mock_result.stdout = "M /file1\nA /file2"
    with patch("subprocess.run", return_value=mock_result):
        changed_objects = get_changed_objects_from_container(container, "2025-12-17")
    assert isinstance(changed_objects, ChangedObjectsList)
    assert changed_objects.get_length() == 2
    paths = [str(obj.file_path) for obj in changed_objects.get()]
    assert "/file1" in paths
    assert "/file2" in paths

    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result):
        changed_objects = get_changed_objects_from_container(container, "2025-12-17")
    assert changed_objects.get_length() == 0

def test_get_new_changed_objects_multiple_containers(mocker):
    container1 = MagicMock()
    container1.id = "c1"
    container2 = MagicMock()
    container2.id = "c2"

    containers_list = DockerContainersList()
    containers_list.add_multi([container1, container2])

    mock_changed_objects = MagicMock()
    mock_changed_objects.get.return_value = []

    mocker.patch(
        "docker_container_collector.models.changed_objects.get_changed_objects_from_container",
        return_value=mock_changed_objects
    )

    result = get_new_changed_objects(containers_list, "2025-12-17")
    assert result.get() == []

def test_get_cached_changed_objects_file(tmp_path):
    cache_file = tmp_path / "cache.json"
    data = [{"container_id": "c1", "file_path": "a.txt", "change_type": "M", "timestamp": "2025-12-17"}]
    cache_file.write_text(json.dumps(data))

    result = get_cached_changed_objects(cache_file)
    assert isinstance(result, ChangedObjectsList)
    assert result.get_length() == len(data)

    cache_file = tmp_path / "nonexistent.json"
    result = get_cached_changed_objects(cache_file)
    assert result.get_length() == 0

def test_add_cached_changed_objects(mocker):
    lst = ChangedObjectsList()
    cached_obj = ChangedObject("c1", Path("a.txt"), "M", "ts")
    cached_list = ChangedObjectsList()
    cached_list.add(cached_obj)

    mocker.patch(
        "docker_container_collector.models.changed_objects.get_cached_changed_objects",
        return_value=cached_list
    )

    result = add_cached_changed_objects(lst, Path("/tmp/cache.json"))
    assert all(obj.from_cache for obj in result.get())


def test_filter_changed_objects(tmp_path):
    obj = ChangedObject("c1", tmp_path / "a.txt", "C", "ts")
    obj.file_path_after_copy = tmp_path / "copy.txt"
    obj.hash = "hash1"
    obj.file_size = 10

    lst = ChangedObjectsList()
    lst.add(obj)

    file_types = {"jpg": ["FFD8FF"]}
    file_types_of_no_interest = set()
    assert lst.get_length() == 1
    with patch("docker_container_collector.models.changed_objects.filesystem.copy_file_from_container") as mock_copy:
        with patch.object(ChangedObject, "is_file", return_value=True):
            with patch.object(ChangedObject, "set_hash"):
                with patch.object(ChangedObject, "set_file_size"):
                    filtered = filter_changed_objects(
                        lst,
                        store_directory=tmp_path,
                        max_file_size=20,
                        skip_known_hashes=False,
                        known_hashes=set(),
                        file_types=file_types,
                        file_types_of_no_interest=file_types_of_no_interest
                    )
    assert filtered.get_length() == 1
    mock_copy.assert_called_once()
