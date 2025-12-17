from unittest.mock import MagicMock, patch

import pytest  # ty:ignore[unresolved-import]

from docker_container_collector.utils import filesystem  # ty:ignore[unresolved-import]


def test_copy_file_from_container_success(tmp_path):
    container_id = "c1"
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"

    with patch("docker_container_collector.utils.filesystem.os.path.exists", return_value=True), \
         patch("docker_container_collector.utils.filesystem.os.makedirs"), \
         patch("docker_container_collector.utils.filesystem.subprocess.run") as mock_run:

        mock_run.return_value.returncode = 0
        filesystem.copy_file_from_container(container_id, src, dst)

        mock_run.assert_called_once_with(
            ["docker", "cp", f"{container_id}:{src}", dst], capture_output=True
        )

def test_copy_file_from_container_failure_container_stopped(tmp_path):
    container_id = "c1"
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"

    mock_run_failure = MagicMock()
    mock_run_failure.returncode = 1
    mock_run_failure.stderr = b"error"

    mock_run_inspect = MagicMock()
    mock_run_inspect.returncode = 0
    mock_run_inspect.stdout = "false\n"

    with patch("docker_container_collector.utils.filesystem.os.path.exists", return_value=True), \
         patch("docker_container_collector.utils.filesystem.os.makedirs"), \
         patch("docker_container_collector.utils.filesystem.subprocess.run", side_effect=[mock_run_failure, \
                                                                                           mock_run_inspect]):
        with pytest.raises(RuntimeError):
            filesystem.copy_file_from_container(container_id, src, dst)

def test_load_file_types(tmp_path):
    file_path = tmp_path / "types.json"
    file_path.write_text('{"jpg":["FFD8FF"], "png":["89504E47"]}')
    file_types = filesystem.load_file_types(file_path)
    assert "jpg" in file_types
    assert "png" in file_types

def test_load_known_file_hashes(tmp_path):
    file_path = tmp_path / "hashes.json"
    file_path.write_text('{"2025-12-17":["hash1","hash2"]}')
    known_hashes = filesystem.load_known_file_hashes(file_path)
    assert known_hashes == {"hash1","hash2"}

def test_save_new_known_file_hashes(tmp_path):
    file_path = tmp_path / "known.json"
    filesystem.save_new_known_file_hashes(file_path, ["h1","h2"], "ts")
    import json
    with open(file_path) as f:
        data = json.load(f)
    assert data["ts"] == ["h1","h2"]

def test_delete_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("content")
    filesystem.delete_file(f)
    assert not f.exists()

def test_delete_file_none():
    filesystem.delete_file(None)
