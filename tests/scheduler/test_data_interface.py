import pytest
import httpx
from unittest.mock import patch, MagicMock, call
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

# Use corrected imports
from scheduler import data_interface

# Import internal models for verifying conversions
from scheduler.models import (
    Technician, Job, Order, Service, Equipment, Address, CustomerVehicle,
    CustomerType, JobStatus, Van, ServiceCategory
)

# Import API models used by data_interface
from scheduler.api.models import (
    AddressResponse, EquipmentResponse, VanResponse, TechnicianResponse,
    ServiceResponse, CustomerVehicleResponse, OrderResponse, JobResponse,
    EquipmentRequirementResponse, JobAssignmentRequest, JobScheduleRequest,
    JobETAUpdate, JobETABulkRequest, EquipmentType, ServiceCategory as APIServiceCategory,
    CustomerType as APICustomerType, JobStatus as APIJobStatus
)

# --- Fixtures --- 

@pytest.fixture
def mock_api_address_json() -> Dict[str, Any]:
    """Mock JSON response for a single address from the API."""
    return {
        "id": 101,
        "street_address": "101 Mock API St",
        "lat": 35.123,
        "lng": -110.456
    }

@pytest.fixture
def mock_make_request():
    """Fixture to mock the _make_request helper function."""
    with patch('scheduler.data_interface._make_request') as mock:
        yield mock

@pytest.fixture
def sample_api_address() -> AddressResponse:
    """Sample API AddressResponse data."""
    return AddressResponse(
        id=1,
        street_address="123 Main St",
        lat=45.5,
        lng=-73.6
    )

@pytest.fixture
def expected_internal_address(sample_api_address: AddressResponse) -> Address:
    """Expected internal Address model corresponding to sample_api_address."""
    return data_interface._api_address_to_internal(sample_api_address)

@pytest.fixture
def sample_api_equipment() -> List[EquipmentResponse]:
    """Sample list of API EquipmentResponse data."""
    return [
        EquipmentResponse(id=101, equipment_type=EquipmentType.ADAS, model="Autel ADAS"),
        EquipmentResponse(id=102, equipment_type=EquipmentType.PROG, model="ProgrammerX")
    ]

@pytest.fixture
def sample_api_van(sample_api_equipment: List[EquipmentResponse]) -> VanResponse:
    """Sample API VanResponse data."""
    return VanResponse(
        id=51,
        last_service=datetime(2023, 10, 1),
        next_service=datetime(2024, 10, 1),
        vin="VAN1VIN",
        equipment=sample_api_equipment
    )

@pytest.fixture
def sample_api_technician(sample_api_address: AddressResponse, sample_api_van: VanResponse) -> TechnicianResponse:
    """Sample API TechnicianResponse data."""
    tech_uuid = uuid.uuid4()
    return TechnicianResponse(
        id=11,
        user_id=tech_uuid,
        assigned_van_id=sample_api_van.id,
        workload=5,
        home_address=sample_api_address,
        current_location=sample_api_address, # Assume same for simplicity
        assigned_van=sample_api_van
    )

@pytest.fixture
def expected_internal_technician(sample_api_technician: TechnicianResponse) -> Technician:
    """Expected internal Technician model corresponding to sample_api_technician."""
    return data_interface._api_technician_to_internal(sample_api_technician)

@pytest.fixture
def sample_api_service() -> ServiceResponse:
    """Sample API ServiceResponse data."""
    return ServiceResponse(
        id=201,
        service_name="Windshield Camera Calibration",
        service_category=APIServiceCategory.ADAS
    )

@pytest.fixture
def expected_internal_service(sample_api_service: ServiceResponse) -> Service:
    """Expected internal Service model corresponding to sample_api_service."""
    return data_interface._api_service_to_internal(sample_api_service)

@pytest.fixture
def sample_api_vehicle() -> CustomerVehicleResponse:
    """Sample API CustomerVehicleResponse data."""
    return CustomerVehicleResponse(
        id=301,
        vin="1HGCM82633A004352",  # Updated to valid 17-character VIN
        make="Honda",
        year=2022,
        model="Civic",
        ymm_id=999 # Example ymm_id
    )

@pytest.fixture
def expected_internal_vehicle(sample_api_vehicle: CustomerVehicleResponse) -> CustomerVehicle:
    """Expected internal CustomerVehicle model corresponding to sample_api_vehicle."""
    return data_interface._api_vehicle_to_internal(sample_api_vehicle)

@pytest.fixture
def sample_api_order(sample_api_address: AddressResponse, sample_api_vehicle: CustomerVehicleResponse, sample_api_service: ServiceResponse) -> OrderResponse:
    """Sample API OrderResponse data."""
    user_uuid = uuid.uuid4()
    return OrderResponse(
        id=401,
        user_id=user_uuid,
        vehicle_id=sample_api_vehicle.id,
        repair_order_number="RO123",
        address_id=sample_api_address.id,
        earliest_available_time=datetime(2024, 5, 20, 9, 0),
        notes="Customer waiting",
        invoice=None,
        customer_type=APICustomerType.COMMERCIAL,
        address=sample_api_address,
        vehicle=sample_api_vehicle,
        services=[sample_api_service] # List of services
    )

@pytest.fixture
def expected_internal_order(sample_api_order: OrderResponse) -> Order:
    """Expected internal Order model corresponding to sample_api_order."""
    return data_interface._api_order_to_internal(sample_api_order)

@pytest.fixture
def sample_api_job(sample_api_order: OrderResponse, sample_api_address: AddressResponse) -> JobResponse:
    """Sample API JobResponse data."""
    return JobResponse(
        id=501,
        order_id=sample_api_order.id,
        service_id=sample_api_order.services[0].id,  # Add the service_id from the first service in the order
        assigned_technician=None,
        address_id=sample_api_address.id,
        priority=2,
        status=APIJobStatus.PENDING_REVIEW,
        requested_time=datetime(2024, 5, 20, 10, 0),
        estimated_sched=None,
        estimated_sched_end=None,
        customer_eta_start=None,
        customer_eta_end=None,
        job_duration=60, # Duration in minutes
        notes="Focus on camera alignment",
        fixed_assignment=False,
        fixed_schedule_time=None,
        order_ref=sample_api_order, # Nested order details
        address=sample_api_address, # Nested address details
        equipment_requirements=["Autel ADAS", "Leveling Kit"] # Example requirements
    )

@pytest.fixture
def expected_internal_job(sample_api_job: JobResponse) -> Job:
    """Expected internal Job model corresponding to sample_api_job."""
    return data_interface._api_job_to_internal(sample_api_job)

@pytest.fixture
def sample_api_equip_req_adas() -> EquipmentRequirementResponse:
    """Sample API EquipmentRequirementResponse for ADAS."""
    return EquipmentRequirementResponse(ymm_id=999, service_id=201, equipment_models=["Autel ADAS", "Target Set A"])

@pytest.fixture
def sample_api_equip_req_prog() -> EquipmentRequirementResponse:
    """Sample API EquipmentRequirementResponse for PROG."""
    return EquipmentRequirementResponse(ymm_id=999, service_id=202, equipment_models=["ProgrammerX"])

@pytest.fixture
def sample_job_etas_update() -> Dict[int, Dict[str, Optional[datetime]]]:
    """Sample data for updating job ETAs."""
    now = datetime.utcnow()
    return {
        501: {
            'estimated_sched': now + timedelta(hours=1),
            'estimated_sched_end': now + timedelta(hours=2),
            'customer_eta_start': now + timedelta(hours=1, minutes=15),
            'customer_eta_end': now + timedelta(hours=1, minutes=45)
        },
        502: {
            'estimated_sched': now + timedelta(hours=3),
            'estimated_sched_end': now + timedelta(hours=4),
            'customer_eta_start': None, # Test handling None
            'customer_eta_end': None
        },
        503: { # Test partial update
             'customer_eta_start': now + timedelta(hours=5),
             'customer_eta_end': now + timedelta(hours=6)
        }
    }

@pytest.fixture
def mock_technician_api_response():
    """Provides a sample API response for fetching technicians."""
    return [
        {
            "id": 1,
            "user_id": "user_uuid_1",
            "full_name": "John Doe",
            "workload": 5,
            "assigned_van": {
                "id": 101,
                "vin": "VAN123",
                "last_service": "2023-01-15T09:00:00+00:00",
                "next_service": "2024-01-15T09:00:00+00:00",
                "equipment": [
                    {"id": 1, "equipment_type": "adas", "model": "Autel 909"}, 
                    {"id": 2, "equipment_type": "prog", "model": "IM608"}
                    ]
            },
            "home_address": {
                "id": 201,
                "street_address": "123 Main St",
                "lat": 40.7128,
                "lng": -74.0060
            }
        },
        # Add more technicians if needed for testing different scenarios
    ]

@pytest.fixture
def expected_technician_internal_model():
    """Provides the expected internal Technician model corresponding to the API response."""
    mock_user_uuid = uuid.uuid4()
    return [
        Technician(
            id=1,
            user_id=mock_user_uuid,
            workload=5,
            assigned_van_id=101,
            assigned_van=Van(
                id=101,
                vin="VAN123",
                last_service=datetime.fromisoformat("2023-01-15T09:00:00+00:00"),
                next_service=datetime.fromisoformat("2024-01-15T09:00:00+00:00"),
                equipment=[
                    Equipment(id=1, equipment_type="adas", model="Autel 909"),
                    Equipment(id=2, equipment_type="prog", model="IM608")
                ]
            ),
            home_address=Address(
                id=201,
                street_address="123 Main St",
                lat=40.7128,
                lng=-74.0060
            ),
            current_location=Address(id=201, street_address="123 Main St", lat=40.7128, lng=-74.0060),
            schedule={}, # Initialize schedule
            availability_windows={}, # Initialize availability
            queue=[] # Initialize queue
        )
    ]

# --- Test Cases --- 

@patch('scheduler.data_interface._make_request')
def test_fetch_address_by_id_success(mock_make_request, mock_api_address_json):
    """Test fetch_address_by_id successful API call and conversion."""
    # Configure the mock response for _make_request
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = mock_api_address_json
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    address_id_to_fetch = mock_api_address_json['id']

    # Call the function under test
    result = data_interface.fetch_address_by_id(address_id_to_fetch)

    # Assertions
    mock_make_request.assert_called_once_with("GET", f"/addresses/{address_id_to_fetch}")
    assert isinstance(result, Address)
    assert result.id == mock_api_address_json['id']
    assert result.street_address == mock_api_address_json['street_address']
    assert result.lat == mock_api_address_json['lat']
    assert result.lng == mock_api_address_json['lng']


@patch('scheduler.data_interface._make_request')
def test_fetch_address_by_id_not_found(mock_make_request):
    """Test fetch_address_by_id handles API 404 Not Found error."""
    # Configure the mock to raise an error simulating a 404
    mock_make_request.side_effect = ValueError("API returned an error: 404 - Not Found")

    # Call the function under test
    result = data_interface.fetch_address_by_id(999)

    # Assertions
    mock_make_request.assert_called_once_with("GET", f"/addresses/999")
    assert result is None # Expect None on 404 based on current implementation


@patch('scheduler.data_interface._make_request')
def test_fetch_address_by_id_connection_error(mock_make_request):
    """Test fetch_address_by_id handles connection error."""
    # Configure the mock to raise a connection error
    mock_make_request.side_effect = ConnectionError("API request failed")

    # Call the function under test
    result = data_interface.fetch_address_by_id(123)

    # Assertions
    mock_make_request.assert_called_once_with("GET", f"/addresses/123")
    assert result is None # Expect None on ConnectionError based on current implementation


# TODO: Add tests for remaining data_interface functions 

def test_fetch_address_by_id_success(mock_make_request: MagicMock, sample_api_address: AddressResponse, expected_internal_address: Address):
    """Test fetch_address_by_id successfully retrieves and converts an address."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = sample_api_address.dict()
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response
    
    address_id = 1

    # Act
    result = data_interface.fetch_address_by_id(address_id)

    # Assert
    mock_make_request.assert_called_once_with("GET", f"/addresses/{address_id}")
    assert result == expected_internal_address
    mock_response.json.assert_called_once() # Ensure JSON parsing happened

def test_fetch_address_by_id_not_found(mock_make_request: MagicMock):
    """Test fetch_address_by_id returns None when API returns 404."""
    # Arrange
    address_id = 999
    # Simulate API raising ValueError for 404 via raise_for_status in the real _make_request
    mock_make_request.side_effect = ValueError("API returned an error: 404 - Not Found")

    # Act
    result = data_interface.fetch_address_by_id(address_id)

    # Assert
    mock_make_request.assert_called_once_with("GET", f"/addresses/{address_id}")
    assert result is None

def test_fetch_address_by_id_connection_error(mock_make_request: MagicMock):
    """Test fetch_address_by_id returns None on ConnectionError."""
    # Arrange
    address_id = 1
    # Simulate _make_request raising ConnectionError
    mock_make_request.side_effect = ConnectionError("API request failed: Network error")

    # Act
    result = data_interface.fetch_address_by_id(address_id)

    # Assert
    mock_make_request.assert_called_once_with("GET", f"/addresses/{address_id}")
    assert result is None

def test_fetch_address_by_id_other_api_error(mock_make_request: MagicMock):
    """Test fetch_address_by_id raises ValueError for non-404 API errors."""
    # Arrange
    address_id = 1
    # Simulate API raising ValueError for 500 via raise_for_status
    mock_make_request.side_effect = ValueError("API returned an error: 500 - Internal Server Error")

    # Act & Assert
    with pytest.raises(ValueError, match="API returned an error: 500"):
        data_interface.fetch_address_by_id(address_id)
    
    mock_make_request.assert_called_once_with("GET", f"/addresses/{address_id}")

# --- Tests for fetch_all_active_technicians ---

@patch('scheduler.data_interface._make_request')
def test_fetch_all_technicians_success(
    mock_make_request, 
    mock_technician_api_response, 
    expected_technician_internal_model
):
    """Test successfully fetching all technicians and converting to internal models."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_technician_api_response
    mock_make_request.return_value = mock_response

    # Act
    technicians = data_interface.fetch_all_technicians()

    # Assert
    mock_make_request.assert_called_once_with("GET", "/api/v1/technicians")
    assert technicians == expected_technician_internal_model
    # Check conversion details if necessary
    assert technicians[0].id == expected_technician_internal_model[0].id
    assert technicians[0].assigned_van.vin == expected_technician_internal_model[0].assigned_van.vin
    assert len(technicians[0].assigned_van.equipment) == len(expected_technician_internal_model[0].assigned_van.equipment)
    assert technicians[0].home_address.lat == expected_technician_internal_model[0].home_address.lat


@patch('scheduler.data_interface._make_request')
def test_fetch_all_technicians_api_error(mock_make_request):
    """Test handling of API error (e.g., 500) when fetching technicians."""
    # Arrange
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )
    mock_make_request.return_value = mock_response

    # Act & Assert
    with pytest.raises(httpx.HTTPStatusError): # Or a custom exception if data_interface wraps it
        data_interface.fetch_all_technicians()
    
    mock_make_request.assert_called_once_with("GET", "/api/v1/technicians")


@patch('scheduler.data_interface._make_request')
def test_fetch_all_technicians_network_error(mock_make_request):
    """Test handling of network errors during technician fetch."""
    # Arrange
    mock_make_request.side_effect = httpx.RequestError("Connection failed")

    # Act & Assert
    with pytest.raises(httpx.RequestError):
        data_interface.fetch_all_technicians()

    mock_make_request.assert_called_once_with("GET", "/api/v1/technicians")

# --- Tests for fetch_pending_jobs ---

@patch('scheduler.data_interface._make_request')
def test_fetch_pending_jobs_success(mock_make_request: MagicMock, sample_api_job: JobResponse, expected_internal_job: Job):
    """Test fetch_pending_jobs successfully retrieves and converts jobs."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    # API returns a list of jobs
    mock_response.json.return_value = [sample_api_job.dict()] 
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.fetch_pending_jobs()

    # Assert
    mock_make_request.assert_called_once_with("GET", "/jobs/schedulable")
    assert result == [expected_internal_job]
    mock_response.json.assert_called_once()

@patch('scheduler.data_interface._make_request')
def test_fetch_pending_jobs_empty(mock_make_request: MagicMock):
    """Test fetch_pending_jobs returns empty list when API returns empty list."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = [] # Empty list from API
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.fetch_pending_jobs()

    # Assert
    mock_make_request.assert_called_once_with("GET", "/jobs/schedulable")
    assert result == []
    mock_response.json.assert_called_once()

@patch('scheduler.data_interface._make_request')
def test_fetch_pending_jobs_api_error(mock_make_request: MagicMock):
    """Test fetch_pending_jobs returns empty list on API error (ValueError)."""
    # Arrange
    mock_make_request.side_effect = ValueError("API returned an error: 503 - Service Unavailable")

    # Act
    result = data_interface.fetch_pending_jobs()

    # Assert
    mock_make_request.assert_called_once_with("GET", "/jobs/schedulable")
    assert result == [] # Function should handle ValueError and return empty list per implementation

@patch('scheduler.data_interface._make_request')
def test_fetch_pending_jobs_connection_error(mock_make_request: MagicMock):
    """Test fetch_pending_jobs returns empty list on ConnectionError."""
    # Arrange
    mock_make_request.side_effect = ConnectionError("API request failed: Timeout")

    # Act
    result = data_interface.fetch_pending_jobs()

    # Assert
    mock_make_request.assert_called_once_with("GET", "/jobs/schedulable")
    assert result == [] # Function should handle ConnectionError and return empty list per implementation

# --- Tests for fetch_equipment_requirements ---

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_single_service(mock_make_request: MagicMock, sample_api_equip_req_adas: EquipmentRequirementResponse):
    """Test fetching requirements for a single service ID."""
    # Arrange
    ymm_id = 999
    service_id = 201
    expected_requirements = sample_api_equip_req_adas.equipment_models

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = sample_api_equip_req_adas.dict()
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.fetch_equipment_requirements(ymm_id, [service_id])

    # Assert
    mock_make_request.assert_called_once_with("GET", "/equipment/requirements", params={"service_id": service_id, "ymm_id": ymm_id})
    assert sorted(result) == sorted(expected_requirements)
    mock_response.json.assert_called_once()

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_multiple_services(mock_make_request: MagicMock, sample_api_equip_req_adas: EquipmentRequirementResponse, sample_api_equip_req_prog: EquipmentRequirementResponse):
    """Test fetching requirements for multiple service IDs, combining results."""
    # Arrange
    ymm_id = 999
    service_ids = [201, 202]
    # Expected is the union of requirements from both services
    expected_requirements = list(set(sample_api_equip_req_adas.equipment_models + sample_api_equip_req_prog.equipment_models))

    # Mock responses for each call (returning dicts)
    mock_response_adas = MagicMock(spec=httpx.Response)
    mock_response_adas.json.return_value = sample_api_equip_req_adas.dict()
    mock_response_adas.status_code = 200

    mock_response_prog = MagicMock(spec=httpx.Response)
    mock_response_prog.json.return_value = sample_api_equip_req_prog.dict()
    mock_response_prog.status_code = 200

    # Set the side_effect to return the responses in order
    mock_make_request.side_effect = [mock_response_adas, mock_response_prog]

    # Act
    result = data_interface.fetch_equipment_requirements(ymm_id, service_ids)

    # Assert
    expected_calls = [
        call("GET", "/equipment/requirements", params={"service_id": 201, "ymm_id": ymm_id}),
        call("GET", "/equipment/requirements", params={"service_id": 202, "ymm_id": ymm_id})
    ]
    # Use assert_has_calls to check for multiple calls in order
    mock_make_request.assert_has_calls(expected_calls, any_order=False) 
    assert mock_make_request.call_count == 2
    # Sort for comparison
    assert sorted(result) == sorted(expected_requirements) 
    assert mock_response_adas.json.call_count == 1
    assert mock_response_prog.json.call_count == 1

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_partial_failure(mock_make_request: MagicMock, sample_api_equip_req_adas: EquipmentRequirementResponse):
    """Test fetching requirements when one API call fails but others succeed."""
    # Arrange
    ymm_id = 999
    service_ids = [201, 999] # Service 999 will fail
    expected_requirements = sample_api_equip_req_adas.equipment_models # Only expect ADAS reqs

    mock_response_adas = MagicMock(spec=httpx.Response)
    mock_response_adas.json.return_value = sample_api_equip_req_adas.dict()
    mock_response_adas.status_code = 200

    # Simulate failure (e.g., ValueError from _make_request) for the second call
    mock_make_request.side_effect = [
        mock_response_adas, 
        ValueError("API returned an error: 404 - Not Found")
    ]

    # Act
    result = data_interface.fetch_equipment_requirements(ymm_id, service_ids)

    # Assert
    expected_calls = [
        call("GET", "/equipment/requirements", params={"service_id": 201, "ymm_id": ymm_id}),
        call("GET", "/equipment/requirements", params={"service_id": 999, "ymm_id": ymm_id})
    ]
    mock_make_request.assert_has_calls(expected_calls, any_order=False)
    assert mock_make_request.call_count == 2
    # Should only contain results from the successful call
    assert sorted(result) == sorted(expected_requirements) 

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_all_failures(mock_make_request: MagicMock):
    """Test fetching requirements when all API calls fail."""
    # Arrange
    ymm_id = 999
    service_ids = [888, 999]
    
    # Simulate failure for all calls (different error types)
    mock_make_request.side_effect = [
        ConnectionError("Timeout"), 
        ValueError("API returned an error: 500 - Server Error")
    ]

    # Act
    result = data_interface.fetch_equipment_requirements(ymm_id, service_ids)

    # Assert
    expected_calls = [
        call("GET", "/equipment/requirements", params={"service_id": 888, "ymm_id": ymm_id}),
        call("GET", "/equipment/requirements", params={"service_id": 999, "ymm_id": ymm_id})
    ]
    mock_make_request.assert_has_calls(expected_calls, any_order=False)
    assert mock_make_request.call_count == 2
    assert result == [] # Expect empty list on total failure

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_empty_input(mock_make_request: MagicMock):
    """Test fetching requirements with empty service_ids list."""
    # Arrange
    ymm_id = 999
    service_ids = []

    # Act
    result = data_interface.fetch_equipment_requirements(ymm_id, service_ids)

    # Assert
    mock_make_request.assert_not_called() # No API calls should be made
    assert result == []

@patch('scheduler.data_interface._make_request')
def test_fetch_equipment_requirements_invalid_ymm(mock_make_request: MagicMock):
    """Test fetching requirements with invalid ymm_id (0 or None)."""
    # Arrange
    service_ids = [201]

    # Act
    result_zero = data_interface.fetch_equipment_requirements(0, service_ids)
    result_none = data_interface.fetch_equipment_requirements(None, service_ids)

    # Assert
    mock_make_request.assert_not_called() # No API calls should be made
    assert result_zero == []
    assert result_none == []

# --- Tests for update_job_assignment ---

@patch('scheduler.data_interface._make_request')
def test_update_job_assignment_success_with_tech(mock_make_request: MagicMock):
    """Test successful job assignment update with a technician ID."""
    # Arrange
    job_id = 501
    technician_id = 11
    status = JobStatus.ASSIGNED
    expected_api_status = "assigned" # String value expected by API
    # Build the expected Pydantic request model
    expected_payload = JobAssignmentRequest(assigned_technician=technician_id, status=expected_api_status)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200 # Successful PATCH indicates success
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.update_job_assignment(job_id, technician_id, status)

    # Assert
    assert result is True
    # Check call arguments, comparing the json payload against the .dict() of the expected Pydantic model
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/assignment", 
        json=expected_payload.dict(exclude_unset=True) # Use exclude_unset as per implementation
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_assignment_success_no_tech(mock_make_request: MagicMock):
    """Test successful job assignment update setting technician ID to None."""
    # Arrange
    job_id = 502
    technician_id = None
    status = JobStatus.PENDING_REVIEW
    expected_api_status = "pending_review"
    expected_payload = JobAssignmentRequest(assigned_technician=technician_id, status=expected_api_status)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.update_job_assignment(job_id, technician_id, status)

    # Assert
    assert result is True
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/assignment", 
        json=expected_payload.dict(exclude_unset=True) 
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_assignment_api_error(mock_make_request: MagicMock):
    """Test job assignment update returns False on API error (e.g., 400, 500)."""
    # Arrange
    job_id = 503
    technician_id = 12
    status = JobStatus.SCHEDULED
    expected_api_status = "scheduled"
    expected_payload = JobAssignmentRequest(assigned_technician=technician_id, status=expected_api_status)
    
    # Simulate API error via _make_request raising ValueError
    mock_make_request.side_effect = ValueError("API returned an error: 400 - Bad Request")

    # Act
    result = data_interface.update_job_assignment(job_id, technician_id, status)

    # Assert
    assert result is False # Expect False on failure
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/assignment", 
        json=expected_payload.dict(exclude_unset=True)
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_assignment_connection_error(mock_make_request: MagicMock):
    """Test job assignment update returns False on ConnectionError."""
    # Arrange
    job_id = 504
    technician_id = 13
    status = JobStatus.ASSIGNED
    expected_api_status = "assigned"
    expected_payload = JobAssignmentRequest(assigned_technician=technician_id, status=expected_api_status)
    
    # Simulate connection error via _make_request raising ConnectionError
    mock_make_request.side_effect = ConnectionError("Network unreachable")

    # Act
    result = data_interface.update_job_assignment(job_id, technician_id, status)

    # Assert
    assert result is False # Expect False on failure
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/assignment", 
        json=expected_payload.dict(exclude_unset=True)
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_assignment_invalid_status(mock_make_request: MagicMock):
    """Test job assignment update returns False for an unknown internal status enum value."""
    # Arrange
    job_id = 505
    technician_id = 14
    # Create a mock object that mimics an enum member but isn't one of the valid JobStatus values
    invalid_status = MagicMock(spec=JobStatus, name='INVALID_STATUS') 
    # Ensure accessing .name or .value doesn't crash if the mapping logic tries it
    invalid_status.value = 'invalid_status_value' 

    # Act
    # The function should catch the invalid status before making an API call
    result = data_interface.update_job_assignment(job_id, technician_id, invalid_status)

    # Assert
    assert result is False # Expect False because status mapping will fail
    mock_make_request.assert_not_called() # API call should NOT be made

# --- Tests for update_job_etas ---

def test_update_job_etas_success(mock_make_request: MagicMock, sample_job_etas_update: Dict):
    """Test successful bulk update of job ETAs."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Construct expected API payload
    expected_api_updates = [
        JobETAUpdate(job_id=501, **{k: v for k, v in sample_job_etas_update[501].items() if v is not None}),
        JobETAUpdate(job_id=502, **{k: v for k, v in sample_job_etas_update[502].items() if v is not None}),
        JobETAUpdate(job_id=503, **{k: v for k, v in sample_job_etas_update[503].items() if v is not None}),
    ]
    expected_payload = JobETABulkRequest(jobs=expected_api_updates)

    # Act
    result = data_interface.update_job_etas(sample_job_etas_update)

    # Assert
    assert result is True
    mock_make_request.assert_called_once_with(
        "PATCH", 
        "/jobs/etas", 
        json=expected_payload.dict() # .dict() needed for comparison
    )

def test_update_job_etas_empty_input(mock_make_request: MagicMock):
    """Test update_job_etas with an empty input dictionary."""
    # Arrange
    job_etas = {}

    # Act
    result = data_interface.update_job_etas(job_etas)

    # Assert
    assert result is True # Should return True for no-op
    mock_make_request.assert_not_called()

def test_update_job_etas_empty_updates_after_filter(mock_make_request: MagicMock):
    """Test update_job_etas when all updates filter out (e.g., all Nones)."""
    # Arrange
    job_etas = {
        601: {
            'estimated_sched': None,
            'estimated_sched_end': None,
            'customer_eta_start': None,
            'customer_eta_end': None
        }
    }

    # Act
    result = data_interface.update_job_etas(job_etas)

    # Assert
    assert result is True # Should return True for no-op
    mock_make_request.assert_not_called()

def test_update_job_etas_api_error(mock_make_request: MagicMock, sample_job_etas_update: Dict):
    """Test update_job_etas returns False on API error."""
    # Arrange
    mock_make_request.side_effect = ValueError("API returned an error: 500")
    # Construct expected payload for assertion
    expected_api_updates = [
        JobETAUpdate(job_id=501, **{k: v for k, v in sample_job_etas_update[501].items() if v is not None}),
        JobETAUpdate(job_id=502, **{k: v for k, v in sample_job_etas_update[502].items() if v is not None}),
        JobETAUpdate(job_id=503, **{k: v for k, v in sample_job_etas_update[503].items() if v is not None}),
    ]
    expected_payload = JobETABulkRequest(jobs=expected_api_updates)

    # Act
    result = data_interface.update_job_etas(sample_job_etas_update)

    # Assert
    assert result is False
    mock_make_request.assert_called_once_with(
        "PATCH", 
        "/jobs/etas", 
        json=expected_payload.dict()
    )

def test_update_job_etas_connection_error(mock_make_request: MagicMock, sample_job_etas_update: Dict):
    """Test update_job_etas returns False on ConnectionError."""
    # Arrange
    mock_make_request.side_effect = ConnectionError("Timeout")
    # Construct expected payload for assertion
    expected_api_updates = [
        JobETAUpdate(job_id=501, **{k: v for k, v in sample_job_etas_update[501].items() if v is not None}),
        JobETAUpdate(job_id=502, **{k: v for k, v in sample_job_etas_update[502].items() if v is not None}),
        JobETAUpdate(job_id=503, **{k: v for k, v in sample_job_etas_update[503].items() if v is not None}),
    ]
    expected_payload = JobETABulkRequest(jobs=expected_api_updates)

    # Act
    result = data_interface.update_job_etas(sample_job_etas_update)

    # Assert
    assert result is False
    mock_make_request.assert_called_once_with(
        "PATCH", 
        "/jobs/etas", 
        json=expected_payload.dict()
    )

# --- Tests for update_job_fixed_schedule ---

@patch('scheduler.data_interface._make_request')
def test_update_job_fixed_schedule_success_set_time(mock_make_request: MagicMock):
    """Test successfully setting a fixed schedule time via API."""
    # Arrange
    job_id = 701
    # Use a specific, non-naive datetime for testing
    fixed_time = datetime(2024, 6, 1, 14, 30, 0, tzinfo=None) # Example fixed time 
    expected_payload = JobScheduleRequest(fixed_schedule_time=fixed_time)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200 # Success status
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.update_job_fixed_schedule(job_id, fixed_time)

    # Assert
    assert result is True
    # Verify the call includes the time, using exclude_none=True as per implementation
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/schedule", 
        json=expected_payload.dict(exclude_none=True) 
    )
    # Double check that the time is actually in the payload sent
    call_args, call_kwargs = mock_make_request.call_args
    assert 'json' in call_kwargs
    assert call_kwargs['json']['fixed_schedule_time'] == fixed_time.isoformat()

@patch('scheduler.data_interface._make_request')
def test_update_job_fixed_schedule_success_clear_time(mock_make_request: MagicMock):
    """Test successfully clearing a fixed schedule time (setting to None) via API."""
    # Arrange
    job_id = 702
    fixed_time = None
    # When fixed_time is None, exclude_none=True should result in an empty JSON object {} 
    expected_payload = JobScheduleRequest(fixed_schedule_time=fixed_time)
    expected_json = expected_payload.dict(exclude_none=True)
    assert expected_json == {} # Payload should be empty

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_make_request.return_value = mock_response

    # Act
    result = data_interface.update_job_fixed_schedule(job_id, fixed_time)

    # Assert
    assert result is True
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/schedule", 
        json=expected_json # Should be called with empty json {}
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_fixed_schedule_api_error(mock_make_request: MagicMock):
    """Test update_job_fixed_schedule returns False on API error."""
    # Arrange
    job_id = 703
    fixed_time = datetime(2024, 6, 2, 9, 0, 0)
    expected_payload = JobScheduleRequest(fixed_schedule_time=fixed_time)
    
    # Simulate API error
    mock_make_request.side_effect = ValueError("API returned an error: 404 - Job not found")

    # Act
    result = data_interface.update_job_fixed_schedule(job_id, fixed_time)

    # Assert
    assert result is False # Expect False on failure
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/schedule", 
        json=expected_payload.dict(exclude_none=True)
    )

@patch('scheduler.data_interface._make_request')
def test_update_job_fixed_schedule_connection_error(mock_make_request: MagicMock):
    """Tests handling a connection error when updating a job's fixed schedule time."""
    # Arrange
    mock_make_request.side_effect = ConnectionError("Network error")
    job_id = 501
    fixed_time = datetime(2024, 6, 10, 15, 0)
    
    # Act
    result = data_interface.update_job_fixed_schedule(job_id, fixed_time)
    
    # Assert
    assert result is False
    mock_make_request.assert_called_once_with(
        "PATCH", 
        f"/jobs/{job_id}/schedule", 
        json={"fixed_schedule_time": fixed_time.isoformat()}
    )

# --- Tests for fetch_jobs function ---

@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_no_filters(mock_make_request: MagicMock, sample_api_job: JobResponse, expected_internal_job: Job):
    """Tests fetching jobs without any filters."""
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_api_job.dict()]
    mock_make_request.return_value = mock_response
    
    # Act
    result = data_interface.fetch_jobs()
    
    # Assert
    assert len(result) == 1
    assert result[0].id == expected_internal_job.id
    assert result[0].status == expected_internal_job.status
    mock_make_request.assert_called_once_with("GET", "/jobs", params={})


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_filter_by_technician(mock_make_request: MagicMock, sample_api_job: JobResponse, expected_internal_job: Job):
    """Tests fetching jobs filtered by technician_id."""
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_api_job.dict()]
    mock_make_request.return_value = mock_response
    technician_id = 101
    
    # Act
    result = data_interface.fetch_jobs(technician_id=technician_id)
    
    # Assert
    assert len(result) == 1
    assert result[0].id == expected_internal_job.id
    mock_make_request.assert_called_once_with("GET", "/jobs", params={"technician_id": technician_id})


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_filter_by_status(mock_make_request: MagicMock, sample_api_job: JobResponse, expected_internal_job: Job):
    """Tests fetching jobs filtered by status."""
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_api_job.dict()]
    mock_make_request.return_value = mock_response
    status = JobStatus.ASSIGNED
    
    # Act
    result = data_interface.fetch_jobs(status=status)
    
    # Assert
    assert len(result) == 1
    assert result[0].id == expected_internal_job.id
    mock_make_request.assert_called_once_with("GET", "/jobs", params={"status": status.value})


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_filter_by_technician_and_status(mock_make_request: MagicMock, sample_api_job: JobResponse, expected_internal_job: Job):
    """Tests fetching jobs filtered by both technician_id and status."""
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [sample_api_job.dict()]
    mock_make_request.return_value = mock_response
    technician_id = 101
    status = JobStatus.ASSIGNED
    
    # Act
    result = data_interface.fetch_jobs(technician_id=technician_id, status=status)
    
    # Assert
    assert len(result) == 1
    assert result[0].id == expected_internal_job.id
    mock_make_request.assert_called_once_with("GET", "/jobs", params={
        "technician_id": technician_id,
        "status": status.value
    })


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_empty_result(mock_make_request: MagicMock):
    """Tests fetching jobs with filters that return no results."""
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = []
    mock_make_request.return_value = mock_response
    
    # Act
    result = data_interface.fetch_jobs(technician_id=999, status=JobStatus.COMPLETED)
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 0
    mock_make_request.assert_called_once()


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_api_error(mock_make_request: MagicMock):
    """Tests handling API errors when fetching jobs."""
    # Arrange
    mock_make_request.side_effect = ValueError("API returned an error: 400 - Invalid parameters")
    
    # Act
    result = data_interface.fetch_jobs()
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 0
    mock_make_request.assert_called_once_with("GET", "/jobs", params={})


@patch('scheduler.data_interface._make_request')
def test_fetch_jobs_connection_error(mock_make_request: MagicMock):
    """Tests handling connection errors when fetching jobs."""
    # Arrange
    mock_make_request.side_effect = ConnectionError("Network error")
    
    # Act
    result = data_interface.fetch_jobs()
    
    # Assert
    assert isinstance(result, list)
    assert len(result) == 0
    mock_make_request.assert_called_once_with("GET", "/jobs", params={})

# --- Add tests for other functions below --- 