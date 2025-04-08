from collections import defaultdict
from datetime import timedelta, datetime
from typing import List, Dict, Optional, Tuple

from .models import Job, SchedulableUnit, Address, Technician

def group_jobs_by_order(jobs: List[Job]) -> Dict[int, List[Job]]:
    """
    Groups a list of Job objects by their order_id.

    Args:
        jobs (List[Job]): A list of Job objects.

    Returns:
        Dict[int, List[Job]]: A dictionary where keys are order_ids
                                and values are lists of Jobs for that order.
    """
    grouped_jobs = defaultdict(list)
    for job in jobs:
        grouped_jobs[job.order_id].append(job)
    return dict(grouped_jobs)

def create_schedulable_units(jobs_by_order: Dict[int, List[Job]]) -> List[SchedulableUnit]:
    """
    Converts jobs grouped by order into SchedulableUnit objects.

    Each SchedulableUnit represents one or more jobs from the same order
    that will be scheduled together. It calculates the unit's priority,
    total duration, location, and fixed status.

    Args:
        jobs_by_order (Dict[int, List[Job]]): Jobs grouped by their order_id.

    Returns:
        List[SchedulableUnit]: A list of SchedulableUnit objects.
    """
    units = []
    for order_id, jobs_in_order in jobs_by_order.items():
        if not jobs_in_order:
            continue # Should not happen with defaultdict, but good practice

        # Priority is the max priority of any job in the group (lower number = higher priority)
        unit_priority = min(job.priority for job in jobs_in_order)

        # Duration is the sum of all job durations in the group
        unit_duration = sum((job.job_duration for job in jobs_in_order), timedelta())

        # Location is assumed to be the same for all jobs in an order
        # Taking the address from the first job
        unit_location = jobs_in_order[0].address

        # If any job in the unit is fixed, the whole unit is considered fixed
        unit_fixed = any(job.fixed for job in jobs_in_order)

        # Check if any job already has an assigned tech ID (for consistency)
        assigned_tech_id = None
        tech_ids_in_unit = {job.assigned_technician_id for job in jobs_in_order if job.assigned_technician_id is not None}
        if len(tech_ids_in_unit) == 1:
            assigned_tech_id = tech_ids_in_unit.pop()
        elif len(tech_ids_in_unit) > 1:
            # This scenario (multiple techs assigned to jobs in the same order unit)
            # might indicate an issue or require specific handling based on business rules.
            # For now, we'll log a warning or raise an error if needed.
            print(f"Warning: Multiple technicians {tech_ids_in_unit} assigned to jobs for order {order_id}. Unit assigned_technician_id set to None.")

        unit = SchedulableUnit(
            order_id=order_id,
            jobs=jobs_in_order,
            priority=unit_priority,
            location=unit_location,
            duration=unit_duration,
            assigned_technician_id=assigned_tech_id, # Carry over if consistently assigned
            fixed=unit_fixed
        )
        units.append(unit)

    return units

def find_unit_in_list(unit_to_find: SchedulableUnit, list_to_search: List[SchedulableUnit]) -> Optional[SchedulableUnit]:
    """
    Finds a specific SchedulableUnit within a list based on its unique ID.

    Args:
        unit_to_find (SchedulableUnit): The unit object to search for (using its id).
        list_to_search (List[SchedulableUnit]): The list to search within.

    Returns:
        Optional[SchedulableUnit]: The found unit object, or None if not found.
    """
    for unit in list_to_search:
        if unit.id == unit_to_find.id:
            return unit
    return None

def calculate_daily_available_windows(
    scheduled_units_today: List[SchedulableUnit],
    day_start: datetime,
    day_end: datetime,
    start_location_today: Address,
    technician_id: int,
    day_number: int,
) -> List[Tuple[datetime, datetime, Address]]:
    """
    Calculates available time windows within a technician's working day,
    considering already scheduled fixed-time units.

    Args:
        scheduled_units_today: List of all units potentially scheduled for the day.
        day_start: The start time of the technician's working day (timezone-aware).
        day_end: The end time of the technician's working day (timezone-aware).
        start_location_today: The technician's starting location for the day.
        technician_id: ID of the technician for logging.
        day_number: The day number (relative to today) for logging.

    Returns:
        A list of tuples, where each tuple represents an available time window:
        (window_start_time, window_end_time, location_before_window).
    """
    fixed_units_today = sorted(
        [u for u in scheduled_units_today if getattr(u, 'fixed_schedule_time', None) is not None],
        key=lambda u: u.fixed_schedule_time
    )

    available_windows: List[Tuple[datetime, datetime, Address]] = []
    last_event_end_time = day_start
    last_event_location = start_location_today

    for fixed_unit in fixed_units_today:
        fixed_start = getattr(fixed_unit, 'fixed_schedule_time', None)
        fixed_duration = getattr(fixed_unit, 'duration', timedelta(0))
        fixed_location = getattr(fixed_unit, 'location', None)

        if not fixed_start or fixed_duration <= timedelta(0) or not fixed_location:
            print(f"Warning: Skipping invalid fixed unit data during window calculation for tech {technician_id}, day {day_number}.")
            continue

        fixed_end = fixed_start + fixed_duration

        # Check basic validity (fixed unit is within work hours and starts after last event)
        if fixed_start >= last_event_end_time and fixed_end <= day_end:
            # Add the window BEFORE this fixed unit
            if fixed_start > last_event_end_time:
                available_windows.append((last_event_end_time, fixed_start, last_event_location))

            # Update for the next potential window
            last_event_end_time = fixed_end
            last_event_location = fixed_location # Location after this fixed job
        else:
            print(f"Warning: Fixed unit {getattr(fixed_unit, 'id', 'unknown')} on day {day_number} for tech {technician_id} has scheduling conflict ({fixed_start} vs {last_event_end_time}) or is outside working hours ({fixed_end} vs {day_end}). Ignoring for window calculation.")
            # Do not update based on this invalid unit

    # Add the final window AFTER the last valid fixed unit (or the whole day if no fixed units)
    if last_event_end_time < day_end:
        available_windows.append((last_event_end_time, day_end, last_event_location))

    return available_windows

def fit_dynamic_units_into_windows(
    dynamic_units: List[SchedulableUnit],
    available_windows: List[Tuple[datetime, datetime, Address]],
) -> Tuple[List[SchedulableUnit], List[SchedulableUnit]]:
    """
    Attempts to fit prioritized dynamic units into the available time windows for a day.

    Args:
        dynamic_units: List of dynamic units sorted by priority.
        available_windows: List of available time windows (start, end, loc_before).

    Returns:
        A tuple containing:
        - scheduled_dynamic_today: List of dynamic units successfully scheduled.
        - remaining_dynamic_units: List of dynamic units that could not be scheduled.
    """
    scheduled_dynamic_today: List[SchedulableUnit] = []
    units_scheduled_ids = set()
    # Work on a copy to avoid modifying the original list during iteration
    temp_remaining_dynamic = list(dynamic_units)
    local_available_windows = available_windows.copy() # Work on a copy of windows

    for dyn_unit in dynamic_units: # Iterate through sorted dynamic units
        fitted = False
        # Try to fit dyn_unit into the earliest possible slot in available_windows
        # HACK: This simplified logic might need review later.
        # It checks duration fit but not travel time *from* the previous event *to* the dynamic unit.
        for i, (win_start, win_end, loc_before_window) in enumerate(local_available_windows):
            # Ensure dyn_unit has duration
            unit_duration = getattr(dyn_unit, 'duration', timedelta(0))
            if unit_duration <= timedelta(0):
                print(f"Warning: Skipping dynamic unit {dyn_unit.id} with zero or negative duration.")
                break # Skip this unit entirely

            # --- Simplified check: does duration fit in window? ---
            # TODO: Refine this check? Add travel time simulation similar to calculate_eta?
            # Requires passing calculate_travel_time and unit location.
            if unit_duration <= (win_end - win_start):
                 # Assume it fits (needs travel check in reality)
                 scheduled_dynamic_today.append(dyn_unit)
                 units_scheduled_ids.add(dyn_unit.id)
                 fitted = True
                 # TODO: Refine window logic (remove/split window after placement)
                 # For now, simple approach: remove the window once used.
                 # This is a simplification and might prevent fitting smaller jobs later in the same window.
                 local_available_windows.pop(i)
                 break # Place in first available window

        if fitted:
            # Remove the fitted unit from the temporary list we are iterating over indirectly
            # This prevents trying to schedule it again.
            temp_remaining_dynamic = [u for u in temp_remaining_dynamic if u.id != dyn_unit.id]

    # The units remaining in the original list that weren't scheduled
    remaining_dynamic_units_final = [u for u in dynamic_units if u.id not in units_scheduled_ids]
    return scheduled_dynamic_today, remaining_dynamic_units_final 