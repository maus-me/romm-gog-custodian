# Game library cleanup module
import logging
import os
import re

# Load modules
from src.modules.config_parse import (
    GAME_PATH, EXTRAS_PATTERNS,
    REMOVE_EMPTY_DIRS, REMOVE_TEXT_FILES,
    REMOVE_EXTRAS
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
    if REMOVE_EXTRAS or REMOVE_TEXT_FILES:
        remove_extras()
    else:
        logger.info("Skipping extras cleanup...")

    if REMOVE_EMPTY_DIRS:
        remove_empty()
    else:
        logger.info("Skipping empty directory cleanup...")


def remove_extras():
    """
    Delete unnecessary files like soundtracks, artbooks, and specific text files.
    """
    logger.info("Removing unnecessary files...")

    archive_exts = ('.zip', '.rar', '.7z', '.tar', '.gz')

    # Create a regex pattern to match extras as whole words or separated by non-alphanumeric characters
    # e.g., "ost" matches "Game OST.zip", "Game_ost.zip", but not "Roster.zip"
    patterns = [re.escape(p.lower()) for p in EXTRAS_PATTERNS if p.strip()]

    extras_regex = None
    if patterns:
        extras_regex = re.compile(rf"(?:^|[^a-z0-9])({'|'.join(patterns)})(?:$|[^a-z0-9])")

    # Walk through the GAME_PATH recursively
    for root, dirs, files in os.walk(GAME_PATH):
        # Skip the root directory
        if root == GAME_PATH:
            continue

        for file_name in files:
            file_name_lower = file_name.lower()
            file_path = os.path.join(root, file_name)
            should_remove = False
            reason = ""

            # Text file cleanup
            if REMOVE_TEXT_FILES and file_name_lower.endswith('gog-games.to.txt'):
                should_remove = True
                reason = "txt"
            # Archive/Extras cleanup
            elif REMOVE_EXTRAS and extras_regex and file_name_lower.endswith(archive_exts):
                if extras_regex.search(file_name_lower):
                    should_remove = True
                    reason = "extras"

            if should_remove:
                try:
                    size = os.path.getsize(file_path)
                    os.remove(file_path)
                    logger.info(f"Removed {reason}: {trim_path(file_path)} | Size: {format_size(size)}")
                except Exception as e:
                    logger.error(f"Error removing {file_path}: {e}")
            else:
                try:
                    size = os.path.getsize(file_path)
                    logger.debug(f"Skipped file: {trim_path(file_path)} | Size: {format_size(size)}")
                except Exception:
                    pass


def remove_empty():
    """
    Remove empty directories in the game library root path.
    """
    logger.info("Removing empty directories...")

    # Walk bottom-up to remove nested empty directories first
    for root, dirs, files in os.walk(GAME_PATH, topdown=False):
        # Skip the root directory itself
        if root == GAME_PATH:
            continue

        try:
            # Check if the directory is empty
            with os.scandir(root) as entries:
                if not any(entries):
                    os.rmdir(root)
                    logger.info(f"Removed empty directory: {root}")
        except OSError as e:
            logger.error(f"Error removing empty directory {root}: {e}")


def trim_path(path):
    """
    Trim the path to only the last part of the path and its parent directory.
    Example: /data/library/Game/file.txt -> Game/file.txt
    """
    head, tail = os.path.split(path)
    parent = os.path.basename(head)
    return os.path.join(parent, tail) if parent else tail
