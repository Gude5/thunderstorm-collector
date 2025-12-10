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

# Get current date
DATE = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Load configuration from YAML file
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

THUNDERSTORM_HOST = config["THUNDERSTORM_HOST"]
THUNDERSTORM_PORT = config["THUNDERSTORM_PORT"]
GLOBAL_CHANGED_FILES_DIRECTORY = config["GLOBAL_CHANGED_FILES_DIRECTORY"]
DIFF_DIRECTORY = os.path.join(GLOBAL_CHANGED_FILES_DIRECTORY, f"diff_{DATE}")
LOCKFILE = config["LOCKFILE"]
SCAN_RESULTS_DIRECTORY = config["SCAN_RESULTS_DIRECTORY"]
LOG_DIRECTORY = config["LOG_DIRECTORY"]
LOGFILE = os.path.join(LOG_DIRECTORY, f"log-scan-docker-diff-with-thunderstorm_{DATE}.log")
SAVE_FILE_HASHES = config["SAVE_FILE_HASHES"]
HASH_FILE = config["HASH_FILE"]
ONLY_SCAN_NEW_FILES = config["ONLY_SCAN_NEW_FILES"]
MAX_FILE_SIZE = config["MAX_FILE_SIZE"] # in bytes, 0 means no limit
SCAN_FILES_SEPARATELY = config["SCAN_FILES_SEPARATELY"]
FILE_TYPE_CONFIG_FILE = "file-type-signatures.cfg"
FILE_TYPES = {}
FILTER_OUT_FILE_TYPES = []
FULL_DIFF = []
FILTERED_DIFF = []
SCAN_RESULTS = []

# logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
# log file handler
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)
handler = logging.FileHandler(LOGFILE)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

def read_arguments():
    global THUNDERSTORM_HOST, THUNDERSTORM_PORT,GLOBAL_CHANGED_FILES_DIRECTORY,SCAN_RESULTS_DIRECTORY,LOGFILE,SAVE_FILE_HASHES,ONLY_SCAN_NEW_FILES,MAX_FILE_SIZE,SCAN_FILES_SEPARATELY,FILTER_OUT_FILE_TYPES
    parser = argparse.ArgumentParser(description="Scan Docker container diffs with Thunderstorm.")
    parser.add_argument("-t", "--thunderstorm-host", type=str, default=THUNDERSTORM_HOST, help="Thunderstorm host address")
    parser.add_argument("-p", "--thunderstorm-port", type=int, default=THUNDERSTORM_PORT, help="Thunderstorm port number")
    parser.add_argument("-d", "--changed-files-directory", type=str, default=GLOBAL_CHANGED_FILES_DIRECTORY, help="Directory to store changed files")
    parser.add_argument("-r", "--scan-results-directory", type=str, default=SCAN_RESULTS_DIRECTORY, help="Directory to store scan results")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    parser.add_argument("-l", "--log-file", type=str, default=LOGFILE, help="Log file path")
    parser.add_argument("-a", "--save-file-hashes", action="store_true", default=SAVE_FILE_HASHES, help="Save scanned file hashes to avoid re-scanning")
    parser.add_argument("-n", "--only-scan-new-files", action="store_true", default=ONLY_SCAN_NEW_FILES, help="Only scan files that have not been scanned before")
    parser.add_argument("--max-file-size", type=int, default=MAX_FILE_SIZE, help="Maximum file size to scan in bytes (0 means no limit)")
    parser.add_argument("-s", "--scan-files-separately", action="store_true", default=SCAN_FILES_SEPARATELY, help="Scan files separately instead of in batch")
    parser.add_argument("-f", "--filter-out-file-types", type=str, action="append", default=FILTER_OUT_FILE_TYPES, help="File types to filter out from scanning (e.g., EXE, DLL), can be specified multiple times to filter multiple types")
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
    logger.info(f"Configuration - Thunderstorm Host: {THUNDERSTORM_HOST}, Port: {THUNDERSTORM_PORT}, Changed Files Directory: {GLOBAL_CHANGED_FILES_DIRECTORY}, Scan Results Directory: {SCAN_RESULTS_DIRECTORY}, Log File: {LOGFILE}, Save File Hashes: {SAVE_FILE_HASHES}, Only Scan New Files: {ONLY_SCAN_NEW_FILES}, Max File Size: {MAX_FILE_SIZE} bytes, Scan Files Separately: {SCAN_FILES_SEPARATELY}, Filter Out File Types: {FILTER_OUT_FILE_TYPES}")

def is_instance_running(lockfile=LOCKFILE):
    fp = open(lockfile, "w")
    try:
        fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return False
    except IOError:
        logger.error("Another instance is running. Exiting.")
        sys.exit(1)

def get_listing_of_running_containers():
    try:
        result = subprocess.run(["docker", "ps", "--format", "{{json .}}"],capture_output=True, text=True)
        list_of_containers = [json.loads(line) for line in result.stdout.splitlines()]
    except Exception as e:
        logger.error(f"Failed to connect to Docker. Error: {e}")
    logger.info(f"Found {len(list_of_containers)} running containers.")
    return list_of_containers

def process_containers(running_containers):
    for container in running_containers:
        process_container(container=container)

def process_container(container):
    global FULL_DIFF
    logger.info(f"Processing container {container["ID"]}, image: {container["Image"]}.")
    result = subprocess.run(["docker", "diff", container["ID"]],capture_output=True,text=True)
    changes = result.stdout.strip().splitlines()
    if not changes:
        logger.info(f"No changes detected in container {container["ID"]}.")
        return
    for change in changes:
        change_type = change[0]
        file_path = change[2:]
        logger.info(f"Found file: container ID: {container["ID"]}, file path: {file_path}, change type: {change_type}")
        FULL_DIFF.append({"container_id": container["ID"], "change_type": change_type, "file_path": file_path})

def filter_out_deleted_items_and_non_files():
    global FULL_DIFF
    global FILTERED_DIFF
    for item in FULL_DIFF:
        if item["change_type"] == "D":
            logger.info(f"Filtering out deleted item {item["file_path"]} in container {item["container_id"]}.")
            continue
        is_file = subprocess.run(["docker", "exec", item["container_id"], "test", "-f", item["file_path"]],capture_output=True).returncode == 0
        if not is_file:
            logger.info(f"Filtering out non-file item {item["file_path"]} in container {item["container_id"]}.")
            continue
        FILTERED_DIFF.append(item)
    logger.info(f"Found {len(FILTERED_DIFF)} changes of type 'modified' or 'added' across all containers.")

def copy_files_from_container():
    logger.info("Copying files from containers to local directory.")
    for item in FILTERED_DIFF:
        copy_file_from_container(item)

def copy_file_from_container(item):
    file = f"{item["container_id"]}:{item["file_path"]}"
    if not os.path.exists(GLOBAL_CHANGED_FILES_DIRECTORY):
        os.makedirs(GLOBAL_CHANGED_FILES_DIRECTORY)
    if not os.path.exists(DIFF_DIRECTORY):
        os.makedirs(DIFF_DIRECTORY)
    try:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
        copy = subprocess.run(["docker", "cp", file, file_path_in_diff_directory], capture_output=True)
        if copy.returncode == 0:
            logger.info(f"Copied file {item["file_path"]} from container {item["container_id"]} successfully.")
        else:
            logger.error(f"Failed to copy file {item["file_path"]} from container {item["container_id"]}. Return code: {copy.returncode}")
    except Exception as e:
        try:
            result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", item["container_id"]],capture_output=True,text=True)
            if result.returncode != 0 or result.stdout.strip().lower() != "true":
                logger.error(f"Failed to copy file {item["file_path"]} from container because container {item["container_id"]} is not running anymore.")
            else:
                logger.error(f"Failed to copy file {item["file_path"]} from container {item["container_id"]}. Error: {e}")
        except Exception as e2:
            logger.error(f"Failed to copy file {item["file_path"]} from container {item["container_id"]}. Error: {e}")

def filter_out_duplicates():
    global FILTERED_DIFF
    unique_items = {}
    for item in FILTERED_DIFF:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
        file_hash = hashlib.sha256(open(file_path_in_diff_directory, "rb").read()).hexdigest()
        if file_hash not in unique_items:
            unique_items[file_hash] = item
            logger.debug(f"Adding unique file {item["file_path"]} with hash {file_hash} from container {item["container_id"]}.")
        else:
            logger.info(f"Filtering out duplicate file {item["file_path"]} from container {item["container_id"]}.")
    FILTERED_DIFF = []
    for file_hash, item in unique_items.items():
        item["sha256"] = file_hash
        FILTERED_DIFF.append(item)
    logger.debug(f"Updated list of filtered files by removing duplicates: {FILTERED_DIFF}")
    logger.info(f"Found {len(FILTERED_DIFF)} unique files after removing duplicates.")

def process_optional_filtering():
    global FILTERED_DIFF
    if ONLY_SCAN_NEW_FILES and os.path.exists(HASH_FILE):
        filter_out_known_files()
    if MAX_FILE_SIZE > 0:
        filter_out_big_files()
    if len(FILTER_OUT_FILE_TYPES) > 0:
        filter_out_files_with_specific_types()

def filter_out_known_files():
    global FILTERED_DIFF
    with open(HASH_FILE, "r") as f:
        saved_file_hashes = json.load(f)
    already_scanned_hashes = set()
    for date, hashes in saved_file_hashes.items():
        already_scanned_hashes.update(hashes)
    FILTERED_DIFF = [item for item in FILTERED_DIFF if item["sha256"] not in already_scanned_hashes]
    logger.info(f"Found {len(FILTERED_DIFF)} files to scan after filtering already scanned files.")

def filter_out_big_files():
    global FILTERED_DIFF
    filtered_items = []
    for item in FILTERED_DIFF:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
        file_size = os.path.getsize(file_path_in_diff_directory)
        if file_size <= MAX_FILE_SIZE:
            filtered_items.append(item)
        else:
            logger.info(f"Filtering out file {item["file_path"]} from container {item["container_id"]} due to size {file_size} bytes exceeding limit of {MAX_FILE_SIZE} bytes.")
    FILTERED_DIFF = filtered_items
    logger.info(f"Found {len(FILTERED_DIFF)} files to scan after filtering out files bigger than {MAX_FILE_SIZE} bytes.")

def filter_out_files_with_specific_types():
    global FILTERED_DIFF
    filtered_items = []
    for item in FILTERED_DIFF:
        file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
        with open(file_path_in_diff_directory, "rb") as f:
            file_header = f.read(20).hex().upper()
        file_type_found = False
        for file_type, headers in FILE_TYPES.items():
            for header in headers:
                if file_header.startswith(header):
                    if file_type in FILTER_OUT_FILE_TYPES:
                        logger.info(f"Filtering out file {item["file_path"]} from container {item["container_id"]} due to file type {file_type}.")
                        file_type_found = True
                        break
            if file_type_found:
                break
        if not file_type_found:
            filtered_items.append(item)
    FILTERED_DIFF = filtered_items
    logger.info(f"Found {len(FILTERED_DIFF)} files to scan after filtering out specific file types.")

def scan_files():
    global SCAN_RESULTS
    global FILTERED_DIFF
    file_hashes = []
    if SCAN_FILES_SEPARATELY:
        for item in FILTERED_DIFF:
            THUNDERSTORM = ThunderstormAPI(host=THUNDERSTORM_HOST, port=THUNDERSTORM_PORT, source=item["container_id"])
            file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
            try:
                scan_results = THUNDERSTORM.scan(file_path_in_diff_directory)
                SCAN_RESULTS.append({"hash": item["sha256"], "date": DATE, "scan_results": scan_results})
                file_hashes.append(item["sha256"])
                logger.info(f"Scanned file {file_path_in_diff_directory}.")
            except Exception as e:
                logger.error(f"Error scanning file {file_path_in_diff_directory}. Check if Thunderstorm is running properly. Error: {e}")
    else:
        THUNDERSTORM = ThunderstormAPI(host=THUNDERSTORM_HOST, port=THUNDERSTORM_PORT)
        files_to_scan = []
        for item in FILTERED_DIFF:
            file_path_in_diff_directory = get_file_path_in_diff_directory(item["container_id"], item["file_path"])
            files_to_scan.append(file_path_in_diff_directory)
            file_hashes.append(item["sha256"])
        try:
            scan_results = THUNDERSTORM.scan_multi(files_to_scan)
            SCAN_RESULTS.append({"date": DATE, "scan_results": [x for x in scan_results if len(x) > 0]})
            logger.info(f"Scanned {len(files_to_scan)} files in batch.")
            logger.info(f"Scan results not mapped to individual files when scanning in batch mode.")
        except Exception as e:
            logger.error(f"Error scanning files in batch. Check if Thunderstorm is running properly. Error: {e}")
    if SAVE_FILE_HASHES:
        save_file_hashes(file_hashes)

def save_file_hashes(file_hashes):
    saved_file_hashes = {}
    if os.path.exists(HASH_FILE):
        with open(HASH_FILE, "r") as f:
            saved_file_hashes = json.load(f)
    saved_file_hashes[DATE] = file_hashes
    with open(HASH_FILE, "w") as f:
        json.dump(saved_file_hashes, f, indent=4)
    if len(file_hashes) > 0:
        logger.info(f"Saved scanned file hashes to {HASH_FILE}.")
    else:
        logger.info("No new file hashes to save.")

def get_file_path_in_diff_directory(container_id, file_path):
    if not os.path.exists(DIFF_DIRECTORY):
        os.makedirs(DIFF_DIRECTORY)
    return os.path.join(DIFF_DIRECTORY, f"{container_id}{file_path.replace("/", "_")}")

def read_file_type_config():
    global FILE_TYPES
    if os.path.exists(FILE_TYPE_CONFIG_FILE):
        with open(FILE_TYPE_CONFIG_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    splitted_line = line.split(";")
                    file_type = splitted_line[1]
                    hex = splitted_line[0].replace(" ", "").upper()
                    if file_type.lower() in [ft.lower() for ft in FILE_TYPES]:
                        FILE_TYPES[file_type].append(hex)
                    else:
                        FILE_TYPES[file_type] = [hex]
        logger.info(f"Loaded file type configuration from {FILE_TYPE_CONFIG_FILE}.")
    else:
        logger.warning(f"File type configuration file {FILE_TYPE_CONFIG_FILE} not found.")

read_arguments()
read_file_type_config()
if not is_instance_running():
    running_containers = get_listing_of_running_containers()
    if not running_containers:
        logger.info("No running containers found. Exiting.")
        sys.exit(0)
    process_containers(running_containers)
    filter_out_deleted_items_and_non_files()
    copy_files_from_container()
    filter_out_duplicates()
    process_optional_filtering()
    scan_files()
    if not os.path.exists(SCAN_RESULTS_DIRECTORY):
        os.makedirs(SCAN_RESULTS_DIRECTORY)
    with open(os.path.join(SCAN_RESULTS_DIRECTORY, f"scan_diff_results_{DATE}.json"), "w") as f:
        json.dump(SCAN_RESULTS, f, indent=4)
    logger.info("Scan results exported successfully.")
else:
    sys.exit(1)

