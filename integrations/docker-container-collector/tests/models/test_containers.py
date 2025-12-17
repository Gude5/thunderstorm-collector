from unittest.mock import MagicMock, patch

import pytest  # ty:ignore[unresolved-import]

from docker_container_collector.models.containers import (  # ty:ignore[unresolved-import]
    DockerContainer,
    DockerContainersList,
    get_list_of_running_containers,
)


def test_docker_containers_list_add_and_get():
    lst = DockerContainersList()
    c1 = DockerContainer("c1", "c1_name", "img1", "running")
    c2 = DockerContainer("c2", "c2_name", "img2", "exited")

    lst.add(c1)
    lst.add_multi([c2])

    assert lst.get_length() == 2
    containers = lst.get()
    assert containers[0] == c1
    assert containers[1] == c2

def test_get_list_of_running_containers_returns_containers():
    docker_output = [
        '{"ID": "c1", "Names": "container1", "Image": "img1", "Status": "running"}',
        '{"ID": "c2", "Names": "container2", "Image": "img2", "Status": "exited"}'
    ]

    mock_result = MagicMock()
    mock_result.stdout = "\n".join(docker_output)

    with patch("docker_container_collector.models.containers.subprocess.run", return_value=mock_result):
        lst = get_list_of_running_containers()

    assert lst.get_length() == 2
    c1, c2 = lst.get()
    assert c1.id == "c1"
    assert c1.name == "container1"
    assert c1.image == "img1"
    assert c1.status == "running"
    assert c2.id == "c2"
    assert c2.status == "exited"

def test_get_list_of_running_containers_handles_exception():
    with patch("docker_container_collector.models.containers.subprocess.run", side_effect=Exception("Docker down")):
        with pytest.raises(Exception, match="Failed to retrieve list of running Docker containers"):
            get_list_of_running_containers()
