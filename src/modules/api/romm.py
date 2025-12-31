import base64
import json
import logging
import time
from typing import Dict, List, Optional

import requests
import websocket
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, Timeout, RequestException
from urllib3.util.retry import Retry

from src.modules.config_parse import ROMM_API_PASSWORD, ROMM_API_USERNAME, ROMM_API_URL, ROMM_PLATFORM_SLUG, \
    ROMM_API_WEBSOCKET

logger = logging.getLogger(__name__)


class RommAPI:
    def __init__(self):
        self.session = requests.Session()
        self.username = ROMM_API_USERNAME
        self.password = ROMM_API_PASSWORD
        self.slug = ROMM_PLATFORM_SLUG
        self.base_url = ROMM_API_URL
        self.websocket = f"{ROMM_API_WEBSOCKET}/ws/socket.io/?EIO=4&transport=websocket"
        self.headers = self._create_auth_headers()
        self._setup_session()

    def _setup_session(self):
        """Configure session with retry strategy and timeouts."""
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.timeout = 30

    def _create_auth_headers(self) -> Dict[str, str]:
        """Create authentication headers using Basic Auth."""
        if self.username and self.password:
            credentials = f"{self.username}:{self.password}"
            auth_token = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            return {"Authorization": f"Basic {auth_token}"}
        return {}

    def _request(self, method, endpoint, **kwargs):
        """
        Send a request to the ROMM API with comprehensive error handling.

        Args:
            method: HTTP method to use
            endpoint: API endpoint path
            **kwargs: Additional arguments to pass to requests.request

        Returns:
            JSON response data or None if no content or error

        Raises:
            ConnectionError: If connection cannot be established
            RequestException: For other request-related errors
        """
        url = f"{self.base_url}{endpoint}"
        try:
            # Ensure headers are included in each request
            if 'headers' in kwargs:
                kwargs['headers'].update(self.headers)
            else:
                kwargs['headers'] = self.headers

            # Set timeout if not provided
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30

            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            if resp.content:
                return resp.json()
            return None
        except ConnectionError as e:
            logger.error(f"Connection failed to ROMM API: {url} - {e}")
            logger.error("Check network connectivity and ROMM_API_URL configuration")
            return None
        except Timeout as e:
            logger.error(f"Request timeout to ROMM API: {url} - {e}")
            return None
        except RequestException as e:
            logger.error(f"Request failed: {method} {url} - {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during API request: {e}")
            return None

    def delete_games(self, game_ids: List[int]) -> Optional[Dict]:
        """
        Delete games from ROMM.

        Args:
            game_ids: List of game IDs to delete

        Returns:
            API response
        """
        data = {"roms": game_ids, "delete_from_fs": []}
        logger.info(f"Deleting {len(game_ids)} ROMMs...")
        return self._request("POST", "/api/roms/delete", json=data)

    # Get Game Endpoint GET: /api/roms/{game_id}
    def get_game_by_id(self, game_id: int) -> Optional[Dict]:
        """
        Retrieve game details by ID.

        Args:
            game_id: ID of the game to retrieve

        Returns:
            Game details
        """
        return self._request("GET", f"/api/roms/{game_id}")

    def heartbeat(self) -> Optional[Dict]:
        """
        Send a heartbeat request to keep the session alive.

        Returns:
            Heartbeat response
        """
        return self._request("GET", "/api/heartbeat")

    def get_profile(self) -> Optional[Dict]:
        """
        Retrieve authenticated user profile information.

        Returns:
            User profile data
        """
        return self._request("GET", "/api/users/me")

    def get_config(self) -> Optional[Dict]:
        """
        Retrieve ROMM configuration settings.

        Returns:
            Configuration settings
        """
        return self._request("GET", "/api/config")

    # Get Platforms Endpoint GET: /api/platforms
    def get_platforms(self) -> Optional[List[Dict]]:
        """
        Retrieve list of platforms from ROMM.

        Returns:
            List of platforms
        """
        return self._request("GET", "/api/platforms")

    def get_collections(self) -> Optional[List[Dict]]:
        """
        Retrieve manually created collections.

        Returns:
            List of collections
        """
        return self._request("GET", "/api/collections")

    def get_virtual_collections(self) -> Optional[List[Dict]]:
        """
        Retrieve virtual collections.

        Returns:
            List of virtual collections
        """
        return self._request("GET", "/api/collections/virtual?type=collection")

    def get_platform_by_slug(self) -> Optional[int]:
        """
        Retrieve platform ID by configured slug.

        Returns:
            Platform ID if found, otherwise None
        """
        platforms = self.get_platforms()
        if platforms:
            for platform in platforms:
                if platform.get('fs_slug') == self.slug:
                    return platform.get('id')
        return None

    def filter_games(self,
                     platform_id: Optional[int] = None,
                     limit: Optional[int] = None,
                     offset: Optional[int] = None,
                     order_by: Optional[str] = None,
                     order_dir: Optional[str] = None,
                     **kwargs
                     ) -> Optional[List[Dict]]:
        """
        Filter games based on various parameters.

        Args:
            platform_id: Platform ID to filter by
            limit: Maximum number of games to return
            offset: Pagination offset
            order_by: Field to order results by
            order_dir: Direction of ordering (asc/desc)
            group_by_meta_id: Whether to group by meta ID
            **kwargs: Additional filter parameters

        Returns:
            List of filtered games
        """

        params = {}

        if platform_id is not None:
            params['platform_id'] = platform_id

        if limit is not None:
            params['limit'] = limit

        if offset is not None:
            params['offset'] = offset

        if order_by is not None:
            params['order_by'] = order_by

        if order_dir is not None:
            params['order_dir'] = order_dir

        params.update(kwargs)

        return self._request("GET", "/api/roms", params=params)

    def scan_library(self, platforms: List[int], scan_type: str = "quick", apis: List[str] = None) -> bool:
        """
        Create a websocket connection to ROMM and issue a scan command.
        Waits for "scan:done" message before closing.

        Args:
            platforms: List of platform IDs to scan
            scan_type: Type of scan (e.g., "quick")
            apis: List of APIs to use for scanning (default: igdb, hltb, sgdb)

        Returns:
            True if command was sent successfully and scan finished, False otherwise
        """
        if apis is None and scan_type != "hashes":
            apis = ["sgdb", "igdb", "hltb"]
        elif apis is None:
            apis = []

        message = [
            "scan",
            {
                "platforms": platforms,
                "type": scan_type,
                "apis": apis
            }
        ]
        message_formatted = f"42{json.dumps(message)}"
        logger.debug(f"Sending scan command to ROMM: {message_formatted}")

        try:
            # TODO: Rewrite this.  It works, but it's ugly.
            # Set a 2-hour timeout (7200 seconds)
            timeout = 7200
            ws = websocket.create_connection(self.websocket, timeout=timeout)
            result = ws.recv()

            logger.debug(f"{result}")
            ws.send("40")
            result = ws.recv()
            logger.debug(f"{result}")

            # Socket.IO websocket transport framing: 42 + JSON message
            # 4 is Message, 2 is Event
            ws.send(message_formatted)
            logger.info(f"Scan command sent to ROMM for platforms: {platforms}. Waiting for completion...")

            start_time = time.time()
            while True:
                # Check for 2-hour timeout as a failsafe
                if time.time() - start_time > timeout:
                    logger.warning("Scan timeout reached (2 hours). Closing connection.")
                    break

                try:
                    result = ws.recv()
                    logger.debug(f"Received from ROMM websocket: {result}")

                    # Check for scan:done message
                    if '"scan:done"' in result:
                        logger.info("ROMM scan completed successfully.")
                        break

                    if '"scan:stop"' in result:
                        logger.info("ROMM scan stopped.")
                        break

                    # Heartbeat (Ping 2 -> Pong 3)
                    if result == "2":
                        ws.send("3")
                        logger.debug("Sent Socket.IO heartbeat (pong)")

                except websocket.WebSocketTimeoutException:
                    logger.warning("Websocket timeout reached during receive. Closing.")
                    break
                except Exception as e:
                    logger.error(f"Error while receiving from websocket: {e}")
                    break

            ws.close()
            return True
        except Exception as e:
            logger.error(f"Failed to communicate with ROMM via websocket: {e}")
            return False
