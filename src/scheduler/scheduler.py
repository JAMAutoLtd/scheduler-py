from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import copy # Needed for deep copying lists

# Import actual data models
from .models import Technician, Job, SchedulableUnit, Address, JobStatus # Added JobStatus
# Remove placeholder classes
# class Address:
#     pass
# class Technician:
#     id: int
#     schedule: Dict[int, List['SchedulableUnit']] = {} # {day_number: [unit1, unit2]}
#     current_location: Optional[Address] = None
#     home_location: Optional[Address] = None
#     def has_equipment(self, required_equipment) -> bool: return True # Placeholder
#     def has_all_equipment(self, order_jobs) -> bool: return True # Placeholder
# 
# class Job:
#     id: int
#     order_id: int
#     fixed: bool = False
#     equipment_required: List[str] = [] # Placeholder
#     duration: timedelta = timedelta(hours=1) # Placeholder
#     location: Optional[Address] = None # Placeholder
#     priority: int = 1 # Placeholder
#     assigned_technician: Optional[Technician] = None # Placeholder
#     estimated_sched: Optional[datetime] = None # Placeholder
#     status: str = "Pending" # Placeholder
# 
# class SchedulableUnit:
#     jobs: List[Job]
#     priority: int
#     duration: timedelta
#     location: Address
#     assigned_technician_id: Optional[int] = None
#     fixed_assignment: bool = False
#     fixed_schedule_time: Optional[datetime] = None

# Import actual utility functions
from .utils import (
    group_jobs_by_order, 
    create_schedulable_units, 
    calculate_daily_available_windows,
    fit_dynamic_units_into_windows
)
# from .availability import get_technician_availability # Keep using placeholder for now
from .routing import calculate_travel_time, optimize_daily_route_and_get_time, update_etas_for_schedule
from .availability import get_technician_availability # Keep using placeholder for now
from .data_interface import update_job_assignment, fetch_assigned_jobs # Added fetch_assigned_jobs

# HACK: Placeholder functions for dependencies - Keep for now
# def get_technician_availability(tech: Technician, day_number: int) -> Optional[Dict]:
#     """Placeholder: Fetches technician availability for a given day."""
#     # ... (implementation remains)
# 
# def calculate_travel_time(loc1: Optional[Address], loc2: Optional[Address]) -> timedelta:
#     """Placeholder: Calculates travel time between two locations."""
#     # ... (implementation remains)

# Remove placeholder create_schedulable_units as we import the real one
# def create_schedulable_units(jobs_by_order: Dict[int, List[Job]]) -> List[SchedulableUnit]:
#     """Placeholder: Creates SchedulableUnit objects from grouped jobs."""
#     # ... (implementation removed)

# Define constants at module level
MAX_PLANNING_DAYS = 14

# Helper function to optimize and finalize the schedule for a single day
def _optimize_and_finalize_daily_schedule(
    tech: Technician,
    day_number: int,
    day_start: datetime,
    availability: Dict, # Includes total_duration
    fixed_units_scheduled_today: List[SchedulableUnit],
    scheduled_dynamic_today: List[SchedulableUnit],
    remaining_dynamic_units: List[SchedulableUnit], # Needed to add back failed units
    all_daily_start_times: Dict[int, Dict[str, datetime]] # To store results
) -> List[SchedulableUnit]: # Returns the updated remaining_dynamic_units
    """
    Combines fixed and dynamic units for the day, calls the route optimizer,
    checks the result against daily duration, and updates the tech's schedule
    and the main start time dictionary.

    Args:
        tech: The technician being scheduled.
        day_number: The current day number being planned.
        day_start: The start datetime of the work day.
        availability: Dictionary containing the technician's availability for the day.
        fixed_units_scheduled_today: List of fixed units scheduled for this day.
        scheduled_dynamic_today: List of dynamic units fitted into windows.
        remaining_dynamic_units: The list of dynamic units *not* scheduled today (before optimization).
        all_daily_start_times: Dictionary to store calculated start times {day_num: {unit_id: start_time}}.

    Returns:
        The updated list of remaining dynamic units (including any that failed optimization).
    """
    all_units_today = fixed_units_scheduled_today + scheduled_dynamic_today
    current_day_schedule: List[SchedulableUnit] = [] # Default to empty if nothing to optimize
    units_scheduled_ids = {u.id for u in scheduled_dynamic_today}

    if all_units_today:
        start_location = tech.current_location if day_number == 1 else tech.home_location
        if not start_location:
             print(f"Error: Missing start location for tech {tech.id} day {day_number}. Cannot optimize route. Scheduling fixed units only.")
             current_day_schedule = fixed_units_scheduled_today
             all_daily_start_times[day_number] = {u.id: u.fixed_schedule_time for u in fixed_units_scheduled_today if u.fixed_schedule_time}
        else:
            time_constraints = {u.id: u.fixed_schedule_time for u in fixed_units_scheduled_today if u.fixed_schedule_time}

            try:
                # Call optimizer with time constraints
                optimized_units, total_time, calculated_start_times_by_id = optimize_daily_route_and_get_time(
                    units_for_day=all_units_today,
                    start_location=start_location,
                    time_constraints=time_constraints,
                    day_start_time=day_start
                )

                # Final check against total daily duration
                if total_time <= availability['total_duration']:
                    current_day_schedule = optimized_units
                    all_daily_start_times[day_number] = {u.id: t for u_id, t in calculated_start_times_by_id.items() if (u := next((unit for unit in optimized_units if unit.id == u_id), None))}
                    # Dynamic units were successfully scheduled, no need to add them back to remaining
                else:
                    print(f"Warning: Optimized route for tech {tech.id} day {day_number} ({total_time}) exceeds available duration ({availability['total_duration']}). Reverting to fixed units only.")
                    # Only schedule fixed units if optimization fails duration check
                    current_day_schedule = fixed_units_scheduled_today
                    all_daily_start_times[day_number] = {u.id: t for u_id, t in calculated_start_times_by_id.items() if (u := next((unit for unit in fixed_units_scheduled_today if unit.id == u_id), None))}
                    # Add back the dynamic units that were attempted today to the remaining list
                    failed_dynamic_units = [u for u in all_units_today if u.id in units_scheduled_ids]
                    remaining_dynamic_units.extend(failed_dynamic_units)
                    # No need to sort here, will be handled by caller if needed

            except Exception as e:
                print(f"Error during route optimization call for tech {tech.id}, day {day_number}: {e}. Scheduling fixed units only.")
                current_day_schedule = fixed_units_scheduled_today # Schedule only fixed if optimizer crashes
                all_daily_start_times[day_number] = {u.id: u.fixed_schedule_time for u in fixed_units_scheduled_today if u.fixed_schedule_time} # Use fixed times
                # Add back dynamic units attempted today
                failed_dynamic_units = [u for u in all_units_today if u.id in units_scheduled_ids]
                remaining_dynamic_units.extend(failed_dynamic_units) # Add back
                # No need to sort here, will be handled by caller if needed

    # Store the final schedule for the day
    tech.schedule[day_number] = current_day_schedule
    # Return the potentially updated list of remaining dynamic units
    return remaining_dynamic_units


# --- Phase 3 Implementation Starts Here ---

def calculate_eta(technician: Technician, jobs_to_consider: List[Job]) -> Optional[datetime]:
    """
    Calculates the predicted ETA for the first job in a potential unit.

    Simulates adding the jobs (as a unit) into the technician's existing
    multi-day schedule to find the earliest possible start time, respecting
    fixed-time job constraints by identifying and checking available windows.

    Args:
        technician: The technician whose schedule is being considered.
        jobs_to_consider: A list of jobs representing a potential SchedulableUnit.

    Returns:
        The predicted ETA (datetime) for the first job, or None if it cannot be scheduled
        within the simulation timeframe (e.g., 14 days).
    """
    if not jobs_to_consider:
        print("Warning: calculate_eta called with empty jobs_to_consider list.")
        return None

    # --- 1. Create a temporary unit representation for calculation ---
    # Use first job's location (assuming jobs in unit are typically co-located or logic groups them appropriately)
    # HACK: Use getattr for location in case job object doesn't have it yet (during testing/dev)
    temp_unit_location = getattr(jobs_to_consider[0], 'location', None)
    if not temp_unit_location:
         print(f"Warning: Job {jobs_to_consider[0].id} missing location for ETA calculation.")
         return None # Cannot calculate without location

    # Ensure job_duration exists and is timedelta
    temp_unit_duration = sum((
        getattr(job, 'job_duration', timedelta(hours=1)) for job in jobs_to_consider
        ), timedelta())
    
    if temp_unit_duration <= timedelta(0):
        print(f"Warning: Job unit duration is zero or negative ({temp_unit_duration}). Cannot calculate ETA.")
        return None

    # --- 2. Iterate through days to find the earliest fit --- 
    current_day = 1
    max_days_to_check = 14  # Limit how far ahead we look

    while current_day <= max_days_to_check:
        # --- 2a. Get Daily Availability --- 
        availability = get_technician_availability(technician, current_day)
        if not availability or availability.get('total_duration', timedelta(0)) <= timedelta(0):
            current_day += 1
            continue  # Skip days with no availability or zero duration

        day_start = availability['start_time']
        day_end = availability['end_time']
        # Determine start location for the day based on whether it's the first day or subsequent
        start_location_today = technician.current_location if current_day == 1 else technician.home_location
        if not start_location_today:
             print(f"Warning: Technician {technician.id} missing start location for day {current_day}. Cannot calculate ETA for this day.")
             current_day += 1
             continue # Cannot calculate without a starting point for the day

        # --- 2b. Use Helper Function to Calculate Available Windows --- 
        scheduled_units_today = technician.schedule.get(current_day, []) 
        # Note: calculate_eta uses the existing schedule directly, 
        # update_job_queues_and_routes uses potentially hypothetical units for the day.
        available_windows = calculate_daily_available_windows(
            scheduled_units_today=scheduled_units_today, 
            day_start=day_start, 
            day_end=day_end, 
            start_location_today=start_location_today,
            technician_id=technician.id, # Pass context for logging
            day_number=current_day       # Pass context for logging
        )

        # --- 2c. Simulate Fitting the New Unit into Windows --- 
        for window_start, window_end, location_before_window in available_windows:

            if not location_before_window:
                print(f"Warning: Missing location_before_window for window {window_start}-{window_end} on day {current_day} for tech {technician.id}. Skipping window.")
                continue
            
            # Calculate travel from the event location immediately preceding this window
            travel_to_new_unit = calculate_travel_time(location_before_window, temp_unit_location)
            
            # Potential start is the later of window start or arrival time after travel
            # Arrival time is the time the previous event ended (window_start) + travel time
            arrival_time = window_start + travel_to_new_unit 
            potential_start = max(window_start, arrival_time)

            potential_end = potential_start + temp_unit_duration

            # Check if the unit fits within this window
            if potential_end <= window_end:
                # Found the earliest possible slot!
                return potential_start 

        # If no fit found in any window on this day, try the next day
        current_day += 1

    # If no slot found within max_days_to_check
    job_ids = [getattr(j, 'id', 'unknown') for j in jobs_to_consider]
    print(f"Could not find suitable ETA slot for jobs {job_ids} within {max_days_to_check} days for tech {technician.id}.")
    return None


def assign_job_to_technician(job: Job, technician: Technician):
    """
    Assigns a job to a technician by calling the data interface.

    Args:
        job: The Job to be assigned.
        technician: The Technician to assign the job to.
    """
    # Call the data interface function to update the assignment via API
    # Status should likely be ASSIGNED when assigning
    success = update_job_assignment(job_id=job.id, technician_id=technician.id, status=JobStatus.ASSIGNED)
    
    if not success:
        # Consider adding proper logging here
        print(f"Error: Failed to assign job {job.id} to technician {technician.id} via API.")
    # Note: We don't update the job object directly here anymore.
    # The source of truth is the database, accessed via the API.


def assign_jobs(all_eligible_jobs: List[Job], technicians: List[Technician]):
    """
    Assigns eligible jobs to the best available technician based on ETA and equipment.

    Follows the logic from PLANNING.md, prioritizing assigning multi-job orders
    to a single technician if possible.

    Args:
        all_eligible_jobs: List of jobs to consider for assignment (non-fixed).
        technicians: List of available technicians.
    """
    # Filter out jobs that are already assigned and marked as fixed
    # Using .fixed_assignment based on updated DATABASE.md
    dynamic_jobs_to_consider = [job for job in all_eligible_jobs if not job.fixed_assignment]

    # Group jobs by order ID
    jobs_by_order_id: Dict[int, List[Job]] = defaultdict(list)
    for job in dynamic_jobs_to_consider:
        jobs_by_order_id[job.order_id].append(job)

    jobs_requiring_individual_assignment: List[Job] = [] # Renamed variable

    for order_id, order_jobs in jobs_by_order_id.items():
        best_tech_for_order: Optional[Technician] = None
        best_eta_for_order: Optional[datetime] = None

        # Try to find a technician who can handle all jobs in the order
        if len(order_jobs) > 1:
            fully_equipped_techs = [tech for tech in technicians if tech.has_all_equipment(order_jobs)]
            if fully_equipped_techs:
                etas = {}
                for tech in fully_equipped_techs:
                    eta = calculate_eta(tech, order_jobs)
                    if eta:
                        etas[tech] = eta
                
                if etas: # If any eligible tech has a valid ETA
                    best_tech_for_order = min(etas, key=etas.get)
                    best_eta_for_order = etas[best_tech_for_order]
            # If no single tech is fully equipped, best_tech_for_order remains None, 
            # Add jobs to the list for individual assignment attempt later
            if best_tech_for_order is None and len(order_jobs) > 1:
                 jobs_requiring_individual_assignment.extend(order_jobs)

        # --- Assignment Phase (Order Grouping) ---
        if best_tech_for_order is not None:
            print(f"Assigning order {order_id} (Jobs: {[j.id for j in order_jobs]}) as a group to Tech {best_tech_for_order.id} (ETA: {best_eta_for_order})")
            for job in order_jobs:
                assign_job_to_technician(job, best_tech_for_order)
        elif len(order_jobs) == 1: # Single job orders are always handled individually
            jobs_requiring_individual_assignment.extend(order_jobs)
        # Else: Multi-job order where no single tech could handle all (already added above)

    # --- Assignment Phase (Individual Jobs) ---
    # Process jobs that couldn't be assigned as a group or are single jobs
    print(f"Attempting individual assignment for {len(jobs_requiring_individual_assignment)} jobs.")
    for job in jobs_requiring_individual_assignment:
        best_tech_for_job: Optional[Technician] = None
        best_eta_for_job: Optional[datetime] = None
        individual_eligible_techs = [tech for tech in technicians if tech.has_equipment([req for req in job.equipment_requirements])] # Check equipment for single job
        
        if individual_eligible_techs:
            etas = {}
            for tech in individual_eligible_techs:
                # Calculate ETA for this specific job
                eta = calculate_eta(tech, [job]) 
                if eta:
                    etas[tech] = eta
            
            if etas: # If any eligible tech has a valid ETA for this job
                best_tech_for_job = min(etas, key=etas.get)
                best_eta_for_job = etas[best_tech_for_job]
            else:
                # Add logging if no eligible tech has a valid ETA for this individual job
                print(f"Warning: No valid ETA could be calculated for individual job {job.id} among eligible technicians {[t.id for t in individual_eligible_techs]}. Job remains unassigned.")

        if best_tech_for_job:
            print(f"Assigning individual job {job.id} (Order: {job.order_id}) to Tech {best_tech_for_job.id} (ETA: {best_eta_for_job})")
            assign_job_to_technician(job, best_tech_for_job)
        # else: If no eligible techs, or no valid ETAs, job remains unassigned (warning printed above if ETAs were the issue)

    # --- Update Routes After All Assignments ---
    print("Assignment phase complete. Updating job queues and routes...")
    update_job_queues_and_routes(technicians)


def update_job_queues_and_routes(technicians: List[Technician]):
    """
    Updates the multi-day schedule for each technician, optimizing daily routes
    and updating ETAs for all assigned jobs.

    Args:
        technicians: List of technicians whose schedules need updating.
    """
    for tech in technicians:
        tech.schedule = {} # Clear existing schedule
        all_daily_start_times: Dict[int, Dict[str, datetime]] = {} # Use unit.id as key

        # 1. Fetch Assigned Jobs for the Technician via API
        try:
            # Replace placeholder fetch with actual data interface call
            tech_assigned_jobs = fetch_assigned_jobs(tech.id)
        except Exception as e:
            # Log error fetching jobs for this tech
            print(f"Error fetching jobs for technician {tech.id}: {e}. Skipping schedule update for this tech.")
            continue # Move to the next technician

        if not tech_assigned_jobs:
            print(f"No assigned jobs found for technician {tech.id}. Clearing schedule and skipping.")
            # Ensure ETAs are cleared/updated if necessary for an empty schedule
            update_etas_for_schedule(tech, {}) 
            continue

        # 2. Create Schedulable Units
        jobs_by_order = group_jobs_by_order(tech_assigned_jobs)
        all_units = create_schedulable_units(jobs_by_order)

        # Assume SchedulableUnit now has a unique `id` attribute (e.g., UUID or derived ID)
        # Ensure all units have a valid ID
        if not all(hasattr(u, 'id') and u.id is not None for u in all_units):
            print(f"Error: Not all schedulable units have a valid 'id' attribute for tech {tech.id}. Skipping schedule update.")
            continue

        # 3. Separate Units and Sort Dynamic by Priority
        fixed_time_units = [u for u in all_units if u.fixed_schedule_time is not None]
        # All other units are considered dynamic in terms of timing
        dynamic_units = [u for u in all_units if u.fixed_schedule_time is None]
        dynamic_units.sort(key=lambda u: u.priority) # Sort high to low prio

        # 4. Plan Schedule Day by Day
        current_day = 1
        remaining_dynamic_units = dynamic_units.copy()
        pending_fixed_time_units = fixed_time_units.copy()

        while (remaining_dynamic_units or pending_fixed_time_units) and current_day <= MAX_PLANNING_DAYS:
            # Get daily availability
            availability = get_technician_availability(tech, current_day)
            if not availability or availability.get('total_duration', timedelta(0)) <= timedelta(0):
                current_day += 1
                continue

            tech.schedule[current_day] = []
            day_start = availability['start_time']
            day_end = availability['end_time']
            start_location_today = tech.current_location if current_day == 1 else tech.home_location
            if not start_location_today:
                print(f"Warning: Tech {tech.id} missing start location for day {current_day}. Cannot schedule.")
                current_day += 1
                continue

            # 4a. Place fixed units for *this* day & determine available windows using helper
            available_windows = calculate_daily_available_windows(
                scheduled_units_today=all_units, # Pass all units considered for the day
                day_start=day_start,
                day_end=day_end,
                start_location_today=start_location_today,
                technician_id=tech.id,
                day_number=current_day
            )

            # 4b. Fill available windows with dynamic units using helper
            scheduled_dynamic_today, remaining_dynamic_units = _fit_dynamic_units_into_windows(
                dynamic_units=remaining_dynamic_units, # Pass the current list of remaining units
                available_windows=available_windows    # Pass the calculated windows
            )
            units_scheduled_ids = {u.id for u in scheduled_dynamic_today} # Get IDs of scheduled units

            # 4c. Combine, Optimize, and Finalize the day's schedule using helper
            fixed_units_scheduled_today = [u for u in fixed_time_units if u.fixed_schedule_time and u.fixed_schedule_time.date() == day_start.date()]
            
            remaining_dynamic_units = _optimize_and_finalize_daily_schedule(
                tech=tech,
                day_number=current_day,
                day_start=day_start,
                availability=availability,
                fixed_units_scheduled_today=fixed_units_scheduled_today,
                scheduled_dynamic_today=scheduled_dynamic_today,
                remaining_dynamic_units=remaining_dynamic_units, # Pass current list
                all_daily_start_times=all_daily_start_times
            )
            # Re-sort if units were added back due to optimization failure
            remaining_dynamic_units.sort(key=lambda u: u.priority) 
            
            # 4d. Prepare for next day
            current_day += 1

        # 5. Store the final multi-day schedule (already done in tech.schedule)

        # 6. Update ETAs for ALL jobs based on the final schedule
        # Ensure update_etas_for_schedule uses unit.id keys from all_daily_start_times
        update_etas_for_schedule(tech, all_daily_start_times)

        # Log unscheduled units
        if remaining_dynamic_units or pending_fixed_time_units:
            unsched_dyn_ids = [u.id for u in remaining_dynamic_units]
            unsched_fixed_ids = [u.id for u in pending_fixed_time_units]
            print(f"Warning: Tech {tech.id} finished planning with unscheduled units. Dynamic: {unsched_dyn_ids}, Fixed: {unsched_fixed_ids}")
