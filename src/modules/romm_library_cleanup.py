# ROMM Library Cleanup Module
import logging

from src.modules.api.romm import RommAPI
from src.modules.config_parse import *
from src.modules.config_parse import ROMM_EMPTY_DIRS_LIBRARY_SPECIFIC

logger = logging.getLogger(__name__)


def run():
    """
    Run the ROMM library cleanup process.
    This function will find and delete empty ROMMs.
    """
    if ROMM_ENABLE:
        logger.info("Starting ROMM library cleanup...")
        try:
            if ROMM_EMPTY_DIRS:
                find_empty()
                find_fragmented()
            if ROMM_MISSING_EXE:
                find_missing_exe()
            if ROMM_SCAN_DANGEROUS_FILETYPES:
                find_dangerous_filetypes()

            logger.info("ROMM library cleanup completed.")
        except Exception as e:
            logger.error(f"Error during ROMM library cleanup: {e}")
    else:
        logger.info("ROMM library cleanup is disabled in the configuration. Skipping...")


def scan_after_import():
    try:
        romm_api = RommAPI()
        platform_id = romm_api.get_platform_by_slug()
        if platform_id:
            # Scan for new metadata sources
            logger.info("Scanning for new metadata sources...")
            romm_api.scan_library(platforms=[platform_id], scan_type="quick", apis=["sgdb", "igdb", "hltb"])
    except Exception as e:
        logger.error(f"Error in scan_after_import: {e}")


def scan_file_changes():
    try:
        romm_api = RommAPI()
        platform_id = romm_api.get_platform_by_slug()
        # Scan the file changes in the library folder, should be quick and entirely local.
        if platform_id:
            logger.info("Scanning for file changes in the library folder...")
            romm_api.scan_library(platforms=[platform_id], scan_type="hashes")
    except Exception as e:
        logger.error(f"Error in scan_file_changes: {e}")

def find_empty():
    # Get the list of romms from the API
    logger.info("Removing empty directories...")
    try:
        romm_api = RommAPI()
        platform_id = None

        if ROMM_EMPTY_DIRS_LIBRARY_SPECIFIC:
            logger.info("Removing empty directories specific to the ROMM library...")
            platform_id = RommAPI().get_platform_by_slug()
            if platform_id is None:
                logger.warning("Could not retrieve platform ID, continuing with all platforms")

        data = romm_api.filter_games(platform_id=platform_id, offset=0, order_by="fs_size_bytes", order_dir="asc",
                                     group_by_meta_id=True)

        if data is None:
            logger.error("Failed to retrieve games from ROMM API")
            return

        game_ids = []
        items = []

        if isinstance(data, dict):
            items = data.get('items', [])
        elif isinstance(data, list):
            items = data

        if not items:
            logger.info("No ROMMs found to check for emptiness.")
            return

        for item in items:
            if item.get('fs_size_bytes') == 0:
                logger.info(f"Found empty ROMM: {item.get('name')} (ID: {item.get('id')})")
                # add the game ID to the list for deletion
                game_ids.append(item.get('id'))

        if game_ids:
            logger.info(f"Deleting empty ROMMs: {len(game_ids)} found.")
            result = romm_api.delete_games(game_ids)
            if result is None:
                logger.error("Failed to delete empty ROMMs")
        else:
            logger.info("No empty ROMMs found.")
    except Exception as e:
        logger.error(f"Error in find_empty: {e}")


def find_fragmented():
    """
    Find ROMMs that are fragmented.
    This function will check each ROMM file for fragmentation and log the results.
    """
    logger.info("Finding ROMMs too small...")
    try:
        romm_api = RommAPI()
        platform_id = None

        if ROMM_EMPTY_DIRS_LIBRARY_SPECIFIC:
            logger.info("Removing fragmented directories specific to the ROMM library...")
            platform_id = RommAPI().get_platform_by_slug()
            if platform_id is None:
                logger.warning("Could not retrieve platform ID, continuing with all platforms")

        data = romm_api.filter_games(platform_id=platform_id, offset=0, order_by="fs_size_bytes", order_dir="asc",
                                     group_by_meta_id=True)

        if data is None:
            logger.error("Failed to retrieve games from ROMM API")
            return

        game_ids = []
        items = []

        if isinstance(data, dict):
            items = data.get('items', [])
        elif isinstance(data, list):
            items = data

        if not items:
            logger.info("No ROMMs found to check for fragmentation.")
            return

        for item in items:
            if item.get(
                    'fs_size_bytes') <= 1100:  # 1.1 KB, should be smaller than the smallest legitimate game file. This value specifically is what an XCI missing its actual game file is.
                logger.info(f"Found fragmented ROMM: {item.get('name')} (ID: {item.get('id')})")
                # add the game ID to the list for deletion
                game_ids.append(item.get('id'))

        if game_ids:
            logger.info(f"Deleting empty ROMMs: {len(game_ids)} found.")
            romm_api.delete_games(game_ids)
        else:
            logger.info("No empty ROMMs found.")
    except Exception as e:
        logger.error(f"Error in find_fragmented: {e}")


def find_missing_exe():
    """
    Find ROMMs that are missing the executable file.
    This function will check each ROMM file for the presence of an executable file.
    """
    logger.info("Finding ROMMs with missing executables...")
    try:
        romm_api = RommAPI()

        platform_id = RommAPI().get_platform_by_slug()  # Ensure platform is set
        if platform_id is None:
            logger.error("Could not retrieve platform ID, skipping missing exe check")
            return

        data = romm_api.filter_games(platform_id=platform_id, offset=0, order_by="fs_size_bytes", order_dir="asc",
                                     group_by_meta_id=True)

        if data is None:
            logger.error("Failed to retrieve games from ROMM API")
            return

        game_ids = []
        items = []

        if isinstance(data, dict):
            items = data.get('items', [])
        elif isinstance(data, list):
            items = data

        if not items:
            logger.info("No ROMMs found to check for missing executables.")
            return

        for item in items:
            is_exe_present = False

            for file in item.get('files', []):
                if file.get('file_name').endswith('.exe'):
                    is_exe_present = True
                    break

            if not is_exe_present:
                logger.info(f"Romm missing executable: {item.get('name')} (ID: {item.get('id')})")
                game_ids.append(item.get('id'))

        if game_ids:
            logger.info(f"Deleting ROMMs with missing executables: {len(game_ids)} found.")
            romm_api.delete_games(game_ids)
        else:
            logger.info("No ROMMs with missing executables found.")
    except Exception as e:
        logger.error(f"Error in find_missing_exe: {e}")


def find_dangerous_filetypes():
    """
    Find ROMMs that contain potentially dangerous file types.
    This function will check each ROMM file for the presence of dangerous file types.
    This is not an exhaustive list, but it includes common dangerous file types that should not exist with any legitimate game GOG release like .bat and .cmd.
    It is recommended to add more file types as needed and to leverage a more comprehensive security solution like ClamAV.
    """
    logger.info("Finding ROMMs with dangerous file types...")
    try:
        romm_api = RommAPI()

        platform_id = RommAPI().get_platform_by_slug()
        if platform_id is None:
            logger.error("Could not retrieve platform ID, skipping dangerous filetype check")
            return

        data = romm_api.filter_games(platform_id=platform_id, offset=0, order_by="fs_size_bytes", order_dir="asc",
                                     group_by_meta_id=True)

        if data is None:
            logger.error("Failed to retrieve games from ROMM API")
            return

        game_ids = []
        items = []

        if isinstance(data, dict):
            items = data.get('items', [])
        elif isinstance(data, list):
            items = data

        if not items:
            logger.info("No ROMMs found to check for dangerous file types.")
            return

        for item in items:
            for file in item.get('files', []):
                if file.get('file_name').endswith(
                        ('.bat', '.cmd', '.url', '.m3u', '.pdf', '.js', '.iso', '.ics', '.msi', '.msix', '.msu', '.one',
                         '.cpl', '.cab', '.gadget', '.iqy', '.msp', '.appx', '.jse', '.scr', '.reg', '.ws', '.wse',
                         '.wsf')):
                    logger.warning(f"Release has potentially dangerous file: {item.get('name')} (ID: {item.get('id')})")
                    game_ids.append(item.get('id'))
                    break

        if game_ids:
            logger.info(f"Releases with dangerous files: {len(game_ids)} found.")
        else:
            logger.info("No releases with dangerous files found.")
    except Exception as e:
        logger.error(f"Error in find_dangerous_filetypes: {e}")