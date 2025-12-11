import fcntl
from datetime import datetime
import hashlib
import json
import sys
import logging
import hashlib
from thunderstormAPI.thunderstorm import ThunderstormAPI
import yaml
import subprocess
import os
import argparse
import socket

# Get current date
DATE = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

# Load configuration from YAML file
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

THUNDERSTORM_HOST = config['THUNDERSTORM_HOST']
THUNDERSTORM_PORT = config['THUNDERSTORM_PORT']
GLOBAL_CHANGED_FILES_DIRECTORY = config['GLOBAL_CHANGED_FILES_DIRECTORY']
DIFF_DIRECTORY = os.path.join(GLOBAL_CHANGED_FILES_DIRECTORY, f'diff_{DATE}')
LOCKFILE = config['LOCKFILE']
SCAN_RESULTS_DIRECTORY = config['SCAN_RESULTS_DIRECTORY']
LOG_DIRECTORY = config['LOG_DIRECTORY']
LOGFILE = os.path.join(LOG_DIRECTORY, f'log-scan-docker-diff-with-thunderstorm_{DATE}.log')
SAVE_FILE_HASHES = config['SAVE_FILE_HASHES']
HASH_FILE = config['HASH_FILE']
ONLY_SCAN_NEW_FILES = config['ONLY_SCAN_NEW_FILES']
MAX_FILE_SIZE = config['MAX_FILE_SIZE'] # in bytes, 0 means no limit
SCAN_FILES_SEPARATELY = config['SCAN_FILES_SEPARATELY']
FILE_TYPE_CONFIG_FILE = config['FILE_TYPE_CONFIG_FILE']
CACHE_FILE = config['CACHE_FILE']
FILE_TYPES = {}
FILTER_OUT_FILE_TYPES = []
DIFF = []
ITEMS_TO_SCAN = []
SCAN_RESULTS = []

# logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
# log file handler
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
handler = logging.FileHandler(LOGFILE)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

def read_arguments():
    """ Reads command-line arguments to override default configuration settings.
    """
    global THUNDERSTORM_HOST, THUNDERSTORM_PORT,GLOBAL_CHANGED_FILES_DIRECTORY,SCAN_RESULTS_DIRECTORY,LOGFILE,SAVE_FILE_HASHES,ONLY_SCAN_NEW_FILES,MAX_FILE_SIZE,SCAN_FILES_SEPARATELY,FILTER_OUT_FILE_TYPES
    parser = argparse.ArgumentParser(description='Scan Docker container diffs with Thunderstorm.')
    parser.add_argument('-t', '--thunderstorm-host', type=str, default=THUNDERSTORM_HOST, help='Thunderstorm host address')
    parser.add_argument('-p', '--thunderstorm-port', type=int, default=THUNDERSTORM_PORT, help='Thunderstorm port number')
    parser.add_argument('-d', '--changed-files-directory', type=str, default=GLOBAL_CHANGED_FILES_DIRECTORY, help='Directory to store changed files')
    parser.add_argument('-r', '--scan-results-directory', type=str, default=SCAN_RESULTS_DIRECTORY, help='Directory to store scan results')
    parser.add_argument('--log-level', type=str, default='INFO', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
    parser.add_argument('-l', '--log-file', type=str, default=LOGFILE, help='Log file path')
    parser.add_argument('-a', '--save-file-hashes', action='store_true', default=SAVE_FILE_HASHES, help='Save scanned file hashes to avoid re-scanning')
    parser.add_argument('-n', '--only-scan-new-files', action='store_true', default=ONLY_SCAN_NEW_FILES, help='Only scan files that have not been scanned before')
    parser.add_argument('--max-file-size', type=int, default=MAX_FILE_SIZE, help='Maximum file size to scan in bytes (0 means no limit)')
    parser.add_argument('-s', '--scan-files-separately', action='store_true', default=SCAN_FILES_SEPARATELY, help='Scan files separately instead of in batch')
    parser.add_argument('-f', '--filter-out-file-types', type=str, action='append', default=FILTER_OUT_FILE_TYPES, help='File types to filter out from scanning (e.g., EXE, DLL), can be specified multiple times to filter multiple types')
    args = parser.parse_args()
    if args.thunderstorm_host:
        THUNDERSTORM_HOST = args.thunderstorm_host
    if args.thunderstorm_port:
        THUNDERSTORM_PORT = args.thunderstorm_port
    if args.changed_files_directory:
        GLOBAL_CHANGED_FILES_DIRECTORY = args.changed_files_directory
    if args.scan_results_directory:
        SCAN_RESULTS_DIRECTORY = args.scan_results_directory
    if args.log_file:
        LOGFILE = args.log_file
    if args.log_level:
        logger.setLevel(getattr(logging, args.log_level.upper(), logging.INFO))
    if args.save_file_hashes is not None:
        SAVE_FILE_HASHES = args.save_file_hashes
    if args.only_scan_new_files is not None:
        ONLY_SCAN_NEW_FILES = args.only_scan_new_files
    if args.max_file_size is not None:
        MAX_FILE_SIZE = args.max_file_size
    if args.scan_files_separately is not None:
        SCAN_FILES_SEPARATELY = args.scan_files_separately
    if args.filter_out_file_types:
        FILTER_OUT_FILE_TYPES = args.filter_out_file_types
    logger.info(f'Configuration - Thunderstorm Host: {THUNDERSTORM_HOST}, Port: {THUNDERSTORM_PORT}, Changed Files Directory: {GLOBAL_CHANGED_FILES_DIRECTORY}, Scan Results Directory: {SCAN_RESULTS_DIRECTORY}, Log File: {LOGFILE}, Save File Hashes: {SAVE_FILE_HASHES}, Only Scan New Files: {ONLY_SCAN_NEW_FILES}, Max File Size: {MAX_FILE_SIZE} bytes, Scan Files Separately: {SCAN_FILES_SEPARATELY}, Filter Out File Types: {FILTER_OUT_FILE_TYPES}')

def is_instance_running(lockfile=LOCKFILE) -> bool:
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
    except IOError:
        logger.error('Another instance is running. Exiting.')
        sys.exit(1)

def get_listing_of_running_containers() -> list:
    """ Creates a list of running Docker containers.

    Returns:
        list: List of running Docker containers.

    Raises:
        Exception: If unable to connect to Docker.
    """
    try:
        result = subprocess.run(['docker', 'ps', '--format', '{{json .}}'],capture_output=True, text=True)
        list_of_containers = [json.loads(line) for line in result.stdout.splitlines()]
    except Exception as e:
        logger.error(f'Failed to connect to Docker. Error: {e}')
    logger.info(f'Found {len(list_of_containers)} running containers.')
    return list_of_containers

def process_containers(running_containers) -> None:
    """ Processes each running Docker container to find changed files.

    Args:
        running_containers (list): List of running Docker containers.
    """
    for container in running_containers:
        process_container(container=container)

def process_container(container) -> None:
    """ Processes a single Docker container to find changed files.
        Initializes list of changed files (DIFF) detected in the container. Each change is represented as a dictionary including container ID, change type, file path, and timestamp.

    Args:
        container (dict): A dictionary representing a Docker container.
    """
    global DIFF
    logger.info(f'Processing container {container["ID"]}, image: {container["Image"]}.')
    result = subprocess.run(['docker', 'diff', container['ID']],capture_output=True,text=True)
    changes = result.stdout.strip().splitlines()
    if not changes:
        logger.info(f'No changes detected in container {container["ID"]}.')
        return
    for change in changes:
        change_type = change[0]
        file_path = change[2:]
        logger.info(f'Found file: container ID: {container["ID"]}, file path: {file_path}, change type: {change_type}')
        DIFF.append({'container_id': container['ID'], 'change_type': change_type, 'file_path': file_path, 'timestamp': DATE})

def filter_out_deleted_items_and_non_files() -> None:
    """ Filters out deleted items and non-file items from the DIFF list.
        Initializes the ITEMS_TO_SCAN list with items that are either modified or added files.
    """
    global DIFF
    global ITEMS_TO_SCAN
    for item in DIFF:
        if item['change_type'] == 'D':
            logger.info(f'Filtering out deleted item {item["file_path"]} in container {item["container_id"]}.')
            continue
        is_file = subprocess.run(['docker', 'exec', item['container_id'], 'test', '-f', item['file_path']],capture_output=True).returncode == 0
        if not is_file:
            logger.info(f'Filtering out non-file item {item["file_path"]} in container {item["container_id"]}.')
            continue
        ITEMS_TO_SCAN.append(item)
    logger.info(f'Found {len(ITEMS_TO_SCAN)} changes of type "modified" or "added" across all containers.')

def copy_files_from_container() -> None:
    """ Copies each file from Docker containers to the local directory.
    """
    logger.info('Copying files from containers to local directory.')
    for item in ITEMS_TO_SCAN:
        copy_file_from_container(item)

def copy_file_from_container(item) -> None:
    """ Copies a single file from a Docker container to the local directory.

    Args:
        item (dict): A dictionary representing a file change, including container ID, file path, change type, and timestamp.

    Raises:
        Exception: If unable to copy the file from the container.
    """
    file = f'{item["container_id"]}:{item["file_path"]}'
    if not os.path.exists(GLOBAL_CHANGED_FILES_DIRECTORY):
        os.makedirs(GLOBAL_CHANGED_FILES_DIRECTORY)
    if not os.path.exists(DIFF_DIRECTORY):
        os.makedirs(DIFF_DIRECTORY)
    try:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        copy = subprocess.run(['docker', 'cp', file, file_path_in_diff_directory], capture_output=True)
        if copy.returncode == 0:
            logger.info(f'Copied file {item["file_path"]} from container {item["container_id"]} successfully.')
        else:
            logger.error(f'Failed to copy file {item["file_path"]} from container {item["container_id"]}. Return code: {copy.returncode}')
    except Exception as e:
        try:
            result = subprocess.run(['docker', 'inspect', '-f', '{{.State.Running}}', item['container_id']],capture_output=True,text=True)
            if result.returncode != 0 or result.stdout.strip().lower() != 'true':
                logger.error(f'Failed to copy file {item["file_path"]} from container because container {item["container_id"]} is not running anymore.')
            else:
                logger.error(f'Failed to copy file {item["file_path"]} from container {item["container_id"]}. Error: {e}')
        except Exception as e2:
            logger.error(f'Failed to copy file {item["file_path"]} from container {item["container_id"]}. Error: {e}')

def add_cached_files() -> None:
    """ Adds cached changed files from previous scans (stored in CACHE_FILE) to the list of changed files to scan.
        Updated list ITEMS_TO_SCAN (changed files) to scan after including cached changed files.
    """
    global ITEMS_TO_SCAN
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cached_items = json.load(f)
        ITEMS_TO_SCAN.extend(cached_items)
        logger.info(f'Added {len(cached_items)} cached files to the list of files to scan.')
    else:
        logger.info('No cache file found. Skipping adding cached files.')

def filter_out_duplicates() -> None:
    """ Filters out duplicate files from the list of changed files to scan based on file content hash.
        Updated list ITEMS_TO_SCAN (changed files) to scan after removing duplicates.
    """
    global ITEMS_TO_SCAN
    unique_items = {}
    for item in ITEMS_TO_SCAN:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        file_hash = hashlib.sha256(open(file_path_in_diff_directory, 'rb').read()).hexdigest()
        if file_hash not in unique_items:
            unique_items[file_hash] = item
            logger.debug(f'Adding unique file {item["file_path"]} with hash {file_hash} from container {item["container_id"]}.')
        else:
            logger.info(f'Filtering out duplicate file {item["file_path"]} from container {item["container_id"]}.')
    ITEMS_TO_SCAN = []
    for file_hash, item in unique_items.items():
        if 'sha256' not in item:
            item['sha256'] = file_hash
        ITEMS_TO_SCAN.append(item)
    logger.debug(f'Updated list of filtered files by removing duplicates: {ITEMS_TO_SCAN}')
    logger.info(f'Found {len(ITEMS_TO_SCAN)} unique files after removing duplicates.')

def process_optional_filtering() -> None:
    """ Processes optional filtering of files based on configuration settings such as scanning only new files, maximum file size, and specific file types to filter out.
        Updated list ITEMS_TO_SCAN (changed files) to scan after applying optional filtering.
    """
    global ITEMS_TO_SCAN
    if ONLY_SCAN_NEW_FILES and os.path.exists(HASH_FILE):
        ITEMS_TO_SCAN = filter_out_known_files()
    if MAX_FILE_SIZE > 0:
        ITEMS_TO_SCAN = filter_out_big_files()
    if len(FILTER_OUT_FILE_TYPES) > 0:
        ITEMS_TO_SCAN = filter_out_files_with_specific_types()

def filter_out_known_files() -> None:
    """ Filters out files that have already been scanned in previous runs of the container-collector based on saved file hashes.
        Updated list ITEMS_TO_SCAN (changed files) to scan after removing files that have been scanned in previous runs (based on saved file hashes in HASH_FILE).
    """
    global ITEMS_TO_SCAN
    with open(HASH_FILE, 'r') as f:
        saved_file_hashes = json.load(f)
    already_scanned_hashes = set()
    for date, hashes in saved_file_hashes.items():
        already_scanned_hashes.update(hashes)
    ITEMS_TO_SCAN = [item for item in ITEMS_TO_SCAN if item['sha256'] not in already_scanned_hashes]
    logger.info(f'Found {len(ITEMS_TO_SCAN)} files to scan after filtering already scanned files.')

def filter_out_big_files() -> None:
    """ Filters out files that exceed the maximum file size limit.
        Updated list ITEMS_TO_SCAN (changed files) to scan after removing files that exceed the maximum file size limit.
    """
    global ITEMS_TO_SCAN
    filtered_items = []
    for item in ITEMS_TO_SCAN:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        file_size = os.path.getsize(file_path_in_diff_directory)
        if file_size <= MAX_FILE_SIZE:
            filtered_items.append(item)
        else:
            logger.info(f'Filtering out file {item["file_path"]} from container {item["container_id"]} due to size {file_size} bytes exceeding limit of {MAX_FILE_SIZE} bytes.')
    ITEMS_TO_SCAN = filtered_items
    logger.info(f'Found {len(ITEMS_TO_SCAN)} files to scan after filtering out files bigger than {MAX_FILE_SIZE} bytes.')

def filter_out_files_with_specific_types() -> None:
    """ Filters out files based on specific file types defined in the configuration.
        Updated list ITEMS_TO_SCAN (changed files) to scan after removing files of specific types.
    """
    global ITEMS_TO_SCAN
    filtered_items = []
    for item in ITEMS_TO_SCAN:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        with open(file_path_in_diff_directory, 'rb') as f:
            file_header = f.read(20).hex().upper()
        file_type_found = False
        for file_type, headers in FILE_TYPES.items():
            for header in headers:
                if file_header.startswith(header):
                    if file_type in FILTER_OUT_FILE_TYPES:
                        logger.info(f'Filtering out file {item["file_path"]} from container {item["container_id"]} due to file type {file_type}.')
                        file_type_found = True
                        break
            if file_type_found:
                break
        if not file_type_found:
            filtered_items.append(item)
    ITEMS_TO_SCAN = filtered_items
    logger.info(f'Found {len(ITEMS_TO_SCAN)} files to scan after filtering out specific file types.')

def scan_files():
    """ Scans files using Thunderstorm API, either separately or in batch mode based on configuration.
        Saves file hashes if configured to do so, and caches files that could not be scanned for later processing.
    """
    global SCAN_RESULTS, ITEMS_TO_SCAN
    if SCAN_FILES_SEPARATELY:
        file_hashes, files_to_cache = scan_files_separately()
    else:
        file_hashes, files_to_cache = scan_files_in_batch()
    if SAVE_FILE_HASHES:
        save_file_hashes(file_hashes)
    if files_to_cache:
        with open(CACHE_FILE, 'w') as f:
            json.dump(files_to_cache, f, indent=4)
        logger.info(f'Saved {len(files_to_cache)} files to cache for later scanning in {CACHE_FILE}.')

def scan_files_separately() -> tuple[list, list]:
    """ Scans files separately using Thunderstorm API.

    Returns:
        tuple: A tuple containing a list of scanned file hashes and a list of files to cache (files are not scanned due to errors) for later scanning.

    Raises:
        Exception: If unable to scan a file.
    """
    global SCAN_RESULTS
    file_hashes = []
    files_to_cache = []
    for item in ITEMS_TO_SCAN:
        THUNDERSTORM = ThunderstormAPI(host=THUNDERSTORM_HOST, port=THUNDERSTORM_PORT, source=item['container_id'])
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        try:
            if not check_connection():
                raise ConnectionError(f'Cannot connect to Thunderstorm instance. Check if it is running properly. Host: {THUNDERSTORM_HOST}, Port: {THUNDERSTORM_PORT}')
            scan_results = THUNDERSTORM.scan(file_path_in_diff_directory)
            SCAN_RESULTS.append({'hash': item['sha256'],'timestamp_file': item['timestamp'], 'timestamp_scan': DATE, 'scan_results': scan_results})
            file_hashes.append(item['sha256'])
            logger.info(f'Scanned file {file_path_in_diff_directory}.')
        except Exception as e:
            logger.error(f'Error scanning file {file_path_in_diff_directory}. Error: {e}')
            logger.info(f'Adding file {item["sha256"]} to cache to scan it later.')
            files_to_cache.append(item)
    return file_hashes, files_to_cache

def scan_files_in_batch() -> tuple[list, list]:
    """ Scans files in batch using Thunderstorm API.

    Returns:
        tuple: A tuple containing a list of scanned file hashes and a list of files to cache (files are not scanned due to errors) for later scanning.

    Raises:
        Exception: If unable to scan files in batch.
    """
    global SCAN_RESULTS
    THUNDERSTORM = ThunderstormAPI(host=THUNDERSTORM_HOST, port=THUNDERSTORM_PORT)
    file_hashes = []
    files_to_cache = []
    files_to_scan = []
    for item in ITEMS_TO_SCAN:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item['container_id'], item['file_path'])
        files_to_scan.append(file_path_in_diff_directory)
        file_hashes.append(item['sha256'])
    try:
        if not check_connection():
            raise ConnectionError(f'Cannot connect to Thunderstorm instance. Check if it is running properly. Host: {THUNDERSTORM_HOST}, Port: {THUNDERSTORM_PORT}')
        scan_results = THUNDERSTORM.scan_multi(files_to_scan)
        SCAN_RESULTS.append({'date': DATE, 'scan_results': [x for x in scan_results if len(x) > 0]})
        logger.info(f'Scanned {len(files_to_scan)} files in batch.')
        logger.info(f'Scan results not mapped to individual files when scanning in batch mode.')
    except Exception as e:
        logger.error(f'Error scanning files in batch. Error: {e}')
        for item in ITEMS_TO_SCAN:
            logger.info(f'Adding file {item["sha256"]} to cache to scan it later.')
            files_to_cache.append(item)
    return file_hashes, files_to_cache

def check_connection(host=THUNDERSTORM_HOST,port=THUNDERSTORM_PORT,timeout=2) -> bool:
    """ Checks if a connection to the Thunderstorm instance can be established.

    Args:
        host (str): Thunderstorm host address.
        port (int): Thunderstorm port number.
        timeout (int): Connection timeout in seconds.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    sock = socket.socket(socket.AF_INET,socket.SOCK_STREAM) 
    sock.settimeout(timeout)
    try:
       sock.connect((host,port))
    except:
       return False
    else:
       sock.close()
       return True

def save_file_hashes(file_hashes) -> None:
    """ Saves scanned file hashes to a JSON file.

    Args:
        file_hashes (list): List of scanned file hashes.
    """
    saved_file_hashes = {}
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, 'r') as f:
            saved_file_hashes = json.load(f)
    saved_file_hashes[DATE] = file_hashes
    with open(HASH_FILE, 'w') as f:
        json.dump(saved_file_hashes, f, indent=4)
    if len(file_hashes) > 0:
        logger.info(f'Saved scanned file hashes to {HASH_FILE}.')
    else:
        logger.info('No new file hashes to save.')

def get_file_path_in_diff_directory(container_id, file_path) -> str:
    """ Generates the file path in the diff directory for a given container ID and file path.
    
    Args:
        container_id (str): The ID of the container.
        file_path (str): The original file path.

    Returns:
        str: The generated file path in the diff directory.
    """
    if not os.path.exists(DIFF_DIRECTORY):
        os.makedirs(DIFF_DIRECTORY)
    return os.path.join(DIFF_DIRECTORY, f'{container_id}{file_path.replace("/", "_")}')

def read_file_type_config() -> None:
    """ Reads the file type configuration from a file and updates the FILE_TYPES dictionary.
    """
    global FILE_TYPES
    if os.path.exists(FILE_TYPE_CONFIG_FILE):
        with open(FILE_TYPE_CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    splitted_line = line.split(';')
                    file_type = splitted_line[1]
                    hex = splitted_line[0].replace(' ', '').upper()
                    if file_type.lower() in [ft.lower() for ft in FILE_TYPES]:
                        FILE_TYPES[file_type].append(hex)
                    else:
                        FILE_TYPES[file_type] = [hex]
        logger.info(f'Loaded file type configuration from {FILE_TYPE_CONFIG_FILE}.')
    else:
        logger.warning(f'File type configuration file {FILE_TYPE_CONFIG_FILE} not found.')

read_arguments()
read_file_type_config()
if not is_instance_running():
    running_containers = get_listing_of_running_containers()
    if running_containers:
        logger.info('No running containers found. Exiting.')
    process_containers(running_containers)
    filter_out_deleted_items_and_non_files()
    copy_files_from_container()
    add_cached_files()
    filter_out_duplicates()
    process_optional_filtering()
    scan_files()
    if not os.path.exists(SCAN_RESULTS_DIRECTORY):
        os.makedirs(SCAN_RESULTS_DIRECTORY)
    with open(os.path.join(SCAN_RESULTS_DIRECTORY, f'scan_results_{DATE}.json'), 'w') as f:
        json.dump(SCAN_RESULTS, f, indent=4)
    logger.info('Scan results exported successfully.')
else:
    sys.exit(1)

