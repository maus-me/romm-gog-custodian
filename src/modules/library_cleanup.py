# Game library cleanup module
import logging
import os

# Load modules
from src.modules.config_parse import (
    GAME_PATH, EXTRAS_PATTERNS,
    REMOVE_EMPTY_DIRS, REMOVE_TEXT_FILES
)
from src.modules.helpers import format_size

logger = logging.getLogger(__name__)


def run():
    """
    Perform post-library cleanup tasks such as renaming folders and removing unnecessary files.
    :return:
    """
    logger.info("Post-library cleanup...")

    # Remove unnecessary files based on configuration
    if REMOVE_EMPTY_DIRS:
        remove_empty()
    else:
        logger.info("Skipping empty directory removal.")


def remove_extras():
    """
    Delete the .zip files that are not needed such as,
    _soundtrack_, OST, FLAC, WAV, MP3, etc.
    :return:
    """
    logger.info("Removing unnecessary files...")

    # Use patterns from configuration
    zip_strings = EXTRAS_PATTERNS

    for folder in os.listdir(GAME_PATH):
        folder_path = os.path.join(GAME_PATH, folder)
        if os.path.isdir(folder_path):
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)

                # calculate filesize
                size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0

                # Text file cleanup (if enabled in config)
                if REMOVE_TEXT_FILES and file.endswith('gog-games.to.txt'):
                    try:
                        os.remove(file_path)
                        logger.info(f'Removed txt: {trim_path(file_path)} | Size: {format_size(size)}')
                    except Exception as e:
                        logger.error(f'Error removing file {file_path}: {e}')

                # Zip file cleanup
                if any(zip_string.lower() in file.lower() for zip_string in zip_strings) and file.endswith('.zip'):
                    try:
                        os.remove(file_path)
                        # log which file was removed and the size of the file
                        logger.info(f'Removed extras: {trim_path(file_path)} | Size: {format_size(size)}')
                    except Exception as e:
                        logger.error(f'Error removing file {file_path}: {e}')
                else:
                    logger.debug(f'Skipped file: {trim_path(file_path)} | Size: {format_size(size)}')


def remove_empty():
    """
    Remove empty directories in the game library root path.
    :return:
    """
    logger.info("Removing empty directories...")

    for folder in os.listdir(GAME_PATH):
        folder_path = os.path.join(GAME_PATH, folder)
        if os.path.isdir(folder_path):
            # Check if the directory is empty
            if not os.listdir(folder_path):
                try:
                    os.rmdir(folder_path)
                    logger.info(f'Removed empty directory: {folder_path}')
                except OSError as e:
                    logger.error(f'Error removing empty directory {folder_path}: {e}')

def trim_path(path):
    """
    Trim the path to only the last part of the path and parent directory.
    :param path: The path to trim.
    :return: The trimmed path.
    """

    # Split the path into parts
    parts = path.split(os.sep)
    # Return the last part and the parent directory
    # TODO: Review this code, it might not work as expected in all cases
    return os.path.join(parts[-2], parts[-1]) if len(parts) > 1 else parts[-1]
