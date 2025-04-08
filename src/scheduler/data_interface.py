import httpx
import os
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, timedelta

# Load environment variables for API configuration
load_dotenv()
API_BASE_URL = os.getenv("SCHEDULER_API_BASE_URL", "http://localhost:8000/api/v1") # Default to local if not set
API_KEY = os.getenv("SCHEDULER_API_KEY") 

# Import internal models
from .models import (
    Technician, Job, Order, Service, Equipment, Address, CustomerVehicle, 
    CustomerType, JobStatus, Van, ServiceCategory
)
# Import API response models for conversion
from .api.models import (
    AddressResponse, EquipmentResponse, VanResponse, TechnicianResponse, 
    ServiceResponse, CustomerVehicleResponse, OrderResponse, JobResponse,
    EquipmentRequirementResponse, JobAssignmentRequest, JobScheduleRequest, 
    JobETAUpdate, JobETABulkRequest
)

# --- HTTP Client Setup ---
# Consider making this async if the scheduler is async
# Set timeout to avoid hanging indefinitely
TIMEOUT = httpx.Timeout(10.0, connect=5.0) 
_client = httpx.Client(base_url=API_BASE_URL, timeout=TIMEOUT)

def _get_auth_headers() -> Dict[str, str]:
    """Returns authentication headers for API requests."""
    if not API_KEY:
        # In a real application, you might raise an error or handle this differently
        print("Warning: SCHEDULER_API_KEY environment variable not set.")
        return {} 
    # Correct header name to match server expectation ('api-key' lowercase)
    return {"api-key": API_KEY}

def _make_request(method: str, endpoint: str, **kwargs) -> httpx.Response:
    """Helper function to make API requests with error handling."""
    try:
        response = _client.request(method, endpoint, headers=_get_auth_headers(), **kwargs)
        response.raise_for_status()  # Raise exception for 4xx/5xx errors
        return response
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}: {exc}")
        # Consider more specific error handling or re-raising
        raise ConnectionError(f"API request failed: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}: {exc.response.text}")
        # Re-raise or handle specific status codes
        raise ValueError(f"API returned an error: {exc.response.status_code} - {exc.response.text}") from exc


# --- Conversion Functions (API Response -> Internal Model) ---

def _api_address_to_internal(api_addr: AddressResponse) -> Address:
    """Converts AddressResponse (API) to Address (Internal)."""
    return Address(
        id=api_addr.id,
        street_address=api_addr.street_address,
        lat=api_addr.lat,
        lng=api_addr.lng
    )

def _api_equipment_to_internal(api_equip: EquipmentResponse) -> Equipment:
    """Converts EquipmentResponse (API) to Equipment (Internal)."""
    # Map API EquipmentType enum to internal ServiceCategory enum
    category_map = {
        "adas": ServiceCategory.ADAS,
        "airbag": ServiceCategory.AIRBAG,
        "immo": ServiceCategory.IMMO,
        "prog": ServiceCategory.PROG,
        "diag": ServiceCategory.DIAG,
    }
    internal_category = category_map.get(api_equip.equipment_type.value)
    if internal_category is None:
        raise ValueError(f"Unknown API equipment type: {api_equip.equipment_type}")
        
    return Equipment(
        id=api_equip.id,
        equipment_type=internal_category,
        model=api_equip.model
    )

def _api_van_to_internal(api_van: VanResponse) -> Van:
    """Converts VanResponse (API) to Van (Internal)."""
    return Van(
        id=api_van.id,
        last_service=api_van.last_service,
        next_service=api_van.next_service,
        vin=api_van.vin,
        equipment=[_api_equipment_to_internal(eq) for eq in api_van.equipment]
    )

def _api_service_to_internal(api_svc: ServiceResponse) -> Service:
    """Converts ServiceResponse (API) to Service (Internal)."""
    # Map API ServiceCategory enum to internal ServiceCategory enum
    category_map = {
        "adas": ServiceCategory.ADAS,
        "airbag": ServiceCategory.AIRBAG,
        "immo": ServiceCategory.IMMO,
        "prog": ServiceCategory.PROG,
        "diag": ServiceCategory.DIAG,
    }
    internal_category = category_map.get(api_svc.service_category.value)
    if internal_category is None:
        raise ValueError(f"Unknown API service category: {api_svc.service_category}")
        
    return Service(
        id=api_svc.id,
        service_name=api_svc.service_name,
        service_category=internal_category
    )

def _api_vehicle_to_internal(api_vehicle: CustomerVehicleResponse) -> CustomerVehicle:
    """Converts CustomerVehicleResponse (API) to CustomerVehicle (Internal)."""
    return CustomerVehicle(
        id=api_vehicle.id,
        vin=api_vehicle.vin,
        make=api_vehicle.make,
        year=api_vehicle.year,
        model=api_vehicle.model,
        ymm_id=api_vehicle.ymm_id
    )

def _api_order_to_internal(api_order: OrderResponse) -> Order:
    """Converts OrderResponse (API) to Order (Internal)."""
    # Map API CustomerType enum to internal CustomerType enum
    customer_type_map = {
        "residential": CustomerType.RESIDENTIAL,
        "commercial": CustomerType.COMMERCIAL,
        "insurance": CustomerType.INSURANCE,
    }
    internal_customer_type = customer_type_map.get(api_order.customer_type.value)
    if internal_customer_type is None:
        raise ValueError(f"Unknown API customer type: {api_order.customer_type}")

    return Order(
        id=api_order.id,
        user_id=api_order.user_id,
        vehicle_id=api_order.vehicle_id,
        repair_order_number=api_order.repair_order_number,
        address_id=api_order.address_id,
        earliest_available_time=api_order.earliest_available_time,
        notes=api_order.notes,
        invoice=api_order.invoice,
        customer_type=internal_customer_type,
        address=_api_address_to_internal(api_order.address),
        vehicle=_api_vehicle_to_internal(api_order.vehicle),
        services=[_api_service_to_internal(svc) for svc in api_order.services]
    )

def _api_job_to_internal(api_job: JobResponse) -> Job:
    """Converts JobResponse (API) to Job (Internal)."""
    # Map API JobStatus enum to internal JobStatus enum
    status_map = {
        "pending_review": JobStatus.PENDING_REVIEW,
        "assigned": JobStatus.ASSIGNED,
        "scheduled": JobStatus.SCHEDULED,
        "pending_revisit": JobStatus.PENDING_REVISIT,
        "completed": JobStatus.COMPLETED,
        "cancelled": JobStatus.CANCELLED,
    }
    internal_status = status_map.get(api_job.status.value)
    if internal_status is None:
        raise ValueError(f"Unknown API job status: {api_job.status}")

    # Convert job_duration (minutes in API) to timedelta (internal)
    job_duration_timedelta = timedelta(minutes=api_job.job_duration)

    return Job(
        id=api_job.id,
        order_id=api_job.order_id,
        service_id=api_job.service_id,
        assigned_technician=api_job.assigned_technician,
        address_id=api_job.address_id,
        priority=api_job.priority,
        status=internal_status,
        requested_time=api_job.requested_time,
        estimated_sched=api_job.estimated_sched,
        estimated_sched_end=api_job.estimated_sched_end,
        customer_eta_start=api_job.customer_eta_start,
        customer_eta_end=api_job.customer_eta_end,
        job_duration=job_duration_timedelta, 
        notes=api_job.notes,
        fixed_assignment=api_job.fixed_assignment,
        fixed_schedule_time=api_job.fixed_schedule_time,
        order_ref=_api_order_to_internal(api_job.order_ref),
        address=_api_address_to_internal(api_job.address),
        equipment_requirements=api_job.equipment_requirements # Already list[str]
    )

def _api_technician_to_internal(api_tech: TechnicianResponse) -> Technician:
    """Converts TechnicianResponse (API) to Technician (Internal)."""
    return Technician(
        id=api_tech.id,
        user_id=api_tech.user_id,
        assigned_van_id=api_tech.assigned_van_id,
        workload=api_tech.workload,
        home_address=_api_address_to_internal(api_tech.home_address),
        current_location=_api_address_to_internal(api_tech.current_location) if api_tech.current_location else None,
        assigned_van=_api_van_to_internal(api_tech.assigned_van) if api_tech.assigned_van else None
    )


# --- Data Interface Functions (Using API) ---

def fetch_address_by_id(address_id: int) -> Optional[Address]:
    """Fetches an address by its ID via the API."""
    try:
        response = _make_request("GET", f"/addresses/{address_id}")
        api_addr = AddressResponse(**response.json())
        return _api_address_to_internal(api_addr)
    except ValueError as e: # Handle API 404s gracefully
        if "404" in str(e):
            return None
        raise # Re-raise other errors
    except ConnectionError:
        # Handle connection errors if needed, maybe return None or raise specific exception
        return None

def fetch_all_active_technicians() -> List[Technician]:
    """
    Fetches all active technicians via the API, populating their associated van,
    equipment, home address, and current location.
    """
    try:
        response = _make_request("GET", "/technicians")
        api_technicians = [TechnicianResponse(**tech_data) for tech_data in response.json()]
        return [_api_technician_to_internal(api_tech) for api_tech in api_technicians]
    except (ValueError, ConnectionError):
        # Handle errors - returning empty list might be appropriate
        return []


def fetch_pending_jobs() -> List[Job]:
    """
    Fetches all jobs eligible for scheduling via the API.
    Populates related Order, Address, Vehicle, Services, and CustomerType.
    Also includes equipment requirements for each job.
    """
    try:
        response = _make_request("GET", "/jobs/schedulable")
        api_jobs = [JobResponse(**job_data) for job_data in response.json()]
        return [_api_job_to_internal(api_job) for api_job in api_jobs]
    except (ValueError, ConnectionError):
         # Handle errors - returning empty list might be appropriate
        return []


def fetch_assigned_jobs(technician_id: int) -> List[Job]:
    """
    Fetches all jobs currently assigned to a specific technician via the API.

    Args:
        technician_id: The ID of the technician whose jobs to fetch.

    Returns:
        A list of Job objects assigned to the technician, or empty list on error.
    """
    try:
        # Assuming the API endpoint /jobs supports filtering by technician_id and status
        # Using the internal JobStatus.ASSIGNED enum value
        params = {"technician_id": technician_id, "status": JobStatus.ASSIGNED.value}
        response = _make_request("GET", "/jobs", params=params)
        api_jobs = [JobResponse(**job_data) for job_data in response.json()]
        return [_api_job_to_internal(api_job) for api_job in api_jobs]
    except (ValueError, ConnectionError) as e:
        print(f"Error fetching assigned jobs for technician {technician_id}: {e}")
        # Handle errors - returning empty list might be appropriate
        return []


def fetch_jobs(technician_id: Optional[int] = None, status: Optional[JobStatus] = None) -> List[Job]:
    """
    Fetches jobs via the API, optionally filtering by technician_id and/or status.
    Populates related Order, Address, Vehicle, Services, and other relationships.
    
    Args:
        technician_id: Optional ID of the technician to filter jobs by
        status: Optional JobStatus to filter jobs by
        
    Returns:
        List of Job objects matching the criteria
    """
    try:
        # Build query parameters
        params = {}
        if technician_id is not None:
            params["technician_id"] = technician_id
        if status is not None:
            params["status"] = status.value  # API expects string value from enum
            
        # Make request with query parameters
        response = _make_request("GET", "/jobs", params=params)
        
        # Convert API response to internal models
        api_jobs = [JobResponse(**job_data) for job_data in response.json()]
        return [_api_job_to_internal(api_job) for api_job in api_jobs]
    except (ValueError, ConnectionError) as e:
        # Log the error
        print(f"Error fetching jobs: {str(e)}")
        # Return empty list for graceful handling
        return []


def fetch_equipment_requirements(ymm_id: int, service_ids: List[int]) -> List[str]:
    """
    Fetches the required equipment models via the API for a given vehicle 
    YMM ID and list of service IDs.
    
    Note: The current API endpoint only supports one service_id at a time.
          This function will make multiple API calls if multiple service_ids are provided.
          Consider enhancing the API if batch fetching is needed frequently.
    """
    if not service_ids or not ymm_id:
        return []

    all_requirements = set()
    for service_id in service_ids:
        try:
            params = {"service_id": service_id, "ymm_id": ymm_id}
            response = _make_request("GET", "/equipment/requirements", params=params)
            api_response = EquipmentRequirementResponse(**response.json())
            all_requirements.update(api_response.equipment_models)
        except (ValueError, ConnectionError) as e:
            print(f"Warning: Failed to fetch equipment requirements for service {service_id}, ymm {ymm_id}: {e}")
            # Continue fetching for other services if one fails
            continue
            
    return list(all_requirements)

def update_job_assignment(job_id: int, technician_id: Optional[int], status: JobStatus) -> bool:
    """Updates the assigned technician and status for a job via the API."""
    # Map internal JobStatus enum back to API JobStatus enum string value
    status_map = {
        JobStatus.PENDING_REVIEW: "pending_review",
        JobStatus.ASSIGNED: "assigned",
        JobStatus.SCHEDULED: "scheduled",
        JobStatus.PENDING_REVISIT: "pending_revisit",
        JobStatus.COMPLETED: "completed",
        JobStatus.CANCELLED: "cancelled",
    }
    api_status_value = status_map.get(status)
    if api_status_value is None:
        print(f"Error: Unknown internal job status for API conversion: {status}")
        return False

    request_data = JobAssignmentRequest(
        assigned_technician=technician_id,
        status=api_status_value 
    )
    
    try:
        _make_request("PATCH", f"/jobs/{job_id}/assignment", json=request_data.dict(exclude_unset=True))
        return True
    except (ValueError, ConnectionError) as e:
        print(f"Error updating job assignment via API for job {job_id}: {e}")
        return False

def update_job_etas(job_etas: Dict[int, Dict[str, Optional[datetime]]]) -> bool:
    """
    Updates the ETA fields for multiple jobs via the API.
    
    The job_etas parameter should be a dictionary mapping job IDs to a dictionary
    of ETA field updates (using internal field names), e.g.:
    {
        1: {
            'estimated_sched': datetime(...), 
            'estimated_sched_end': datetime(...),
            'customer_eta_start': datetime(...),
            'customer_eta_end': datetime(...)
        },
        2: { ... }
    }
    """
    if not job_etas:
        return True
        
    # Convert internal ETA dictionary format to API's JobETABulkRequest format
    api_eta_updates: List[JobETAUpdate] = []
    for job_id, eta_fields in job_etas.items():
        # Filter out None values and convert field names if necessary 
        # (API and Internal seem aligned here)
        update_data = {k: v for k, v in eta_fields.items() if v is not None}
        if update_data: # Only add if there are actual updates
            api_eta_updates.append(JobETAUpdate(job_id=job_id, **update_data))

    if not api_eta_updates:
        return True # Nothing to update

    request_data = JobETABulkRequest(jobs=api_eta_updates)
    
    try:
        _make_request("PATCH", "/jobs/etas", json=request_data.dict())
        return True
    except (ValueError, ConnectionError) as e:
        print(f"Error updating job ETAs via API: {e}")
        return False

def update_job_fixed_schedule(job_id: int, fixed_schedule_time: Optional[datetime]) -> bool:
    """Updates the fixed schedule time for a job via the API."""
    request_data = JobScheduleRequest(fixed_schedule_time=fixed_schedule_time)
    
    try:
        _make_request("PATCH", f"/jobs/{job_id}/schedule", json=request_data.dict(exclude_none=True))
        return True
    except (ValueError, ConnectionError) as e:
        print(f"Error updating job fixed schedule time via API for job {job_id}: {e}")
        return False 