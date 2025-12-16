"""Console script for docker_container_collector."""

import fcntl
import logging
import os
import sys
from pathlib import Path
from typing import Annotated

import typer  # ty:ignore[unresolved-import]
from rich.console import Console  # ty:ignore[unresolved-import]

from docker_container_collector.services import docker_container_collector
from docker_container_collector.utils import time

app = typer.Typer()
console = Console()

logger = logging.getLogger(__name__)

def setup_logging(log_dir: Path, log_file: Path, log_level: str) -> None:
    # logging configuration
    logging.basicConfig(level=getattr(logging, log_level.upper()), format='%(asctime)s [%(levelname)s] %(message)s')
    logger = logging.getLogger(__name__)
    # log file handler
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    handler = logging.FileHandler(log_dir / log_file)
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

def check_if_instance_is_running(lockfile="/tmp/docker_container_collector.lock") -> bool:
    """ Checks if another instance of the script is running using a lock file.

    Args:
        lockfile (str): Path to the lock file.

    Returns:
        bool: True if another instance is running, False otherwise.

    Raises:
        SystemExit: If another instance is running, exits the script.
    """
    fp = open(lockfile, 'w')
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except OSError:
        logger.error('Another instance is running. Exiting.')
        return True

@app.command()
def main(
    thunderstorm_host: Annotated[str, typer.Option(
        "--thunderstorm-host", "-t",
        help="Host of the Thunderstorm instance.")] = "localhost",
    thunderstorm_port: Annotated[int, typer.Option(
        "--thunderstorm-port", "-p",
        help="Port of the Thunderstorm instance.")] = 8080,
    store_directory: Annotated[Path, typer.Option(
        "--store-directory", "-s",
        help="Directory to store copied files from Docker containers.",
        file_okay=False,
        dir_okay=True)] = Path("store_of_copied_files"),
    scan_results_directory: Annotated[Path, typer.Option(
        "--scan-results-directory", "-r",
        help="Directory to store scan results.",
        file_okay=False,
        dir_okay=True)] = Path("scan_results"),
    skip_known_hashes: Annotated[bool, typer.Option(
        "--skip-known-hashes","-s",
        help="Whether to skip scanning files with known hashes.")] = False,
    max_file_size: Annotated[int, typer.Option(
        "--max-file-size", "-m",
        help="Maximum file size to process in bytes. 0 means no limit.")] = 0,
    file_types_of_no_interest: Annotated[list[str], typer.Option(
        "--file-types-of-no-interest", "-f",
        help="File types to exclude from processing. Use flag multiple times for multiple types.",
        case_sensitive=False,)] = [],  # noqa: B006
    log_level: Annotated[str, typer.Option(
        "--log-level",
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).")] = "INFO",
    ):
    """Console script for docker_container_collector."""

    if file_types_of_no_interest is None:
        file_types_of_no_interest = list()
    timestamp = time.get_current_timestamp()

    setup_logging(log_dir=Path("logs"),
                  log_file=Path(f"docker_container_collector-{timestamp}.log"),
                  log_level=log_level)

    if check_if_instance_is_running():
        sys.exit(1)
    try:
        docker_container_collector.run_docker_container_collector(
            timestamp=timestamp,
            cache_file_path=Path("cached_changed_objects.json"),
            store_directory=Path(f"{store_directory}/{timestamp}"),
            max_file_size=max_file_size,
            skip_known_hashes=skip_known_hashes,
            known_hashes_file_path=Path("known_file_hashes.json"),
            file_types_file_path=Path("file_types_config.json"),
            file_types_of_no_interest=set(file_types_of_no_interest),
            host="localhost",
            port=8080,
            scan_results_directory=Path(f"{scan_results_directory}/{timestamp}")
        )
    except Exception as e:
        logger.error(f"An error occurred while running the Docker Container Collector service. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    app()
