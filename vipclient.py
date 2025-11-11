import requests
import warnings
import strings
from requests import Session
from typing import Optional, Callable, Dict
from urllib.parse import urlparse

class VideoIPathClientError(Exception):
    pass

class VideoIPathClient:
    def __init__(self, base_url: str, verify_ssl: bool = True, 
                 ssl_exception_callback: Optional[Callable[[str], bool]] = None,
                 timeout: int = 5) -> None:
        self.base_url = base_url.rstrip("/")
        self.session: Session = requests.Session()
        self.session.verify = verify_ssl
        self.xsrf_token: Optional[str] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        # Callback for SSL exceptions - should return True to continue with insecure connection
        self.ssl_exception_callback = ssl_exception_callback
        # Dictionary to store user decisions about SSL exceptions per domain
        self.ssl_exceptions: Dict[str, bool] = {}
        # Default timeout for all requests
        self.timeout = timeout
        
    def get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for tracking SSL exceptions"""
        return urlparse(url).netloc
        
    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        domain = self.get_domain_from_url(url)
        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        # Disable automatic redirects to handle them manually
        # This allows us to handle SSL errors on redirected HTTPS URLs
        if 'allow_redirects' not in kwargs:
            kwargs['allow_redirects'] = False
        
        # Check if we already have a decision for this domain
        if domain in self.ssl_exceptions and not self.session.verify:
            # User previously accepted the risk for this domain
            try:
                response = self.session.request(method, url, **kwargs)
                # Handle redirects manually
                if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                    redirect_url = response.headers['Location']
                    return self._request(method, redirect_url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                raise VideoIPathClientError(f"Connection to {domain} timed out. Please check the server address and network connection.")
            except requests.exceptions.ConnectionError as e:
                raise VideoIPathClientError(f"Could not connect to {domain}. Please verify the server is running and accessible.")
            except requests.exceptions.RequestException as e:
                raise VideoIPathClientError(f"Request failed: {e}") from e
        
        # First try with SSL verification per current setting
        try:
            response = self.session.request(method, url, **kwargs)
            
            # Handle redirects manually
            if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                redirect_url = response.headers['Location']
                return self._request(method, redirect_url, **kwargs)
            
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            raise VideoIPathClientError(f"Connection to {domain} timed out. Please check the server address and network connection.")
        except requests.exceptions.SSLError as ssl_err:
            # Only proceed if we have a callback to confirm with user
            if self.ssl_exception_callback is None:
                raise VideoIPathClientError(
                    "SSL certificate verification failed and no exception handler is available"
                ) from ssl_err
                
            message = strings.ERROR_SSL_CERT_CONTINUE.format(domain)
                        
            # Get user decision via callback
            proceed = self.ssl_exception_callback(message)
            
            if proceed:
                # Remember this decision for this domain
                self.ssl_exceptions[domain] = True
                # Temporarily disable verification for this request
                old_verify = self.session.verify
                self.session.verify = False
                
                warnings.warn(
                    f"SSL verification disabled for {domain} per user request. "
                    "This is less secure and should only be used when necessary.",
                    RuntimeWarning
                )
                
                try:
                    response = self.session.request(method, url, **kwargs)
                    # Handle redirects manually
                    if response.status_code in (301, 302, 303, 307, 308) and 'Location' in response.headers:
                        redirect_url = response.headers['Location']
                        return self._request(method, redirect_url, **kwargs)
                    response.raise_for_status()
                    return response
                except requests.exceptions.Timeout:
                    raise VideoIPathClientError(f"Connection to {domain} timed out. Please check the server address and network connection.")
                except requests.exceptions.ConnectionError:
                    raise VideoIPathClientError(f"Could not connect to {domain}. Please verify the server is running and accessible.")
                except requests.exceptions.RequestException as e:
                    raise VideoIPathClientError(f"Request failed after SSL exception: {e}") from e
            else:
                # User declined to proceed with insecure connection
                raise VideoIPathClientError(
                    f"SSL certificate verification failed for {domain}. "
                    "Connection aborted per user request."
                ) from ssl_err
        except requests.exceptions.ConnectionError:
            raise VideoIPathClientError(f"Could not connect to {domain}. Please verify the server is running and accessible.")
        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else "Unknown"
            raise VideoIPathClientError(f"HTTP error {status_code}: {http_err}")
        except requests.exceptions.RequestException as e:
            raise VideoIPathClientError(f"Request failed: {e}") from e

    def login(self, username: str, password: str) -> None:
        """
        Attempts to log in using cookie-based session authentication.
        First, it tries the secure (HTTPS) connection; if that fails due to SSL issues,
        it will prompt the user before proceeding with an insecure connection.
        """
        url = f"{self.base_url}/api/_session"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        # Use a dict so that requests handles URL encoding
        data = {"name": username, "password": password}
        
        try:
            resp = self._request("POST", url, headers=headers, data=data)
        except VideoIPathClientError as e:
            raise VideoIPathClientError(f"Login attempt failed: {e}") from e

        try:
            result = resp.json()
        except Exception as err:
            raise VideoIPathClientError(f"Invalid JSON response during login: {err}")

        # Check for successful login
        if not result.get("ok"):
            # Extract error details in order of preference
            error_msg = result.get("error") or result.get("msg") or result.get("reason")
            if error_msg:
                raise VideoIPathClientError(f"Login failed: {error_msg}")
            else:
                # Check if we got an empty userCtx (common for invalid credentials)
                user_ctx = result.get("userCtx", {})
                if not user_ctx.get("name"):
                    raise VideoIPathClientError("Login failed: Invalid username or password")
                else:
                    raise VideoIPathClientError("Login failed: Authentication was not successful")

        # Store session cookies and set the X-XSRF-TOKEN header for subsequent requests.
        token = self.session.cookies.get("XSRF-TOKEN")
        if token:
            self.xsrf_token = token
            self.session.headers.update({"X-XSRF-TOKEN": token})

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