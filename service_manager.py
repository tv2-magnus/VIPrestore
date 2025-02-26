import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any

from vipclient import VideoIPathClient, VideoIPathClientError

logger = logging.getLogger(__name__)

class ServiceManagerError(Exception):
    """Exception raised for errors in the ServiceManager."""
    pass

class ServiceManager:
    """
    Manages service operations including retrieval, creation, cancellation, and persistence.
    Handles communication with the VideoIPathClient and processes service data.
    """
    
    def __init__(self, client: Optional[VideoIPathClient] = None):
        """
        Initialize the ServiceManager with an optional VideoIPathClient.
        
        Args:
            client: An optional VideoIPathClient instance for communication with the server.
        """
        self.client = client
        self.executor = ThreadPoolExecutor()
        self.current_services = {}
        self.profile_mapping = {}
        self.endpoint_map = {}
        self.child_to_group = {}
    
    def set_client(self, client: VideoIPathClient) -> None:
        """
        Set or update the VideoIPathClient instance.
        
        Args:
            client: The VideoIPathClient to use for server communications.
        """
        self.client = client
    
    async def _run_api_call(self, func, *args, timeout: int = 10, retries: int = 2):
        """
        Run an API call with retry logic and timeout in a separate thread.
        
        Args:
            func: The function to call.
            *args: Arguments to pass to the function.
            timeout: Timeout in seconds.
            retries: Number of retry attempts.
            
        Returns:
            The result of the function call.
            
        Raises:
            Exception: If all retries fail.
        """
        loop = asyncio.get_running_loop()
        for attempt in range(retries):
            try:
                return await asyncio.wait_for(
                    loop.run_in_executor(self.executor, func, *args), 
                    timeout
                )
            except Exception as e:
                if attempt == retries - 1:
                    raise e
                logger.warning(f"API call failed, retrying ({attempt+1}/{retries}): {e}")
    
    async def fetch_services_data(self) -> Dict[str, Any]:
        """
        Fetch all services data, including profiles and endpoint information.
        
        Returns:
            Dictionary containing merged services, profile mapping, endpoint mapping,
            and child-to-group mapping.
            
        Raises:
            ServiceManagerError: If client is not set or API calls fail.
        """
        if not self.client:
            raise ServiceManagerError("Client not set")
        
        # Fetch data in parallel for better performance
        future_normal = self._run_api_call(self.client.retrieve_services)
        future_profiles = self._run_api_call(self.client.get_profiles)
        future_endpoint_map = self._run_api_call(self.client.get_endpoint_map)
        future_group = self._run_api_call(self.client.retrieve_group_connections)
        
        try:
            normal_services, profiles_resp, endpoint_map, group_res = await asyncio.gather(
                future_normal, future_profiles, future_endpoint_map, future_group
            )
        except Exception as e:
            raise ServiceManagerError(f"Failed to fetch services data: {e}")
        
        # Process the results
        group_services, child_to_group = group_res
        
        # Merge normal and group services
        merged = {}
        merged.update(normal_services)
        merged.update(group_services)
        
        # Add group parent info to child services
        for svc_id, svc_obj in normal_services.items():
            if svc_id in child_to_group:
                svc_obj["groupParent"] = child_to_group[svc_id]
        
        # Extract profile information
        used_profile_ids = set()
        for svc_data in merged.values():
            booking = svc_data.get("booking", {})
            pid = booking.get("profile", "")
            if pid:
                used_profile_ids.add(pid)
        
        # Create profile mapping
        prof_data = profiles_resp.get("data", {}).get("config", {}).get("profiles", {})
        profile_mapping = {pid: info.get("name", pid) for pid, info in prof_data.items()}
        
        # Update instance variables
        self.current_services = merged
        self.profile_mapping = profile_mapping
        self.endpoint_map = endpoint_map
        self.child_to_group = child_to_group
        
        return {
            "merged": merged,
            "used_profile_ids": used_profile_ids,
            "profile_mapping": profile_mapping,
            "endpoint_map": endpoint_map,
            "child_to_group": child_to_group,
        }
    
    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a service by ID.
        
        Args:
            service_id: The ID of the service to retrieve.
            
        Returns:
            The service data or None if not found.
        """
        return self.current_services.get(service_id)
    
    def get_service_details(self, service_id: str) -> List[Tuple[str, str]]:
        """
        Get detailed information for a service suitable for display.
        
        Args:
            service_id: The ID of the service.
            
        Returns:
            List of tuples with (field_name, field_value) for display.
            
        Raises:
            ServiceManagerError: If service is not found.
        """
        import re
        
        service = self.get_service(service_id)
        if not service:
            raise ServiceManagerError(f"Service {service_id} not found")
        
        details = []
        
        # Add service type information
        svc_type = service.get("type", "")
        if svc_type == "group":
            details.append(("Service Kind", "Group-Based Service"))
        else:
            group_par = service.get("groupParent", "")
            if group_par:
                details.append(("Service Kind", f"Endpoint-Based (Child of group {group_par})"))
            else:
                details.append(("Service Kind", "Endpoint-Based Service"))
        
        if svc_type:
            details.append(("type", str(svc_type)))
        
        # Add booking information
        booking = service.get("booking", {})
        details.append(("serviceId", str(booking.get("serviceId", service_id))))
        
        if "allocationState" in booking:
            details.append(("allocationState", str(booking["allocationState"])))
        
        details.append(("createdBy", str(booking.get("createdBy", ""))))
        details.append(("lockedBy", str(booking.get("lockedBy", ""))))
        details.append(("isRecurrentInstance", str(booking.get("isRecurrentInstance", False))))
        details.append(("timestamp", str(booking.get("timestamp", ""))))
        
        # Add group parent if applicable
        group_parent_id = service.get("groupParent", "")
        if group_parent_id:
            details.append(("Group Parent", group_parent_id))
        
        # Add source/destination information
        from_uid = booking.get("from", "")
        to_uid = booking.get("to", "")
        from_label = self.endpoint_map.get(from_uid, from_uid)
        to_label = self.endpoint_map.get(to_uid, to_uid)
        
        descriptor = booking.get("descriptor", {})
        desc_label = descriptor.get("label", "")
        details.append(("descriptor.label", desc_label))
        details.append(("descriptor.desc", descriptor.get("desc", "")))
        
        m = re.match(r'(.+?)\s*->\s*(.+)', desc_label)
        if m:
            from_label, to_label = m.group(1).strip(), m.group(2).strip()
        
        details.append(("from label", from_label))
        details.append(("from device", from_uid))
        details.append(("to label", to_label))
        details.append(("to device", to_uid))
        
        # Process timestamps
        start_ts = booking.get("start", "")
        if start_ts:
            try:
                dt_val = datetime.fromtimestamp(int(start_ts) / 1000)
                start_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                start_str = start_ts
        else:
            start_str = ""
        details.append(("start", start_str))
        
        # Process end timestamp
        end_ts = booking.get("end", "")
        if end_ts:
            try:
                dt_val = datetime.fromtimestamp(int(end_ts) / 1000)
                if dt_val - datetime.now() > timedelta(days=3650):
                    end_str = "∞"
                else:
                    end_str = dt_val.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                end_str = end_ts
        else:
            end_str = ""
        details.append(("end", end_str))
        
        details.append(("cancelTime", str(booking.get("cancelTime", ""))))
        
        # Add profile information
        prof_id = booking.get("profile", "")
        prof_name = self.profile_mapping.get(prof_id, prof_id)
        details.append(("profile name", prof_name))
        details.append(("profile ID", prof_id))
        
        # Add audit history
        for i, audit in enumerate(booking.get("auditHistory", []), start=1):
            combined = (
                f"msg: {audit.get('msg','')}\n"
                f"user: {audit.get('user','')}\n"
                f"rev: {audit.get('rev','')}\n"
                f"ts: {audit.get('ts','')}"
            )
            details.append((f"auditHistory[{i}]", combined))
        
        # Add resource data
        res_data = service.get("res")
        if res_data is not None:
            details.append(("res", json.dumps(res_data, indent=2)))
        
        return details
    
    async def fetch_group_connection(self, group_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a group connection by ID.
        
        Args:
            group_id: The ID of the group connection.
            
        Returns:
            The group connection data or None if not found or if client is not set.
        """
        if not self.client:
            return None
        
        try:
            group_svc = self.current_services.get(group_id)
            if not group_svc:
                group_svc = await self._run_api_call(self.client.fetch_single_group_connection, group_id)
                if group_svc:
                    self.current_services[group_id] = group_svc
            return group_svc
        except Exception as e:
            logger.error(f"Error fetching group connection {group_id}: {e}")
            return None
    
    async def save_services(self, services: Dict[str, Any], file_path: str) -> None:
        """
        Save services to a file.
        
        Args:
            services: Dictionary of services to save.
            file_path: Path to save the services to.
            
        Raises:
            ServiceManagerError: If saving fails.
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(services, f, indent=2)
        except Exception as e:
            raise ServiceManagerError(f"Failed to save services: {e}")
    
    async def load_services(self, file_path: str) -> Dict[str, Any]:
        """
        Load services from a file.
        
        Args:
            file_path: Path to load services from.
            
        Returns:
            Dictionary of loaded services.
            
        Raises:
            ServiceManagerError: If loading fails.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise ServiceManagerError(f"Failed to load services: {e}")
    
    async def create_services(self, services: Dict[str, Any], selected_ids: Set[str]) -> Dict[str, Any]:
        """
        Create services on the server.
        
        Args:
            services: Dictionary of services to create.
            selected_ids: Set of service IDs to create.
            
        Returns:
            Dictionary with results of the operation.
            
        Raises:
            ServiceManagerError: If client is not set or API call fails.
        """
        if not self.client:
            raise ServiceManagerError("Client not set")
        
        # Build the list of entries from the selected services
        entries = [services[service_id] for service_id in selected_ids if service_id in services]
        
        payload = {
            "header": {"id": 1},
            "data": {
                "conflictStrategy": 0,
                "bookingStrategy": 2,
                "entries": entries
            }
        }
        
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.client._request(
                    "POST",
                    f"{self.client.base_url}/api/setModernServices",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
            )
            resp_json = response.json()
        except Exception as e:
            raise ServiceManagerError(f"Failed to create services: {e}")
        
        # Parse the response
        data = resp_json.get("data", {})
        entriesLink = data.get("entriesLink", [])
        bookresult = data.get("bookresult", {})
        details = bookresult.get("details", {})
        
        # Analyze results
        success_count = 0
        failed_services = []
        
        for link in entriesLink:
            entry_id = link.get("id")
            if link.get("error") is None and entry_id:
                detail = details.get(entry_id, {})
                if detail.get("status", 0) == 0:
                    success_count += 1
                else:
                    failed_services.append((entry_id, f"Status {detail.get('status')}"))
            else:
                error_msg = link.get("error", "Unknown error")
                failed_services.append((entry_id if entry_id else "Unknown", error_msg))
        
        return {
            "total": len(entries),
            "success_count": success_count,
            "failed_services": failed_services
        }
    
    async def cancel_services(self, service_ids: List[str]) -> Dict[str, Any]:
        """
        Cancel services.
        
        Args:
            service_ids: List of service IDs to cancel.
            
        Returns:
            Dictionary with results of the operation.
            
        Raises:
            ServiceManagerError: If client is not set or API call fails.
        """
        if not self.client:
            raise ServiceManagerError("Client not set")
        
        entries = []
        for service_id in service_ids:
            service_data = self.current_services.get(service_id)
            if not service_data:
                raise ServiceManagerError(f"Service {service_id} not found")
            
            booking_data = service_data.get("booking")
            if not booking_data:
                raise ServiceManagerError(f"Could not find booking data for service {service_id}")
            
            revision = booking_data.get("rev")
            if revision is None:
                raise ServiceManagerError(f"Could not retrieve revision for service {service_id}")
            
            entries.append({"id": service_id, "rev": revision})
        
        payload = {
            "header": {"id": 1},
            "data": {
                "conflictStrategy": 0,
                "bookingStrategy": 2,
                "entries": entries
            }
        }
        
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.client._request(
                    "POST",
                    f"{self.client.base_url}/api/cancelModernServices",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
            )
            response_json = response.json()
        except Exception as e:
            raise ServiceManagerError(f"Failed to cancel services: {e}")
        
        if not response_json.get('header', {}).get('ok'):
            raise ServiceManagerError(f"API call failed: {response_json.get('header', {}).get('msg')}")
        
        # Process response
        data = response_json.get("data", {})
        entries_link = data.get("entriesLink", [])
        bookresult = data.get("bookresult", {})
        details = bookresult.get("details", {})
        
        success_count = 0
        failed_services = []
        
        for link in entries_link:
            service_id = link.get("id")
            if link.get("error") is None and service_id:
                detail = details.get(service_id, {})
                if detail.get("status") == 0:  # 0 is success
                    success_count += 1
                else:
                    failed_services.append((service_id, f"Status {detail.get('status')}"))
            else:
                error_msg = link.get("error", "Unknown error")
                failed_services.append((service_id if service_id else "Unknown", error_msg))
        
        return {
            "total": len(entries),
            "success_count": success_count,
            "failed_services": failed_services
        }
    
    def prepare_services_for_export(self, service_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Prepare services for export to file.
        
        Args:
            service_ids: List of service IDs to export.
            
        Returns:
            Dictionary of prepared services for export.
            
        Raises:
            ServiceManagerError: If any service is not found.
        """
        modern_services_to_save = {}
        
        for service_id in service_ids:
            service_data = self.current_services.get(service_id)
            if not service_data:
                raise ServiceManagerError(f"Service {service_id} not found")
            
            booking = service_data.get("booking", {})
            
            # Parse timestamps
            try:
                start_ts = int(booking.get("start", 0))
            except:
                start_ts = 0
                
            try:
                end_ts = int(booking.get("end", 0))
            except:
                end_ts = 0
            
            # Extract device labels from descriptor label if formatted as "Source -> Destination"
            descriptor = booking.get("descriptor", {})
            descriptor_label = descriptor.get("label", "")
            
            if "->" in descriptor_label:
                parts = descriptor_label.split("->")
                from_label = parts[0].strip()
                to_label = parts[1].strip() if len(parts) > 1 else ""
            else:
                from_label = booking.get("from", "")
                to_label = booking.get("to", "")
            
            # Get profile id and then the profile name from the mapping
            profile_id = booking.get("profile", "")
            profile_name = self.profile_mapping.get(profile_id, profile_id) if profile_id else ""
            
            modern_entry = {
                "scheduleInfo": {
                    "startTimestamp": start_ts,
                    "type": "once",
                    "endTimestamp": end_ts
                },
                "locked": False,
                "serviceDefinition": {
                    "from": booking.get("from", ""),
                    "to": booking.get("to", ""),
                    "fromLabel": from_label,
                    "toLabel": to_label,
                    "allocationState": booking.get("allocationState", 0),
                    "descriptor": {
                        "desc": descriptor.get("desc", ""),
                        "label": descriptor_label
                    },
                    "profileId": profile_id,
                    "profileName": profile_name,
                    "tags": booking.get("tags", []),
                    "type": "connection",
                    "ctype": 2
                }
            }
            
            modern_services_to_save[service_id] = modern_entry
        
        return modern_services_to_save