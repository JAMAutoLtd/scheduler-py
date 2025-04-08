# Scheduler Development Tasks

## Phase 1: Core Models & Data Access

-   [ ] **Define Data Models (`src/scheduler/models.py`):**
    -   [ ] Create Python classes/dataclasses for `Address`, `Technician`, `Van`, `Equipment`, `Job`, `Order`, `Service`, `SchedulableUnit`, `DailyAvailability`.
    -   [ ] Include relevant fields based on `DATABASE.md` (e.g., IDs, location coordinates, equipment lists, job duration, priority, fixed status, etc.).
    -   [ ] Implement helper methods on `Technician` for `has_equipment(required_equipment)` and `has_all_equipment(order_jobs)`.
-   [ ] **Implement Data Interface (`src/scheduler/data_interface.py`):**
    -   [ ] Function to fetch all active technicians with their associated van and equipment details.
    -   [ ] Function to fetch all pending/dynamic jobs eligible for scheduling (not fixed, appropriate status).
    -   [ ] Function(s) to fetch necessary related data for jobs/orders (services, vehicle ymm_id, address_id, customer details for priority).
    -   [ ] Function(s) to fetch equipment requirements based on service_id and ymm_id.
    -   [ ] Function to update a job's assignment (`assigned_technician`, `status`, potentially `estimated_sched`).
    -   [ ] Function to update job ETAs (e.g., `estimated_sched` field).

## Phase 2: Utilities & Core Logic

-   [ ] **Implement Availability Logic (`src/scheduler/availability.py`):**
    -   [ ] Implement `get_technician_availability(tech_id, day_number)`: Fetches/calculates `start_time`, `end_time`, `total_duration` for a given tech on a specific day (relative to today). Define how availability is stored/retrieved.
-   [ ] **Implement Utility Functions (`src/scheduler/utils.py`):**
    -   [ ] Implement `group_jobs_by_order(list_of_jobs)`: Groups jobs based on their `order_id`.
    -   [ ] Implement `create_schedulable_units(jobs_by_order)`: Converts grouped jobs into `SchedulableUnit` objects, calculating block priority, aggregate duration, and determining the primary location.
    -   [ ] Implement `find_unit_in_list(unit_to_find, list_to_search)`: Helper for removing units.
-   [ ] **Implement Routing & Time Calculations (`src/scheduler/routing.py`):**
    -   [ ] Implement `calculate_travel_time(loc1: Address, loc2: Address)`: Integrates with a mapping API or uses a pre-computed distance matrix to estimate travel time.
    -   [ ] Implement `optimize_daily_route_and_get_time(units: List[SchedulableUnit], start_location: Address)`:
        -   Requires integrating a TSP solver (e.g., `python-tsp`, OR-Tools).
        -   Takes a list of units and a start location.
        -   Returns the optimized sequence of units and the total calculated time (travel + durations).
    -   [ ] Implement `update_etas_for_schedule(technician)`: Calculates specific start/end times and customer-facing ETAs for all jobs in the `technician.schedule` multi-day structure.

## Phase 3: Main Scheduler Implementation

-   [ ] **Implement Main Scheduler Logic (`src/scheduler/scheduler.py`):**
    -   [ ] Implement `calculate_eta(technician, jobs_to_consider)`: Simulates adding `jobs_to_consider` (as a unit) into the technician's *existing* multi-day schedule, respecting daily limits, and returns the predicted ETA for the *first* job in the unit. This will likely need to call parts of the daily planning logic internally.
    -   [ ] Implement `assign_job_to_technician(job, technician)`: Handles the logic/database update for assigning a job. (May call data interface function).
    -   [ ] Implement `assign_jobs(all_eligible_jobs, all_technicians)` based on pseudocode, using the helper functions/classes defined above.
    -   [ ] Implement `update_job_queues_and_routes(all_technicians)` based on pseudocode, using the helper functions/classes.
-   [ ] **Implement Triggering Mechanism (Location TBD):**
    -   [ ] Design and implement how the `assign_jobs` and `update_job_queues_and_routes` cycle is triggered (e.g., listener on new jobs, scheduled task).

## Phase 4: Integration & Testing

-   [ ] **Integration:** Ensure all components work together seamlessly.
-   [ ] **Testing:**
    -   [ ] Unit tests for utility functions, routing calculations, availability logic.
    -   [ ] Integration tests for `assign_jobs` and `update_job_queues_and_routes` with mock data.
    -   [ ] End-to-end tests simulating event triggers and verifying schedule/ETA updates.
