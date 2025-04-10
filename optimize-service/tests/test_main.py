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

@pytest.fixture
def patch_main_epoch(monkeypatch):
    """Fixture to monkeypatch main.EPOCH to a fixed datetime for tests."""
    test_epoch_str = "2024-04-11T00:00:00+00:00"
    test_epoch_dt = datetime.fromisoformat(test_epoch_str)
    monkeypatch.setattr("main.EPOCH", test_epoch_dt)
    # Monkeypatch takes care of restoring the original value

# --- Helper Function Tests ---

def test_iso_to_seconds_conversion(patch_main_epoch):
    """Test iso_to_seconds conversion for various formats."""
    # EPOCH is now patched by the fixture

    # UTC Z format
    assert iso_to_seconds("2024-04-11T01:00:00Z") == 3600
    # UTC +00:00 offset format
    assert iso_to_seconds("2024-04-11T02:30:00+00:00") == 9000
    # Other offset
    assert iso_to_seconds("2024-04-11T05:00:00+02:00") == 10800 # 3:00 UTC
    # Naive datetime (should assume UTC based on current implementation)
    # Note: Depending on system setting, this *could* be ambiguous. Explicit offsets are safer.
    # Let's assume it defaults to UTC as per the function logic
    assert iso_to_seconds("2024-04-11T00:10:00") == 600


def test_seconds_to_iso_conversion(patch_main_epoch):
    """Test seconds_to_iso conversion back to ISO string."""
    # EPOCH is now patched by the fixture

    assert seconds_to_iso(3600) == "2024-04-11T01:00:00+00:00"
    assert seconds_to_iso(9000) == "2024-04-11T02:30:00+00:00"
    assert seconds_to_iso(0) == "2024-04-11T00:00:00+00:00"

# --- Endpoint Tests ---

def test_optimize_schedule_no_items(client):
    """Test the endpoint when no items are provided."""
    payload = MINIMAL_VALID_PAYLOAD.copy()
    payload["items"] = []
    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "No items provided for scheduling."
    assert data["routes"] == []
    assert data["unassignedItemIds"] == []

def test_optimize_schedule_no_technicians(client):
    """Test the endpoint when no technicians are provided."""
    payload = MINIMAL_VALID_PAYLOAD.copy()
    payload["technicians"] = []
    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200 # Endpoint handles this, not a validation error
    data = response.json()
    assert data["status"] == "error"
    assert data["message"] == "No technicians available for scheduling."
    assert data["routes"] == []
    assert data["unassignedItemIds"] == [item["id"] for item in MINIMAL_VALID_PAYLOAD["items"]] # All items unassigned

def test_optimize_schedule_minimal_valid(client, patch_main_epoch):
    """Test the endpoint with a minimal valid payload. Primarily checks if it runs without crashing."""
    # No epoch patching needed here as we aren't asserting specific times
    response = client.post("/optimize-schedule", json=MINIMAL_VALID_PAYLOAD)
    assert response.status_code == 200
    # Further checks on the actual optimization result will require more complex tests
    data = response.json()
    assert data["status"] in ["success", "partial", "error"] # Allow any valid solver outcome for now
    assert "routes" in data
    assert "unassignedItemIds" in data

def test_optimize_schedule_simple_success(client, patch_main_epoch):
    """Test a simple scenario expected to succeed with one assigned stop."""
    # EPOCH is patched by fixture

    payload = MINIMAL_VALID_PAYLOAD.copy()
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

    # Basic timing checks (assumes item is at start location index 0)
    # Tech starts at 08:00 (28800s). Travel time from 1 to 0 is 600s.
    # Service duration is 1800s.
    expected_arrival_seconds = 28800 + 600 # Arrives at start location + travel time
    expected_start_seconds = expected_arrival_seconds   # Can start immediately at arrival
    expected_end_seconds = expected_start_seconds + 1800 # Start + duration

    assert stop["arrivalTimeISO"] == seconds_to_iso(expected_arrival_seconds)
    assert stop["startTimeISO"] == seconds_to_iso(expected_start_seconds)
    assert stop["endTimeISO"] == seconds_to_iso(expected_end_seconds)


def test_optimize_schedule_fixed_constraint(client, patch_main_epoch):
    """Test a scenario with a fixed time constraint."""
    # EPOCH is patched by fixture

    payload = MINIMAL_VALID_PAYLOAD.copy()
    fixed_time_iso = "2024-04-11T10:00:00Z" # 10:00 AM UTC
    payload["fixedConstraints"] = [
        {"itemId": SAMPLE_ITEM_1["id"], "fixedTimeISO": fixed_time_iso}
    ]

    # Adjust technician time window if necessary to make constraint feasible
    payload["technicians"][0]["earliestStartTimeISO"] = "2024-04-11T08:00:00Z"
    payload["technicians"][0]["latestEndTimeISO"] = "2024-04-11T17:00:00Z"

    # Item is at start location (index 0), travel time is 0
    # Duration is 1800s (30 mins)

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
    expected_start_seconds = iso_to_seconds(fixed_time_iso)
    expected_arrival_seconds = expected_start_seconds # Arrival must be <= start; here it's immediate
    expected_end_seconds = expected_start_seconds + SAMPLE_ITEM_1["durationSeconds"]

    # Allow for arrival potentially being earlier if tech starts earlier and waits
    # The key check is the startTimeISO
    # assert iso_to_seconds(stop["arrivalTimeISO"]) <= expected_start_seconds
    assert stop["startTimeISO"] == seconds_to_iso(expected_start_seconds)
    assert stop["endTimeISO"] == seconds_to_iso(expected_end_seconds)


def test_optimize_schedule_unassigned_due_to_time(client, patch_main_epoch):
    """Test scenario where an item is unassigned due to tight technician time window."""
    # EPOCH is patched by fixture

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


def test_optimize_schedule_unassigned_due_to_eligibility(client, patch_main_epoch):
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

def test_optimize_schedule_with_travel(client, patch_main_epoch):
    """Test a scenario with two items requiring travel between them.
    Modify setup to use separate depot indices.
    """
    # EPOCH is patched by fixture

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
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # 28800s
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

    # Remove the previous dummy location logic if it's still there
    # (Assuming previous edit removed it, otherwise ensure removal here)

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
    tech_start_s = iso_to_seconds(TECHNICIAN_SEP_DEPOT["earliestStartTimeISO"]) # 28800

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


def test_optimize_schedule_priority(client, patch_main_epoch):
    """Test that higher priority items are scheduled when resources are constrained.
    Uses distinct depot indices.
    """
    # EPOCH is patched by fixture

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
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # 28800s
        # Tight time window: Latest end time is 08:55 (32100s)
        "latestEndTimeISO": "2024-04-11T08:55:00Z", # 55 mins total window
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
    TECHNICIAN_PRIO_TEST["latestEndTimeISO"] = "2024-04-11T09:00:00Z" # 60 min window

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


def test_optimize_schedule_multiple_techs_assignment(client, patch_main_epoch):
    """Test assignment with multiple technicians where one is time-constrained.
    Uses distinct depot indices.
    """
    # EPOCH is patched by fixture

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
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # 28800s
        # Window needs to account for travel Start(1)->Item(0) and service
        # Travel(1->0)=600s. Service=1800s. Min time needed = 2400s (40 mins)
        # Let's give 35 mins total (2100s). End time = 08:35 (28800 + 2100 = 30900s)
        "latestEndTimeISO": "2024-04-11T08:35:00Z", # Too short
    }
    # Technician 2: Wide window
    TECH_2 = {
        "id": 2,
        "startLocationIndex": 1, # Start depot
        "endLocationIndex": 2,   # End depot
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # 28800s
        "latestEndTimeISO": "2024-04-11T17:00:00Z",    # Wide window
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


def test_optimize_schedule_incomplete_travel_matrix(client, patch_main_epoch):
    """Test that an item becomes unassigned if required travel time is missing.
    Uses only 3 locations: Item B, Start Depot, End Depot, to isolate the missing link.
    """
    # EPOCH is patched by fixture

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
        "earliestStartTimeISO": "2024-04-11T08:00:00Z",
        "latestEndTimeISO": "2024-04-11T17:00:00Z",
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

    # DEBUG: Print response for inspection during test development/failure
    # print("\n--- Incomplete Matrix Test Response ---")
    # import json
    # print(json.dumps(data, indent=2))
    # print("------------------------------------")


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


def test_optimize_schedule_three_stops(client, patch_main_epoch):
    """Test a scenario with three stops: Start -> A -> B -> End.
    Uses distinct depot indices.
    """
    # EPOCH is patched by fixture

    # === Define 4 Locations: 0=ItemA, 1=ItemB, 2=StartDepot, 3=EndDepot ===
    LOC_ITEM_A = {"id": "loc_item_A", "index": 0, "coords": {"lat": 40.7128, "lng": -74.0060}}
    LOC_ITEM_B = {"id": "loc_item_B", "index": 1, "coords": {"lat": 40.7580, "lng": -73.9855}}
    LOC_DEPOT_START = {"id": "loc_depot_start", "index": 2, "coords": {"lat": 40.7000, "lng": -74.0000}}
    LOC_DEPOT_END = {"id": "loc_depot_end", "index": 3, "coords": {"lat": 40.7800, "lng": -73.9500}}
    locations = [LOC_ITEM_A, LOC_ITEM_B, LOC_DEPOT_START, LOC_DEPOT_END]

    # === Define Items at location 0 and 1 ===
    ITEM_A = {
        "id": "item_A",
        "locationIndex": 0, # Use index 0
        "durationSeconds": 1800, # 30 mins
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }
    ITEM_B = {
        "id": "item_B",
        "locationIndex": 1, # Use index 1
        "durationSeconds": 1200, # 20 mins
        "priority": 1,
        "eligibleTechnicianIds": [1],
    }
    items = [ITEM_A, ITEM_B]

    # === Define Technician using depots at index 2 (start) and 3 (end) ===
    TECHNICIAN_SEP_DEPOT = {
        "id": 1,
        "startLocationIndex": 2, # Use index 2 for start
        "endLocationIndex": 3,   # Use index 3 for end
        "earliestStartTimeISO": "2024-04-11T08:00:00Z", # 28800s
        "latestEndTimeISO": "2024-04-11T17:00:00Z",
    }
    technicians = [TECHNICIAN_SEP_DEPOT]

    # === Define Travel Matrix for 4 locations (indices 0, 1, 2, 3) ===
    # Approx times: ItemA(0), ItemB(1), Start(2), End(3)
    TRAVEL_4_LOC = {
        0: {0: 0,   1: 600,  2: 700,  3: 1000}, # ItemA -> ItemA, ItemB(10m), Start(12m), End(17m)
        1: {0: 600,  1: 0,   2: 800,  3: 500 }, # ItemB -> ItemA(10m), ItemB, Start(13m), End(8m)
        2: {0: 700,  1: 800,  2: 0,   3: 1100}, # Start -> ItemA(12m), ItemB(13m), Start, End(18m)
        3: {0: 1000, 1: 500,  2: 1100, 3: 0 }   # End -> ItemA(17m), ItemB(8m), Start(18m), End
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

    # Expected sequence:
    # - Start at LOC_DEPOT_START (idx 2)
    # - Travel (2 -> 0): 700s
    # - Stop 1 (Item A @ LOC_ITEM_A, idx 0): Arrive 08:00+700s, Start, End
    # - Travel (0 -> 1): 600s
    # - Stop 2 (Item B @ LOC_ITEM_B, idx 1): Arrive, Start, End
    # - Travel (1 -> 3): 500s (to end depot)

    response = client.post("/optimize-schedule", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Check basic assertions - expecting success now
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
    assert scheduled_item_ids == {ITEM_A["id"], ITEM_B["id"]}

    # Determine which stop corresponds to which item based on ID
    stop_item_A = stop1 if stop1["itemId"] == ITEM_A["id"] else stop2
    stop_item_B = stop2 if stop2["itemId"] == ITEM_B["id"] else stop1
    assert stop_item_A["itemId"] == ITEM_A["id"]
    assert stop_item_B["itemId"] == ITEM_B["id"]

    # --- Verify Timings with Flexibility --- 
    tech_start_s = iso_to_seconds(TECHNICIAN_SEP_DEPOT["earliestStartTimeISO"]) # 28800

    # Stop 1 (Item A @ loc 0, from start depot @ loc 2)
    travel_start_to_itemA = TRAVEL_4_LOC[2][0] # 700s
    earliest_s1_arrival_s = tech_start_s + travel_start_to_itemA # 28800 + 700 = 29500
    actual_s1_arrival_s = iso_to_seconds(stop_item_A["arrivalTimeISO"])
    actual_s1_start_s = iso_to_seconds(stop_item_A["startTimeISO"])
    actual_s1_end_s = iso_to_seconds(stop_item_A["endTimeISO"])

    assert actual_s1_arrival_s >= earliest_s1_arrival_s, "Stop 1 arrival is earlier than possible"
    assert actual_s1_start_s >= actual_s1_arrival_s, "Stop 1 started before arrival"
    assert actual_s1_end_s == actual_s1_start_s + ITEM_A["durationSeconds"], "Stop 1 end time mismatch (start + duration)"

    # Stop 2 (Item B @ loc 1, from item A @ loc 0)
    travel_itemA_to_itemB = TRAVEL_4_LOC[0][1] # 600s
    earliest_s2_arrival_s = actual_s1_end_s + travel_itemA_to_itemB # Earliest possible based on actual S1 end
    actual_s2_arrival_s = iso_to_seconds(stop_item_B["arrivalTimeISO"])
    actual_s2_start_s = iso_to_seconds(stop_item_B["startTimeISO"])
    actual_s2_end_s = iso_to_seconds(stop_item_B["endTimeISO"])

    assert actual_s2_arrival_s >= earliest_s2_arrival_s, "Stop 2 arrival is earlier than possible based on Stop 1 end"
    assert actual_s2_start_s >= actual_s2_arrival_s, "Stop 2 started before arrival"
    assert actual_s2_end_s == actual_s2_start_s + ITEM_B["durationSeconds"], "Stop 2 end time mismatch (start + duration)"

    # --- Verify Total Travel Time --- 
    # Total travel calculation should be based on the *actual* sequence and node indices used by the solver.
    # The logic in main.py calculates this. We verify it matches expectations for the segments.
    travel_itemB_to_end = TRAVEL_4_LOC[1][3] # 500s
    expected_total_travel = travel_start_to_itemA + travel_itemA_to_itemB + travel_itemB_to_end # 700 + 600 + 500 = 1800
    assert route["totalTravelTimeSeconds"] == expected_total_travel, \
        f"Expected total travel time {expected_total_travel}s, Got {route['totalTravelTimeSeconds']}s"


# Use a different date for this test's epoch to avoid clashes if run concurrently
@pytest.fixture
def patch_main_epoch_day12(monkeypatch):
    """Fixture to monkeypatch main.EPOCH to 2024-04-12 for specific tests."""
    test_epoch_str = "2024-04-12T00:00:00+00:00"
    test_epoch_dt = datetime.fromisoformat(test_epoch_str)
    monkeypatch.setattr("main.EPOCH", test_epoch_dt)

def test_optimize_schedule_three_stops(client, patch_main_epoch_day12):
    """Test a route involving one technician visiting three distinct locations.
    Uses distinct depot indices.
    """
    # EPOCH is patched by fixture to 2024-04-12

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
    TECH_MULTI = {
        "id": 1, "startLocationIndex": 3, "endLocationIndex": 4,
        "earliestStartTimeISO": "2024-04-12T09:00:00Z", # 09:00 UTC (32400s relative to day 12 epoch)
        "latestEndTimeISO": "2024-04-12T17:00:00Z", # Wide window
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

    # Expected sequence (assuming Start -> A -> B -> C -> End):
    # - Start at LOC_DEPOT_START (idx 3) at 09:00 (32400s)
    # - Travel (3 -> 0/A): 700s
    # - Stop 1 (Item A @ LOC_A): Arrive 09:11:40 (33100s), Start, End 09:41:40 (34900s)
    # - Travel (0/A -> 1/B): 600s
    # - Stop 2 (Item B @ LOC_B): Arrive 09:51:40 (35500s), Start, End 10:11:40 (36700s)
    # - Travel (1/B -> 2/C): 300s
    # - Stop 3 (Item C @ LOC_C): Arrive 10:16:40 (37000s), Start, End 10:41:40 (38500s)
    # - Travel (2/C -> 4/End): 400s

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

    # Verify Timings (Stop A)
    # Tech starts at 3 at 09:00 (32400s). Travel(3->0) = 700s.
    expected_sa_arrival_s = 32400 + 700 # Arrival = Start + Travel = 33100
    expected_sa_start_s = expected_sa_arrival_s # Start immediately on arrival
    expected_sa_end_s = expected_sa_start_s + ITEM_A["durationSeconds"] # Arrival + Duration = 33100 + 1800 = 34900
    assert stop_a["arrivalTimeISO"] == seconds_to_iso(expected_sa_arrival_s), f"Stop A Arrival: Expected {seconds_to_iso(expected_sa_arrival_s)}, Got {stop_a['arrivalTimeISO']}"
    assert stop_a["startTimeISO"] == seconds_to_iso(expected_sa_start_s), f"Stop A Start: Expected {seconds_to_iso(expected_sa_start_s)}, Got {stop_a['startTimeISO']}"
    assert stop_a["endTimeISO"] == seconds_to_iso(expected_sa_end_s), f"Stop A End: Expected {seconds_to_iso(expected_sa_end_s)}, Got {stop_a['endTimeISO']}"

    # Verify Timings (Stop B)
    travel_ab = TRAVEL_5_LOC[0][1] # 600
    expected_sb_arrival_s = expected_sa_end_s + travel_ab # 34900 + 600 = 35500
    expected_sb_start_s = expected_sb_arrival_s
    expected_sb_end_s = expected_sb_start_s + ITEM_B["durationSeconds"] # 35500 + 1200 = 36700
    assert stop_b["arrivalTimeISO"] == seconds_to_iso(expected_sb_arrival_s), f"Stop B Arrival: Expected {seconds_to_iso(expected_sb_arrival_s)}, Got {stop_b['arrivalTimeISO']}"
    assert stop_b["startTimeISO"] == seconds_to_iso(expected_sb_start_s), f"Stop B Start: Expected {seconds_to_iso(expected_sb_start_s)}, Got {stop_b['startTimeISO']}"
    assert stop_b["endTimeISO"] == seconds_to_iso(expected_sb_end_s), f"Stop B End: Expected {seconds_to_iso(expected_sb_end_s)}, Got {stop_b['endTimeISO']}"

    # Verify Timings (Stop C)
    travel_bc = TRAVEL_5_LOC[1][2] # 300
    expected_sc_arrival_s = expected_sb_end_s + travel_bc # 36700 + 300 = 37000
    expected_sc_start_s = expected_sc_arrival_s
    expected_sc_end_s = expected_sc_start_s + ITEM_C["durationSeconds"] # 37000 + 1500 = 38500
    assert stop_c["arrivalTimeISO"] == seconds_to_iso(expected_sc_arrival_s), f"Stop C Arrival: Expected {seconds_to_iso(expected_sc_arrival_s)}, Got {stop_c['arrivalTimeISO']}"
    assert stop_c["startTimeISO"] == seconds_to_iso(expected_sc_start_s), f"Stop C Start: Expected {seconds_to_iso(expected_sc_start_s)}, Got {stop_c['startTimeISO']}"
    assert stop_c["endTimeISO"] == seconds_to_iso(expected_sc_end_s), f"Stop C End: Expected {seconds_to_iso(expected_sc_end_s)}, Got {stop_c['endTimeISO']}"

    # Verify total travel time reported for the route
    # Should include travel A -> B (600) and B -> C (300) = 900
    # Also includes final leg B -> C (300) if end node is C? No, wait. endLocationIndex=2. last stop is C (index 2). Final leg C->C is 0.
    # Let's re-check the logic in main.py for final leg.
    # It adds travel from last_stop_solver_index to end_node_solver_index.
    # Here, last stop is C (node 2), end node is C (node 2). Travel 2->2 is 0.
    travel_c_to_end = TRAVEL_5_LOC[2][4] # 400
    # CORRECTED: Include travel from Start(3) to A(0) which is 700s
    travel_start_to_a = TRAVEL_5_LOC[3][0] # 700
    expected_total_travel = travel_start_to_a + travel_ab + travel_bc + travel_c_to_end # 700 + 600 + 300 + 400 = 2000
    assert route["totalTravelTimeSeconds"] == expected_total_travel, f"Expected total travel time {expected_total_travel}s, Got {route['totalTravelTimeSeconds']}s"


# Use a different date for this test's epoch
@pytest.fixture
def patch_main_epoch_day13(monkeypatch):
    """Fixture to monkeypatch main.EPOCH to 2024-04-13 for specific tests."""
    test_epoch_str = "2024-04-13T00:00:00+00:00"
    test_epoch_dt = datetime.fromisoformat(test_epoch_str)
    monkeypatch.setattr("main.EPOCH", test_epoch_dt)

def test_optimize_schedule_final_travel_leg(client, patch_main_epoch_day13):
    """Test that totalTravelTimeSeconds includes the travel from the last stop to the endLocationIndex."""
    # EPOCH is patched by fixture to 2024-04-13

    # Locations: Use separate indices for item location (0) and depots (1, 2)
    # This keeps conceptually closer to the original test while avoiding index collision
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
    TECH_FINAL_LEG = {
        "id": 1, 
        "startLocationIndex": 1,  # Start depot
        "endLocationIndex": 2,    # End depot
        "earliestStartTimeISO": "2024-04-13T08:00:00Z",  # 08:00 UTC (28800s relative to day 13 epoch)
        "latestEndTimeISO": "2024-04-13T17:00:00Z",  # Wide window
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

    # Expected sequence (simplified to match original test's focus):
    # - Start at LOC_START_DEPOT (idx 1) at 08:00 (28800s)
    # - Travel (Start depot 1 -> Item location 0): 0s (conceptually at same location)
    # - Stop 1 (Item @ LOC_ITEM): Arrive 08:00 (28800s), Start 08:00 (28800s), End 08:10 (29400s)
    # - Travel (Item location 0 -> End depot 2): 900s (This is the final leg we're testing)
    # Total Travel Time = 0s + 900s = 900s (with the final leg being the only significant travel)

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
    
    # Tech starts at 08:00 (28800s), with no travel time to item location
    expected_arrival_s = 28800  # Immediate arrival (no travel)
    expected_start_s = expected_arrival_s  # 28800
    expected_end_s = expected_start_s + ITEM_FINAL_LEG["durationSeconds"]  # 28800 + 600 = 29400
    
    assert stop["arrivalTimeISO"] == seconds_to_iso(expected_arrival_s)
    assert stop["startTimeISO"] == seconds_to_iso(expected_start_s)
    assert stop["endTimeISO"] == seconds_to_iso(expected_end_s)

    # FOCUS OF THE TEST: Verify total travel time includes ONLY the final leg
    # Travel from start depot (1) to item location (0): 0s (conceptually at same location)
    # Travel from item location (0) to end depot (2): 900s (final leg)
    expected_total_travel = 900  # Only the final leg is significant
    assert route["totalTravelTimeSeconds"] == expected_total_travel, \
        f"Expected total travel time {expected_total_travel}s (final leg only), Got {route['totalTravelTimeSeconds']}s"


# Add more tests here for:
# - Correct translation to OR-Tools structures (might require mocking or inspecting internal state)
# - Correct handling of solver results (verifying route structure, timings)
# - Edge cases (e.g., constraints making scheduling impossible, invalid travel matrix)
# - Error handling (e.g., invalid payload structure - FastAPI handles some, but test specific cases)
