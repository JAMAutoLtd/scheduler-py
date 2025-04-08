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
- **Inventory Check for Key Jobs:**
    - Check inventory with [Boxhero Inventory Management](https://www.boxhero.io).
    - If keys are out of stock:
        - Generate a quote using [Keydirect](https://keydirect.ca/) \(CAD\) and [UHS Hardware](https://www.uhs-hardware.com/) \(USD, customs\).
        - On customer acceptance, notify admin to order keys and confirm the job schedule.
        - Key jobs are scheduled only after keys are confirmed in stock or ordered, with a 3-day wait if keys must be ordered.
- **Invoice Generation \(Insurance Orders\):**
- Create unsent invoices to the customer using QuickBooks, incorporating the Repair Order Number, vehicle details, and any attached order files.

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
    *   **ETA Optimization:** When multiple technicians are eligible, selects the one predicted to have the earliest ETA. **Note:** ETA prediction during assignment must simulate placement within the technician's multi-day schedule respecting daily constraints.
    *   **Fixed Assignments:** Supports manual ("fixed") job assignments. Fixed jobs *cannot* be dynamically reassigned but *are* included in their assigned technician's route optimization.

2.  **Job Queuing & Routing Logic (Daily Planning)**
    *   **Daily Boundaries:** Routes are planned on a day-by-day basis, respecting each technician's specific working hours and availability for that day.
    *   **Starting Locations:** Route calculation starts from the technician's *current location* for the first day (today) and from their *home base* for subsequent days.
    *   **Schedulable Units:** Jobs are grouped into units: indivisible blocks for multi-job orders assigned to the same tech, or individual units for single jobs. Block priority is determined by the highest priority job within it.
    *   **Priority & Daily Fit:** Units are sorted by priority. The system iteratively fills each available day, selecting the highest priority units that fit within the remaining work time (considering travel + duration).
    *   **Route Optimization (Daily TSP):** A TSP algorithm optimizes the sequence of units scheduled *within each specific day* to minimize travel time for that day.
    *   **Multi-Day Schedule:** The result is a multi-day schedule for each technician (e.g., `tech.schedule = {day1: [unitA, unitB], day2: [unitC]}`).
    *   **Continuous ETA Updates:** ETAs for *all* jobs (across all scheduled days) are calculated and updated based on their position in the final, optimized multi-day schedule.

### Dynamic Operation & Recalculation

The system operates dynamically, constantly seeking the optimal state:

*   **Recalculation Loop:** Core assignment and daily routing logic is re-evaluated in response to specific events.
*   **Re-evaluation Scope:** Re-evaluation considers *all* active, non-fixed jobs against the current multi-day schedules and technician statuses.
*   **Event Triggers:** Recalculations are typically triggered by: new jobs, job status changes, technician status/location changes, manual interventions, or optional periodic timers.

This continuous re-optimization ensures the system adapts to changing conditions, always aiming for the best possible job assignments and ETAs according to defined priorities and daily operational constraints.

##SCHEDULER PSEUDOCODE

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
                        etas = {tech: calculate_eta(tech, [job]) for tech in individual_eligible}
                        best_tech_for_job = min(etas, key=etas.get)
                        assign_job_to_technician(job, best_tech_for_job)
                    # Else: Handle case where no tech can do this specific job (optional logging/error handling)

    # Routing update remains the same (processes all assigned jobs per tech)
    update_job_queues_and_routes(technicians)

# Revised update_job_queues_and_routes with daily boundaries & availability
def update_job_queues_and_routes(technicians):
    for tech in technicians:
        all_assigned_jobs = tech.queue # Or however all jobs for the tech are retrieved

        # 1. Group jobs by order & Create schedulable units (priority based on highest in block)
        jobs_by_order = group_jobs_by_order(all_assigned_jobs)
        schedulable_units = create_schedulable_units(jobs_by_order) # Includes priority calculation

        # 2. Sort all potential units by priority
        schedulable_units.sort(key=lambda unit: unit['priority'])

        # 3. Plan schedule day by day
        tech_schedule = {} # Stores the plan, e.g., {1: [unit1, unit2], 2: [unit3], ...}
        remaining_units_to_schedule = list(schedulable_units)
        day_number = 1 # Represents the current day being planned (1 = today)
        # last_location = tech.current_location # Initial location potentially needed for first travel time

        while remaining_units_to_schedule:
            daily_units_for_optimization = []
            # Determine start location for the day
            start_location_for_day = tech.current_location if day_number == 1 else tech.home_location
            
            # Get tech availability for this specific day (needs helper function)
            # Returns structure like {start_time, end_time, total_duration}
            daily_availability = get_technician_availability(tech, day_number) 
            
            # Check if tech is available at all this day
            if not daily_availability or daily_availability['total_duration'] <= timedelta(0):
                 if not remaining_units_to_schedule: break # Exit if no more units
                 day_number += 1 # Skip to planning the next day
                 continue

            # Available time is just the total duration from availability
            available_work_time = daily_availability['total_duration'] 
            current_route_time_estimate = timedelta(0)
            last_stop_location = start_location_for_day

            # Attempt to fill the day from the remaining prioritized units
            units_considered_for_day = list(remaining_units_to_schedule) # Copy to iterate safely
            temp_units_added_today = [] # Track units tentatively added

            for unit in units_considered_for_day:
                 # Simulate adding this unit: calculate travel time + unit duration
                 travel_time = calculate_travel_time(last_stop_location, unit['location'])
                 unit_total_time = travel_time + unit['duration'] # unit['duration'] includes all jobs in block

                 # Check if adding this unit exceeds the day's available work time
                 if current_route_time_estimate + unit_total_time <= available_work_time:
                     # Tentatively add to potential day's route
                     temp_units_added_today.append(unit)
                     current_route_time_estimate += unit_total_time
                     last_stop_location = unit['location'] # Update for next iteration estimate
                 else:
                     # Cannot fit this unit (or any lower priority ones) today based on estimate
                     break # Stop trying to add units for this day

            # Now, perform actual optimization for the selected units for the day
            if temp_units_added_today:
                # Optimize the route for the units tentatively selected for the day
                # This function performs TSP and calculates the *actual* optimized time.
                optimized_daily_units, actual_optimized_time = optimize_daily_route_and_get_time(temp_units_added_today, start_location_for_day)
                
                # Final check: Does the *optimized* route still fit? (Could be slightly different from estimate)
                if actual_optimized_time <= available_work_time:
                    tech_schedule[day_number] = optimized_daily_units
                    # Remove scheduled units from the master remaining list
                    for scheduled_unit in optimized_daily_units:
                        remaining_units_to_schedule.remove(find_unit_in_list(scheduled_unit, remaining_units_to_schedule))
                else:
                    # Optimized route didn't fit! This indicates complexity. 
                    # Simplest fallback: Don't schedule anything today, try again next day. Or try removing last unit.
                    # For pseudocode simplicity, we might just log and skip day for now.
                    print(f"Warning: Optimized route for tech {tech.id} on day {day_number} exceeded available time. Skipping day planning.")
            
            # Handle case where no units were added today
            if not temp_units_added_today and remaining_units_to_schedule:
                 print(f"Warning: Could not schedule any units for tech {tech.id} on day {day_number}. Check availability/unit durations.")
                 # Avoid infinite loop if stuck
                 day_number += 1 # Move to next day even if nothing scheduled
                 continue
            elif not remaining_units_to_schedule:
                 break # All units scheduled

            # Prepare for the next day
            day_number += 1

        # 4. Store the structured schedule
        tech.schedule = tech_schedule # e.g., {1: [jobA, jobB], 2: [jobC]}

        # 5. Update ETAs for ALL jobs based on the multi-day schedule
        # This function iterates through tech.schedule, calculating exact start/end times and ETAs
        update_etas_for_schedule(tech)

# --- Helper function signatures needed ---
# def create_schedulable_units(jobs_by_order): -> list_of_units (with jobs, priority, location, duration)
# def get_technician_availability(tech, day_number): -> dict (with start_time, end_time, total_duration) or None
# def calculate_travel_time(loc1, loc2): -> timedelta
# def optimize_daily_route_and_get_time(units_for_day, start_location): -> (list_of_units_ordered, total_timedelta) # Runs TSP
# def find_unit_in_list(unit_to_find, list_to_search): -> found_unit # Needs comparison logic
# def update_etas_for_schedule(tech): # Updates Job ETAs based on tech.schedule structure