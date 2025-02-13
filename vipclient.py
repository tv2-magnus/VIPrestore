import requests
import warnings
from requests import Session
from typing import Optional

class VideoIPathClientError(Exception):
    pass

class VideoIPathClient:
    def __init__(self, base_url: str, verify_ssl: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.session: Session = requests.Session()
        self.session.verify = verify_ssl
        self.xsrf_token: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        try:
            resp = self.session.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.SSLError:
            warnings.warn("SSL verification failed, retrying without certificate verification.", RuntimeWarning)
            self.session.verify = False
            try:
                resp = self.session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as e:
                raise VideoIPathClientError(f"Request failed after SSL fallback: {e}") from e

        except requests.exceptions.ConnectTimeout:
            raise VideoIPathClientError("Connection timed out while trying to reach the server.")

        except requests.exceptions.ConnectionError:
            raise VideoIPathClientError("Failed to connect to the server.")

        except requests.exceptions.HTTPError as http_err:
            raise VideoIPathClientError(f"HTTP error: {http_err.response.status_code} {http_err.response.reason}") from http_err

        except requests.exceptions.RequestException as req_exc:
            raise VideoIPathClientError(f"Request failed: {req_exc}") from req_exc

    def login(self, username: str, password: str) -> None:
        url = f"{self.base_url}/api/_session"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = f"name={username}&password={password}"
        resp = self._request("POST", url, headers=headers, data=data)
        try:
            result = resp.json()
        except Exception as err:
            raise VideoIPathClientError(f"Invalid JSON response: {err}")
        if not result.get("ok"):
            details = result.get("error") or result.get("msg") or str(result)
            raise VideoIPathClientError(f"Login failed: {details}")
        token = self.session.cookies.get("XSRF-TOKEN")
        if token:
            self.xsrf_token = token
            self.session.headers.update({"X-XSRF-TOKEN": token})
        # Store credentials for later use in GET requests
        self.username = username
        self.password = password

    def get(self, endpoint: str) -> dict:
        url = f"{self.base_url}{endpoint}"
        resp = self._request("GET", url)
        return resp.json()

    def validate_session(self) -> bool:
        url = f"{self.base_url}/api/_session"
        resp = self._request("GET", url)
        try:
            result = resp.json()
        except Exception as err:
            raise VideoIPathClientError(f"Invalid JSON response during session validation: {err}")
        return result.get("ok", False)

    def logout(self) -> None:
        url = f"{self.base_url}/api/_session"
        self._request("DELETE", url)
        self.session.cookies.clear()
        self.xsrf_token = None
        self.username = None
        self.password = None

    def retrieve_services(self) -> dict:
        url = f"{self.base_url}/rest/v1/data/status/pathman/currentModernServices/**"
        resp = self._request("GET", url)
        try:
            data = resp.json()
            return data["data"]["status"]["pathman"]["currentModernServices"]
        except (KeyError, ValueError) as e:
            raise VideoIPathClientError(f"Failed to parse services data: {e}")

    def count_services(self) -> int:
        return len(self.retrieve_services())
