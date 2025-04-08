# Overview

## 1. Order Submission

**Customer provides the following information:**

- **Vehicle Information:**
    - **VIN** \(or **Year/Make/Model** if VIN is unavailable; form auto-calculates YMM from VIN\)
- **Repair Order Number:** _\(Insurance customers only\)_
- **Address:** Selected from saved addresses \(modifiable by admin or customer; addresses may be shared\)
- **Earliest Available Date & Time**
- **Services Required:** _\(Multiple selections allowed\)_
    - **ADAS:**
        - Front Radar
        - Windshield Camera
        - 360 Camera/Side Mirror
        - Blind Spot Monitor
        - Parking Assist Sensor
    - **Module Replacement Programming:**
        - ECM, TCM, BCM, Airbag Module, Instrument Cluster, Front Radar, Windshield Camera, Blind Spot Monitor, Headlamp Module, Other
    - **Keys or Immobilizer Programming:**
        - Immobilizer Module Replaced
        - All Keys Lost/No Working Keys
            - **Push Button Start:**
                - JAM Provides Keys \(with Key Quantity\)
                - Customer Provides Keys \(with Key Quantity\)
            - **Blade Ignition:**
                - JAM Provides Keys \(with Key Quantity\)
                - Customer Provides Keys \(with Key Quantity\)
        - Adding Spare Keys _\(same options as above\)_
    - **Diagnostic or Wiring Repair**
- **Additional Details:**
    - Notes
    - Uploads \(pictures, scan reports, etc.\)

---
## 2. Checks & Processes

- **ADAS Equipment Check:**
    - For each service requested, find the equipment required for the service/vehicle in our database, e.g. for Front Radar service on vehicle 2022 ACURA ILX, use AUTEL-CSC0602/01.

---
## 3. Job Creation & Prioritization

- **Job Creation:**
- Jobs are created from orders, creating a job for each service requested. The results of the _equipment_requirements check will be used in determining the assigned technicians.

- **Job Prioritization:**
- Jobs are assigned priorty based on the following:
    1. Insurance customer jobs
    2. Commercial customer ADAS jobs
    3. Airbag jobs
    4. Key/Immobilizer jobs
    5. Commercial customer module replacement and diagnostic jobs
    6. Residential customer module replacement jobs
    7. Residential customer ADAS jobs
    8. Residential customer diagnostic jobs

---
## SCHEDULER SYSTEM OVERVIEW

The scheduler is a dynamic system designed to continuously optimize job assignments and technician routes, balancing efficiency, customer ETAs, and job priorities within daily operational constraints.

### Core Components

1.  **Technician Assignment Logic**
    *   **Eligibility:** Determines technician suitability based on `van_equipment` versus job `equipment_requirements`.
    *   **Order Grouping Preference:** For multi-job orders, prioritizes assigning all jobs to a single, fully equipped technician if available. If not, jobs from the order are assigned individually based on best fit.
    *   **ETA Optimization:** When multiple technicians are eligible, selects the one predicted to have the earliest ETA. **Note:** ETA prediction during assignment must simulate placement within the technician's multi-day schedule respecting daily constraints and existing fixed-time appointments.
    *   **Fixed Assignments:** Supports manual ("fixed") job assignments (`jobs.fixed_assignment` field). Jobs with `fixed_assignment=true` *cannot* be dynamically reassigned but *are* included in their assigned technician's route optimization.
    *   **Fixed Schedule Times:** Supports optional fixed start times (`jobs.fixed_schedule_time` field). These jobs act as anchors in the daily schedule.

2.  **Job Queuing & Routing Logic (Daily Planning)**
    *   **Daily Boundaries:** Routes are planned on a day-by-day basis, respecting each technician's specific working hours and availability for that day.
    *   **Starting Locations:** Route calculation starts from the technician's *current location* for the first day (today) and from their *home base* for subsequent days.
    *   **Handling Fixed Times:** Jobs with a `fixed_schedule_time` for the current planning day are scheduled first. They consume their required time slots, potentially fragmenting the remaining available time for dynamic jobs.
    *   **Schedulable Units:** Dynamic (non-fixed-time) jobs are grouped into units: indivisible blocks for multi-job orders assigned to the same tech, or individual units for single jobs. Block priority is determined by the highest priority job within it.
    *   **Priority & Daily Fit (Dynamic Units):** Dynamic units are sorted by priority. The system iteratively fills the *available time windows* within each day, selecting the highest priority units that fit (considering travel + duration).
    *   **Route Optimization (Daily TSP):** A TSP algorithm optimizes the sequence of *all* units scheduled *within each specific day* (both fixed-time and dynamic) to minimize travel time. **Google OR-Tools will be used** for this task due to its robust capabilities and native support for time window constraints, which are essential for handling `fixed_schedule_time` jobs correctly.
    *   **Multi-Day Schedule:** The result is a multi-day schedule for each technician (e.g., `tech.schedule = {day1: [unitA_fixed, unitB, unitC_fixed], day2: [unitD]}`).
    *   **Continuous ETA Updates:** ETAs for *all* jobs (across all scheduled days) are calculated and updated based on their position in the final, optimized multi-day schedule.

### Dynamic Operation & Recalculation

The system operates dynamically, constantly seeking the optimal state:

*   **Recalculation Loop:** Core assignment and daily routing logic is re-evaluated in response to specific events.
*   **Re-evaluation Scope:** Re-evaluation considers *all* active, non-fixed jobs against the current multi-day schedules and technician statuses.
*   **Event Triggers:** Recalculations are typically triggered by: new jobs, job status changes, technician status/location changes, manual interventions, or optional periodic timers.

This continuous re-optimization ensures the system adapts to changing conditions, always aiming for the best possible job assignments and ETAs according to defined priorities and daily operational constraints.

---
## API LAYER FOR DATA ACCESS

To facilitate interaction between the dynamic scheduler components and the underlying database, a dedicated API layer is implemented using FastAPI. This layer serves several key purposes:

1.  **Abstraction:** Decouples the scheduler logic from direct database interaction. The scheduler only needs to know how to communicate with the API endpoints.
2.  **Encapsulation:** The API enforces how data is accessed and modified. It should contain the necessary database query logic (using SQLAlchemy/SQLModel), joins, and data transformations.
3.  **Scalability & Maintainability:** Allows the scheduler and the data access logic to be developed, scaled, and maintained independently.
4.  **Production Readiness:** Provides a standard, robust HTTP-based interface suitable for deployment, replacing placeholders or direct database calls within the scheduler.

**Intended Architecture:**

*   The `scheduler` (`src/scheduler/scheduler.py`, `src/scheduler/routing.py`) interacts with the API via the `data_interface.py` module.
*   `src/scheduler/data_interface.py` acts purely as an **HTTP client**, making requests to the API endpoints and converting data between API models and internal scheduler models.
*   `src/scheduler/api/routes.py` defines the API endpoints and contains the core application logic, including interaction with the database (potentially via a dedicated database access layer/module).

**Current State & Required Refactoring:**

*   Currently, a **circular dependency** exists: `api/routes.py` incorrectly calls functions within `data_interface.py`, which in turn makes HTTP calls back to the API defined in `routes.py`.
*   **Refactoring Needed:** The logic for database interaction currently present within `data_interface.py` needs to be moved into the `api/routes.py` handlers (or a new dedicated database access module used by the API). `data_interface.py` must be simplified to only handle making HTTP requests and performing data model conversions.

---
## SCHEDULER PSEUDOCODE

# Revised assign_jobs pseudocode (Job-centric assignment)
def assign_jobs(all_jobs, technicians):
    # Filter out jobs that are already assigned and marked as fixed
    dynamic_jobs_to_consider = [job for job in all_jobs if not job.fixed]

    # Group ONLY the dynamic jobs by order
    for order in group_jobs_by_order(dynamic_jobs_to_consider):
        best_tech_for_order = None
        eligible_techs = [] # Initialize eligible_techs

        # Check if this is a multi-job order
        if len(order.jobs) > 1:
            # Identify technicians fully equipped for the entire order
            fully_equipped_techs = [tech for tech in technicians if tech.has_all_equipment(order)]
            if fully_equipped_techs:
                eligible_techs = fully_equipped_techs
                # Calculate ETAs for fully equipped techs based on the whole order
                # Note: calculate_eta needs to simulate insertion considering existing fixed_schedule_time constraints
                etas = {tech: calculate_eta(tech, order.jobs) for tech in eligible_techs}
                best_tech_for_order = min(etas, key=etas.get)
            else:
                # No single tech is fully equipped; handle jobs individually later
                pass 
        else: # Single job order
            single_job = order.jobs[0]
            eligible_techs = [tech for tech in technicians if tech.has_equipment(single_job.equipment_required)]
            if eligible_techs:
                 # Calculate ETAs for the single job
                 # Note: calculate_eta needs to simulate insertion considering existing fixed_schedule_time constraints
                etas = {tech: calculate_eta(tech, [single_job]) for tech in eligible_techs}
                best_tech_for_order = min(etas, key=etas.get)

        # --- Assignment Phase ---
        if best_tech_for_order is not None:
            # Assign ALL jobs in this order to the determined best technician
            for job in order.jobs:
                assign_job_to_technician(job, best_tech_for_order)
        else:
            # Handle multi-job orders where NO single tech was fully equipped
            # Process each job individually to find the best available tech for THAT job
            if len(order.jobs) > 1: # Check needed as single jobs are handled above
                for job in order.jobs:
                    individual_eligible = [tech for tech in technicians if tech.has_equipment(job.equipment_required)]
                    if individual_eligible:
                        # Note: calculate_eta needs to simulate insertion considering existing fixed_schedule_time constraints
                        etas = {tech: calculate_eta(tech, [job]) for tech in individual_eligible}
                        best_tech_for_job = min(etas, key=etas.get)
                        assign_job_to_technician(job, best_tech_for_job)
                    # Else: Handle case where no tech can do this specific job (optional logging/error handling)

    # Routing update remains the same (processes all assigned jobs per tech)
    update_job_queues_and_routes(technicians)

# Revised update_job_queues_and_routes with fixed schedule time handling
def update_job_queues_and_routes(technicians):
    for tech in technicians:
        all_assigned_jobs = tech.queue # Get all jobs assigned to the tech

        # 1. Group jobs & Create schedulable units
        jobs_by_order = group_jobs_by_order(all_assigned_jobs)
        all_units = create_schedulable_units(jobs_by_order) # Includes priority, fixed_assignment, fixed_schedule_time

        # 2. Separate fixed-time and dynamic units
        fixed_time_units = [u for u in all_units if u.fixed_schedule_time is not None]
        dynamic_units = [u for u in all_units if u.fixed_schedule_time is None]
        
        # 3. Sort dynamic units by priority
        dynamic_units.sort(key=lambda unit: unit.priority)

        # 4. Plan schedule day by day
        tech_schedule = {} # Stores the final plan {day_num: [unit1, unit2], ...}
        remaining_dynamic_units = list(dynamic_units)
        pending_fixed_units = list(fixed_time_units) # Track fixed units yet to be placed
        day_number = 1
        max_planning_days = 14 # Or some reasonable limit

        while (remaining_dynamic_units or pending_fixed_units) and day_number <= max_planning_days:
            # Get tech availability for this specific day
            daily_availability = get_technician_availability(tech, day_number)
            if not daily_availability or daily_availability['total_duration'] <= timedelta(0):
                if not remaining_dynamic_units and not pending_fixed_units: break
                day_number += 1
                continue

            day_start = daily_availability['start_time']
            day_end = daily_availability['end_time']
            tech_schedule[day_number] = [] # Initialize empty schedule for the day

            # 4a. Place fixed units for *this* day & determine available windows
            scheduled_fixed_today = []
            available_windows = []
            current_window_start = day_start
            fixed_for_today_sorted = sorted(
                [u for u in pending_fixed_units if u.fixed_schedule_time.date() == day_start.date()],
                key=lambda u: u.fixed_schedule_time
            )
            units_not_scheduled_fixed = []

            for fixed_unit in fixed_for_today_sorted:
                fixed_start = fixed_unit.fixed_schedule_time
                fixed_end = fixed_start + fixed_unit.duration
                if fixed_start >= current_window_start and fixed_end <= day_end:
                    # Add window before this fixed unit
                    if fixed_start > current_window_start:
                        available_windows.append((current_window_start, fixed_start))
                    scheduled_fixed_today.append(fixed_unit)
                    current_window_start = fixed_end # Advance start for next potential window
                else:
                    log(f"Warning: Fixed unit {fixed_unit.id} conflicts on day {day_number}")
                    units_not_scheduled_fixed.append(fixed_unit)
            
            # Add final window after the last fixed unit
            if current_window_start < day_end:
                available_windows.append((current_window_start, day_end))

            # Update overall pending fixed list
            pending_fixed_units = [u for u in pending_fixed_units if u not in fixed_for_today_sorted] + units_not_scheduled_fixed

            # 4b. Fill available windows with dynamic units (prioritized)
            scheduled_dynamic_today = []
            temp_remaining_dynamic = list(remaining_dynamic_units) # Work on a copy
            units_scheduled_ids = set()

            for dyn_unit in temp_remaining_dynamic: # Already sorted by priority
                fitted = False
                # Try to fit dyn_unit into the earliest possible slot in available_windows
                # This requires simulating travel time from the previous event (fixed or dynamic)
                # Simplified logic: find first window where it fits sequentially after last placement
                # (Pseudocode omits complex travel simulation within windows for brevity)
                for i, (win_start, win_end) in enumerate(available_windows):
                    # Simplified check: does duration fit in window?
                    if dyn_unit.duration <= (win_end - win_start): 
                         # Assume it fits (needs travel check in reality)
                         scheduled_dynamic_today.append(dyn_unit)
                         units_scheduled_ids.add(dyn_unit.id)
                         fitted = True
                         # TODO: Refine window logic (remove/split window after placement)
                         break # Place in first available window for simplicity
                # If fitted, it's removed from consideration for this day (handled later)
            
            # 4c. Combine and Optimize the day's schedule
            all_units_today = scheduled_fixed_today + scheduled_dynamic_today
            if all_units_today:
                start_location = tech.current_location if day_number == 1 else tech.home_location
                time_constraints = {u.id: u.fixed_schedule_time for u in scheduled_fixed_today}
                
                # Call optimizer with time constraints
                optimized_units, total_time = optimize_daily_route_and_get_time(
                    all_units_today, start_location, time_constraints
                )

                # Final check against total daily duration
                if total_time <= daily_availability['total_duration']:
                    tech_schedule[day_number] = optimized_units
                    # Remove successfully scheduled dynamic units from main list
                    remaining_dynamic_units = [u for u in remaining_dynamic_units if u.id not in units_scheduled_ids]
                else:
                    log(f"Warning: Optimized route for tech {tech.id} day {day_number} too long. Only scheduling fixed.")
                    # Only keep fixed units if optimized route failed
                    tech_schedule[day_number] = [u for u in optimized_units if u in scheduled_fixed_today]
                    # Dynamic units remain in remaining_dynamic_units

            # 4d. Prepare for next day
            day_number += 1

        # 5. Store the final multi-day schedule
        tech.schedule = tech_schedule

        # 6. Update ETAs for ALL jobs based on the final schedule
        update_etas_for_schedule(tech)

# --- Helper function signatures needed ---
# def create_schedulable_units(jobs_by_order): -> list_of_units (with jobs, priority, location, duration, fixed_assignment, fixed_schedule_time)
# def get_technician_availability(tech, day_number): -> dict (with start_time, end_time, total_duration) or None # Should return tz-aware datetimes
# def calculate_travel_time(loc1, loc2): -> timedelta
# def optimize_daily_route_and_get_time(units_for_day, start_location, time_constraints=None, day_start_time=None): -> (list_of_units_ordered, total_timedelta, dict_of_start_times_utc) # Requires tz-aware day_start_time and time_constraints, returns UTC start times
# def find_unit_in_list(unit_to_find, list_to_search): -> found_unit # Needs comparison logic
# def update_etas_for_schedule(tech, daily_start_times_utc=None): # Updates Job ETAs (as UTC) based on tech.schedule structure and optional UTC start times

# Database Description

## 1. Users (users)

**Purpose:** Stores all user accounts in the system, including customers, admins, and technicians.

**Fields**

- **id** (uuid, PK) - Primary key, also references auth.users
- **full_name** (varchar(100)) - User's full name
- **phone** (varchar(100)) - Contact phone number
- **home_address_id** (int, FK → addresses.id) - Reference to user's home address
- **is_admin** (boolean) - Indicates if the user is an administrator (default: false)
- **customer_type** (enum: 'residential', 'commercial', 'insurance') - Defines the type of customer

**Key Points**

- Any user—customer, technician, or admin—exists here.
- CustomerType is used for determining job priority.
- Links to the auth.users table for authentication.

---

## 2. Technicians (technicians)

**Purpose:** Extends the `Users` table for technician-specific details, including which van they drive and their current workload.

**Fields**

- **id** (int, PK)
- **user_id** (uuid, FK → users.id) - References the main user record
- **assigned_van_id** (int, FK → vans.id) - Which van they currently use
- **workload** (int) - A numeric indicator of workload (must be >= 0)

**Key Points**

- Every technician is also a user.
- The technician is associated with a single van at a time.
- Workload can help with scheduling to see who is most available.

---

## 3. Vans (vans)

**Purpose:** Represents each service van in the fleet. Basic info includes last/next service dates.

**Fields**

- **id** (int, PK)
- **last_service** (timestamp with time zone)
- **next_service** (timestamp with time zone)
- **vin** (varchar, FK → customer_vehicles.vin) - Vehicle identification number

**Key Points**

- Detailed equipment is tracked separately in `van_equipment`.
- A technician is assigned to one van at a time.

---

## 4. Addresses (addresses)

**Purpose:** Standardizes location information (street addresses plus coordinates) used by orders, users, and jobs for routing.

**Fields**

- **id** (int, PK)
- **street_address** (varchar(255))
- **lat** (numeric) - Latitude coordinate
- **lng** (numeric) - Longitude coordinate

**Key Points**

- Coordinates enable route optimization (e.g., traveling salesman problem).
- Multiple users (or orders/jobs) can reference the same address.
- Has an index on coordinates for efficient geospatial queries.

---

## 5. User Addresses (user_addresses)

**Purpose:** A many-to-many link between `Users` and `Addresses`, so one user can have multiple addresses, and one address can belong to multiple users.

**Fields**

- **user_id** (uuid, FK → users.id)
- **address_id** (int, FK → addresses.id)

**Key Points**

- Useful for shared addresses (e.g., multiple customers using the same body shop).
- Has a composite primary key of (user_id, address_id).

---

## 6. Orders (orders)

**Purpose:** Records a customer's service request (an order). An order may be split into multiple jobs if needed.

**Fields**

- **id** (int, PK)
- **user_id** (uuid, FK → users.id) - The customer placing the order
- **vehicle_id** (int, FK → customer_vehicles.id) - The vehicle being serviced
- **repair_order_number** (varchar(50)) - Used by insurance or external reference
- **address_id** (int, FK → addresses.id) - Where service is requested
- **earliest_available_time** (timestamp with time zone) - Earliest time the vehicle is available
- **notes** (text) - Any additional instructions from the customer
- **invoice** (int) - Placeholder for QuickBooks or accounting reference

**Key Points**

- Captures all high-level info about the request.
- Detailed services for the order go into `order_services`.
- File uploads are tracked in `order_uploads`.

---

## 7. Order Services (order_services)

**Purpose:** A junction table listing which services the customer requested for a particular order.

**Fields**

- **order_id** (int, FK → orders.id)
- **service_id** (int, FK → services.id)

**Key Points**

- One order can request multiple services.
- Used by logic to determine if a single van can handle all requested services or if multiple jobs are required.

---

## 8. Order Uploads (order_uploads)

**Purpose:** Tracks file uploads associated with an order.

**Fields**

- **id** (int, PK)
- **order_id** (int, FK → orders.id)
- **file_name** (varchar(255))
- **file_type** (varchar(100))
- **file_url** (text)
- **uploaded_at** (timestamp with time zone) - Defaults to current timestamp

**Key Points**

- Stores metadata about uploaded files (photos, scans, etc.)
- Links back to the original order

---

## 9. Jobs (jobs)

**Purpose:** Represents an individual work assignment that can be scheduled and dispatched to a single technician.

**Fields**

- **id** (int, PK)
- **order_id** (int, FK → orders.id) - Links back to the original order
- **assigned_technician** (int, FK → technicians.id) - Who will perform this job
- **address_id** (int, FK → addresses.id) - Service location
- **priority** (int) - Scheduling priority (must be >= 0)
- **status** (USER-DEFINED) - e.g., 'Pending', 'Scheduled', 'InProgress', 'Completed'
- **requested_time** (timestamp with time zone) - Customer's requested time
- **estimated_sched** (timestamp with time zone) - The dispatch-scheduled time
- **job_duration** (int) - Estimated minutes to complete (must be > 0)
- **notes** (text)
- **fixed_assignment** (boolean, default: false) - Indicates if the job assignment is manually fixed and should not be changed by the dynamic scheduler. Needed to support manual overrides.
- **fixed_schedule_time** (timestamp with time zone, nullable) - If set, specifies a mandatory start time for the job. The scheduler must plan other dynamic jobs around this constraint.
- **estimated_sched_end** (timestamp with time zone, nullable) - Calculated end time based on schedule optimization. Complements `estimated_sched` (start time).
- **customer_eta_start** (timestamp with time zone, nullable) - Start of the ETA window communicated to the customer.
- **customer_eta_end** (timestamp with time zone, nullable) - End of the ETA window communicated to the customer.

**Key Points**

- An order can be split into multiple jobs if no single van can handle all services.
- Each job is assigned to exactly one technician (and thus one van).
- `job_services` will specify which services this job includes.
- Has indexes on status and estimated_sched for efficient querying.

---

## 10. Job Services (job_services)

**Purpose:** Links each job to the specific services it will perform.

**Fields**

- **job_id** (int, FK → jobs.id)
- **service_id** (int, FK → services.id)

**Key Points**

- A single job can handle multiple services.
- Has a composite primary key on (job_id, service_id).

---

## 11. Keys (keys)

**Purpose:** Tracks inventory of car key blanks and related key parts for immobilizer jobs.

**Fields**

- **sku_id** (varchar(50), PK)
- **quantity** (int) - Must be >= 0
- **min_quantity** (int) - Must be >= 0
- **part_number** (varchar(50))
- **purchase_price** (numeric)
- **sale_price** (numeric)
- **supplier** (varchar(100))
- **fcc_id** (varchar(50))

**Key Points**

- This table is not directly linked to the Orders/Jobs schema, but the logic layer checks key availability when scheduling key/immobilizer jobs.
- Helps decide if you need to order new keys before scheduling.

---

## 12. Services (services)

**Purpose:** Defines the various services offered (e.g., ADAS calibration, module programming, key programming, etc.).

**Fields**

- **id** (int, PK)
- **service_name** (varchar(100)) - Must be unique
- **service_category** (enum: 'adas', 'airbag', 'immo', 'prog', 'diag') - Type of service

**Key Points**

- Basic service definitions.
- Required equipment is defined in the specialized `*_equipment_requirements` tables based on service and vehicle.
- Ties to `order_services` and `job_services` to indicate requested and assigned services.
- Service categories are strictly controlled via enum.

---

## 13. Equipment (equipment)

**Purpose:** A master list of all possible equipment/tools needed to perform services (e.g., cones, calibration plates, doppler, etc.).

**Fields**

- **id** (int, PK)
- **equipment_type** (enum: 'adas', 'airbag', 'immo', 'prog', 'diag') - Must be unique
- **model** (text)

**Key Points**

- Used in `van_equipment` to specify which van has which gear.
- Equipment requirements for specific services and vehicles are defined in the specialized `*_equipment_requirements` tables.
- Equipment types align with service categories for consistency.

---

## 14. Van Equipment (van_equipment)

**Purpose:** Indicates which equipment items are available in each service van.

**Fields**

- **van_id** (int, FK → vans.id)
- **equipment_id** (int, FK → equipment.id)
- **equipment_model** (text)

**Key Points**

- Has a composite primary key on (van_id, equipment_id).
- Includes the specific model of equipment in each van.

---

## 15. Customer Vehicles (customer_vehicles)

**Purpose:** Stores information about customer vehicles that can be serviced.

**Fields**

- **id** (int, PK)
- **vin** (varchar(17)) - Vehicle identification number, must be unique
- **make** (varchar(100))
- **year** (smallint)
- **model** (varchar)

**Key Points**

- Referenced by orders to identify which vehicle needs service
- Referenced by vans to identify service vehicles

---

## 16. YMM Reference (ymm_ref)

**Purpose:** Standardized reference table for year/make/model combinations used across the system.

**Fields**
- **ymm_id** (int, PK)
- **year** (smallint) NOT NULL
- **make** (varchar(50)) NOT NULL
- **model** (varchar(100)) NOT NULL
- Unique constraint on (year, make, model)

**Key Points**
- Used for vehicle identification across the system
- Provides consistent vehicle information for both customer vehicles and service vans
- Used by equipment requirements tables to determine required equipment for specific vehicles

---

## 17. Equipment Requirements Tables

The system uses separate tables for different types of equipment requirements, each following a similar structure but specialized for different service categories:

### ADAS Equipment Requirements (adas_equipment_requirements)

**Purpose:** Defines ADAS-specific equipment requirements for vehicle models and services.

**Fields**
- **id** (int, PK)
- **ymm_id** (int, FK → ymm_ref.ymm_id)
- **service_id** (int, FK → services.id)
- **equipment_model** (varchar(100)) NOT NULL
- **has_adas_service** (boolean) - Default: false
- Unique constraint on (ymm_id, service_id)

### Programming Equipment Requirements (prog_equipment_requirements)

**Purpose:** Defines programming-specific equipment requirements for vehicle models and services.

**Fields**
- **id** (int, PK)
- **ymm_id** (int, FK → ymm_ref.ymm_id)
- **service_id** (int, FK → services.id)
- **equipment_model** (text) NOT NULL - Default: 'prog'
- Unique constraint on (ymm_id, service_id)

### Immobilizer Equipment Requirements (immo_equipment_requirements)

**Purpose:** Defines immobilizer-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'immo'

### Airbag Equipment Requirements (airbag_equipment_requirements)

**Purpose:** Defines airbag-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'airbag'

### Diagnostic Equipment Requirements (diag_equipment_requirements)

**Purpose:** Defines diagnostic-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'diag'

**Key Points for All Equipment Requirement Tables**
- Each table links vehicles and services to required equipment
- Used for scheduling and equipment allocation
- Helps determine if a specific van has the right equipment for a job
- Each maintains a unique constraint on (ymm_id, service_id)

---

## 18. Enums

The database uses several enum types to ensure data consistency:

1. **customer_type**
   - Values: 'residential', 'commercial', 'insurance'
   - Used in: users table

2. **job_status**
   - Values: 'pending_review', 'assigned', 'scheduled', 'pending_revisit', 'completed', 'cancelled'
   - Used in: jobs table

3. **service_category**
   - Values: 'adas', 'airbag', 'immo', 'prog', 'diag'
   - Used in: services table and equipment table