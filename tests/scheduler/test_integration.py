"""
Integration tests for the scheduler, focusing on the interaction
between update_job_queues_and_routes and optimize_daily_route_and_get_time.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from typing import List, Dict, Optional, Tuple
import uuid
from httpx import Response, RequestError # Import necessary httpx exceptions

# Use corrected imports (no src.)
from scheduler.models import (
    Address, Technician, Job, Order, Service, Equipment, Van, SchedulableUnit,
    CustomerVehicle, CustomerType, JobStatus, ServiceCategory, DailyAvailability
)
from scheduler.scheduler import update_job_queues_and_routes, MAX_PLANNING_DAYS
from scheduler.utils import group_jobs_by_order, create_schedulable_units
from scheduler.availability import get_technician_availability
from scheduler.routing import update_etas_for_schedule # Removed fetch_distance_matrix
from scheduler import data_interface # For mocking its functions

# Imports from other test files (if needed for fixtures/mocks)
# Use absolute import from tests directory
from tests.scheduler.test_scheduler import MockJob, MockAddress, MockTechnician, MockSchedulableUnit, mock_get_availability_update
# from .test_routing import _create_mock_matrix # Use helper for mock matrix
# TODO: Revisit if _create_mock_matrix is needed and import appropriately

# --- Constants and Base Data ---

TECH_HOME_INTEG = MockAddress(1, "Home Base Integ")
LOC_INT_A = MockAddress(201, "Integ Loc A")
LOC_INT_B = MockAddress(202, "Integ Loc B")
LOC_INT_C = MockAddress(203, "Integ Loc C")

DAY_START_INTEG = datetime(2024, 5, 20, 9, 0, 0, tzinfo=timezone.utc) # Example date in UTC

# --- Test Fixtures ---

@pytest.fixture
def integ_technician():
    """Provides a technician for integration tests."""
    tech = MockTechnician(
        id=10, 
        name="IntegTech",
        van_equipment_models=["tool_a", "tool_b"],
        current_loc=TECH_HOME_INTEG, 
        home_loc=TECH_HOME_INTEG
    )
    tech.schedule = {} # Ensure clean schedule
    tech._assigned_jobs = [] # Initialize job list
    return tech

# --- Mock Setup ---

# Mock for the OR-Tools Solver itself (within optimize_daily_route_and_get_time)
@pytest.fixture
def mock_or_tools_solver():
    with patch('src.scheduler.routing.pywrapcp.RoutingModel.SolveWithParameters') as mock_solve:
        yield mock_solve

# Mock for the final ETA update call (to check results)
@pytest.fixture
def mock_final_eta_update():
    # Assuming update_etas_for_schedule calls update_job_etas in data_interface
    # Patch where the function is looked up (likely in data_interface)
    with patch('scheduler.data_interface.update_job_etas') as mock_update:
        yield mock_update

# --- Integration Test Case(s) ---

def test_update_queues_integrates_with_optimizer(
    integ_technician,
    mock_or_tools_solver,
    mock_final_eta_update,
    monkeypatch
):
    """
    Test the integration path:
    1. update_job_queues_and_routes prepares data.
    2. Calls optimize_daily_route_and_get_time (real function).
    3. optimize_daily_route_and_get_time sets up OR-Tools model.
    4. OR-Tools solver is called (mocked).
    5. Mocked solution is processed by optimize_daily_route_and_get_time.
    6. Result is processed by update_job_queues_and_routes.
    7. Technician schedule is updated.
    8. Final ETA update is called with expected data.
    """
    # Arrange
    
    # 1. Assign Jobs to Technician
    job1 = MockJob(order_id=201, location=LOC_INT_A, equipment=[], duration_hours=2, priority=5)
    job2 = MockJob(order_id=202, location=LOC_INT_B, equipment=[], duration_hours=3, priority=1)
    integ_technician._assigned_jobs = [job1, job2]

    # 2. Mock Dependencies
    #    - Availability (Use existing mock from test_scheduler)
    monkeypatch.setattr("src.scheduler.scheduler.get_technician_availability", mock_get_availability_update)
    #    - Distance Matrix (Use existing helper from test_routing)
    #      Need to ensure the locations passed to fetch match the expected matrix keys
    locations_for_day1 = [TECH_HOME_INTEG, LOC_INT_A, LOC_INT_B]
    mock_matrix_day1 = _create_mock_matrix(locations_for_day1)
    def mock_fetch_matrix_integ(*args, **kwargs):
        # Basic mock - assumes only day 1 is planned in this test
        # A more complex test might need to return different matrices based on day
        print(f"--- Mock Matrix Fetch Called (Integ Test) Args: {args} Kwargs: {kwargs} ---")
        # Check if the locations match what we expect for day 1
        passed_locs = args[0]
        passed_loc_ids = sorted([l.id for l in passed_locs])
        expected_loc_ids = sorted([l.id for l in locations_for_day1])
        if passed_loc_ids == expected_loc_ids:
            return mock_matrix_day1
        else:
            print(f"WARN: Mock matrix fetch received unexpected locations: {passed_loc_ids} vs {expected_loc_ids}")
            # Return a default empty matrix or raise error?
            return _create_mock_matrix(passed_locs) 

    monkeypatch.setattr("src.scheduler.routing.fetch_distance_matrix", mock_fetch_matrix_integ)
    monkeypatch.setattr("src.scheduler.scheduler.GOOGLE_MAPS_API_KEY", "DUMMY_KEY_INTEG")

    # 3. Configure the Mocked OR-Tools Solver Result
    #    Simulate a solution: Home -> Job2 (Prio 1) -> Job1 -> Home
    mock_solution = MagicMock()
    # Define the sequence (node indices: 0=Depot, 1=Job1(A), 2=Job2(B))
    # Route: 0 -> 2 -> 1 -> 0 
    # Values returned by solution.Value(routing.NextVar(node))
    mock_solution.Value.side_effect = lambda var_index: {0: 2, 2: 1, 1: 0}.get(var_index, -1) # Map current node to next node index

    # Define the start times returned by solution.Min(time_dimension.CumulVar(node))
    # Assume 30 min travel Home->B, 30 min B->A
    start_time_job2 = DAY_START_INTEG + timedelta(minutes=30) # Arrive B 9:30
    end_time_job2 = start_time_job2 + job2.job_duration # Finish B 12:30
    start_time_job1 = end_time_job2 + timedelta(minutes=30) # Arrive A 13:00
    end_time_job1 = start_time_job1 + job1.job_duration # Finish A 15:00
    
    # Need mapping from OR-Tools node index to our Unit ID (or Order ID if using that)
    # Let's assume optimize_daily_route_and_get_time uses order_id as key internally for now
    order_id_job1 = job1.order_id
    order_id_job2 = job2.order_id
    
    # Mock solution.Min needs to return time in *seconds* from start
    def mock_min_side_effect(cumul_var_mock):
        # We need to map the OR-Tools node index back to our job/unit to return the right time
        # This requires knowing the mapping used inside optimize_daily_route_and_get_time
        # HACK: Assume node 1 -> job1, node 2 -> job2 for this test. THIS IS FRAGILE.
        node_index = cumul_var_mock.Index() 
        if node_index == 2: # Job 2 (B)
             return int((start_time_job2 - DAY_START_INTEG).total_seconds())
        elif node_index == 1: # Job 1 (A)
             return int((start_time_job1 - DAY_START_INTEG).total_seconds())
        return 0 # Depot start time
    mock_solution.Min.side_effect = mock_min_side_effect

    # Configure the mocked solver to return this solution object
    mock_or_tools_solver.return_value = mock_solution

    # Act
    update_job_queues_and_routes([integ_technician])

    # Assert

    # 1. Check if the schedule on the technician object matches the mocked solution order
    assert 1 in integ_technician.schedule # Should have schedule for Day 1
    day1_schedule = integ_technician.schedule[1]
    assert len(day1_schedule) == 2
    # Check order based on job IDs (assuming create_schedulable_units creates units with single jobs here)
    scheduled_job_ids = [unit.jobs[0].id for unit in day1_schedule]
    assert scheduled_job_ids == [job2.id, job1.id] # Job2 first (Prio 1), then Job1

    # 2. Check if the final ETA update was called with correct ETAs
    #    The update_etas_for_schedule function calculates these based on the optimizer result.
    #    We need to mock the API call made by scheduler.update_job_etas
    mock_final_eta_update.assert_called_once()
    call_args, _ = mock_final_eta_update.call_args
    eta_updates_passed = call_args[0] # Expecting a list of tuples: (job_id, eta_start, eta_end)
    
    assert isinstance(eta_updates_passed, list)
    etas_dict = {job_id: start for job_id, start, end in eta_updates_passed}

    # Verify the start times match those derived from the mocked solver solution
    assert job2.id in etas_dict
    assert etas_dict[job2.id] == start_time_job2
    assert job1.id in etas_dict
    assert etas_dict[job1.id] == start_time_job1

    # Optional: Add more assertions
    # - Check mock_or_tools_solver was called once.
    # - Check properties of the OR-Tools model setup if desired (more complex mocking needed).
    mock_or_tools_solver.assert_called_once()
    