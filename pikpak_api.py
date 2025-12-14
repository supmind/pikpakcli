import asyncio
import hashlib
import json
import time
import uuid
from typing import Optional, Dict, List, Any
from urllib.parse import urlencode

import httpx

# Constants
CLIENT_ID = "YNxT9w7GMdWvEOKa"
CLIENT_SECRET = "dbw2OtmVEeuUvIptb1Coyg"
PACKAGE_NAME = "com.pikcloud.pikpak"
CLIENT_VERSION = "1.21.0"
API_HOST = "api-drive.mypikpak.com"
USER_HOST = "user.mypikpak.com"

# MD5 Salt Object from Go code
MD5_SALT_OBJ = [
    {"alg": "md5", "salt": ""},
    {"alg": "md5", "salt": "E32cSkYXC2bciKJGxRsE8ZgwmH/YwkvpD6/O9guSOa2irCwciH4xPHaH"},
    {"alg": "md5", "salt": "QtqgfMgHP2TFl"},
    {"alg": "md5", "salt": "zOKgHT56L7nIzFzDpUGhpWFrgP53m3G6ML"},
    {"alg": "md5", "salt": "S"},
    {"alg": "md5", "salt": "THxpsktzfFXizUv7DK1y/N7NZ1WhayViluBEvAJJ8bA1Wr6"},
    {"alg": "md5", "salt": "y9PXH3xGUhG/zQI8CaapRw2LhldCaFM9CRlKpZXJvj+pifu"},
    {"alg": "md5", "salt": "+RaaG7T8FRTI4cP019N5y9ofLyHE9ySFUr"},
    {"alg": "md5", "salt": "6Pf1l8UTeuzYldGtb/d"}
]

class PikPakException(Exception):
    pass

class PikPakApi:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None, device_id: Optional[str] = None):
        self.username = username
        self.password = password
        self.device_id = device_id or self._generate_device_id()
        self.access_token = None
        self.refresh_token = None
        self.user_id = ""
        self.captcha_token = ""
        self.client = httpx.AsyncClient(timeout=30.0)

    def _generate_device_id(self) -> str:
        return uuid.uuid4().hex[:16]

    def _calculate_captcha_sign(self, timestamp: str) -> str:
        s = f"{CLIENT_ID}{CLIENT_VERSION}{PACKAGE_NAME}{self.device_id}{timestamp}"
        for item in MD5_SALT_OBJ:
            if item["alg"] == "md5":
                s = hashlib.md5((s + item["salt"]).encode('utf-8')).hexdigest()
        return f"1.{s}"

    async def _request(self, method: str, url: str, headers: Dict[str, str] = None, **kwargs) -> Dict[str, Any]:
        if headers is None:
            headers = {}

        # Add default headers
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        if self.device_id:
            headers["X-Device-Id"] = self.device_id

        if self.captcha_token:
            headers["X-Captcha-Token"] = self.captcha_token

        headers.setdefault("User-Agent", "ANDROID-com.pikcloud.pikpak/1.21.0")
        headers.setdefault("Content-Type", "application/json; charset=utf-8")

        try:
            resp = await self.client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            data = resp.json()

            # Check for API level errors (if any, though usually HTTP status is enough)
            if "error_code" in data and data["error_code"] != 0:
                 # Check for captcha required error (code 9)
                if data["error_code"] == 9:
                    raise PikPakException(f"Captcha required (Code 9): {data.get('error')}")
                # Check for token expired (code 16)
                if data["error_code"] == 16:
                     # Attempt refresh logic could go here, but for simplicity we raise exception
                    raise PikPakException(f"Token expired (Code 16): {data.get('error')}")

                # Raise generic error for non-zero error_code
                raise PikPakException(f"API Error {data['error_code']}: {data.get('error')}")

            return data
        except httpx.HTTPStatusError as e:
            # Handle HTTP errors (like 400, 401) and try to parse response body for details
            try:
                error_data = e.response.json()
                if "error_code" in error_data:
                     # Specific handling for captcha (9) or auth (16) if status is 4xx
                    if error_data["error_code"] == 9:
                         raise PikPakException(f"Captcha required (Code 9): {error_data.get('error_description') or error_data.get('error')}")
                    if error_data["error_code"] == 16:
                         raise PikPakException(f"Token expired (Code 16): {error_data.get('error_description') or error_data.get('error')}")

                    raise PikPakException(f"API Error {error_data['error_code']}: {error_data.get('error_description') or error_data.get('error')}")
            except json.JSONDecodeError:
                pass
            raise PikPakException(f"HTTP Error: {e}")

    async def get_captcha_token(self, action: str) -> str:
        """
        Obtain a captcha token for a specific action.
        Updates self.captcha_token and returns it.
        """
        timestamp = str(int(time.time() * 1000))
        sign = self._calculate_captcha_sign(timestamp)

        url = f"https://{USER_HOST}/v1/shield/captcha/init"
        params = {"client_id": CLIENT_ID}

        body = {
            "action": action,
            "captcha_token": self.captcha_token,
            "client_id": CLIENT_ID,
            "device_id": self.device_id,
            "meta": {
                "captcha_sign": sign,
                "user_id": self.user_id,
                "package_name": PACKAGE_NAME,
                "client_version": CLIENT_VERSION,
                "timestamp": timestamp
            },
            "redirect_uri": "https://api.mypikpak.com/v1/auth/callback"
        }

        # Note: We don't use self._request here because this is the Auth request itself
        # and we need to handle headers specifically without injecting invalid tokens.
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Device-Id": self.device_id,
            "User-Agent": "ANDROID-com.pikcloud.pikpak/1.21.0"
        }

        resp = await self.client.post(url, params=params, json=body, headers=headers)
        data = resp.json()

        if data.get("error_code", 0) != 0:
            raise PikPakException(f"Captcha Init Error: {data.get('error')}")

        self.captcha_token = data.get("captcha_token")
        return self.captcha_token

    async def login(self):
        """
        Login with username and password.
        """
        if not self.username or not self.password:
            raise ValueError("Username and Password required for login")

        # 1. Get initial captcha token for login action
        action = f"POST:https://{USER_HOST}/v1/auth/signin"
        await self.get_captcha_token(action)

        # 2. Perform Login
        url = f"https://{USER_HOST}/v1/auth/signin"
        body = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "captcha_token": self.captcha_token
        }

        data = await self._request("POST", url, json=body)

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.user_id = data["sub"]
        return data

    async def refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        url = f"https://{USER_HOST}/v1/auth/token"
        body = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }

        data = await self._request("POST", url, json=body)

        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        # Update user_id just in case, though usually 'sub' is consistent
        if "sub" in data:
            self.user_id = data["sub"]
        return data

    # --- File Management ---

    async def file_list(self, parent_id: str = None, limit: int = 100, next_page_token: str = None) -> Dict[str, Any]:
        """
        List files in a directory.
        """
        url = f"https://{API_HOST}/drive/v1/files"
        filters = {"trashed": {"eq": False}}

        params = {
            "thumbnail_size": "SIZE_MEDIUM",
            "limit": str(limit),
            "with_audit": "false",
            "filters": json.dumps(filters)
        }
        if parent_id:
            params["parent_id"] = parent_id
        if next_page_token:
            params["page_token"] = next_page_token

        try:
            return await self._request("GET", url, params=params)
        except PikPakException as e:
            if "Captcha required" in str(e):
                await self.get_captcha_token("GET:/drive/v1/files")
                return await self._request("GET", url, params=params)
            raise e

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """
        Get details of a single file.
        """
        url = f"https://{API_HOST}/drive/v1/files/{file_id}"
        params = {"thumbnail_size": "SIZE_MEDIUM"}

        try:
            return await self._request("GET", url, params=params)
        except PikPakException as e:
            if "Captcha required" in str(e):
                await self.get_captcha_token("GET:/drive/v1/files")
                return await self._request("GET", url, params=params)
            raise e

    async def create_folder(self, name: str, parent_id: str = None) -> Dict[str, Any]:
        """
        Create a new folder.
        """
        url = f"https://{API_HOST}/drive/v1/files"
        body = {
            "kind": "drive#folder",
            "name": name
        }
        if parent_id:
            body["parent_id"] = parent_id

        # Headers required for creation
        headers = {
            "Product_flavor_name": "cha",
            "X-Client-Version-Code": "10083",
            "X-Peer-Id": self.device_id,
            "X-User-Region": "1",
            "X-Alt-Capability": "3",
            "Country": "CN"
        }

        try:
            return await self._request("POST", url, json=body, headers=headers)
        except PikPakException as e:
            if "Captcha required" in str(e):
                await self.get_captcha_token("POST:/drive/v1/files")
                return await self._request("POST", url, json=body, headers=headers)
            raise e

    async def trash_file(self, file_id: str):
        """
        Move a file to trash (batchTrash).
        """
        # Based on Python reference provided by user: files:batchTrash
        url = f"https://{API_HOST}/drive/v1/files:batchTrash"
        body = {"ids": [file_id]}
        return await self._request("POST", url, json=body)

    async def delete_file_forever(self, file_id: str):
        """
        Delete a file permanently.
        """
        url = f"https://{API_HOST}/drive/v1/files:batchDelete"
        body = {"ids": [file_id]}
        return await self._request("POST", url, json=body)

    # --- Upload / Download Tasks ---

    async def add_url_task(self, file_url: str, parent_id: str = None) -> Dict[str, Any]:
        """
        Add an offline download task (URL upload).
        """
        url = f"https://{API_HOST}/drive/v1/files"
        body = {
            "kind": "drive#file",
            "upload_type": "UPLOAD_TYPE_URL",
            "url": {"url": file_url}
        }
        if parent_id:
            body["parent_id"] = parent_id

        headers = {
            "Product_flavor_name": "cha",
            "X-Client-Version-Code": "10083",
            "X-Peer-Id": self.device_id,
            "X-User-Region": "1",
            "X-Alt-Capability": "3",
            "Country": "CN"
        }

        try:
            return await self._request("POST", url, json=body, headers=headers)
        except PikPakException as e:
            if "Captcha required" in str(e):
                await self.get_captcha_token("POST:/drive/v1/files")
                return await self._request("POST", url, json=body, headers=headers)
            raise e

    # --- Share API ---

    async def get_share_info(self, share_id: str, pass_code: str = None) -> Dict[str, Any]:
        """
        Get information about a share link.
        """
        # Get captcha for Share Info action
        await self.get_captcha_token("GET:/drive/v1/share")

        url = f"https://{API_HOST}/drive/v1/share"
        params = {
            "share_id": share_id,
            "client_id": CLIENT_ID
        }
        if pass_code:
            params["pass_code"] = pass_code

        return await self._request("GET", url, params=params)

    async def get_share_files(self, share_id: str, pass_code_token: str, parent_id: str = None, limit: int = 100) -> Dict[str, Any]:
        """
        List files in a shared folder.
        """
        # Get captcha for Share Detail action
        await self.get_captcha_token("GET:/drive/v1/share/detail")

        url = f"https://{API_HOST}/drive/v1/share/detail"
        params = {
            "share_id": share_id,
            "pass_code_token": pass_code_token,
            "client_id": CLIENT_ID,
            "limit": str(limit),
            "thumbnail_size": "SIZE_LARGE",
            "order": "6" # Default sort
        }
        if parent_id:
            params["parent_id"] = parent_id

        return await self._request("GET", url, params=params)

    # --- User Info ---

    async def get_quota(self) -> Dict[str, Any]:
        """
        Get user quota information.
        """
        url = f"https://{API_HOST}/drive/v1/about"
        return await self._request("GET", url)

    async def close(self):
        await self.client.aclose()


# Example Usage
if __name__ == "__main__":
    async def main():
        # 1. Initialize API (can provide existing credentials or log in)
        # Note: Replace with actual username/password to test login
        # pikpak = PikPakApi(username="YOUR_USERNAME", password="YOUR_PASSWORD")

        # Or just use it for Share API (anonymous mode)
        pikpak = PikPakApi()

        print(f"Device ID: {pikpak.device_id}")

        try:
            # Example: Get Share Info
            share_id = "VOKb91vMpLUddAoRhJXcCYHQo1"
            pass_code = "AAAABF_tZ4hH7dxk683DdWOfo1_VOK"

            print(f"\n--- Getting Share Info: {share_id} ---")
            share_info = await pikpak.get_share_info(share_id, pass_code)
            print(f"Share Name: {share_info.get('title')}")
            pass_code_token = share_info.get("pass_code_token")

            if share_info.get("files"):
                root_file = share_info["files"][0]
                root_id = root_file["id"]
                print(f"Root File: {root_file['name']} (ID: {root_id})")

                # Example: List Share Files
                print(f"\n--- Listing Files in Share Root ---")
                files_resp = await pikpak.get_share_files(share_id, pass_code_token, parent_id=root_id)
                for f in files_resp.get("files", []):
                    print(f"- {f['name']} ({f['kind']}) Size: {f['size']}")

            # If you were logged in, you could do:
            # await pikpak.login()
            # files = await pikpak.file_list()
            # print(files)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await pikpak.close()

    asyncio.run(main())
