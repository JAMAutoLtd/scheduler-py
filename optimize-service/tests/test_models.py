import pytest
from pydantic import ValidationError

from models import (
    LatLngLiteral,
    OptimizationLocation,
    OptimizationTechnician,
    OptimizationItem,
    OptimizationFixedConstraint,
    OptimizationRequestPayload,
    RouteStop,
    TechnicianRoute,
    OptimizationResponsePayload,
)

# Sample valid data for testing
SAMPLE_LAT_LNG = {"lat": 40.7128, "lng": -74.0060}
SAMPLE_LOCATION_1 = {"id": "address_1", "index": 0, "coords": SAMPLE_LAT_LNG}
SAMPLE_LOCATION_2 = {"id": "depot", "index": 1, "coords": {"lat": 40.7580, "lng": -73.9855}}
SAMPLE_TECHNICIAN_1 = {
    "id": 1,
    "startLocationIndex": 0,
    "endLocationIndex": 1,
    "earliestStartTimeISO": "2024-04-10T08:00:00Z",
    "latestEndTimeISO": "2024-04-10T17:00:00Z",
}
SAMPLE_ITEM_1 = {
    "id": "job_123",
    "locationIndex": 0,
    "durationSeconds": 3600,
    "priority": 1,
    "eligibleTechnicianIds": [1],
}
SAMPLE_ITEM_2 = {
    "id": "job_456",
    "locationIndex": 1,
    "durationSeconds": 1800,
    "priority": 2,
    "eligibleTechnicianIds": [1],
}
SAMPLE_FIXED_CONSTRAINT = {
    "itemId": "job_123",
    "fixedTimeISO": "2024-04-10T10:00:00Z",
}
SAMPLE_TRAVEL_MATRIX = {0: {0: 0, 1: 900}, 1: {0: 900, 1: 0}}

SAMPLE_REQUEST_PAYLOAD = {
    "locations": [SAMPLE_LOCATION_1, SAMPLE_LOCATION_2],
    "technicians": [SAMPLE_TECHNICIAN_1],
    "items": [SAMPLE_ITEM_1, SAMPLE_ITEM_2],
    "fixedConstraints": [SAMPLE_FIXED_CONSTRAINT],
    "travelTimeMatrix": SAMPLE_TRAVEL_MATRIX,
}

SAMPLE_ROUTE_STOP_1 = {
    "itemId": "job_123",
    "arrivalTimeISO": "2024-04-10T09:45:00Z",
    "startTimeISO": "2024-04-10T10:00:00Z",
    "endTimeISO": "2024-04-10T11:00:00Z",
}
SAMPLE_TECHNICIAN_ROUTE_1 = {
    "technicianId": 1,
    "stops": [SAMPLE_ROUTE_STOP_1],
    "totalTravelTimeSeconds": 900,
    "totalDurationSeconds": 4500,
}

SAMPLE_RESPONSE_PAYLOAD_SUCCESS = {
    "status": "success",
    "routes": [SAMPLE_TECHNICIAN_ROUTE_1],
    "unassignedItemIds": ["job_456"],
}

SAMPLE_RESPONSE_PAYLOAD_ERROR = {
    "status": "error",
    "message": "Invalid input data",
    "routes": [],
}


def test_lat_lng_literal_valid():
    """Test valid LatLngLiteral instantiation."""
    obj = LatLngLiteral(**SAMPLE_LAT_LNG)
    assert obj.lat == SAMPLE_LAT_LNG["lat"]
    assert obj.lng == SAMPLE_LAT_LNG["lng"]

def test_optimization_location_valid():
    """Test valid OptimizationLocation instantiation."""
    obj = OptimizationLocation(**SAMPLE_LOCATION_1)
    assert obj.id == SAMPLE_LOCATION_1["id"]
    assert obj.index == SAMPLE_LOCATION_1["index"]
    assert obj.coords.lat == SAMPLE_LOCATION_1["coords"]["lat"]
    assert obj.coords.lng == SAMPLE_LOCATION_1["coords"]["lng"]

def test_optimization_technician_valid():
    """Test valid OptimizationTechnician instantiation."""
    obj = OptimizationTechnician(**SAMPLE_TECHNICIAN_1)
    assert obj.id == SAMPLE_TECHNICIAN_1["id"]
    assert obj.startLocationIndex == SAMPLE_TECHNICIAN_1["startLocationIndex"]
    assert obj.endLocationIndex == SAMPLE_TECHNICIAN_1["endLocationIndex"]
    assert obj.earliestStartTimeISO == SAMPLE_TECHNICIAN_1["earliestStartTimeISO"]
    assert obj.latestEndTimeISO == SAMPLE_TECHNICIAN_1["latestEndTimeISO"]

def test_optimization_item_valid():
    """Test valid OptimizationItem instantiation."""
    obj = OptimizationItem(**SAMPLE_ITEM_1)
    assert obj.id == SAMPLE_ITEM_1["id"]
    assert obj.locationIndex == SAMPLE_ITEM_1["locationIndex"]
    assert obj.durationSeconds == SAMPLE_ITEM_1["durationSeconds"]
    assert obj.priority == SAMPLE_ITEM_1["priority"]
    assert obj.eligibleTechnicianIds == SAMPLE_ITEM_1["eligibleTechnicianIds"]

def test_optimization_fixed_constraint_valid():
    """Test valid OptimizationFixedConstraint instantiation."""
    obj = OptimizationFixedConstraint(**SAMPLE_FIXED_CONSTRAINT)
    assert obj.itemId == SAMPLE_FIXED_CONSTRAINT["itemId"]
    assert obj.fixedTimeISO == SAMPLE_FIXED_CONSTRAINT["fixedTimeISO"]

def test_optimization_request_payload_valid():
    """Test valid OptimizationRequestPayload instantiation."""
    obj = OptimizationRequestPayload(**SAMPLE_REQUEST_PAYLOAD)
    assert len(obj.locations) == len(SAMPLE_REQUEST_PAYLOAD["locations"])
    assert len(obj.technicians) == len(SAMPLE_REQUEST_PAYLOAD["technicians"])
    assert len(obj.items) == len(SAMPLE_REQUEST_PAYLOAD["items"])
    assert len(obj.fixedConstraints) == len(SAMPLE_REQUEST_PAYLOAD["fixedConstraints"])
    assert obj.travelTimeMatrix == SAMPLE_REQUEST_PAYLOAD["travelTimeMatrix"]
    # Check nested object types
    assert isinstance(obj.locations[0], OptimizationLocation)
    assert isinstance(obj.technicians[0], OptimizationTechnician)
    assert isinstance(obj.items[0], OptimizationItem)
    assert isinstance(obj.fixedConstraints[0], OptimizationFixedConstraint)

def test_route_stop_valid():
    """Test valid RouteStop instantiation."""
    obj = RouteStop(**SAMPLE_ROUTE_STOP_1)
    assert obj.itemId == SAMPLE_ROUTE_STOP_1["itemId"]
    assert obj.arrivalTimeISO == SAMPLE_ROUTE_STOP_1["arrivalTimeISO"]
    assert obj.startTimeISO == SAMPLE_ROUTE_STOP_1["startTimeISO"]
    assert obj.endTimeISO == SAMPLE_ROUTE_STOP_1["endTimeISO"]

def test_technician_route_valid():
    """Test valid TechnicianRoute instantiation."""
    obj = TechnicianRoute(**SAMPLE_TECHNICIAN_ROUTE_1)
    assert obj.technicianId == SAMPLE_TECHNICIAN_ROUTE_1["technicianId"]
    assert len(obj.stops) == len(SAMPLE_TECHNICIAN_ROUTE_1["stops"])
    assert isinstance(obj.stops[0], RouteStop)
    assert obj.totalTravelTimeSeconds == SAMPLE_TECHNICIAN_ROUTE_1["totalTravelTimeSeconds"]
    assert obj.totalDurationSeconds == SAMPLE_TECHNICIAN_ROUTE_1["totalDurationSeconds"]

def test_optimization_response_payload_valid_success():
    """Test valid successful OptimizationResponsePayload instantiation."""
    obj = OptimizationResponsePayload(**SAMPLE_RESPONSE_PAYLOAD_SUCCESS)
    assert obj.status == "success"
    assert obj.message is None
    assert len(obj.routes) == len(SAMPLE_RESPONSE_PAYLOAD_SUCCESS["routes"])
    assert isinstance(obj.routes[0], TechnicianRoute)
    assert obj.unassignedItemIds == SAMPLE_RESPONSE_PAYLOAD_SUCCESS["unassignedItemIds"]

def test_optimization_response_payload_valid_error():
    """Test valid error OptimizationResponsePayload instantiation."""
    obj = OptimizationResponsePayload(**SAMPLE_RESPONSE_PAYLOAD_ERROR)
    assert obj.status == "error"
    assert obj.message == SAMPLE_RESPONSE_PAYLOAD_ERROR["message"]
    assert len(obj.routes) == 0
    assert obj.unassignedItemIds is None

# --- Tests for Invalid Data ---

def test_lat_lng_literal_invalid_missing():
    """Test LatLngLiteral instantiation with missing fields."""
    with pytest.raises(ValidationError):
        LatLngLiteral(lat=40.7128) # Missing lng
    with pytest.raises(ValidationError):
        LatLngLiteral(lng=-74.0060) # Missing lat

def test_lat_lng_literal_invalid_type():
    """Test LatLngLiteral instantiation with wrong types."""
    with pytest.raises(ValidationError):
        LatLngLiteral(lat="invalid", lng=-74.0060)
    with pytest.raises(ValidationError):
        LatLngLiteral(lat=40.7128, lng="invalid")

def test_optimization_location_invalid_missing():
    """Test OptimizationLocation instantiation with missing fields."""
    with pytest.raises(ValidationError):
        OptimizationLocation(id="address_1", index=0) # Missing coords
    with pytest.raises(ValidationError):
        OptimizationLocation(id="address_1", coords=SAMPLE_LAT_LNG) # Missing index

def test_optimization_technician_invalid_type():
    """Test OptimizationTechnician instantiation with wrong types."""
    invalid_technician = SAMPLE_TECHNICIAN_1.copy()
    invalid_technician["id"] = "not_an_int"
    with pytest.raises(ValidationError):
        OptimizationTechnician(**invalid_technician)

def test_optimization_request_payload_invalid_missing():
    """Test OptimizationRequestPayload instantiation with missing fields."""
    # Example: missing 'locations'
    invalid_payload = SAMPLE_REQUEST_PAYLOAD.copy()
    del invalid_payload["locations"]
    with pytest.raises(ValidationError):
        OptimizationRequestPayload(**invalid_payload)

def test_optimization_response_payload_invalid_status():
    """Test OptimizationResponsePayload instantiation with invalid status."""
    invalid_response = SAMPLE_RESPONSE_PAYLOAD_SUCCESS.copy()
    invalid_response["status"] = "invalid_status"
    with pytest.raises(ValidationError):
        OptimizationResponsePayload(**invalid_response)

def test_technician_route_missing_optional():
    """Test TechnicianRoute instantiation works without optional fields."""
    route_data = {
        "technicianId": 1,
        "stops": [SAMPLE_ROUTE_STOP_1],
        # totalTravelTimeSeconds and totalDurationSeconds are omitted
    }
    obj = TechnicianRoute(**route_data)
    assert obj.technicianId == 1
    assert len(obj.stops) == 1
    assert obj.totalTravelTimeSeconds is None
    assert obj.totalDurationSeconds is None
