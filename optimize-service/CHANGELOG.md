# Changelog

## [Unreleased] - YYYY-MM-DD

### Fixed
- **Prevent potential `AddDisjunction` crash for items located at depot indices:**
    - **Issue:** While previous fixes ensured test data avoided depot indices for items, the core logic in `main.py` could still crash. If an `OptimizationItem.locationIndex` matched a technician's start/end index, `manager.NodeToIndex(locationIndex)` would return `-1`. The subsequent check `if solver_index == routing.Start()` would fail, leading to an attempt to call `routing.AddDisjunction([-1], ...)` which causes a fatal C++ abort.
    - **Fix:** Added an explicit check in `main.py` *before* calling `manager.NodeToIndex`. It now verifies if `item.locationIndex` exists in the pre-compiled lists of `start` or `end` depot indices. If it does, an info message is logged, and the loop continues to the next item, skipping the `NodeToIndex` and `AddDisjunction` calls entirely for that item. This ensures the application won't crash even if such an item exists in the payload.
- **Resolved `Fatal Python error: Aborted` during optimization:**
    - **Issue:** The application crashed when calling `routing.AddDisjunction` in scenarios where `OptimizationItem` locations (`locationIndex`) coincided with technician start/end depot locations.
    - **Investigation:**
        - Initial checks for invalid parameters (negative penalty, out-of-bounds index) did not reveal the cause.
        - Confirmed via logging that checks preventing `AddDisjunction` for depot nodes (`routing.IsStart/End`) were working, yet the crash persisted on that line, implying it was triggered later for a non-depot item.
        - Temporarily commenting out `AddDisjunction` prevented the crash but revealed that `manager.NodeToIndex(location_index)` was returning `-1` for items located at the depot indices (specifically index 1).
        - Confirmed that `RoutingIndexManager` was initialized with the correct `num_locations`.
        - Hypothesis: `NodeToIndex` behaves unexpectedly or returns `-1` when a `location_index` is also designated as a start/end depot index during manager initialization.
    - **Root Cause:** `manager.NodeToIndex(location_index)` returns `-1` (invalid index) if `location_index` matches an index used for a start/end depot in the `RoutingIndexManager` constructor, even if `num_locations` is correctly specified. Calling `AddDisjunction` with this invalid index `-1` causes the fatal C++ level abort.
    - **Fix:** Refactored the test (`test_optimize_schedule_with_travel`) and potentially underlying data generation logic (if applicable elsewhere) to ensure that location indices used for serviceable items are distinct from location indices used for technician start/end depots. This guarantees `NodeToIndex` returns valid indices for items, preventing the crash when `AddDisjunction` is called.
- **Corrected technician eligibility check:** Fixed logic to correctly check `tech.id in item.eligibleTechnicianIds` instead of the other way around.
- **Fixed timing inconsistency in results:**
    - **Issue:** The solver reported start times for stops that were earlier than the calculated arrival times based on the previous stop's departure and travel time, causing test failures and indicating a problem with time dimension propagation.
    - **Investigation:**
        - The issue persisted even with reduced solver time limits and added slack to the time dimension.
        - Confirmed that `travel_time_callback` and `service_time_callback` were returning correct individual values.
    - **Root Cause:** The `routing.AddDimensionWithVehicleCapacity` method's first argument (`evaluator_index`) defines the *total* transit cost for the dimension's propagation. We were incorrectly passing only the service time callback index. The dimension was therefore only considering service time for propagation and ignoring travel time between nodes for its internal constraints (e.g., `Cumul(j) >= Cumul(i) + TransitCost(i, j)`).
    - **Fix:** Created a new callback `transit_plus_service_time_callback` that sums the travel time and the service time of the *source* node. Registered this combined callback and used its index as the `evaluator_index` for `AddDimensionWithVehicleCapacity`. The `SetArcCostEvaluatorOfAllVehicles` remains set to use *only* the travel time callback index, ensuring the optimization objective correctly minimizes travel distance/time.

### Added
- Added validation checks before `routing.AddDisjunction` call in `main.py`:
    - Check for valid `item.locationIndex` range.
    - Check for non-negative penalty calculation.
    - Explicit check to skip `AddDisjunction` if the item's `solver_index` corresponds to a `routing.Start()` or `routing.End()` node for any vehicle (as per OR-Tools documentation).
    - Added `try...except` block around `AddDisjunction` for better error reporting.
