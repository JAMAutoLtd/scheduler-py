import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

# Change relative imports to absolute relative to the optimize-service dir
# Import the main module itself to allow monkeypatching its variables
import main 
from main import app, iso_to_seconds, seconds_to_iso
# Use the correct model names as defined in models.py
from models import OptimizationRequestPayload, OptimizationResponsePayload, OptimizationLocation, OptimizationTechnician, OptimizationItem

# Reuse sample data from test_models if applicable, or define minimal here
# Refactored Sample Data (ensure distinct item/depot indices)
SAMPLE_LAT_LNG_A = {"lat": 40.7128, "lng": -74.0060} # Item location
SAMPLE_LAT_LNG_B = {"lat": 40.7000, "lng": -74.0100} # Start Depot
SAMPLE_LAT_LNG_C = {"lat": 40.7200, "lng": -74.0000} # End Depot

# Locations: 0 = Item, 1 = Start Depot, 2 = End Depot
SAMPLE_LOCATION_ITEM = {"id": "loc_item", "index": 0, "coords": SAMPLE_LAT_LNG_A}
SAMPLE_LOCATION_START_DEPOT = {"id": "loc_start_depot", "index": 1, "coords": SAMPLE_LAT_LNG_B}
SAMPLE_LOCATION_END_DEPOT = {"id": "loc_end_depot", "index": 2, "coords": SAMPLE_LAT_LNG_C}

SAMPLE_TECHNICIAN_1 = {
    "id": 1,
    "startLocationIndex": 1, # Start at depot index 1
    "endLocationIndex": 2,   # End at depot index 2
    "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Use a fixed date for consistency
    "latestEndTimeISO": "2024-04-11T17:00:00Z",
}

SAMPLE_ITEM_1 = {
    "id": "item_1",
    "locationIndex": 0, # Item location remains index 0
    "durationSeconds": 1800, # 30 mins
    "priority": 1,
    "eligibleTechnicianIds": [1],
}

# Travel Matrix for 3 locations (0=Item, 1=Start, 2=End)
SAMPLE_TRAVEL_MATRIX = {
    0: {0: 0, 1: 600, 2: 700},    # Item -> Item, Start(10m), End(12m)
    1: {0: 600, 1: 0, 2: 800},    # Start -> Item(10m), Start, End(13m)
    2: {0: 700, 1: 800, 2: 0}     # End -> Item(12m), Start(13m), End
}

MINIMAL_VALID_PAYLOAD = {
    "locations": [SAMPLE_LOCATION_ITEM, SAMPLE_LOCATION_START_DEPOT, SAMPLE_LOCATION_END_DEPOT],
    "technicians": [SAMPLE_TECHNICIAN_1],
    "items": [SAMPLE_ITEM_1],
    "fixedConstraints": [],
    "travelTimeMatrix": SAMPLE_TRAVEL_MATRIX,
}


@pytest.fixture(scope="module")
def client():
    """Test client fixture for making API requests."""
    with TestClient(app) as c:
        yield c

# Removing fixtures that patch the non-existent main.EPOCH
# @pytest.fixture
# def patch_main_epoch(monkeypatch):
#     ...

# @pytest.fixture
# def patch_main_epoch_day12(monkeypatch):
#     ...

# @pytest.fixture
# def patch_main_epoch_day13(monkeypatch):
#     ...

# --- Helper Function Tests ---

# Removed patch_main_epoch fixture argument
def test_iso_to_seconds_conversion():
    """Test iso_to_seconds conversion for various formats."""
    # EPOCH is now fixed to Unix epoch in main.py

    # UTC Z format -> Correct expected timestamp
    assert iso_to_seconds("2024-04-11T01:00:00Z") == 1712797200 # Unix timestamp for 2024-04-11 01:00:00 UTC
    # UTC +00:00 offset format
    assert iso_to_seconds("2024-04-11T02:30:00+00:00") == 1712802600 # Unix timestamp for 2024-04-11 02:30:00 UTC
    # Other offset
    assert iso_to_seconds("2024-04-11T05:00:00+02:00") == 1712804400 # This is 2024-04-11T03:00:00Z UTC
    # Naive datetime (should assume UTC based on current implementation)
    # Note: Dependence on naive datetime assumption is risky. Prefer explicit offsets.
    # Assuming it defaults to UTC
    assert iso_to_seconds("2024-04-11T00:10:00") == 1712794200 # Unix timestamp for 2024-04-11 00:10:00 UTC

# Removed patch_main_epoch fixture argument
def test_seconds_to_iso_conversion():
    """Test seconds_to_iso conversion back to ISO string."""
    # EPOCH is now fixed to Unix epoch in main.py
    # Expect 'Z' suffix from the updated function

    # Corrected assertion: Input 1712797200 (01:00 UTC) should yield "2024-04-11T01:00:00Z"
    assert seconds_to_iso(1712797200) == "2024-04-11T01:00:00Z"
    # Corrected assertion: Input 1712802600 (02:30 UTC) should yield "2024-04-11T02:30:00Z"
    assert seconds_to_iso(1712802600) == "2024-04-11T02:30:00Z"
    # Test with Unix epoch itself
    assert seconds_to_iso(0) == "1970-01-01T00:00:00Z"
    # Test another value
    assert seconds_to_iso(1712794200) == "2024-04-11T00:10:00Z" # 00:10 UTC

# --- Endpoint Tests ---

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_minimal_valid(client):
    """Test the endpoint with a minimal valid payload. Primarily checks if it runs without crashing."""
    # No epoch patching needed here as we aren't asserting specific times
    response = client.post("/optimize-schedule", json=MINIMAL_VALID_PAYLOAD)
    assert response.status_code == 200
    # Further checks on the actual optimization result will require more complex tests
    data = response.json()
    assert data["status"] in ["success", "partial", "error"] # Allow any valid solver outcome for now
    assert "routes" in data
    assert "unassignedItemIds" in data

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_simple_success(client):
    """Test a simple scenario expected to succeed with one assigned stop."""
    # No explicit epoch patching needed. Use fixed known ISO strings.

    payload = MINIMAL_VALID_PAYLOAD.copy()
    # Use a fixed, known date/time for technician window
    tech_start_iso = payload["technicians"][0]["earliestStartTimeISO"] # "2024-04-11T08:00:00Z"
    tech_start_seconds_unix = iso_to_seconds(tech_start_iso) # Absolute Unix timestamp

    # Expected timing calculation using Unix epoch seconds
    travel_time_start_to_item = SAMPLE_TRAVEL_MATRIX[1][0] # Tech starts at index 1, item at index 0 -> 600s
    # Tech starts at their start location at tech_start_seconds_unix
    expected_arrival_seconds_unix = tech_start_seconds_unix + travel_time_start_to_item # Unix timestamp of arrival
    expected_start_seconds_unix = expected_arrival_seconds_unix   # Can start immediately at arrival
    expected_end_seconds_unix = expected_start_seconds_unix + SAMPLE_ITEM_1["durationSeconds"] # Unix timestamp of completion

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Assertions for a successful simple case
    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert "Optimization successful" in data["message"]
    assert len(data["routes"]) == 1, f"Expected 1 route, got {len(data['routes'])}"
    assert data["unassignedItemIds"] == [], f"Expected no unassigned items, got {data['unassignedItemIds']}"

    route = data["routes"][0]
    assert route["technicianId"] == SAMPLE_TECHNICIAN_1["id"]
    assert len(route["stops"]) == 1, f"Expected 1 stop in the route, got {len(route['stops'])}"

    stop = route["stops"][0]
    assert stop["itemId"] == SAMPLE_ITEM_1["id"]

    # Basic timing checks - Assert against expected ISO strings derived from Unix timestamps
    # Use the corrected seconds_to_iso which returns 'Z' format
    expected_arrival_iso = seconds_to_iso(expected_arrival_seconds_unix)
    expected_start_iso = seconds_to_iso(expected_start_seconds_unix)
    expected_end_iso = seconds_to_iso(expected_end_seconds_unix)

    assert stop["arrivalTimeISO"] == expected_arrival_iso, f"Arrival time mismatch. Expected {expected_arrival_iso}, Got {stop['arrivalTimeISO']}"
    assert stop["startTimeISO"] == expected_start_iso, f"Start time mismatch. Expected {expected_start_iso}, Got {stop['startTimeISO']}"
    assert stop["endTimeISO"] == expected_end_iso, f"End time mismatch. Expected {expected_end_iso}, Got {stop['endTimeISO']}"

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_fixed_constraint(client):
    """Test a scenario with a fixed time constraint."""
    # No explicit epoch patching needed.

    payload = MINIMAL_VALID_PAYLOAD.copy()
    fixed_time_iso = "2024-04-11T10:00:00Z" # 10:00 AM UTC
    payload["fixedConstraints"] = [
        {"itemId": SAMPLE_ITEM_1["id"], "fixedTimeISO": fixed_time_iso}
    ]

    # Adjust technician time window if necessary to make constraint feasible
    payload["technicians"][0]["earliestStartTimeISO"] = "2024-04-11T08:00:00Z"
    payload["technicians"][0]["latestEndTimeISO"] = "2024-04-11T17:00:00Z"

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert len(data["routes"]) == 1
    assert data["unassignedItemIds"] == []

    route = data["routes"][0]
    assert len(route["stops"]) == 1
    stop = route["stops"][0]
    assert stop["itemId"] == SAMPLE_ITEM_1["id"]

    # Verify the start time matches the fixed constraint
    expected_start_seconds_unix = iso_to_seconds(fixed_time_iso)
    # Arrival must be <= fixed start time. Tech starts 08:00, Travel(1->0)=600s. Arrival at item = 08:10.
    # Since fixed time is 10:00, tech will arrive and wait.
    tech_start_seconds_unix = iso_to_seconds(payload["technicians"][0]["earliestStartTimeISO"])
    travel_start_to_item = SAMPLE_TRAVEL_MATRIX[1][0] # 600s
    expected_arrival_seconds_unix = tech_start_seconds_unix + travel_start_to_item # Unix timestamp of arrival
    expected_end_seconds_unix = expected_start_seconds_unix + SAMPLE_ITEM_1["durationSeconds"]

    # Convert expected times to ISO strings ('Z' format)
    expected_arrival_iso = seconds_to_iso(expected_arrival_seconds_unix)
    expected_start_iso = seconds_to_iso(expected_start_seconds_unix) # Should match fixed_time_iso
    expected_end_iso = seconds_to_iso(expected_end_seconds_unix)

    # Check that arrival time is calculated correctly (tech waits)
    assert stop["arrivalTimeISO"] == expected_arrival_iso, f"Arrival time mismatch. Expected {expected_arrival_iso}, Got {stop['arrivalTimeISO']}"
    # Check start time matches the fixed constraint
    assert stop["startTimeISO"] == expected_start_iso, f"Start time mismatch. Expected {expected_start_iso}, Got {stop['startTimeISO']}"
    # Check end time is based on fixed start + duration
    assert stop["endTimeISO"] == expected_end_iso, f"End time mismatch. Expected {expected_end_iso}, Got {stop['endTimeISO']}"

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_unassigned_due_to_time(client):
    """Test scenario where an item is unassigned due to tight technician time window."""
    # No explicit epoch patching needed.

    payload = MINIMAL_VALID_PAYLOAD.copy()

    # Modify technician time window to be too short
    # Tech starts at 08:00 (28800s). Item is at start location (index 0), duration 1800s.
    # Needs to finish by 08:30 (28800 + 1800 = 30600s).
    # Let's set the end time *before* the job can finish.
    payload["technicians"][0]["earliestStartTimeISO"] = "2024-04-11T08:00:00Z"
    payload["technicians"][0]["latestEndTimeISO"] = "2024-04-11T08:15:00Z" # Only 15 mins available (needs 30)

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Expect the job to be unassigned
    # Since this is the *only* item and it cannot be scheduled, expect 'error'
    assert data["status"] == "error", f"Expected status 'error' when the only item is unassigned due to time, got '{data['status']}' with message: {data.get('message')}"
    # Check for specific error messages related to no assignment or no solution
    assert ("No routes could be assigned" in data["message"] or
            "No solution found" in data["message"] or
            f"{len(payload['items'])} items could not be scheduled" in data["message"] # Check for partial message if solver logic changes
           ), f"Unexpected error message: {data['message']}"

    # Verify the item is in the unassigned list
    assert SAMPLE_ITEM_1["id"] in data["unassignedItemIds"], f"Item {SAMPLE_ITEM_1['id']} not found in unassignedItemIds: {data['unassignedItemIds']}"

    # Check that no routes were successfully generated
    assert not data.get("routes", []), "Routes list should be empty when status is error."

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_unassigned_due_to_eligibility(client):
    """Test scenario where an item is unassigned because no technician is eligible."""
    # No epoch manipulation needed as timing isn't the primary factor here

    payload = MINIMAL_VALID_PAYLOAD.copy()

    # Modify item eligibility so the existing technician (ID 1) is not eligible
    payload["items"][0]["eligibleTechnicianIds"] = [999] # Assign an ID that doesn't exist

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Expect the job to be unassigned because no one can do it
    # Since this is the only item, status should be 'error'
    assert data["status"] == "error", f"Expected status 'error' when the only item is unassigned due to eligibility, got '{data['status']}' with message: {data.get('message')}"
    # Check for specific error messages
    assert ("No routes could be assigned" in data["message"] or
            "No solution found" in data["message"] or
            f"{len(payload['items'])} items could not be scheduled" in data["message"] # Check for partial message if solver logic changes
           ), f"Unexpected error message: {data['message']}"

    # Verify the item is in the unassigned list
    assert SAMPLE_ITEM_1["id"] in data["unassignedItemIds"], f"Item {SAMPLE_ITEM_1['id']} not found in unassignedItemIds: {data['unassignedItemIds']}"

    # Check that no routes were successfully generated
    assert not data.get("routes", []), "Routes list should be empty when status is error."

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_with_travel(client):
    """Test a scenario with two items requiring travel between them.
    Modify setup to use separate depot indices.
    """
    # No explicit epoch patching needed.

    # === Define 4 Locations: 0,1 for items; 2 for start depot, 3 for end depot ===
    LOC_ITEM_1 = {"id": "loc_item_1", "index": 0, "coords": {"lat": 40.7128, "lng": -74.0060}}
    LOC_ITEM_2 = {"id": "loc_item_2", "index": 1, "coords": {"lat": 40.7580, "lng": -73.9855}}
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 2, "coords": {"lat": 40.7000, "lng": -74.0000}}
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 3, "coords": {"lat": 40.7800, "lng": -73.9500}}
    locations = [LOC_ITEM_1, LOC_ITEM_2, LOC_DEPOT_START, LOC_DEPOT_END]

    # === Define Items at location 0 and 1 ===
    ITEM_1 = {
        "id": "item_1",
        "locationIndex": 0, # Use index 0
        "durationSeconds": 1800, # 30 mins
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }
    ITEM_2 = {
        "id": "item_2",
        "locationIndex": 1, # Use index 1
        "durationSeconds": 1200, # 20 mins
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }
    items = [ITEM_1, ITEM_2]

    # === Define Technician using depots at index 2 (start) and 3 (end) ===
    TECHNICIAN_SEP_DEPOT = {
        "id": 1,
        "startLocationIndex": 2, # Use index 2 for start
        "endLocationIndex": 3,   # Use index 3 for end
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Fixed time
        "latestEndTimeISO": "2024-04-11T17:00:00Z",
    }
    technicians = [TECHNICIAN_SEP_DEPOT]

    # === Define Travel Matrix for 4 locations (indices 0, 1, 2, 3) ===
    # Approx times: Item1(0), Item2(1), Start(2), End(3)
    TRAVEL_4_LOC = {
        0: {0: 0,   1: 600,  2: 700,  3: 1000}, # Item1 -> Item1, Item2(10m), Start(12m), End(17m)
        1: {0: 600,  1: 0,   2: 800,  3: 500 }, # Item2 -> Item1(10m), Item2, Start(13m), End(8m)
        2: {0: 700,  1: 800,  2: 0,   3: 1100}, # Start -> Item1(12m), Item2(13m), Start, End(18m)
        3: {0: 1000, 1: 500,  2: 1100, 3: 0 }   # End -> Item1(17m), Item2(8m), Start(18m), End
    }
    travelTimeMatrix = TRAVEL_4_LOC

    # === Construct Payload ===
    payload = {
        "locations": locations,
        "technicians": technicians,
        "items": items,
        "fixedConstraints": [],
        "travelTimeMatrix": travelTimeMatrix,
    }

    # Expected sequence now (simplified):
    # - Start at LOC_DEPOT_START (idx 2)
    # - Travel (2 -> 0): 700s
    # - Stop 1 (Item 1 @ LOC_ITEM_1, idx 0): Arrive 08:00+700s, Start, End
    # - Travel (0 -> 1): 600s
    # - Stop 2 (Item 2 @ LOC_ITEM_2, idx 1): Arrive, Start, End
    # - Travel (1 -> 3): 500s (to end depot)

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Check basic assertions - expecting success now
    # assert data["status"] == "error", f"Expected status 'error' (as AddDisjunction is commented), got '{data['status']}' with message: {data.get('message')}"
    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert len(data["routes"]) == 1, f"Expected 1 route, got {len(data['routes'])}"
    route = data["routes"][0]
    assert len(route["stops"]) == 2, f"Expected 2 stops, got {len(route['stops'])}"
    assert data["unassignedItemIds"] == [], f"Expected no unassigned items, got {data['unassignedItemIds']}"

    # Sort stops by arrival time to ensure consistent order for assertions
    route["stops"].sort(key=lambda x: iso_to_seconds(x["arrivalTimeISO"]))

    stop1 = route["stops"][0]
    stop2 = route["stops"][1]

    # Verify item IDs are correct (order might vary slightly based on solver)
    # Check that both expected items are present
    scheduled_item_ids = {stop["itemId"] for stop in route["stops"]}
    assert scheduled_item_ids == {ITEM_1["id"], ITEM_2["id"]}

    # Determine which stop corresponds to which item based on ID
    stop_item_1 = stop1 if stop1["itemId"] == ITEM_1["id"] else stop2
    stop_item_2 = stop2 if stop2["itemId"] == ITEM_2["id"] else stop1
    assert stop_item_1["itemId"] == ITEM_1["id"]
    assert stop_item_2["itemId"] == ITEM_2["id"]

    # --- Verify Timings with Flexibility --- 
    tech_start_s = iso_to_seconds(TECHNICIAN_SEP_DEPOT["earliestStartTimeISO"]) # Unix timestamp

    # Stop 1 (Item 1 @ loc 0, from start depot @ loc 2)
    travel_start_to_itemA = TRAVEL_4_LOC[2][0] # 700s
    earliest_s1_arrival_s = tech_start_s + travel_start_to_itemA # 28800 + 700 = 29500
    actual_s1_arrival_s = iso_to_seconds(stop_item_1["arrivalTimeISO"])
    actual_s1_start_s = iso_to_seconds(stop_item_1["startTimeISO"])
    actual_s1_end_s = iso_to_seconds(stop_item_1["endTimeISO"])

    assert actual_s1_arrival_s >= earliest_s1_arrival_s, "Stop 1 arrival is earlier than possible"
    assert actual_s1_start_s >= actual_s1_arrival_s, "Stop 1 started before arrival"
    assert actual_s1_end_s == actual_s1_start_s + ITEM_1["durationSeconds"], "Stop 1 end time mismatch (start + duration)"

    # Stop 2 (Item 2 @ loc 1, from item A @ loc 0)
    travel_itemA_to_itemB = TRAVEL_4_LOC[0][1] # 600s
    earliest_s2_arrival_s = actual_s1_end_s + travel_itemA_to_itemB # Earliest possible based on actual S1 end
    actual_s2_arrival_s = iso_to_seconds(stop_item_2["arrivalTimeISO"])
    actual_s2_start_s = iso_to_seconds(stop_item_2["startTimeISO"])
    actual_s2_end_s = iso_to_seconds(stop_item_2["endTimeISO"])

    assert actual_s2_arrival_s >= earliest_s2_arrival_s, "Stop 2 arrival is earlier than possible based on Stop 1 end"
    assert actual_s2_start_s >= actual_s2_arrival_s, "Stop 2 started before arrival"
    assert actual_s2_end_s == actual_s2_start_s + ITEM_2["durationSeconds"], "Stop 2 end time mismatch (start + duration)"

    # --- Verify Total Travel Time --- 
    # Total travel calculation should be based on the *actual* sequence and node indices used by the solver.
    # The logic in main.py calculates this. We verify it matches expectations for the segments.
    travel_itemB_to_end = TRAVEL_4_LOC[1][3] # 500s
    expected_total_travel = travel_start_to_itemA + travel_itemA_to_itemB + travel_itemB_to_end # 700 + 600 + 500 = 1800
    assert route["totalTravelTimeSeconds"] == expected_total_travel, \
        f"Expected total travel time {expected_total_travel}s, Got {route['totalTravelTimeSeconds']}s"

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_priority(client):
    """Test that higher priority items are scheduled when resources are constrained.
    Uses distinct depot indices.
    """
    # No explicit epoch patching needed.

    # === Locations: 0, 1 for items; 2 for start, 3 for end ===
    LOC_ITEM_1 = {"id": "loc_item_1", "index": 0, "coords": {"lat": 40.7128, "lng": -74.0060}}
    LOC_ITEM_2 = {"id": "loc_item_2", "index": 1, "coords": {"lat": 40.7580, "lng": -73.9855}}
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 2, "coords": {"lat": 40.7000, "lng": -74.0000}}
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 3, "coords": {"lat": 40.7800, "lng": -73.9500}}
    locations = [LOC_ITEM_1, LOC_ITEM_2, LOC_DEPOT_START, LOC_DEPOT_END]

    # Item 1: High priority (1), 30 mins duration at location 0
    ITEM_PRIO_1 = {
        "id": "item_prio_1",
        "locationIndex": 0, # At index 0
        "durationSeconds": 1800, # 30 mins
        "priority": 1, # Higher priority
        "eligibleTechnicianIds": [1],
    }
    # Item 2: Lower priority (5), 30 mins duration at location 1
    ITEM_PRIO_2 = {
        "id": "item_prio_2",
        "locationIndex": 1, # At index 1
        "durationSeconds": 1800, # 30 mins
        "priority": 5, # Lower priority
        "eligibleTechnicianIds": [1],
    }
    items = [ITEM_PRIO_1, ITEM_PRIO_2]

    # === Technician using depots at index 2 (start) and 3 (end) ===
    TECHNICIAN_PRIO_TEST = {
        "id": 1,
        "startLocationIndex": 2, # Use index 2 for start
        "endLocationIndex": 3,   # Use index 3 for end
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Fixed time
        # Tight time window: Latest end time is 08:55 (32100s)
        "latestEndTimeISO": "2024-04-11T08:55:00Z", # Fixed time
    }
    technicians = [TECHNICIAN_PRIO_TEST]

    # === Define Travel Matrix for 4 locations (indices 0, 1, 2, 3) ===
    # Approx times: Item1(0), Item2(1), Start(2), End(3)
    TRAVEL_4_LOC = {
        0: {0: 0,   1: 600,  2: 700,  3: 1000}, # Item1 -> Item1, Item2(10m), Start(12m), End(17m)
        1: {0: 600,  1: 0,   2: 800,  3: 500 }, # Item2 -> Item1(10m), Item2, Start(13m), End(8m)
        2: {0: 700,  1: 800,  2: 0,   3: 1100}, # Start -> Item1(12m), Item2(13m), Start, End(18m)
        3: {0: 1000, 1: 500,  2: 1100, 3: 0 }   # End -> Item1(17m), Item2(8m), Start(18m), End
    }
    travelTimeMatrix = TRAVEL_4_LOC


    # --- Time Calculation ---
    # Tech starts at 08:00 (28800s) at loc 2. Window is 55 mins (until 32100s).
    # Option 1: Serve ITEM_PRIO_1 (High Prio)
    #   - Travel (Start 2 -> Item1 0): 700s
    #   - Service Item1: 1800s
    #   - Travel (Item1 0 -> End 3): 1000s
    #   - Total time = 700 + 1800 + 1000 = 3500s (58.3 mins) -> TOO LONG for 55 min window
    # Option 2: Serve ITEM_PRIO_2 (Low Prio)
    #   - Travel (Start 2 -> Item2 1): 800s
    #   - Service Item2: 1800s
    #   - Travel (Item2 1 -> End 3): 500s
    #   - Total time = 800 + 1800 + 500 = 3100s (51.7 mins) -> FITS within 55 min window

    # Since only the low-priority item fits, but the high-priority one has a large penalty,
    # the solver should drop *both* items. Let's adjust the window slightly.
    # Make window 60 mins (until 09:00 / 32400s).
    # Option 1 (High Prio) still takes 3500s (58.3m) -> FITS.
    # Option 2 (Low Prio) still takes 3100s (51.7m) -> FITS.
    # Now, the solver should choose Option 1 because the penalty for dropping Item 1 is higher.
    TECHNICIAN_PRIO_TEST["latestEndTimeISO"] = "2024-04-11T09:00:00Z" # 60 min window (fixed time)

    # === Construct Payload ===
    payload = {
        "locations": locations,
        "technicians": technicians,
        "items": items,
        "fixedConstraints": [],
        "travelTimeMatrix": travelTimeMatrix,
    }

    # --- Make Request ---
    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Expect partial success, with the higher priority item scheduled
    assert data["status"] == "partial", f"Expected status 'partial', got '{data['status']}' with message: {data.get('message')}"
    assert len(data["routes"]) >= 1, f"Expected at least 1 route, got {len(data['routes'])}" # Allow empty route for tech if nothing assigned
    
    scheduled_item_id = None
    route_found = False
    for route in data["routes"]:
        if route["stops"]:
            assert not route_found, "Found more than one non-empty route."
            route_found = True
            assert len(route["stops"]) == 1, f"Expected 1 stop, got {len(route['stops'])}"
            scheduled_item_id = route["stops"][0]["itemId"]

    assert route_found, "No non-empty route found with a scheduled stop."
    # Verify the high-priority item is scheduled
    assert scheduled_item_id == ITEM_PRIO_1["id"], "High priority item was not scheduled."

    # Verify the low-priority item is unassigned
    assert ITEM_PRIO_2["id"] in data["unassignedItemIds"], "Low priority item was not in unassigned list."
    assert ITEM_PRIO_1["id"] not in data["unassignedItemIds"], "High priority item was unexpectedly in unassigned list."

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_multiple_techs_assignment(client):
    """Test assignment with multiple technicians where one is time-constrained.
    Uses distinct depot indices.
    """
    # No explicit epoch patching needed.

    # Locations: 0=Item, 1=Start Depot, 2=End Depot
    LOC_ITEM_0 = {"id": "loc_item_0", "index": 0, "coords": {"lat": 40.7128, "lng": -74.0060}}
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 1, "coords": {"lat": 40.7000, "lng": -74.0100}}
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 2, "coords": {"lat": 40.7200, "lng": -74.0000}}
    locations = [LOC_ITEM_0, LOC_DEPOT_START, LOC_DEPOT_END]

    # Technician 1: Very tight window
    TECH_1 = {
        "id": 1,
        "startLocationIndex": 1, # Start depot
        "endLocationIndex": 2,   # End depot
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Fixed time
        # Window needs to account for travel Start(1)->Item(0) and service
        # Travel(1->0)=600s. Service=1800s. Min time needed = 2400s (40 mins)
        # Let's give 35 mins total (2100s). End time = 08:35 (28800 + 2100 = 30900s)
        "latestEndTimeISO": "2024-04-11T08:35:00Z", # Fixed time
    }
    # Technician 2: Wide window
    TECH_2 = {
        "id": 2,
        "startLocationIndex": 1, # Start depot
        "endLocationIndex": 2,   # End depot
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Fixed time
        "latestEndTimeISO": "2024-04-11T17:00:00Z",    # Fixed time
    }

    # Item 1: Requires 30 mins, at location 0
    ITEM_MULTI = {
        "id": "item_multi_1",
        "locationIndex": 0,
        "durationSeconds": 1800, # 30 mins
        "priority": 1,
        "eligibleTechnicianIds": [1, 2], # Both are eligible
    }

    # Use the standard 3-location travel matrix
    travelTimeMatrix = SAMPLE_TRAVEL_MATRIX.copy()

    payload = {
        "locations": locations,
        "technicians": [TECH_1, TECH_2],
        "items": [ITEM_MULTI],
        "fixedConstraints": [],
        "travelTimeMatrix": travelTimeMatrix,
    }

    # Expectation:
    # Tech 1 starts 08:00 (28800s) at loc 1. Needs Travel(1->0)=600s + Service=1800s = 2400s.
    # Tech 1 window ends 08:35 (30900s). Available time = 30900 - 28800 = 2100s. Too short.
    # Tech 2 starts 08:00 (28800s) at loc 1. Ample time.
    # Job should be assigned to Tech 2.

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert data["unassignedItemIds"] == [], f"Expected no unassigned items, got {data['unassignedItemIds']}"

    # Check the routes - should have one actual route for Tech 2
    scheduled_tech_id = None
    route_found = False
    for route in data["routes"]:
        if route["stops"]:
             # This assertion helps catch cases where multiple routes might be incorrectly generated
            assert not route_found, "Found more than one non-empty route when only one was expected."
            route_found = True
            assert len(route["stops"]) == 1, "Expected exactly one stop in the route."
            assert route["stops"][0]["itemId"] == ITEM_MULTI["id"], "Incorrect item scheduled."
            scheduled_tech_id = route["technicianId"]

    assert route_found, "No non-empty route found in the response."
    assert scheduled_tech_id == TECH_2["id"], f"Item was assigned to tech {scheduled_tech_id}, expected tech {TECH_2['id']}."

# Removed patch_main_epoch fixture argument
def test_optimize_schedule_incomplete_travel_matrix(client):
    """Test that an item becomes unassigned if required travel time is missing.
    Uses only 3 locations: Item B, Start Depot, End Depot, to isolate the missing link.
    """
    # No explicit epoch patching needed.

    # Locations: 0=ItemB, 1=StartDepot, 2=EndDepot
    # Original Indices: ItemA(0), ItemB(1), Start(2), End(3)
    LOC_ITEM_B = {"id": "loc_item_B", "index": 0, "coords": {"lat": 40.7580, "lng": -73.9855}} # Was index 1
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 1, "coords": {"lat": 40.7000, "lng": -74.0000}} # Was index 2
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 2, "coords": {"lat": 40.7800, "lng": -73.9500}} # Was index 3
    locations = [LOC_ITEM_B, LOC_DEPOT_START, LOC_DEPOT_END] # Simplified list

    # Only Item B, updated location index
    ITEM_B = {
        "id": "item_B",
        "locationIndex": 0, # Location 0 (Item B's location)
        "durationSeconds": 1200, # 20 mins
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }
    items = [ITEM_B] # Only one item

    # Technician starts at Start Depot (1), ends at End Depot (2)
    TECHNICIAN_INCOMPLETE = {
        "id": 1,
        "startLocationIndex": 1, # Start Depot
        "endLocationIndex": 2,   # End Depot
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # Fixed time
        "latestEndTimeISO": "2024-04-11T17:00:00Z", # Fixed time
    }
    technicians = [TECHNICIAN_INCOMPLETE]

    # Create a 3x3 travel matrix based on relevant parts of the original 4x4,
    # specifically omitting the travel from Start Depot (1) to Item B (0).
    # New Indices: ItemB(0), Start(1), End(2)
    # Original Indices: ItemA(0), ItemB(1), Start(2), End(3)
    # ItemB(1) -> End(3) = 500   => [0][2] = 500
    # ItemB(1) -> Start(2)= 800   => [0][1] = 800
    # Start(2) -> End(3) = 1100  => [1][2] = 1100
    # End(3) -> ItemB(1) = 500   => [2][0] = 500
    # End(3) -> Start(2)= 1100  => [2][1] = 1100
    specific_incomplete_matrix = {
        0: {0: 0,   1: 800,  2: 500 }, # ItemB -> B, Start, End
        1: {        1: 0,   2: 1100}, # Start -> (missing B), Start, End
        2: {0: 500,  1: 1100, 2: 0 }   # End -> B, Start, End
    }
    travelTimeMatrix = specific_incomplete_matrix

    payload = {
        "locations": locations,
        "technicians": technicians,
        "items": items,
        "fixedConstraints": [],
        "travelTimeMatrix": travelTimeMatrix,
    }

    # Expected outcome:
    # - Tech starts at loc 1 (Start Depot).
    # - Travel Start(1) -> Item B(0) is missing (high cost).
    # - Solver cannot schedule Item B.
    # - Solver will drop Item B (penalty 100000).
    # - The only possible 'route' is direct Start(1) -> End(2) (travel 1100s).
    # - Since the only item is dropped, the optimization result should indicate an error
    #   or at least show the item as unassigned.
    # - Let's assert for 'error' as the API should reflect that it couldn't fulfill the request.
    #   If it returns 'success', we need to check 'unassignedItemIds'.

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Primary Assertion: Item B MUST be unassigned due to the missing matrix entry.
    # The OR-Tools solver itself might still find a "solution" (depot-to-depot),
    # but our service logic should report the inability to schedule the item.
    # Let's check unassigned first, then status.
    assert ITEM_B["id"] in data.get("unassignedItemIds", []), \
        f"Item B should be unassigned due to missing travel time, but wasn't. Unassigned: {data.get('unassignedItemIds')}"
    assert len(data.get("unassignedItemIds", [])) == 1, \
        f"Expected exactly 1 unassigned item, got {len(data.get('unassignedItemIds', []))}"

    # Secondary Assertion: Status should ideally reflect the failure, but might be 'success'
    # if the solver completed but dropped items. We accept 'success' ONLY IF the item is unassigned.
    if data["status"] == "error":
        assert not data.get("routes", []), "Routes list should be empty when status is error"
    elif data["status"] == "success":
        # If status is success, ensure the route list is empty or contains only depot-to-depot.
        # The current solver logic might still create a route object for the depot-to-depot journey.
        if data.get("routes"):
            assert len(data["routes"]) == 1, "Expected 0 or 1 route if status is success"
            assert not data["routes"][0].get("stops", []), \
                "Route should have no stops if the only item was unassigned."
            # Optionally check total travel time for the depot-to-depot leg
            # expected_depot_travel = specific_incomplete_matrix[1][2] # Start(1) -> End(2)
            # assert data["routes"][0]["totalTravelTimeSeconds"] == expected_depot_travel
    else:
        pytest.fail(f"Unexpected status '{data['status']}'. Expected 'error' or 'success' with unassigned item.")

    # Ensure Item B is the *only* unassigned item.
    assert data.get("unassignedItemIds") == [ITEM_B["id"]]

# Removed patch_main_epoch_day12 fixture argument
def test_optimize_schedule_three_stops_renamed(client):
    """Test a route involving one technician visiting three distinct locations.
    Uses distinct depot indices. Renamed to avoid conflict with potentially similar test name.
    Uses 2024-04-12 as the date in ISO strings.
    """
    # No explicit epoch patching needed.

    # Locations: 0=A, 1=B, 2=C, 3=StartDepot, 4=EndDepot
    LOC_A = {"id": "loc_A", "index": 0, "coords": {"lat": 40.7128, "lng": -74.0060}}
    LOC_B = {"id": "loc_B", "index": 1, "coords": {"lat": 40.7580, "lng": -73.9855}}
    LOC_C = {"id": "loc_C", "index": 2, "coords": {"lat": 40.7614, "lng": -73.9776}}
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 3, "coords": {"lat": 40.7000, "lng": -74.0000}}
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 4, "coords": {"lat": 40.7800, "lng": -73.9500}}
    locations = [LOC_A, LOC_B, LOC_C, LOC_DEPOT_START, LOC_DEPOT_END]

    # Define Items at each location (0, 1, 2)
    ITEM_A = {
        "id": "item_A", "locationIndex": 0, "durationSeconds": 1800, # 30m
        "priority": 1, "eligibleTechnicianIds": [1],
    }
    ITEM_B = {
        "id": "item_B", "locationIndex": 1, "durationSeconds": 1200, # 20m
        "priority": 1, "eligibleTechnicianIds": [1],
    }
    ITEM_C = {
        "id": "item_C", "locationIndex": 2, "durationSeconds": 1500, # 25m
        "priority": 1, "eligibleTechnicianIds": [1],
    }
    items = [ITEM_A, ITEM_B, ITEM_C]

    # Technician starts at Depot 3, ends at Depot 4
    tech_start_iso = "2024-04-12T09:00:00Z" # Fixed time
    TECH_MULTI = {
        "id": 1, "startLocationIndex": 3, "endLocationIndex": 4,
        "earliestStartTimeISO": tech_start_iso,
        "latestEndTimeISO": "2024-04-12T17:00:00Z", # Fixed time
    }
    technicians = [TECH_MULTI]

    # Define Travel Matrix for 5 locations (approximate times in seconds)
    # Indices: A(0), B(1), C(2), Start(3), End(4)
    TRAVEL_5_LOC = {
        0: {0: 0,   1: 600,  2: 900,  3: 700,  4: 1000}, # A -> A, B(10m), C(15m), Start(12m), End(17m)
        1: {0: 600,  1: 0,   2: 300,  3: 800,  4: 500 }, # B -> A(10m), B, C(5m), Start(13m), End(8m)
        2: {0: 900,  1: 300,  2: 0,   3: 900,  4: 400 }, # C -> A(15m), B(5m), C, Start(15m), End(7m)
        3: {0: 700,  1: 800,  2: 900,  3: 0,   4: 1100}, # Start -> A(12m), B(13m), C(15m), Start, End(18m)
        4: {0: 1000, 1: 500,  2: 400,  3: 1100, 4: 0 }   # End -> A(17m), B(8m), C(7m), Start(18m), End
    }
    travelTimeMatrix = TRAVEL_5_LOC

    payload = {
        "locations": locations,
        "technicians": technicians,
        "items": items,
        "fixedConstraints": [],
        "travelTimeMatrix": travelTimeMatrix,
    }

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert len(data["routes"]) == 1, f"Expected 1 route, got {len(data['routes'])}"
    route = data["routes"][0]
    assert len(route["stops"]) == 3, f"Expected 3 stops, got {len(route['stops'])}"
    assert data["unassignedItemIds"] == [], f"Expected no unassigned items, got {data['unassignedItemIds']}"

    # Sort stops by arrival time to ensure consistent order for assertions
    route["stops"].sort(key=lambda x: iso_to_seconds(x["arrivalTimeISO"]))

    stop_a = route["stops"][0]
    stop_b = route["stops"][1]
    stop_c = route["stops"][2]

    # Verify Item IDs (assuming A->B->C is the optimal path chosen)
    assert stop_a["itemId"] == ITEM_A["id"], f"Expected first stop to be {ITEM_A['id']}, got {stop_a['itemId']}"
    assert stop_b["itemId"] == ITEM_B["id"], f"Expected second stop to be {ITEM_B['id']}, got {stop_b['itemId']}"
    assert stop_c["itemId"] == ITEM_C["id"], f"Expected third stop to be {ITEM_C['id']}, got {stop_c['itemId']}"

    # --- Calculate Expected Timings using Unix Timestamps ---
    tech_start_unix = iso_to_seconds(tech_start_iso) # Absolute start time

    # Stop A (Item A @ loc 0, from start depot @ loc 3)
    travel_start_to_a = TRAVEL_5_LOC[3][0] # 700
    expected_sa_arrival_unix = tech_start_unix + travel_start_to_a
    expected_sa_start_unix = expected_sa_arrival_unix # Start immediately
    expected_sa_end_unix = expected_sa_start_unix + ITEM_A["durationSeconds"]

    # Stop B (Item B @ loc 1, from Item A @ loc 0)
    travel_ab = TRAVEL_5_LOC[0][1] # 600
    expected_sb_arrival_unix = expected_sa_end_unix + travel_ab
    expected_sb_start_unix = expected_sb_arrival_unix # Start immediately
    expected_sb_end_unix = expected_sb_start_unix + ITEM_B["durationSeconds"]

    # Stop C (Item C @ loc 2, from Item B @ loc 1)
    travel_bc = TRAVEL_5_LOC[1][2] # 300
    expected_sc_arrival_unix = expected_sb_end_unix + travel_bc
    expected_sc_start_unix = expected_sc_arrival_unix # Start immediately
    expected_sc_end_unix = expected_sc_start_unix + ITEM_C["durationSeconds"]

    # --- Verify Timings using ISO strings (expect 'Z' format) ---
    assert stop_a["arrivalTimeISO"] == seconds_to_iso(expected_sa_arrival_unix), f"Stop A Arrival: Expected {seconds_to_iso(expected_sa_arrival_unix)}, Got {stop_a['arrivalTimeISO']}"
    assert stop_a["startTimeISO"] == seconds_to_iso(expected_sa_start_unix), f"Stop A Start: Expected {seconds_to_iso(expected_sa_start_unix)}, Got {stop_a['startTimeISO']}"
    assert stop_a["endTimeISO"] == seconds_to_iso(expected_sa_end_unix), f"Stop A End: Expected {seconds_to_iso(expected_sa_end_unix)}, Got {stop_a['endTimeISO']}"

    assert stop_b["arrivalTimeISO"] == seconds_to_iso(expected_sb_arrival_unix), f"Stop B Arrival: Expected {seconds_to_iso(expected_sb_arrival_unix)}, Got {stop_b['arrivalTimeISO']}"
    assert stop_b["startTimeISO"] == seconds_to_iso(expected_sb_start_unix), f"Stop B Start: Expected {seconds_to_iso(expected_sb_start_unix)}, Got {stop_b['startTimeISO']}"
    assert stop_b["endTimeISO"] == seconds_to_iso(expected_sb_end_unix), f"Stop B End: Expected {seconds_to_iso(expected_sb_end_unix)}, Got {stop_b['endTimeISO']}"

    assert stop_c["arrivalTimeISO"] == seconds_to_iso(expected_sc_arrival_unix), f"Stop C Arrival: Expected {seconds_to_iso(expected_sc_arrival_unix)}, Got {stop_c['arrivalTimeISO']}"
    assert stop_c["startTimeISO"] == seconds_to_iso(expected_sc_start_unix), f"Stop C Start: Expected {seconds_to_iso(expected_sc_start_unix)}, Got {stop_c['startTimeISO']}"
    assert stop_c["endTimeISO"] == seconds_to_iso(expected_sc_end_unix), f"Stop C End: Expected {seconds_to_iso(expected_sc_end_unix)}, Got {stop_c['endTimeISO']}"

    # Verify total travel time reported for the route
    travel_c_to_end = TRAVEL_5_LOC[2][4] # 400
    expected_total_travel = travel_start_to_a + travel_ab + travel_bc + travel_c_to_end # 700 + 600 + 300 + 400 = 2000
    assert route["totalTravelTimeSeconds"] == expected_total_travel, f"Expected total travel time {expected_total_travel}s, Got {route['totalTravelTimeSeconds']}s"

# Removed patch_main_epoch_day13 fixture argument
def test_optimize_schedule_final_travel_leg(client):
    """Test that totalTravelTimeSeconds includes the travel from the last stop to the endLocationIndex."""
    # Uses 2024-04-13 as the date in ISO strings.

    # Locations: Use separate indices for item location (0) and depots (1, 2)
    LOC_ITEM = {"id": "loc_item", "index": 0, "coords": {"lat": 40.0, "lng": -74.0}}
    LOC_START_DEPOT = {"id": "loc_start_depot", "index": 1, "coords": {"lat": 40.0, "lng": -74.0}}  # Same coords as item
    LOC_END_DEPOT = {"id": "loc_end_depot", "index": 2, "coords": {"lat": 40.1, "lng": -74.1}}

    # Item at location index 0 (separate from depot indices)
    ITEM_FINAL_LEG = {
        "id": "item_final_leg",
        "locationIndex": 0,  # At item location
        "durationSeconds": 600,  # 10m
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }

    # Technician starting at depot 1 and ending at depot 2
    tech_start_iso = "2024-04-13T08:00:00Z" # Fixed time
    TECH_FINAL_LEG = {
        "id": 1,
        "startLocationIndex": 1,  # Start depot
        "endLocationIndex": 2,    # End depot
        "earliestStartTimeISO": tech_start_iso,
        "latestEndTimeISO": "2024-04-13T17:00:00Z",  # Fixed time
    }

    # Travel Matrix: Define travel times, with zero travel from start to item (conceptually same location)
    TRAVEL_FINAL_LEG = {
        0: {0: 0, 1: 0, 2: 900},    # Item -> Item(0), Start(0), End(900s)
        1: {0: 0, 1: 0, 2: 900},    # Start -> Item(0), Start(0), End(900s)
        2: {0: 900, 1: 900, 2: 0}   # End -> Item(900s), Start(900s), End(0)
    }

    payload = {
        "locations": [LOC_ITEM, LOC_START_DEPOT, LOC_END_DEPOT],
        "technicians": [TECH_FINAL_LEG],
        "items": [ITEM_FINAL_LEG],
        "fixedConstraints": [],
        "travelTimeMatrix": TRAVEL_FINAL_LEG,
    }

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success", f"Expected status 'success', got '{data['status']}' with message: {data.get('message')}"
    assert len(data["routes"]) == 1, f"Expected 1 route, got {len(data['routes'])}"
    route = data["routes"][0]
    assert len(route["stops"]) == 1, f"Expected 1 stop, got {len(route['stops'])}"
    assert data["unassignedItemIds"] == [], f"Expected no unassigned items, got {data['unassignedItemIds']}"

    # Verify the single stop timings
    stop = route["stops"][0]
    assert stop["itemId"] == ITEM_FINAL_LEG["id"]

    # --- Calculate Expected Timings using Unix Timestamps ---
    tech_start_unix = iso_to_seconds(tech_start_iso) # Absolute Unix timestamp for 08:00

    # Travel from start depot (1) to item location (0) is 0s
    travel_start_to_item = TRAVEL_FINAL_LEG[1][0] # 0
    expected_arrival_unix = tech_start_unix + travel_start_to_item # Still tech_start_unix
    expected_start_unix = expected_arrival_unix  # Start immediately
    expected_end_unix = expected_start_unix + ITEM_FINAL_LEG["durationSeconds"] # Start + duration

    # --- CORRECTED: Verify timings by comparing ISO strings ---
    expected_arrival_iso = seconds_to_iso(expected_arrival_unix) # e.g., "2024-04-13T08:00:00Z"
    expected_start_iso = seconds_to_iso(expected_start_unix)     # e.g., "2024-04-13T08:00:00Z"
    expected_end_iso = seconds_to_iso(expected_end_unix)         # e.g., "2024-04-13T08:10:00Z"

    assert stop["arrivalTimeISO"] == expected_arrival_iso, f"Arrival time mismatch. Expected {expected_arrival_iso}, Got {stop['arrivalTimeISO']}"
    assert stop["startTimeISO"] == expected_start_iso, f"Start time mismatch. Expected {expected_start_iso}, Got {stop['startTimeISO']}"
    assert stop["endTimeISO"] == expected_end_iso, f"End time mismatch. Expected {expected_end_iso}, Got {stop['endTimeISO']}"

    # FOCUS OF THE TEST: Verify total travel time includes ONLY the final leg
    # Travel from start depot (1) to item location (0): 0s
    # Travel from item location (0) to end depot (2): 900s (final leg)
    travel_item_to_end = TRAVEL_FINAL_LEG[0][2] # 900
    expected_total_travel = travel_start_to_item + travel_item_to_end # 0 + 900 = 900
    assert route["totalTravelTimeSeconds"] == expected_total_travel, \
        f"Expected total travel time {expected_total_travel}s (final leg only), Got {route['totalTravelTimeSeconds']}s"


# Add more tests here for:
# - Correct translation to OR-Tools structures (might require mocking or inspecting internal state)
# - Correct handling of solver results (verifying route structure, timings)
# - Edge cases (e.g., constraints making scheduling impossible, invalid travel matrix)
# - Error handling (e.g., invalid payload structure - FastAPI handles some, but test specific cases)
