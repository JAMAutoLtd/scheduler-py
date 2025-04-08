# Scheduler Development Tasks

## Phase 1: Core Models & Data Access

-   [x] **Define Data Models (`src/scheduler/models.py`):**
    -   [x] Create Python classes/dataclasses for `Address`, `Technician`, `Van`, `Equipment`, `Job`, `Order`, `Service`, `SchedulableUnit`, `DailyAvailability`.
    -   [x] Include relevant fields based on `DATABASE.md` (e.g., IDs, location coordinates, equipment lists, job duration, priority, fixed status, etc.).
    -   [x] Implement helper methods on `Technician` for `has_equipment(required_equipment)` and `has_all_equipment(order_jobs)`.
-   [x] **Implement Data Interface (`src/scheduler/data_interface.py`):**
    -   [x] Function to fetch all active technicians with their associated van and equipment details.
    -   [x] Function to fetch all pending/dynamic jobs eligible for scheduling (not fixed, appropriate status).
    -   [x] Function(s) to fetch necessary related data for jobs/orders (services, vehicle ymm_id, address_id, customer details for priority).
    -   [x] Function(s) to fetch equipment requirements based on service_id and ymm_id.
    -   [x] Function to update a job's assignment (`assigned_technician`, `status`, potentially `estimated_sched`).
    -   [x] Function to update job ETAs (e.g., `estimated_sched` field).

## Phase 1.5: API Layer Implementation

-   [x] **1. Set up Basic FastAPI Application Structure:**
    -   [x] Create `src/scheduler/api` directory with necessary files
    -   [x] Set up main FastAPI app file with proper routing and middleware
    -   [x] Configure CORS, error handling, and authentication requirements
    -   [x] Define API versioning strategy
-   [x] **2. Define API Data Models (Pydantic):**
    -   [x] Create API-specific versions of existing models in `src/scheduler/api/models.py`
    -   [x] Define request/response schemas for each planned endpoint
    -   [x] Implement validation rules and documentation descriptions
    -   [x] Create model conversion utilities between API and internal models
-   [x] **3. Implement Core API Endpoints:**
    -   [x] `GET /technicians` - Fetch active technicians with equipment
    -   [x] `GET /jobs/schedulable` - Fetch pending jobs for scheduling
    -   [x] `GET /equipment/requirements` - Query equipment requirements
    -   [x] `PATCH /jobs/{job_id}/assignment` - Update job assignments
    -   [x] `PATCH /jobs/etas` - Bulk update job ETAs
    -   [x] `GET /jobs` - Add general endpoint to fetch jobs with filtering (e.g., by technician_id, status) (Added: 2024-05-23)
-   [x] **4. API Logic Implementation Details:**
    -   [x] Implement logic within relevant API endpoints to look up the `ymm_id` from `ymm_ref` based on `customer_vehicles.year`, `make`, and `model`
    -   [x] Ensure the fetched `ymm_id` is used for subsequent equipment requirement queries
    -   [x] Create conversion functions between internal models and API response models
    -   [x] Implement proper error handling for database queries and model conversions
-   [x] **5. Database Schema Updates:**
    -   [x] Add `fixed_assignment` (boolean, default: false) field to the `jobs` table - Already in database
    -   [x] Add `fixed_schedule_time` (nullable timestamp) field to the `jobs` table - Already in database
    -   [x] Add `estimated_sched_end`, `customer_eta_start`, `customer_eta_end` (nullable timestamps) - Already in database
    -   [x] Update data_interface.py to use the correct field names (`fixed_assignment` instead of `fixed`, `assigned_technician` instead of `assigned_technician_id`)
-   [x] **6. Implement Remaining Endpoints:**
    -   [x] `PATCH /jobs/{job_id}/schedule` - Set/clear fixed schedule times
    -   [x] `GET /addresses/{id}` - Fetch address details
    -   [x] Other utility endpoints as needed
-   [x] **7. API Testing:**
    -   [x] Create test directory structure with pytest fixtures
    -   [x] Implement tests for each endpoint (success and error cases)
    -   [x] Set up testing patterns for API endpoints

## Phase 2: Utilities & Core Logic

-   [x] **Implement Availability Logic (`src/scheduler/availability.py`):**
    -   [x] Implement `get_technician_availability(tech_id, day_number)`: Fetches/calculates `start_time`, `end_time`, `total_duration` for a given tech on a specific day (relative to today). Define how availability is stored/retrieved. (Placeholder added)
-   [x] **Implement Utility Functions (`src/scheduler/utils.py`):**
    -   [x] Implement `group_jobs_by_order(list_of_jobs)`: Groups jobs based on their `order_id`.
    -   [x] Implement `create_schedulable_units(jobs_by_order)`: Converts grouped jobs into `SchedulableUnit` objects, calculating block priority, aggregate duration, and determining the primary location.
    -   [x] Implement `find_unit_in_list(unit_to_find, list_to_search)`: Helper for removing units.
-   [x] **Implement Routing & Time Calculations (`src/scheduler/routing.py`):**
    -   [x] Implement `fetch_distance_matrix(locations: List[Address], api_key: str)`: Creates and executes calls to the Google Maps Distance Matrix API to get travel times between all provided locations.
    -   [x] Implement `optimize_daily_route_and_get_time(units: List[SchedulableUnit], start_location: Address)`:
        -   Requires integrating a TSP solver (e.g., `python-tsp`, OR-Tools).
        -   Takes a list of units and a start location.
        -   Returns the optimized sequence of units and the total calculated time (travel + durations). (Placeholder added)
    -   [x] Implement `update_etas_for_schedule(technician)`: Calculates specific start/end times and customer-facing ETAs for all jobs in the `technician.schedule` multi-day structure, using accurate travel times. (Logic improved, needs travel time integration)

## Phase 3: Main Scheduler Implementation

-   [ ] **Implement Main Scheduler Logic (`src/scheduler/scheduler.py`):**
    -   [x] Implement `calculate_eta(technician, jobs_to_consider)`: Simulates adding `jobs_to_consider` (as a unit) into the technician's *existing* multi-day schedule, respecting daily limits **and fixed-time job constraints**, and returns the predicted ETA for the *first* job in the unit. (Refined simulation logic 2024-05-21)
    -   [x] Implement `assign_job_to_technician(job, technician)`: Handles the logic/database update for assigning a job via data_interface. (Updated 2024-05-21)
    -   [ ] **Review & Refine `assign_jobs(all_eligible_jobs, all_technicians)` logic** based on pseudocode, using helper functions/classes.
    -   [ ] **Review & Refine `update_job_queues_and_routes(all_technicians)` logic** based on pseudocode, focusing on fixed-time handling and window filling:
        -   [x] Modify daily planning loop to first place fixed-time jobs and calculate remaining time windows (Basic implementation done).
        -   [x] Refine dynamic unit filling logic to accurately respect fragmented time windows, considering travel time. (Refactored 2024-05-23)
    -   [x] **Refactor `scheduler.py` for Modularity & Length:** (Added: {today's date}) (Completed: {today's date})
        -   [x] Extract helper function from `update_job_queues_and_routes` for calculating daily available time windows based on fixed jobs (Step 4a).
        -   [x] Extract helper function from `update_job_queues_and_routes` for fitting dynamic units into available windows (Step 4b).
        -   [x] Extract helper function from `update_job_queues_and_routes` for combining/optimizing the daily route (Step 4c).
        -   [x] Extract helper function from `calculate_eta` for calculating available time windows (potentially shared logic).
        -   [x] Verify/Implement job fetching at the start of `update_job_queues_and_routes`.
-   [ ] **Implement Triggering Mechanism (Location TBD):**
    -   [ ] Design and implement how the `assign_jobs` and `update_job_queues_and_routes` cycle is triggered (e.g., listener on new jobs, scheduled task).

## Phase 4: Refactoring, Integration & Testing

-   [x] **1. Refactor API Layer (`src/scheduler/api/routes.py`):**
    -   [x] **Goal:** Resolve the circular dependency between `api/routes.py` and `data_interface.py`.
    -   [x] Move database interaction logic (currently misplaced in `data_interface.py` functions) into the API route handlers in `routes.py` or into a new dedicated database access module imported by `routes.py`.
    -   [x] Ensure API routes handle data fetching, updates, and necessary data transformations directly.
-   [x] **2. Simplify Data Interface (`src/scheduler/data_interface.py`):** (Verified - No changes needed)
    -   [x] **Goal:** Make `data_interface.py` a pure HTTP client for the scheduler.
    -   [x] Remove database interaction logic. (Already absent)
    -   [x] Retain functions for making API calls (`_make_request`) and converting between API models and internal scheduler models. (Already present)
-   [x] **3. Implement API Tests (`tests/scheduler/api/`):** (Refactored existing tests)
    -   [x] Use a test client (`FastAPI.TestClient`) to send requests to the API endpoints.
    -   [x] Mock database interactions using dependency overrides and `MagicMock` session.
    -   [x] Verify API responses (status codes, JSON structure/data using `api/models.py`).
    -   [x] Test success cases, edge cases, and error handling (4xx/5xx errors).
-   [x] **4. Implement Data Interface Tests (`tests/scheduler/test_data_interface.py` - New File):**
       - **Objective:** Test each function in `src/scheduler/data_interface.py` to verify correct API interaction (calls, response handling, error handling, model conversion).
       - **Strategy:**
             - Mock HTTP requests (e.g., patch `_make_request` or `httpx.Client`).
             - Simulate various API responses (200 success with JSON, 404, 500, network errors).
             - Assert correct API call parameters (URL, method, payload).
             - Assert correct handling of responses (return values, model conversions, error handling).
             - Create test cases for success, errors, and edge cases for each function.
       - **Status:** [x] Completed (2024-05-23)
-   [x] **5. Verify & Update Scheduler Logic Tests (`tests/scheduler/test_scheduler.py`):**
    -   [x] Update mocks to use HTTP calls made via the refactored `data_interface.py`.
    -   [x] Fix test assertions and mocks to handle edge cases appropriately.
    -   [x] Ensure all tests pass with the updated codebase.
-   [ ] **6. Enhance Test Accuracy & Coverage:**
    -   [ ] Implement integration/end-to-end tests simulating full workflows (job creation -> scheduling -> API calls -> DB updates -> ETA updates).
    -   [ ] Add specific tests (API or integration) to verify `fixed_schedule_time` constraints are handled correctly by the *actual* routing/optimization logic (not just mocks).
    -   [ ] Ensure ETA calculations are tested against results from the OR-Tools optimizer.
    -   [ ] Refine Google Maps API Usage (`src/scheduler/routing.py`): Address error handling, timezone consistency, API limits/costs.
-   [ ] **7. Integration:** Ensure all refactored components work together seamlessly.

## Discovered During Work
-   [x] **Integrate Scheduler with API (`src/scheduler/data_interface.py`):** (Completed - Implemented via HTTP calls)
    -   [x] Modify functions in `data_interface.py` to make HTTP calls to the new API endpoints (using `requests` or `httpx`).
    -   [x] Handle API responses and errors appropriately.
    -   [ ] ~~Update scheduler tests to mock HTTP calls instead of database functions.~~ (**Moved to Phase 4.5**)
-   [ ] **Implement Availability Logic (`src/scheduler/availability.py`):** Replace placeholder function `get_technician_availability` with actual logic (Needs implementation beyond placeholder). (Added: 2023-10-27)
-   [x] **Implement Routing Logic with Google Maps & OR-Tools (`src/scheduler/routing.py`):**
    -   [x] Implement `fetch_distance_matrix` function using Google Maps Distance Matrix API.
    -   [x] Ensure `optimize_daily_route_and_get_time` accepts time window constraints (`time_constraints` param added).
    -   [x] Implement time constraint handling within the OR-Tools solver logic. (Done)
-   [x] **Add Dependencies:** Add `ortools` and an HTTP client (e.g., `requests`, `httpx`) to the project's dependency management. (Added: 2024-05-17, Updated: 2024-05-18)
-   [x] **Integrate Google Maps and OR-Tools (`src/scheduler/routing.py`):**
    -   [x] Create OR-Tools data model (time dimension).
    -   [x] Modify OR-Tools distance/transit callbacks to use the pre-fetched distance matrix from `fetch_distance_matrix`.
    -   [x] Set up routing parameters (single vehicle, start/end locations).
    -   [x] Implement time window constraints based on `time_constraints` parameter.
    -   [x] Add service time for each stop (unit duration).
    -   [x] Solve the routing problem and extract the optimized sequence and total time.
    -   [ ] ~~Refine OR-Tools implementation: Add error handling for API calls, ensure timezone consistency, handle API limits/costs.~~ (**Moved to Phase 4.6**)
    -   [x] Refine `update_etas_for_schedule` logic to use precise timings from the OR-Tools solution (when available). (**Done**)
-   [x] Refine `calculate_eta` Simulation (`src/scheduler/scheduler.py`):** Improve accuracy of calculating `last_scheduled_event_end_time` and `last_location`. (Completed 2024-05-21)
-   [ ] ~~**Refine Window Filling Logic (`src/scheduler/scheduler.py`):** Improve travel time calculation accuracy when fitting dynamic units into windows in `update_job_queues_and_routes`.~~ (**Integrated into Phase 3 - update_job_queues_and_routes Refactoring**)
-   [x] **Replace Placeholders in `scheduler.py` (`src/scheduler/scheduler.py`):** Update HACK/TODO comments to use actual imported models and utility functions once available/implemented. (Completed 2024-05-21)

## Future Enhancements
-   [ ] **Enhance Availability System:** Replace the fixed Mon-Fri 9:00-18:30 schedule with a more sophisticated system supporting:
    - Database-driven schedules (Requires schema design - e.g., `technician_schedules`, `time_off` tables)
    - Implementation of query logic in `src/scheduler/availability.py`'s `get_technician_availability` function.
    - Potential API endpoint if availability data needs to be managed externally.
    - External calendar integration (e.g., Google Calendar, Outlook).
    - PTO/vacation tracking.
    - Flexible work hours.
    - Break times (scheduled breaks during the day).
    - Holidays (company-wide or regional).
    - Multiple shifts.
    (Added: 2024-05-16, Details Added: 2024-05-21)
-   [ ] **Adapt Tests for External APIs:** Implement strategies for testing code that interacts with external APIs like Google Maps:
        -   [x] Mock API calls in unit tests (`fetch_distance_matrix` mocked in `test_routing.py`).
        -   [ ] Add optional integration tests marked with pytest marker (`@pytest.mark.google_api`) to verify live interaction.
        -   [ ] Configure pytest (`pytest.ini`) to exclude marked integration tests by default.
-   [ ] **Enhance Routing System:** Replace the simplified routing calculations with a production-ready system:
    - Integrate with Google Maps Distance Matrix API or Here Maps API
    - Implement pre-computed distance matrices for common locations
    - Use professional TSP solver (e.g., OR-Tools)
    - Add traffic-aware routing
    - Consider historical travel time data
    - Handle time windows and constraints
    - Support route optimization across multiple days
    - Add break and lunch period scheduling
    (Added: 2024-05-16)
