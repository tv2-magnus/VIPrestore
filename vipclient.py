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

    def retrieve_group_connections(self) -> tuple[dict, dict]:
        """
        Returns a tuple (group_services, child_to_group).
        group_services: dict of all group-based services
        child_to_group: dict that maps each child service ID to its group parent ID
        """
        try:
            url = (
                "/rest/v1/data/status/conman/services/"
                "*%20where%20type='group'/connection/"
                "connection.generic,generic/**/.../.../connection.to,from,to,id,rev,specific/"
                "specific.breakAway,breakAway,complete,missingActiveConnections,numChildren,children/*"
            )
            resp = self.get(url)
            conman = resp.get("data", {}).get("status", {}).get("conman", {})
            raw_services = conman.get("services", {})

            group_services = {}
            child_to_group = {}

            for svc_key, svc_data in raw_services.items():
                connection = svc_data.get("connection", {})
                group_id = connection.get("id", svc_key)
                gen = connection.get("generic", {})
                spec = connection.get("specific", {})
                desc = gen.get("descriptor", {})

                group_services[group_id] = {
                    "type": "group",
                    "booking": {
                        "serviceId": group_id,
                        "from": connection.get("from", ""),
                        "to": connection.get("to", ""),
                        "allocationState": None,
                        "createdBy": "",
                        "lockedBy": ("GroupLocked" if gen.get("locked") else ""),
                        "isRecurrentInstance": False,
                        "timestamp": "",
                        "descriptor": {
                            "label": desc.get("label", ""),
                            "desc": desc.get("desc", "")
                        },
                        "profile": "",
                        "auditHistory": [],
                    },
                    "res": {
                        "breakAway": spec.get("breakAway"),
                        "complete": spec.get("complete"),
                        "missingActiveConnections": spec.get("missingActiveConnections", {}),
                        "numChildren": spec.get("numChildren", 0),
                        "children": spec.get("children", {}),
                        "rev": connection.get("rev", ""),
                        "state": gen.get("state", None)
                    }
                }

                # Map any child connections to this group
                children_map = spec.get("children", {})
                for child_id in children_map.keys():
                    child_to_group[child_id] = group_id

            return (group_services, child_to_group)

        except VideoIPathClientError:
            return ({}, {})

    def fetch_single_group_connection(self, group_id: str) -> Optional[dict]:
        """
        Fetch a single group-based service from the server by group_id.
        Returns the service dict or None if not found.
        """
        try:
            url = (
                "/rest/v1/data/status/conman/services/"
                "*%20where%20type='group'/connection/"
                "connection.generic,generic/**/.../.../connection.to,from,to,id,rev,specific/"
                "specific.breakAway,breakAway,complete,missingActiveConnections,numChildren,children/*"
            )
            resp = self.get(url)
            conman = resp.get("data", {}).get("status", {}).get("conman", {})
            raw_services = conman.get("services", {})

            for svc_key, svc_data in raw_services.items():
                connection = svc_data.get("connection", {})
                g_id = connection.get("id", svc_key)
                if g_id == group_id:
                    gen = connection.get("generic", {})
                    spec = connection.get("specific", {})
                    desc = gen.get("descriptor", {})

                    return {
                        "type": "group",
                        "booking": {
                            "serviceId": g_id,
                            "from": connection.get("from", ""),
                            "to": connection.get("to", ""),
                            "allocationState": None,
                            "createdBy": "",
                            "lockedBy": ("GroupLocked" if gen.get("locked") else ""),
                            "isRecurrentInstance": False,
                            "timestamp": "",
                            "descriptor": {
                                "label": desc.get("label", ""),
                                "desc": desc.get("desc", "")
                            },
                            "profile": "",
                            "auditHistory": [],
                        },
                        "res": {
                            "breakAway": spec.get("breakAway"),
                            "complete": spec.get("complete"),
                            "missingActiveConnections": spec.get("missingActiveConnections", {}),
                            "numChildren": spec.get("numChildren", 0),
                            "children": spec.get("children", {}),
                            "rev": connection.get("rev", ""),
                            "state": gen.get("state", None)
                        }
                    }
        except VideoIPathClientError:
            pass
        return None

    def get_profiles(self) -> dict:
        return self.get("/rest/v1/data/config/profiles/*/id,name,description,tags/**")

    def get_local_endpoints(self) -> dict:
        return self.get("/rest/v1/data/config/network/nGraphElements/**")

    def get_external_endpoints(self) -> dict:
        return self.get("/rest/v1/data/status/network/externalEndpoints/**")

    def get_endpoint_map(self) -> dict:
        endpoint_map = {}
        try:
            local = self.get_local_endpoints()
            ngraph = local.get("data", {}).get("config", {}).get("network", {}).get("nGraphElements", {})
            for node_id, node_data in ngraph.items():
                label = node_data.get("value", {}).get("descriptor", {}).get("label", "")
                endpoint_map[node_id] = label if label else node_id
        except Exception:
            pass
        try:
            external = self.get_external_endpoints()
            ext_data = external.get("data", {}).get("status", {}).get("network", {}).get("externalEndpoints", {})
            for ext_id, ext_val in ext_data.items():
                lbl = ext_val.get("descriptor", {}).get("label") or ""
                endpoint_map[ext_id] = lbl if lbl else ext_id
        except Exception:
            pass
        return endpoint_map