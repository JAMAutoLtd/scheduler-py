"""
Routing and scheduling utilities module.

This module provides placeholder implementations for:
- Travel time calculation between locations
- Route optimization (TSP solver)
- ETA calculations and updates

TODO: Replace with actual implementations that could include:
- Google Maps Distance Matrix API integration
- Here Maps API integration
- Pre-computed distance matrices
- Professional TSP solver (e.g., OR-Tools)
- Traffic-aware routing
- Historical travel time data
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import math
# from itertools import permutations # No longer needed for brute-force

# OR-Tools import
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from .models import Address, SchedulableUnit, Technician, Job
from .availability import get_technician_availability

# --- Placeholder Implementations --- 

def calculate_travel_time(start_loc: Optional[Address], end_loc: Optional[Address]) -> timedelta:
    """
    Calculates estimated travel time between two locations.
    
    This is a placeholder that:
    1. Uses straight-line (Haversine) distance
    2. Assumes 30 mph average speed
    3. Enforces minimum 5-minute travel time
    4. Handles None locations gracefully
    
    Args:
        start_loc: Starting location (Address with lat/lng)
        end_loc: Ending location (Address with lat/lng)
        
    Returns:
        Estimated travel time as timedelta
    """
    if not start_loc or not end_loc:
        return timedelta(minutes=5)  # Minimum travel time
        
    if start_loc == end_loc:
        return timedelta(minutes=5)  # Minimum travel time for same location
        
    # Calculate Haversine distance
    R = 3959.87433  # Earth radius in miles
    
    lat1, lng1 = math.radians(start_loc.lat), math.radians(start_loc.lng)
    lat2, lng2 = math.radians(end_loc.lat), math.radians(end_loc.lng)
    
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c  # Distance in miles
    
    # Assume 30 mph average speed
    hours = distance / 30.0
    minutes = max(5, int(hours * 60))  # At least 5 minutes
    
    return timedelta(minutes=minutes)

def optimize_daily_route_and_get_time(
    units: List[SchedulableUnit], 
    start_location: Address, 
    time_constraints: Optional[Dict[str, datetime]] = None, # unit.id -> fixed_start_time
    day_start_time: Optional[datetime] = None # Need the actual start time of the availability window
) -> Tuple[List[SchedulableUnit], timedelta, Dict[str, datetime]]:
    """
    Optimizes the sequence of units for a single day using OR-Tools and calculates total time.
    
    Requires timezone-aware datetimes for day_start_time and fixed schedule times.
    Performs calculations in UTC and returns calculated start times in UTC.

    Args:
        units: List of SchedulableUnit to optimize.
        start_location: Starting location for the route (technician's start for the day).
        time_constraints: Optional dictionary of fixed start times (must be tz-aware).
        day_start_time: The actual start time of the technician's availability (must be tz-aware).
        
    Returns:
        Tuple of (optimized sequence of SchedulableUnits, 
                  total time including travel and service,
                  dictionary mapping unit.id to calculated start datetime in UTC).
        Returns ([], timedelta(0), {}) if optimization fails or no units.

    Raises:
        ValueError: If day_start_time is None or not timezone-aware, or if any
                    fixed_schedule_time in time_constraints is not timezone-aware.
    """
    if not units:
        return [], timedelta(0), {}
        
    if time_constraints is None:
        time_constraints = {}
        
    # --- Input Validation ---
    if day_start_time is None:
        raise ValueError("optimize_daily_route_and_get_time requires day_start_time.")
    if day_start_time.tzinfo is None:
         raise ValueError("day_start_time must be timezone-aware.")

    for unit_id, fixed_time in time_constraints.items():
        if fixed_time.tzinfo is None:
            raise ValueError(f"Fixed time for unit {unit_id} must be timezone-aware.")

    # --- 1. Prepare Data for OR-Tools (Convert times to UTC) ---
    
    day_start_utc = day_start_time.astimezone(timezone.utc)

    # Combine start location and unit locations into a list
    locations = [start_location] + [u.location for u in units]
    num_locations = len(locations)
    num_vehicles = 1
    depot_index = 0 # Index of the start_location in the locations list
    
    # Map unit IDs to their index in the OR-Tools model (offset by 1 for depot)
    unit_id_to_index_map = {unit.id: i + 1 for i, unit in enumerate(units)}
    index_to_unit_map = {i + 1: unit for i, unit in enumerate(units)}

    # Create the routing index manager
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot_index)

    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)

    # --- 2. Define Callbacks --- 

    # Distance Callback (Travel Time)
    def distance_callback(from_index_int, to_index_int): 
        """Returns the travel time between two locations in seconds."""
        from_node = manager.IndexToNode(from_index_int)
        to_node = manager.IndexToNode(to_index_int)
        
        # Get Address objects, handle depot index 0
        start_loc = locations[from_node]
        end_loc = locations[to_node]
        
        travel_delta = calculate_travel_time(start_loc, end_loc)
        return int(travel_delta.total_seconds())

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Time Dimension Callback (Travel Time + Service Time)
    def time_callback(from_index_int, to_index_int):
        """Returns total time (travel + service) between stops in seconds."""
        from_node = manager.IndexToNode(from_index_int)
        to_node = manager.IndexToNode(to_index_int)
        
        # Get Address objects
        start_loc = locations[from_node]
        end_loc = locations[to_node]
        
        travel_seconds = distance_callback(from_index_int, to_index_int)
        
        # Get service time (duration) for the *destination* node
        service_seconds = 0
        if to_node != depot_index:
            unit = index_to_unit_map.get(to_node)
            if unit:
                service_seconds = int(unit.duration.total_seconds())
                
        return travel_seconds + service_seconds

    time_callback_index = routing.RegisterTransitCallback(time_callback)

    # --- 3. Add Time Dimension and Constraints (Using UTC epoch) --- 
    
    time_dimension_name = 'TimeDim'
    max_daily_seconds = 24 * 3600 # Allow planning within a 24-hour horizon initially
    routing.AddDimension(
        time_callback_index,
        0,  # No slack
        max_daily_seconds, # Vehicle maximum capacity (seconds)
        False,  # Don't force start cumul to zero; handled by UTC reference
        time_dimension_name)
    time_dimension = routing.GetDimensionOrDie(time_dimension_name)

    # Apply Fixed Time Windows using UTC seconds relative to day_start_utc
    for unit_id, fixed_time in time_constraints.items():
        if unit_id in unit_id_to_index_map:
            index = manager.NodeToIndex(unit_id_to_index_map[unit_id])
            fixed_time_utc = fixed_time.astimezone(timezone.utc)

            # Calculate fixed time in seconds relative to day_start_utc
            fixed_time_seconds_rel = (fixed_time_utc - day_start_utc).total_seconds()
            
            # Ensure non-negative time (should not happen with valid inputs)
            fixed_time_seconds_rel = max(0, int(fixed_time_seconds_rel))
            
            # Set a narrow window [fixed_time, fixed_time + buffer] 
            buffer_seconds = 60 # 1 minute buffer
            time_dimension.CumulVar(index).SetRange(
                fixed_time_seconds_rel, 
                fixed_time_seconds_rel + buffer_seconds
            )

    # Set start time constraint for the depot relative to day_start_utc (which is 0 seconds)
    # index = routing.Start(0) # Vehicle 0 start
    # time_dimension.CumulVar(index).SetRange(0, 60) # Allow starting within first minute

    # --- 4. Set Search Parameters and Solve --- 
    
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    # search_parameters.local_search_metaheuristic = (
    #     routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    # search_parameters.time_limit.seconds = 30 # Example time limit

    solution = routing.SolveWithParameters(search_parameters)

    # --- 5. Process Solution (Calculate start times in UTC) --- 
    
    optimized_sequence = []
    # Dictionary to store unit.id -> calculated start datetime (UTC)
    calculated_start_times_utc = {} 
    total_route_time_seconds = 0 # Initialize

    if solution:
        time_dimension = routing.GetDimensionOrDie(time_dimension_name) 
        index = routing.Start(0) # Vehicle 0
        route_nodes = [] # Store node indices in order
        last_job_arrival_seconds_rel = 0 # Relative to day_start_utc
        last_job_node_index = -1 # Track the node index of the last job

        # Iterate through the route determined by the solver
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_nodes.append(node_index)
            
            # Calculate and store start time if it's a job (not depot)
            if node_index != depot_index:
                unit = index_to_unit_map[node_index]
                or_tools_index = manager.NodeToIndex(node_index)
                
                # Get start time in seconds *relative to day_start_utc* from the solver
                start_seconds_rel = solution.Min(time_dimension.CumulVar(or_tools_index))
                
                # Convert relative seconds back to an absolute UTC datetime
                calculated_start_utc = day_start_utc + timedelta(seconds=start_seconds_rel)
                calculated_start_times_utc[unit.id] = calculated_start_utc

                # Update the arrival time (relative seconds) and index of the latest job visited
                last_job_arrival_seconds_rel = start_seconds_rel
                last_job_node_index = node_index
                
            # Move to the next node in the solution
            index = solution.Value(routing.NextVar(index))
            
        # Build the optimized sequence of SchedulableUnits from the node list (excluding depot)
        last_unit = None
        for node in route_nodes:
            if node != depot_index:
                unit = index_to_unit_map[node]
                optimized_sequence.append(unit)
                last_unit = unit # The last unit added is the final one in the sequence
                
        # Calculate total time = arrival at last job + service duration of last job
        if last_unit: 
            # Get the service duration of the last unit
            last_job_duration_seconds = int(last_unit.duration.total_seconds())
            # Total time is calculated relative to the start
            total_route_time_seconds = last_job_arrival_seconds_rel + last_job_duration_seconds
        else:
            # If there were no units in the route (only depot start/end), time is 0
            total_route_time_seconds = 0
            
    else:
        # Handle case where OR-Tools found no solution
        print('No solution found for route optimization!')
        # Return empty sequence and zero time
        return [], timedelta(0), {}

    # Convert total seconds to timedelta for the return value
    total_time_delta = timedelta(seconds=total_route_time_seconds)
    
    # Return UTC start times
    return optimized_sequence, total_time_delta, calculated_start_times_utc

def update_etas_for_schedule(technician: Technician, daily_unit_start_times: Optional[Dict[int, Dict[str, datetime]]] = None):
    """Update ETAs for all jobs in a technician's schedule.

    If daily_unit_start_times are provided (from optimize_daily_route_and_get_time),
    uses the precise timings derived from the OR-Tools solution.
    Otherwise, falls back to recalculating based on sequence and travel time.

    Note: The function modifies Job objects in place.
          Assumes daily_unit_start_times are provided in UTC if available.

    Args:
        technician: The technician whose schedule needs ETA updates.
        daily_unit_start_times: Optional dict mapping day_number to a dict mapping 
                                unit.id to calculated start datetime (expected in UTC).
    """
    # No return value needed, jobs updated by reference

    for day, units in technician.schedule.items():
        if not units:
            continue

        # Get the calculated start times for this day, if available
        # Assumes these are already in UTC if provided
        unit_start_times_today_utc = daily_unit_start_times.get(day) if daily_unit_start_times else None

        if unit_start_times_today_utc:
            # --- Calculate ETAs using Provided UTC Start Times --- 
            for unit in units:
                calculated_start_utc = unit_start_times_today_utc.get(unit.id)
                if calculated_start_utc is None:
                    print(f"Warning: Missing calculated start time for unit {unit.id} on day {day}. ETA might be inaccurate.")
                    continue 
                
                # Store UTC times in the Job objects
                unit_start_time_utc = calculated_start_utc
                
                # Update unit object times (optional, keeping UTC for now)
                unit.estimated_start_time = unit_start_time_utc
                unit.estimated_end_time = unit_start_time_utc + unit.duration

                # Update ETAs for all jobs within this unit (in UTC)
                job_current_start_utc = unit_start_time_utc
                for job in unit.jobs:
                    # Store all schedule/ETA times as timezone-aware UTC
                    job.estimated_sched = job_current_start_utc 
                    job.estimated_sched_end = job_current_start_utc + job.job_duration
                    # TODO: Define logic for calculating customer_eta_start/end 
                    # based on the UTC estimated_sched. This might involve converting
                    # to local time and adding a buffer, or keeping UTC.
                    # For now, set them based on estimated_sched UTC +/- buffer
                    buffer = timedelta(hours=1)
                    job.customer_eta_start = job_current_start_utc - buffer
                    job.customer_eta_end = job_current_start_utc + job.job_duration + buffer
                    
                    job_current_start_utc += job.job_duration # Stack jobs sequentially within the unit (in UTC)

        else:
            # --- Fallback: Recalculate ETAs Manually (using UTC) --- 
            print(f"Recalculating ETAs manually using UTC for day {day}")
            try:
                # Assume get_technician_availability returns timezone-aware times
                avail = get_technician_availability(technician, day)
                if avail is None:
                    print(f"Warning: No availability found for day {day} during ETA fallback.")
                    continue
                # Extract and convert start/end to UTC if not already
                # Handle both dict and object access for flexibility
                if isinstance(avail, dict):
                    day_start_local = avail.get('start_time')
                    day_end_local = avail.get('end_time')
                else: # Assuming object access
                    day_start_local = getattr(avail, 'start_time', None)
                    day_end_local = getattr(avail, 'end_time', None)
                
                if not day_start_local or not day_end_local:
                    print(f"Warning: Missing start/end time from availability for day {day}.")
                    continue
                if day_start_local.tzinfo is None or day_end_local.tzinfo is None:
                    # This should ideally not happen if availability function is correct
                    print(f"Warning: Availability times for day {day} are not timezone-aware. Cannot perform UTC conversion.")
                    continue
                    
                day_start_utc = day_start_local.astimezone(timezone.utc)
                day_end_utc = day_end_local.astimezone(timezone.utc)

            except Exception as e:
                 print(f"Error getting availability or converting to UTC for day {day} during ETA fallback: {e}")
                 continue # Skip day if lookup/conversion fails

            current_time_utc = day_start_utc
            current_loc = technician.current_location if day == 1 else technician.home_location

            for unit in units:
                travel = calculate_travel_time(current_loc, unit.location)
                unit_start_utc = current_time_utc + travel
                
                # Handle fixed time constraints (compare in UTC)
                if unit.fixed_schedule_time:
                    if unit.fixed_schedule_time.tzinfo is None:
                        # This indicates an upstream issue, cannot reliably compare
                         print(f"Warning: Fixed schedule time for unit {unit.id} is naive, cannot compare in fallback.")
                         # Decide behavior: skip unit, ignore constraint?
                         # Skipping unit for safety:
                         continue
                    fixed_time_utc = unit.fixed_schedule_time.astimezone(timezone.utc)
                    unit_start_utc = max(unit_start_utc, fixed_time_utc)

                # Check against day end (in UTC)
                if unit_start_utc + unit.duration > day_end_utc:
                    print(f"Warning: Manual UTC ETA calc overflow day {day} for tech {technician.id}")
                    # Clear remaining job ETAs
                    for subsequent_unit in units[units.index(unit):]:
                        for job in subsequent_unit.jobs:
                            job.estimated_sched = None
                            job.estimated_sched_end = None
                            job.customer_eta_start = None
                            job.customer_eta_end = None
                    break

                # Update unit object times (optional, keeping UTC)
                unit.estimated_start_time = unit_start_utc
                unit.estimated_end_time = unit_start_utc + unit.duration

                job_current_start_utc = unit_start_utc
                for job in unit.jobs:
                    # Store all schedule/ETA times as timezone-aware UTC
                    job.estimated_sched = job_current_start_utc 
                    job.estimated_sched_end = job_current_start_utc + job.job_duration
                    # TODO: Refine customer ETA logic (same as above)
                    buffer = timedelta(hours=1)
                    job.customer_eta_start = job_current_start_utc - buffer
                    job.customer_eta_end = job_current_start_utc + job.job_duration + buffer
                    
                    job_current_start_utc += job.job_duration # Stack jobs (in UTC)
                
                current_time_utc = unit_start_utc + unit.duration # End time of this unit (in UTC)
                current_loc = unit.location

    # The Job objects within technician.schedule are updated directly by reference.
    # No explicit return value needed unless specifically required later. 