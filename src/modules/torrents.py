"""
Torrent handling module for Game Library Manager Scripts.

This module provides functionality for:
- Connecting to qBittorrent via its API
- Monitoring torrents in a specified category
- Processing completed torrents by moving them to the game library
- Renaming game folders based on GOG metadata
- Deleting torrents from qBittorrent after processing

The module uses a configuration file to determine paths, connection details,
and other settings.
"""
import json
import logging
import os
import shutil
import time
from typing import Optional

import qbittorrentapi
from qbittorrentapi import Client

# Load modules with explicit imports
from src.modules import romm_library_cleanup, library_cleanup
from src.modules.config_parse import (
    GAME_PATH, conn_info, QBIT_CATEGORY,
    GOG_ALL_GAMES_FILE, GOG_ALL_GAMES_URL,
    MAX_TORRENTS_PER_RUN, DELETE_AFTER_PROCESSING, QBIT_ENABLE, ROMM_ENABLE, ROMM_SCAN_AFTER_IMPORT, REMOVE_EXTRAS,
    ROMM_SCAN_DANGEROUS_FILETYPES
)
from src.modules.helpers import fetch_json_data

logger = logging.getLogger(__name__)

# Number of retries for API calls
MAX_RETRIES = 3
# Delay between retries in seconds
RETRY_DELAY = 5


def get_qbittorrent_client() -> Client | bool:
    """
    Initialize and return a qBittorrent client.
    
    Returns:
        qbittorrentapi.Client: Initialized qBittorrent client
        
    Raises:
        qbittorrentapi.LoginFailed: If authentication fails
    """
    try:
        client = qbittorrentapi.Client(**conn_info)
        client.auth_log_in()
        return client
    except qbittorrentapi.APIConnectionError as e:
        logger.error(f"Failed to connect to qBittorrent: {e}")
        return False


def qbit_preflight() -> bool:
    """
    Test Authentication with qBittorrent and log the app version and web API version.
    
    Returns:
        bool: True if authentication was successful, False otherwise
    """
    try:
        client = get_qbittorrent_client()

        if client:
            logger.info(f"qBittorrent App Version: {client.app.version}")
            logger.info(f"qBittorrent Web API: {client.app.web_api_version}")
            return True
        else:
            return False

    except qbittorrentapi.LoginFailed as e:
        logger.error(f"qBittorrent Login failed: {e}")
        return False


def torrent_manager():
    """
    Process completed torrents in the specified category.
    
    This function:
    1. Retrieves all completed torrents in the specified category
    2. Checks if they have finished seeding
    3. Renames and moves them to the game library
    4. Optionally deletes the torrent from qBittorrent based on configuration
    
    Returns:
        None
    """
    try:

        client = get_qbittorrent_client()

        # Get all completed torrents in the category
        completed_torrents = client.torrents_info(category=QBIT_CATEGORY, limit=None, status_filter='completed')

        # Apply limit if configured
        if MAX_TORRENTS_PER_RUN > 0:
            logger.info(
                f"Limiting to {MAX_TORRENTS_PER_RUN} torrents per run (from {len(completed_torrents)} available)")
            completed_torrents = completed_torrents[:MAX_TORRENTS_PER_RUN]
        else:
            logger.info(f"Processing all {len(completed_torrents)} available torrents")

        # Filter for torrents in the specific category that are done seeding.
        replaced_any = False
        new_any = False

        for torrent in completed_torrents:
            # Validate the torrent state is "Stopped".  This means that the torrent has finished downloading AND seeding.
            if torrent.state == 'stoppedUP':
                # Log which torrents are in the category.  Includes the name, hash, and path.
                logger.info(f'Torrent: {torrent.name} | Hash: {torrent.hash} | Path: {torrent.content_path}')

                source = torrent.content_path
                name = torrent.name
                # Create new folder name based on the torrent name
                new_name = new_folder(name)

                # Skip if new_folder returned None (error occurred)
                if new_name is None:
                    logger.warning(f"Skipping torrent {name} due to error in new_folder()")
                    continue

                # Copy and Delete to the game library root path
                destination = os.path.join(GAME_PATH, new_name)

                success, replaced, new = move_torrent_folder(source, destination)
                if success:
                    if replaced:
                        replaced_any = True
                    if new:
                        new_any = True
                    # Only delete torrent if configured to do so
                    if DELETE_AFTER_PROCESSING:
                        delete_torrent(torrent.hash)
                    else:
                        logger.info(f"Keeping torrent {name} (delete_after_processing is disabled)")

        # If any folder was replaced and ROMM integration is enabled, trigger a file changes scan
        if ROMM_ENABLE and ROMM_SCAN_AFTER_IMPORT:
            if replaced_any or new_any:
                if REMOVE_EXTRAS:
                    library_cleanup.remove_extras()
                else:
                    logger.info("Skipping extras removal.")
                if ROMM_SCAN_DANGEROUS_FILETYPES:
                    romm_library_cleanup.find_dangerous_filetypes()
            # Fix for issue #1
            if new_any:
                logger.info("Triggering ROMM scan due to new folders being created")
                romm_library_cleanup.scan_after_import()
            if replaced_any:
                logger.info("Triggering ROMM file hash scan due to replacing files within existing folders")
                romm_library_cleanup.scan_file_changes()
    except qbittorrentapi.LoginFailed as e:
        logger.error(f"qBittorrent login failed: {e}")
    except qbittorrentapi.APIConnectionError as e:
        logger.error(f"qBittorrent API connection error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in torrent manager: {e}")


def move_torrent_folder(source: str, destination: str) -> tuple[bool, bool, bool]:
    """
    Move a torrent folder from source to destination.
    
    This function attempts to move a folder using os.rename first (which is faster),
    and falls back to shutil.move if that fails.
    
    Args:
        source: The source path of the torrent folder.
        destination: The destination path where the torrent folder should be moved.
        
    Returns:
        tuple[bool, bool]: (success, replaced)
            success: True if the folder was successfully moved, False otherwise.
            replaced: True if an existing destination folder was deleted, False otherwise.
    """
    replaced = False
    new = False
    # Check if source exists
    if not os.path.exists(source):
        logger.error(f"Source path does not exist: {source}")
        return False, replaced, new

    # Check if source is a directory
    if not os.path.isdir(source):
        logger.error(f"Source is not a directory: {source}")
        return False, replaced, new

    # Handle existing destination (old version of game)

    if os.path.exists(destination):
        try:
            logger.info(f'Deleting existing version: {destination}')
            shutil.rmtree(destination)
            replaced = True
        except OSError as e:
            logger.error(f"Error deleting {destination}: {e}")
            return False, replaced, new

    # Try to move using os.rename (fast)
    try:
        os.rename(source, destination)
        logger.info(f'Moved {source} to {destination}')
        new = True
        return True, replaced, new
    except OSError as e:
        logger.warning(f'Unable to use os.rename to move {source} to {destination}: {e}. Falling back to shutil.move.')

        # Fall back to shutil.move (slower but more robust)
        try:
            shutil.move(source, destination)
            logger.info(f'Moved {source} to {destination} using shutil.move')
            new = True
            return True, replaced, new
        except (OSError, shutil.Error) as e:
            logger.error(f'Error moving {source} using shutil.move: {e}')
            return False, replaced, new
    except Exception as e:
        logger.error(f'Unexpected error moving {source}: {e}')
        return False, replaced, new


def delete_torrent(torrent_hash: str) -> bool:
    """
    Delete a torrent from qBittorrent by its hash.
    
    Args:
        torrent_hash: The hash of the torrent to delete.
        
    Returns:
        bool: True if the torrent was successfully deleted, False otherwise.
    """
    for attempt in range(MAX_RETRIES):
        try:
            client = get_qbittorrent_client()
            client.torrents_delete(torrent_hashes=torrent_hash, delete_files=False)
            logger.info(f"Deleted torrent with hash: {torrent_hash}")
            return True
        except qbittorrentapi.LoginFailed as e:
            logger.error(f"qBittorrent login failed: {e}")
            return False
        except qbittorrentapi.APIConnectionError as e:
            logger.error(
                f"Failed to delete torrent with hash {torrent_hash} (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"Max retries reached. Failed to delete torrent with hash {torrent_hash}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error deleting torrent with hash {torrent_hash}: {e}")
            return False

    return False


def new_folder(torrent_name: str) -> Optional[str]:
    """
    Rework the folder name based on the torrent name.
    
    This function:
    1. Cleans up the torrent name by removing platform-specific parts
    2. Looks up the game in the GOG games database to get the proper title
    3. Removes special characters from the title
    
    Example of original folder name: stalker_2_heart_of_chornobyl_windows_gog_(83415)
    
    Args:
        torrent_name: The original torrent folder name
        
    Returns:
        Optional[str]: The new folder name, or None if an error occurred
    """
    if not torrent_name:
        logger.error("Empty torrent name provided")
        return None

    logger.info(f"Processing torrent name: {torrent_name}")
    new_name = torrent_name

    # Remove everything after the first underscore in _windows_gog_
    if '_windows_gog_' in new_name:
        new_name = torrent_name.split('_windows_gog_')[0]
        logger.debug(f"Removed platform suffix: {new_name}")

    # Search for the game in the GOG games database
    try:
        # Check if the GOG games file exists
        if not os.path.isfile(GOG_ALL_GAMES_FILE):
            logger.warning(f"{GOG_ALL_GAMES_FILE} not found. Fetching data from API...")
            fetch_json_data(GOG_ALL_GAMES_URL, GOG_ALL_GAMES_FILE)
            
        with open(GOG_ALL_GAMES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.info(f"Loaded {GOG_ALL_GAMES_FILE} with {len(data)} games.")

        # First try to find an exact match
        exact_match = False
        for item in data:
            if new_name == item.get('slug'):
                new_name = item.get('title')
                logger.info(f'Found exact match: {item.get("slug")} for title: {new_name}')
                exact_match = True
                break

        # Only try partial matches if no exact match was found
        if not exact_match:
            # Sort items by slug length to prefer shorter/closer matches
            # This helps avoid matching with DLCs or similar named games
            sorted_items = sorted(data, key=lambda x: len(x.get('slug', '')))

            for item in sorted_items:
                slug = item.get('slug', '')
                if slug and new_name in slug:
                    # Check if it's a reasonable match (avoid matching with DLCs)
                    # For example, if new_name is "witcher", don't match with "witcher-3-dlc"
                    if len(slug) <= len(new_name) + 10:  # Allow some flexibility
                        new_name = item.get('title')
                        logger.info(f'Found partial match: {slug} for title: {new_name}')
                        break
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing {GOG_ALL_GAMES_FILE}: {e}")
        return None
    except FileNotFoundError as e:
        logger.error(f"File not found: {GOG_ALL_GAMES_FILE}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing {GOG_ALL_GAMES_FILE}: {e}")
        return None

    # Remove copyright characters and other unwanted characters that may appear in the metadata.
    # TODO: Move these to the configuration file
    for char in '©®™':
        new_name = new_name.replace(char, '')

    # Remove leading/trailing whitespace
    new_name = new_name.strip()

    # If we end up with an empty string, use the original name
    if not new_name:
        logger.warning(f"New name is empty, using original: {torrent_name}")
        new_name = torrent_name

    logger.info(f'Renamed folder: {torrent_name} to {new_name}')
    return new_name


def run():
    """
    Manage torrents by renaming folders and moving completed torrents to the game library root path.
    
    This function:
    1. Checks the connection to qBittorrent
    2. Fetches the latest game data from GOG
    3. Processes completed torrents
    
    Returns:
        None
    """
    if QBIT_ENABLE:
        logger.info("Starting torrent manager...")

        # Check qBittorrent connection
        if not qbit_preflight():
            logger.error("qBittorrent preflight check failed. Exiting torrent manager.")
            return

        # Ensure we have the latest game data
        try:
            logger.info(f"Fetching latest game data from {GOG_ALL_GAMES_URL}")
            fetch_json_data(GOG_ALL_GAMES_URL, GOG_ALL_GAMES_FILE)
        except Exception as e:
            logger.error(f"Error fetching game data: {e}")
            logger.warning("Continuing with existing game data if available...")

        # Process completed torrents
        torrent_manager()

        logger.info("Torrent manager completed")
    else:
        logger.info("Torrent manager is disabled in the configuration. Skipping...")
