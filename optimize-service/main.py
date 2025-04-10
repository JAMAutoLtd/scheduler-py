from fastapi import FastAPI, HTTPException
from models import (
    OptimizationRequestPayload, 
    OptimizationResponsePayload, 
    TechnicianRoute, 
    RouteStop
)
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from datetime import datetime, timedelta, timezone
import pytz # For robust timezone handling if needed, though ISO strings often include offset
from typing import List, Literal

# --- Helper Functions ---

# Define a reference epoch (e.g., start of the day or earliest time in payload)
# Using UTC for consistency is generally best.
# EPOCH = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) # Removed floating EPOCH

def iso_to_seconds(iso_str: str) -> int:
    """Converts ISO 8601 string to seconds since the Unix epoch (UTC)."""
    # global EPOCH # Removed usage
    dt = datetime.fromisoformat(iso_str)
    # Ensure dt is offset-aware, defaulting to UTC if naive
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC timestamp (seconds since Unix epoch)
    return int(dt.timestamp())
    # return int((dt - EPOCH).total_seconds()) # Old logic

def seconds_to_iso(seconds: int) -> str:
    """Converts seconds since the Unix epoch back to ISO 8601 string (UTC)."""
    # global EPOCH # Removed usage
    # Convert seconds since epoch to UTC datetime object
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    # dt = EPOCH + timedelta(seconds=seconds) # Old logic
    return dt.isoformat()

# --- FastAPI App ---

app = FastAPI(
    title="Job Scheduler Optimization Service",
    description="Receives scheduling problems and returns optimized routes using OR-Tools.",
    version="0.1.0"
)

@app.post("/optimize-schedule", 
            response_model=OptimizationResponsePayload,
            summary="Solve the vehicle routing problem for job scheduling",
            tags=["Optimization"]
            )
async def optimize_schedule(payload: OptimizationRequestPayload) -> OptimizationResponsePayload:
    """
    Accepts a detailed scheduling problem description and returns optimized routes.
    """
    print(f"Received optimization request with {len(payload.items)} items and {len(payload.technicians)} technicians.")
    
    if not payload.items:
        return OptimizationResponsePayload(status='success', message='No items provided for scheduling.', routes=[], unassignedItemIds=[])
    if not payload.technicians:
        return OptimizationResponsePayload(status='error', message='No technicians available for scheduling.', routes=[], unassignedItemIds=[item.id for item in payload.items])

    num_locations = len(payload.locations)
    num_vehicles = len(payload.technicians)
    num_items = len(payload.items)
    
    # Map item IDs to their index in the payload.items list for easier lookup
    item_id_to_payload_index = {item.id: i for i, item in enumerate(payload.items)}
    # Map solver indices back to location IDs/coords for travel matrix lookup
    location_index_map = {loc.index: loc for loc in payload.locations}
    
    # Create the routing index manager.
    # Number of nodes = locations. Start/End nodes are defined per vehicle.
    manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, 
                                           [t.startLocationIndex for t in payload.technicians],
                                           [t.endLocationIndex for t in payload.technicians])

    # Create Routing Model.
    routing = pywrapcp.RoutingModel(manager)

    # --- Callbacks ---
    
    # Travel time callback
    def travel_time_callback(from_index_mgr, to_index_mgr):
        from_node = manager.IndexToNode(from_index_mgr)
        to_node = manager.IndexToNode(to_index_mgr)
        
        # Use the precomputed matrix from the payload
        # The matrix keys are expected to be the location indices defined in payload.locations
        try:
            # Matrix uses original location indices
            # <<< Ensure location_index_map is accessible or defined earlier if needed >>>
            # Assuming location_index_map is defined in the outer scope
            from_loc_idx = location_index_map.get(from_node) # Use .get for safety
            to_loc_idx = location_index_map.get(to_node)
            
            if from_loc_idx is None or to_loc_idx is None:
                print(f"TRAVEL_CALLBACK WARN: Node index not found in location_index_map (from: {from_node}, to: {to_node}). Returning large cost.")
                return 999999

            # Access the actual index field from the location object
            from_loc_payload_idx = from_loc_idx.index 
            to_loc_payload_idx = to_loc_idx.index

            travel_time = payload.travelTimeMatrix.get(from_loc_payload_idx, {}).get(to_loc_payload_idx, 999999)
            return travel_time
        except Exception as e:
            print(f"TRAVEL_CALLBACK ERROR: Exception for nodes {from_node} -> {to_node}. Error: {e}. Returning large cost.")
            return 999999

    transit_callback_index = routing.RegisterTransitCallback(travel_time_callback)
    # Arc cost is based *only* on travel time
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Service time (demand) callback
    item_solver_indices = {} 
    def service_time_callback(index_mgr):
        node = manager.IndexToNode(index_mgr)
        for i, item in enumerate(payload.items):
            if item.locationIndex == node:
                item_solver_indices[item.id] = index_mgr
                return item.durationSeconds
        return 0 # Depots have zero service time

    # Combined Transit + Service Time Callback for Time Dimension
    def transit_plus_service_time_callback(from_index_mgr, to_index_mgr):
        """Returns travel_time(from, to) + service_time(from)."""
        travel = travel_time_callback(from_index_mgr, to_index_mgr)
        service = service_time_callback(from_index_mgr)
        # Add safety check for large costs indicating errors
        if travel >= 999999 or service >= 999999:
             return 999999 # Propagate large cost if inputs were invalid
        return travel + service

    # Register the combined callback
    combined_time_callback_index = routing.RegisterTransitCallback(transit_plus_service_time_callback)

    # --- Dimensions ---

    # Time Dimension
    routing.AddDimensionWithVehicleCapacity(
        combined_time_callback_index, # Use combined travel + service time for dimension propagation
        0,  # Revert slack back to 0
        [3600 * 24 * 7] * num_vehicles,  # Large upper bound for total route time (e.g., 1 week)
        False,  # start cumul to zero = False (start times vary based on tech availability)
        "Time"
    )
    time_dimension = routing.GetDimensionOrDie("Time")
    # Ensure the time dimension uses the travel time for transit calculations
    # (This might already be implicit via SetArcCostEvaluatorOfAllVehicles, but let's be explicit if possible/needed)
    # The previous attempt time_dimension.SetTransitEvaluatorOfAllVehicles caused AttributeError.
    # Checking docs again... the dimension implicitly uses the transit callback registered with the model.
    # No need to set it explicitly on the dimension itself.

    # --- Constraints ---

    # Technician Time Windows
    for i, tech in enumerate(payload.technicians):
        start_seconds = iso_to_seconds(tech.earliestStartTimeISO)
        end_seconds = iso_to_seconds(tech.latestEndTimeISO)
        # Ensure times are non-negative relative to EPOCH
        start_seconds = max(0, start_seconds)
        end_seconds = max(0, end_seconds)
        # Ensure start <= end (basic sanity check)
        if start_seconds > end_seconds:
            print(f"Warning: Technician {tech.id} has start time after end time ({start_seconds} > {end_seconds}). Setting range to [{start_seconds}, {start_seconds}].")
            end_seconds = start_seconds # Or handle as error?
        
        time_dimension.CumulVar(routing.Start(i)).SetRange(start_seconds, end_seconds)
        time_dimension.CumulVar(routing.End(i)).SetRange(start_seconds, end_seconds)

    # Fixed Time Constraints
    for constraint in payload.fixedConstraints:
        item_payload_idx = item_id_to_payload_index.get(constraint.itemId)
        if item_payload_idx is None:
            print(f"Warning: Fixed constraint for unknown item ID {constraint.itemId}. Skipping.")
            continue

        item_loc_index = payload.items[item_payload_idx].locationIndex
        solver_index = manager.NodeToIndex(item_loc_index)

        fixed_time_seconds = iso_to_seconds(constraint.fixedTimeISO)
        # Ensure time is non-negative
        fixed_time_seconds = max(0, fixed_time_seconds)

        # Add constraint for the specific item index
        # For a fixed time, the range is [fixed_time, fixed_time]
        time_dimension.CumulVar(solver_index).SetRange(fixed_time_seconds, fixed_time_seconds)
        print(f"Applied fixed time constraint for item {constraint.itemId} at index {solver_index} to be {fixed_time_seconds}s")


    # Technician Eligibility (Disjunctions) & Priority Penalties
    # Get lists of all start and end location indices for depot check
    starts = [t.startLocationIndex for t in payload.technicians]
    ends = [t.endLocationIndex for t in payload.technicians]

    # Add high penalty for dropping high-priority nodes
    # OR-Tools handles priority implicitly via penalties for dropping nodes
    # Higher penalty means less likely to be dropped.
    # Adjust penalty calculation as needed based on priority scale (e.g., 1 = highest)
    max_priority = max((item.priority for item in payload.items if item.priority is not None), default=1)
    # base_penalty = 1000 # Base penalty for being unserved
    # <<< INCREASE PENALTY SIGNIFICANTLY >>>
    # Ensure penalty outweighs reasonable travel times. If max travel is ~1hr (3600s), penalty should be higher.
    base_penalty = 100000 

    for i, item in enumerate(payload.items):
        # Ensure locationIndex is valid
        if not (0 <= item.locationIndex < num_locations):
             print(f"Warning: Item {item.id} has invalid locationIndex {item.locationIndex}. Skipping disjunction.")
             continue

        # Convert payload location index to solver's internal node index
        solver_index = manager.NodeToIndex(item.locationIndex)

        # Determine if this solver index corresponds to ANY vehicle's start or end node.
        # --- This block IS necessary again to handle items at depots correctly ---
        is_depot_node = False
        for v_idx in range(num_vehicles):
            # Check against the *solver's* representation of start/end nodes
            if solver_index == routing.Start(v_idx) or solver_index == routing.End(v_idx):
                is_depot_node = True
                break
        # --- End block ---

        # Per OR-Tools documentation, disjunctions cannot include start/end nodes.
        if is_depot_node:
            # If an item is at a depot location, treat it as mandatory if the location is visited.
            # Do not add a disjunction or penalty for skipping.
            # This branch IS relevant again for items at depot locations
            print(f"Info: Item {item.id} (solver index {solver_index}) matched routing.Start/End. No disjunction added.")
            continue # Skip disjunction logic
        else:
            # --- This logic only applies to non-depot nodes ---
            
            # Filter eligible vehicles for THIS item
            eligible_vehicles = [
                tech_idx for tech_idx, tech in enumerate(payload.technicians)
                if tech.id in item.eligibleTechnicianIds # Check if tech's ID is in the item's eligible list
            ]

            # If a non-depot item has NO eligible vehicles, it cannot be served.
            if not eligible_vehicles:
                print(f"Warning: Non-depot Item {item.id} has no eligible technicians. Cannot be scheduled.")
                # This item will naturally be unassigned as no vehicle can visit it.
                continue # Skip to the next item

            # Priority calculation (ensure priority is not None)
            if item.priority is None:
                 print(f"Warning: Item {item.id} has None priority. Using default base penalty.")
                 priority_penalty = base_penalty
            else:
                priority_penalty = base_penalty * (max_priority - item.priority + 1)

            # Ensure penalty is non-negative
            if priority_penalty < 0:
                print(f"Warning: Calculated negative penalty ({priority_penalty}) for item {item.id}. Clamping to 0.")
                priority_penalty = 0

            # Allow the solver to drop the NON-DEPOT node (item) with the calculated penalty.
            # max_cardinality=1 means at most one technician will serve this item.
            # print(f"  Attempting AddDisjunction for non-depot item {item.id} (solver_index {solver_index})") # <<< REMOVING DEBUG PRINT
            try:
                 # === RESTORING AddDisjunction CALL ===
                 # routing.AddDisjunction([solver_index], priority_penalty, 1) # <<< TEMPORARILY COMMENTED OUT FOR DEBUGGING
                 routing.AddDisjunction([solver_index], priority_penalty, 1) # <<< RESTORED
                 # === END RESTORED CALL ===
                 # print(f"SKIPPED AddDisjunction for {item.id} (DEBUGGING)") # Indicate skipping for debugging
                 print(f"Added disjunction for non-depot item {item.id} (idx {solver_index}), penalty {priority_penalty}, max_card=1")
            except Exception as e:
                 print(f"!!! CRITICAL ERROR adding disjunction for non-depot item {item.id} (locIdx: {item.locationIndex}, solverIdx: {solver_index}, penalty: {priority_penalty}): {e}")
                 raise
            # --- End logic for non-depot nodes ---

        # Calculation of total travel time in post-processing seems complex and might need review later.
        # Consider if OR-Tools provides a simpler way to get route travel times.

    # --- Solve ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    # search_parameters.time_limit.seconds = 30 # Example time limit
    search_parameters.time_limit.FromSeconds(30) # Set time limit to 30s
    # <<< Add solution limit to stop after first solution >>>
    # search_parameters.solution_limit = 1 # <<< REMOVED

    print("Starting OR-Tools solver...")
    assignment = routing.SolveWithParameters(search_parameters)
    print("Solver finished.")

    # --- Process Results ---
    routes: List[TechnicianRoute] = []
    assigned_item_ids = set()

    if assignment:
        print("Solution found.")
        # Define helper to find item by location index safely
        def find_item_by_location(loc_idx):
            for item in payload.items:
                if item.locationIndex == loc_idx:
                    return item
            return None
            
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            technician_id = payload.technicians[vehicle_id].id
            route_stops: List[RouteStop] = []
            total_travel_time_seconds = 0

            while True: # Loop until we explicitly break at the end node
                # Get the next index in the route assigned by the solver
                next_index = assignment.Value(routing.NextVar(index))

                # Calculate travel time for the segment from current index to next index
                segment_travel_time = travel_time_callback(index, next_index)
                total_travel_time_seconds += segment_travel_time

                # Check if the next node is the end node for this vehicle
                if routing.IsEnd(next_index):
                    # We have completed the route segments for this vehicle.
                    # The loop terminates after this iteration.
                    print(f"Vehicle {vehicle_id}: Reached end node {manager.IndexToNode(next_index)}. Total travel: {total_travel_time_seconds}s")
                    break 

                # --- Process the stop at `next_index` (it's not the end node) ---
                node_index = manager.IndexToNode(next_index)
                current_item = find_item_by_location(node_index)

                if current_item:
                    assigned_item_ids.add(current_item.id)

                    # Calculate arrival time at this stop (next_index)
                    # Arrival = Departure_from_previous(index) + Travel_time(index -> next_index)
                    last_start_time_var = time_dimension.CumulVar(index)
                    last_service_duration = service_time_callback(index) # Duration at previous node (0 for start)
                    last_departure_time = assignment.Value(last_start_time_var) + last_service_duration
                    calculated_arrival_at_current = last_departure_time + segment_travel_time

                    # Get the service start time at this stop (next_index) directly from the solver
                    current_start_time_var = time_dimension.CumulVar(next_index)
                    current_start_time = assignment.Value(current_start_time_var)

                    # Calculate service end time
                    current_service_duration = current_item.durationSeconds
                    current_end_time = current_start_time + current_service_duration
                    
                    # Consistency check (optional but good for debugging)
                    if current_start_time < calculated_arrival_at_current - 1: # Allow 1s tolerance for float issues
                         print(f"!!! WARNING Vehicle {vehicle_id}, Item {current_item.id}: Solver start time {current_start_time} is earlier than calculated arrival {calculated_arrival_at_current}. Check model consistency.")

                    route_stops.append(RouteStop(
                        itemId=current_item.id,
                        arrivalTimeISO=seconds_to_iso(calculated_arrival_at_current),
                        startTimeISO=seconds_to_iso(current_start_time),
                        endTimeISO=seconds_to_iso(current_end_time)
                    ))
                else:
                    # This case should not happen if only item locations are visited besides start/end
                    print(f"Warning: Could not find item for node index {node_index} (solver index {next_index}) in route for vehicle {vehicle_id}")

                # Move to the next node for the next iteration
                index = next_index
                # --- End of loop iteration ---

            # --- After loop for one vehicle --- 
            total_duration_seconds = 0
            if route_stops:
                 # Duration from first arrival to last end time
                 first_stop_arrival = iso_to_seconds(route_stops[0].arrivalTimeISO)
                 last_stop_end = iso_to_seconds(route_stops[-1].endTimeISO)
                 total_duration_seconds = last_stop_end - first_stop_arrival
            
            # Only add routes that actually have stops
            if route_stops:
                # Re-verify technician eligibility (should be guaranteed by solver if model is correct, but good practice)
                is_route_valid = True
                for stop in route_stops:
                    item_payload_idx = item_id_to_payload_index.get(stop.itemId)
                    if item_payload_idx is None: continue 
                    item = payload.items[item_payload_idx]
                    if technician_id not in item.eligibleTechnicianIds:
                        print(f"Error: Solver assigned item {stop.itemId} to ineligible technician {technician_id}. Route invalid.")
                        is_route_valid = False
                        # Mark items from this invalid route as unassigned
                        for s in route_stops: assigned_item_ids.discard(s.itemId)
                        break 
                
                if is_route_valid:
                    routes.append(TechnicianRoute(
                        technicianId=technician_id,
                        stops=route_stops,
                        totalTravelTimeSeconds=total_travel_time_seconds,
                        totalDurationSeconds=total_duration_seconds
                    ))

        # --- After processing all vehicles --- 
        unassigned_item_ids = [item.id for item in payload.items if item.id not in assigned_item_ids]
        
        status: Literal['success', 'partial', 'error']
        message: str
        if not unassigned_item_ids:
            status = 'success'
            message = 'Optimization successful. All items scheduled.'
        elif len(unassigned_item_ids) < num_items:
            status = 'partial'
            message = f'Optimization partially successful. {len(unassigned_item_ids)} items could not be scheduled.'
            print(f"Unassigned items: {unassigned_item_ids}")
        else: # All items unassigned
             status = 'error' # Treat as error if nothing could be scheduled
             message = 'Optimization failed. No routes could be assigned.'
             print(f"All items were unassigned.")

        if assignment: # Check if a solution was found
            print(f"Solver finished. Final Objective Value: {assignment.ObjectiveValue()}")

        return OptimizationResponsePayload(
            status=status,
            message=message,
            routes=routes,
            unassignedItemIds=unassigned_item_ids
        )
    else:
        print("No solution found by the solver.")
        # No solution found
        return OptimizationResponsePayload(
            status='error',
            message='Optimization failed. No solution found.',
            routes=[],
            unassignedItemIds=[item.id for item in payload.items] # All items are unassigned
        )

# Example of how to run this locally (requires uvicorn):
# uvicorn main:app --reload --port 8000 
# You can then access the interactive API docs at http://127.0.0.1:8000/docs
