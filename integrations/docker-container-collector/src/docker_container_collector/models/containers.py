import json
import logging
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DockerContainer:
    id: str
    name: str
    image: str
    status: str

class DockerContainersList:
    def __init__(self):
        self.docker_containers: list[DockerContainer] = []

    def add(self, docker_container: DockerContainer):
        self.docker_containers.append(docker_container)

    def add_multi(self, docker_containers: list[DockerContainer]):
        self.docker_containers.extend(docker_containers)

    def get(self) -> list[DockerContainer]:
        return self.docker_containers

    def get_length(self) -> int:
        return len(self.docker_containers)

def get_list_of_running_containers() -> DockerContainersList:
    """ Creates a list of running Docker containers.

    Returns:
        list: List of running Docker containers.

    Raises:
        Exception: If unable to connect to Docker.
    """
    logger.info("Retrieving list of running Docker containers.")
    list_of_running_containers = DockerContainersList()
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{json .}}"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            container_info = json.loads(line)
            docker_container = DockerContainer(
                id=container_info.get("ID"),
                name=container_info.get("Names"),
                image=container_info.get("Image"),
                status=container_info.get("Status")
            )
            list_of_running_containers.add(docker_container)
    except Exception as e:
        raise Exception(f"Failed to retrieve list of running Docker containers. Error: {e}") from e
    logger.info(f"Found {list_of_running_containers.get_length()} running containers.")
    return list_of_running_containers
