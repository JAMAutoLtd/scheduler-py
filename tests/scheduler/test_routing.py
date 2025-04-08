"""Tests for routing and scheduling utilities."""

import pytest
from datetime import datetime, timedelta, time
import math
import uuid
from unittest.mock import patch, MagicMock
from typing import Optional, List, Dict, Tuple

from scheduler.routing import (
    calculate_travel_time,
    optimize_daily_route_and_get_time,
    update_etas_for_schedule,
    get_technician_availability
)
from scheduler.models import (
    Address, SchedulableUnit, Technician, Job, DailyAvailability, JobStatus,
    Order, CustomerType, CustomerVehicle, Service, ServiceCategory, EquipmentType
)

# --- Test Data ---

@pytest.fixture
def test_locations():
    """Create a set of test locations with known distances."""
    # Using real NYC area coordinates for realistic testing
    return {
        'manhattan': Address(id=1, street_address="Manhattan", lat=40.7128, lng=-74.0060),
        'brooklyn': Address(id=2, street_address="Brooklyn", lat=40.6782, lng=-73.9442),
        'queens': Address(id=3, street_address="Queens", lat=40.7282, lng=-73.7949),
        'bronx': Address(id=4, street_address="Bronx", lat=40.8448, lng=-73.8648),
        'staten': Address(id=5, street_address="Staten Island", lat=40.5795, lng=-74.1502),
    }

@pytest.fixture
def test_orders(test_locations):
    """Create test orders."""
    vehicle = CustomerVehicle(
        id=1,
        vin="1HGCM82633A123456",
        make="Honda",
        year=2020,
        model="Accord"
    )
    
    return [
        Order(
            id=i,
            user_id=uuid.uuid4(),
            vehicle_id=vehicle.id,
            address_id=test_locations['manhattan'].id,
            earliest_available_time=datetime.now(),
            customer_type=CustomerType.RESIDENTIAL,
            address=test_locations['manhattan'],
            vehicle=vehicle,
            services=[]
        )
        for i in range(1, 4)  # Create orders 1, 2, 3
    ]

@pytest.fixture
def test_jobs(test_locations, test_orders):
    """Create test jobs at different locations."""
    return [
        Job(
            id=1,
            order_id=1,
            service_id=101,
            address_id=test_locations['manhattan'].id,
            priority=1,
            status=JobStatus.PENDING_REVIEW,
            job_duration=timedelta(hours=1),
            address=test_locations['manhattan'],
            equipment_requirements=[],
            order_ref=test_orders[0]
        ),
        Job(
            id=2,
            order_id=2,
            service_id=102,
            address_id=test_locations['brooklyn'].id,
            priority=2,
            status=JobStatus.PENDING_REVIEW,
            job_duration=timedelta(hours=2),
            address=test_locations['brooklyn'],
            equipment_requirements=[],
            order_ref=test_orders[1]
        ),
        Job(
            id=3,
            order_id=3,
            service_id=103,
            address_id=test_locations['queens'].id,
            priority=1,
            status=JobStatus.PENDING_REVIEW,
            job_duration=timedelta(hours=1),
            address=test_locations['queens'],
            equipment_requirements=[],
            order_ref=test_orders[2]
        )
    ]

@pytest.fixture
def test_units(test_jobs, test_locations):
    """Create test schedulable units."""
    class HashableSchedulableUnit(SchedulableUnit):
        def __eq__(self, other):
            if not isinstance(other, SchedulableUnit):
                return False
            return (self.order_id == other.order_id and
                   self.jobs == other.jobs and
                   self.priority == other.priority and
                   self.location == other.location and
                   self.duration == other.duration)

        def __hash__(self):
            return hash((self.order_id, tuple(self.jobs), self.priority))

    return [
        HashableSchedulableUnit(
            order_id=j.order_id,
            jobs=[j],
            priority=j.priority,
            location=j.address,
            duration=j.job_duration
        )
        for j in test_jobs
    ]

@pytest.fixture
def test_technician(test_locations):
    """Create a test technician with availability."""
    tech = Technician(
        id=1,
        user_id=uuid.uuid4(),
        workload=0,
        home_address=test_locations['manhattan'],
        current_location=test_locations['manhattan']
    )
    
    # Add availability for day 1
    base_date = datetime.today().replace(hour=9, minute=0, second=0, microsecond=0)
    tech.availability[1] = DailyAvailability(
        day_number=1,
        start_time=base_date,
        end_time=base_date.replace(hour=18, minute=30),
        total_duration=timedelta(hours=9, minutes=30)
    )
    
    return tech

# --- Tests for calculate_travel_time ---

def test_calculate_travel_time_same_location(test_locations):
    """Test travel time calculation when start and end are the same location."""
    time = calculate_travel_time(test_locations['manhattan'], test_locations['manhattan'])
    assert time == timedelta(minutes=5)  # Should return minimum travel time

def test_calculate_travel_time_known_distance(test_locations):
    """Test travel time calculation between locations with known distance."""
    # Manhattan to Brooklyn is roughly 5-6 miles as the crow flies
    time = calculate_travel_time(test_locations['manhattan'], test_locations['brooklyn'])
    
    # At 30mph, should take 10-12 minutes plus some buffer
    assert timedelta(minutes=8) <= time <= timedelta(minutes=15)

def test_calculate_travel_time_symmetry(test_locations):
    """Test that travel time is the same in both directions."""
    time_there = calculate_travel_time(test_locations['manhattan'], test_locations['queens'])
    time_back = calculate_travel_time(test_locations['queens'], test_locations['manhattan'])
    assert time_there == time_back

def test_calculate_travel_time_triangle_inequality(test_locations):
    """Test that direct route is never longer than going through intermediate point."""
    direct = calculate_travel_time(test_locations['manhattan'], test_locations['bronx'])
    via_queens = (
        calculate_travel_time(test_locations['manhattan'], test_locations['queens']) +
        calculate_travel_time(test_locations['queens'], test_locations['bronx'])
    )
    assert direct <= via_queens

# --- Tests for optimize_daily_route_and_get_time ---

@pytest.mark.skip(reason="Original implementation replaced by OR-Tools")
def test_optimize_empty_route(test_locations):
    """Test optimization with empty route."""
    sequence, total_time = optimize_daily_route_and_get_time([], test_locations['manhattan'])
    assert sequence == []
    assert total_time == timedelta(0)

@pytest.mark.skip(reason="Original implementation replaced by OR-Tools")
def test_optimize_single_stop(test_units, test_locations):
    """Test optimization with single stop."""
    # This test needs updating for the new return signature if reactivated
    sequence, total_time = optimize_daily_route_and_get_time(
        [test_units[0]], test_locations['manhattan']
    )
    assert len(sequence) == 1
    assert sequence[0] == test_units[0]
    # Total time should be travel + duration
    expected_time = (
        calculate_travel_time(test_locations['manhattan'], test_units[0].location) +
        test_units[0].duration
    )
    assert total_time == expected_time

@pytest.mark.skip(reason="Original implementation replaced by OR-Tools")
def test_optimize_small_route(test_units, test_locations):
    """Test optimization with small route (should use brute force)."""
    sequence, total_time = optimize_daily_route_and_get_time(
        test_units[:2], test_locations['manhattan']
    )
    assert len(sequence) == 2
    assert set(sequence) == set(test_units[:2])
    # Verify it's actually optimized
    reverse_sequence, reverse_time = optimize_daily_route_and_get_time(
        list(reversed(test_units[:2])), test_locations['manhattan']
    )
    assert total_time <= reverse_time

@pytest.mark.skip(reason="Original implementation replaced by OR-Tools")
def test_optimize_large_route(test_units, test_locations):
    """Test optimization with large route (should use nearest neighbor)."""
    # Create more units to force nearest neighbor algorithm
    many_units = test_units * 3  # 9 units total
    sequence, total_time = optimize_daily_route_and_get_time(
        many_units, test_locations['manhattan']
    )
    assert len(sequence) == len(many_units)
    assert set(sequence) == set(many_units)
    # Verify each step follows nearest neighbor
    current_loc = test_locations['manhattan']
    for unit in sequence:
        # Should be the closest among remaining
        remaining = set(many_units) - set(sequence[:sequence.index(unit)])
        nearest = min(remaining, key=lambda u: 
            calculate_travel_time(current_loc, u.location))
        assert unit == nearest
        current_loc = unit.location

# --- Tests for update_etas_for_schedule ---

def test_update_etas_empty_schedule(test_technician):
    """Test ETA updates with empty schedule."""
    # Arrange - ensure schedule is empty
    test_technician.schedule = {}
    # Act
    update_etas_for_schedule(test_technician)
    # Assert - Function should run without error, no jobs to check ETA on
    assert True # Pass if no exceptions

def test_update_etas_single_day(test_technician, test_units):
    """Test ETA updates for a single day schedule."""
    # Add units to day 1
    unit1, unit2 = test_units[:2]
    test_technician.schedule[1] = [unit1, unit2]
    
    # Act
    update_etas_for_schedule(test_technician)
    
    # Assert - check job ETAs directly
    job1_eta = unit1.jobs[0].estimated_sched
    job2_eta = unit2.jobs[0].estimated_sched
    assert job1_eta is not None
    assert job2_eta is not None
    # Verify chronological order
    assert job1_eta < job2_eta 
    # Verify within availability window
    avail = test_technician.availability[1]
    assert avail.start_time <= job1_eta <= avail.end_time
    assert avail.start_time <= job2_eta <= avail.end_time 

def test_update_etas_respects_availability(test_technician, test_units):
    """Test that ETA updates respect daily availability windows."""
    # Add more units than can fit in a day
    many_units = test_units * 4  # 12 hours of work
    test_technician.schedule[1] = many_units
    
    # Act
    update_etas_for_schedule(test_technician)
    
    avail = test_technician.availability[1]
    # Assert - jobs that could be scheduled should have ETAs within the window
    # The fallback logic now clears ETAs for overflowed jobs
    for unit in test_technician.schedule[1]:
        for job in unit.jobs:
            if job.estimated_sched is not None:
                assert avail.start_time <= job.estimated_sched <= avail.end_time

def test_update_etas_no_availability(test_technician, test_units):
    """Test ETA updates when availability is missing."""
    # Remove availability
    test_technician.availability.clear()
    unit1 = test_units[0]
    test_technician.schedule[1] = [unit1]
    job1 = unit1.jobs[0]
    job1.estimated_sched = datetime.now() # Give it a dummy value first
    
    # Act
    update_etas_for_schedule(test_technician)
    
    # Assert - ETA should not be calculated (or potentially cleared)
    # The fallback now skips the day, so existing ETA might remain or be None.
    # Let's assert it doesn't raise an error and doesn't have a *new* value if it was None.
    assert job1.estimated_sched is not None # Check it didn't get set to None if it had a value
    # A more robust check depends on desired behavior for missing availability

def test_update_etas_sequential_jobs(test_technician, test_units):
    """Test that jobs within a unit are scheduled sequentially."""
    # Create a unit with multiple jobs
    unit1, unit2 = test_units[:2]
    multi_job_unit = SchedulableUnit(
        order_id=99,
        jobs=unit1.jobs + unit2.jobs,
        priority=1,
        location=unit1.location,
        duration=unit1.duration + unit2.duration
    )
    test_technician.schedule[1] = [multi_job_unit]
    
    # Act
    update_etas_for_schedule(test_technician)
    
    # Assert - Verify jobs are sequential by checking estimated_sched
    job_etas = [job.estimated_sched for job in multi_job_unit.jobs]
    assert all(eta is not None for eta in job_etas) # Ensure all got set
    assert all(job_etas[i] + multi_job_unit.jobs[i].job_duration == job_etas[i+1]
              for i in range(len(job_etas)-1))

# --- New tests for optimize_daily_route_and_get_time ---

TECH_HOME = Address(id=1, street_address="Tech Base", lat=40.0, lng=-75.0)
LOC_A = Address(id=10, street_address="1 First St", lat=40.1, lng=-75.1)
LOC_B = Address(id=11, street_address="2 Second St", lat=40.2, lng=-75.2)
LOC_C = Address(id=12, street_address="3 Third St", lat=40.3, lng=-75.3)

DAY_START = datetime(2024, 1, 1, 8, 0, 0) # 8 AM

# Helper to create basic units
def create_unit(id: str, location: Address, duration_minutes: int, fixed_time: Optional[datetime] = None) -> SchedulableUnit:
    # Create minimal Job and Order stubs needed for SchedulableUnit
    dummy_service = Service(id=1, service_name="Test Svc", service_category=ServiceCategory.DIAG)
    dummy_vehicle = CustomerVehicle(id=1, vin="TESTVIN1234567890", make="Make", year=2024, model="Model")
    dummy_user_id = uuid.uuid4() # Generate a dummy UUID
    dummy_order = Order(
        id=int(id.split('_')[1]), user_id=dummy_user_id, vehicle_id=1, address_id=location.id, 
        earliest_available_time=DAY_START, customer_type=CustomerType.RESIDENTIAL,
        address=location, vehicle=dummy_vehicle, services=[dummy_service]
    )
    job = Job(
        id=int(id.split('_')[1]), 
        order_id=dummy_order.id, 
        service_id=dummy_service.id,
        address_id=location.id, 
        priority=5,
        status=JobStatus.ASSIGNED, 
        job_duration=timedelta(minutes=duration_minutes),
        fixed_schedule_time=fixed_time, 
        order_ref=dummy_order, 
        address=location, 
        services=[dummy_service]
    )
    return SchedulableUnit(
        id=id,
        order_id=job.order_id,
        jobs=[job],
        priority=job.priority,
        location=location,
        duration=job.job_duration,
        fixed_schedule_time=fixed_time
    )

UNIT_A = create_unit("unit_101", LOC_A, 60) # 1 hour
UNIT_B = create_unit("unit_102", LOC_B, 90) # 1.5 hours
UNIT_C = create_unit("unit_103", LOC_C, 30) # 0.5 hours
UNIT_FIXED = create_unit("unit_104", LOC_B, 60, fixed_time=DAY_START + timedelta(hours=4)) # Fixed at 12 PM

# --- Mocks --- 

# Mock calculate_travel_time for deterministic results
@pytest.fixture
def mock_travel_time():
    def mock_calc(loc1, loc2):
        if loc1 == loc2: return timedelta(minutes=0) # Should be handled by OR-Tools cost matrix anyway
        # Simple mock: 30 mins between any different locations for simplicity
        return timedelta(minutes=30) 
    with patch('scheduler.routing.calculate_travel_time', side_effect=mock_calc) as mock:
        yield mock

# Mock availability
@pytest.fixture
def mock_availability():
    def mock_get_avail(tech, day):
        if day == 1:
            # Use a Pydantic model or a compatible dict for availability
            # Assuming DailyAvailability model exists and is appropriate
            from scheduler.models import DailyAvailability # Import locally if needed
            return DailyAvailability(
                day_number=day,
                start_time=DAY_START, 
                end_time=DAY_START + timedelta(hours=9), 
                total_duration=timedelta(hours=9)
            )
            # Alternative if returning dict:
            # return {'start_time': DAY_START, 'end_time': DAY_START + timedelta(hours=9), 'total_duration': timedelta(hours=9)} 
        return None
    # Patch the availability function in the *routing* module where it's used by the fallback
    with patch('scheduler.routing.get_technician_availability', side_effect=mock_get_avail) as mock:
        yield mock

# --- Tests for optimize_daily_route_and_get_time --- 

@patch('scheduler.routing.pywrapcp.RoutingModel') # Patch the Model class
@patch('scheduler.routing.pywrapcp.RoutingModel.SolveWithParameters') # Keep patch for Solve
def test_optimize_basic_route(mock_solve, mock_routing_model_cls, mock_travel_time):
    """Test basic optimization without fixed constraints."""
    # Arrange
    # Mock the RoutingModel instance that the code creates
    mock_routing = MagicMock()
    mock_routing_model_cls.return_value = mock_routing # routing = pywrapcp.RoutingModel(manager)

    # Mock IsEnd to control the loop termination
    # Sequence 0 -> 1 -> 3 -> 2 -> 0(end). Loop runs for index 0, 1, 3, 2. 
    # IsEnd(0)=F, IsEnd(1)=F, IsEnd(3)=F, IsEnd(2)=F, IsEnd(0)=T
    mock_routing.IsEnd.side_effect = [False, False, False, False, True]
    # Mock Start to return the starting index 0
    mock_routing.Start.return_value = 0 
    # Mock NextVar to just return the index, so solution.Value gets called with 0, 1, 3, 2
    mock_routing.NextVar.side_effect = lambda index: index 

    # Mock GetDimensionOrDie to return a mock dimension
    mock_time_dimension = MagicMock()
    mock_routing.GetDimensionOrDie.return_value = mock_time_dimension
    
    # Mock the CumulVar method on the time dimension mock
    # It should return a mock variable that has an Index() method
    def cumul_var_side_effect(index):
        mock_var = MagicMock()
        # Need to get the node index from the OR-Tools internal index
        # We need the manager for this, but we aren't mocking it anymore.
        # Assume the index passed *is* the node index for testing.
        # Let's refine this - maybe mock NodeToIndex on the manager?
        # For now, assume index directly corresponds to node 0, 1, 2, 3
        mock_var.Index.return_value = index # HACK: Assumes index == node_index
        return mock_var
    mock_time_dimension.CumulVar.side_effect = cumul_var_side_effect

    mock_solution = MagicMock()
    mock_solution.Value.side_effect = [1, 3, 2, 0]

    # Mock solution.Min using the mock variable structure
    def min_side_effect(cumul_var_mock):
        node_index = cumul_var_mock.Index() # Use the Index() method we mocked
        if node_index == 1: return 1800
        if node_index == 3: return 7200
        if node_index == 2: return 10800
        return 0
    mock_solution.Min.side_effect = min_side_effect
    
    mock_routing.SolveWithParameters.return_value = mock_solution

    units_to_schedule = [UNIT_A, UNIT_B, UNIT_C]
    
    # Act
    optimized_sequence, total_time, start_times = optimize_daily_route_and_get_time(
        units_to_schedule, TECH_HOME, day_start_time=DAY_START
    )
    
    # Assert
    # Verify CumulVar was called for expected nodes
    assert mock_time_dimension.CumulVar.call_count >= 3 # Called for nodes 1, 3, 2 and maybe end node 0
    assert len(optimized_sequence) == 3
    # Check sequence based on mocked solution A -> C -> B
    assert optimized_sequence[0].id == "unit_101"
    assert optimized_sequence[1].id == "unit_103"
    assert optimized_sequence[2].id == "unit_102"
    # Check total time (seconds)
    expected_total_seconds = 10800 + 5400 # Arrival at B + Service B 
    assert total_time == timedelta(seconds=expected_total_seconds)
    # Check start times
    assert start_times["unit_101"] == DAY_START + timedelta(seconds=1800) # Arrive A
    assert start_times["unit_103"] == DAY_START + timedelta(seconds=7200) # Arrive C
    assert start_times["unit_102"] == DAY_START + timedelta(seconds=10800) # Arrive B

@patch('scheduler.routing.pywrapcp.RoutingModel') # Patch the Model class
@patch('scheduler.routing.pywrapcp.RoutingModel.SolveWithParameters') # Keep patch for Solve
def test_optimize_with_fixed_time(mock_solve, mock_routing_model_cls, mock_travel_time):
    """Test optimization respects fixed time constraints."""
    # Arrange
    mock_routing = MagicMock()
    mock_routing_model_cls.return_value = mock_routing

    # Mock IsEnd: Sequence 0 -> 1 -> 2 -> 0(end). Loop runs for index 0, 1, 2.
    # IsEnd(0)=F, IsEnd(1)=F, IsEnd(2)=F, IsEnd(0)=T
    mock_routing.IsEnd.side_effect = [False, False, False, True]
    mock_routing.Start.return_value = 0
    mock_routing.NextVar.side_effect = lambda index: index

    # Mock GetDimensionOrDie and CumulVar
    mock_time_dimension = MagicMock()
    mock_routing.GetDimensionOrDie.return_value = mock_time_dimension
    def cumul_var_fixed_side_effect(index):
        mock_var = MagicMock()
        mock_var.Index.return_value = index # HACK: Assumes index == node_index
        return mock_var
    mock_time_dimension.CumulVar.side_effect = cumul_var_fixed_side_effect

    mock_solution = MagicMock()
    mock_solution.Value.side_effect = [1, 2, 0]
    
    # Mock solution.Min using the mock variable structure
    def min_fixed_side_effect(cumul_var_mock):
        node_index = cumul_var_mock.Index()
        if node_index == 1: return 1800
        if node_index == 2: return 14400
        return 0
    mock_solution.Min.side_effect = min_fixed_side_effect
    
    mock_routing.SolveWithParameters.return_value = mock_solution

    units_to_schedule = [UNIT_A, UNIT_FIXED]
    time_constraints = {UNIT_FIXED.id: UNIT_FIXED.fixed_schedule_time}
    
    # Act
    optimized_sequence, total_time, start_times = optimize_daily_route_and_get_time(
        units_to_schedule, TECH_HOME, time_constraints=time_constraints, day_start_time=DAY_START
    )
    
    # Assert
    mock_routing.SolveWithParameters.assert_called_once()
    assert len(optimized_sequence) == 2
    assert optimized_sequence[0].id == "unit_101"
    assert optimized_sequence[1].id == "unit_104"
    # Check start times
    assert start_times["unit_101"] == DAY_START + timedelta(seconds=1800)
    assert start_times["unit_104"] == DAY_START + timedelta(seconds=14400) # Should match fixed time

@patch('scheduler.routing.pywrapcp.RoutingModel') # Patch the Model class
@patch('scheduler.routing.pywrapcp.RoutingModel.SolveWithParameters') # Keep patch for Solve
def test_optimize_no_solution(mock_solve, mock_routing_model_cls, mock_travel_time):
    """Test case where OR-Tools returns no solution."""
    # Arrange
    mock_routing = MagicMock()
    mock_routing_model_cls.return_value = mock_routing
    mock_routing.SolveWithParameters.return_value = None # Simulate solver failure
    
    units_to_schedule = [UNIT_A]
    
    # Act
    optimized_sequence, total_time, start_times = optimize_daily_route_and_get_time(
        units_to_schedule, TECH_HOME, day_start_time=DAY_START
    )
    
    # Assert
    # No need to check sequence/time if solve returns None
    mock_routing.SolveWithParameters.assert_called_once()
    assert optimized_sequence == []
    assert total_time == timedelta(0)
    assert start_times == {}

# --- Tests for update_etas_for_schedule --- 

def test_update_etas_with_start_times():
    """Test updating ETAs using the provided start times dict."""
    # Arrange
    tech = Technician(id=1, user_id=uuid.uuid4(), home_address=TECH_HOME)
    unit1 = create_unit("unit_101", LOC_A, 60)
    unit2 = create_unit("unit_102", LOC_B, 90)
    tech.schedule = {1: [unit1, unit2]} # Day 1 schedule
    
    # Pre-calculated start times (e.g., from optimizer)
    start_times_day1 = {
        "unit_101": DAY_START + timedelta(hours=1), # 9 AM
        "unit_102": DAY_START + timedelta(hours=3)  # 11 AM
    }
    daily_start_times = {1: start_times_day1}

    # Act
    update_etas_for_schedule(tech, daily_start_times)

    # Assert
    assert unit1.jobs[0].estimated_sched == DAY_START + timedelta(hours=1)
    assert unit2.jobs[0].estimated_sched == DAY_START + timedelta(hours=3)

def test_update_etas_fallback_calculation(mock_travel_time, mock_availability):
    """Test updating ETAs using the fallback manual calculation."""
    # Arrange
    tech = Technician(id=1, user_id=uuid.uuid4(), home_address=TECH_HOME, current_location=TECH_HOME)
    unit1 = create_unit("unit_101", LOC_A, 60) # 1 hr service
    unit2 = create_unit("unit_102", LOC_B, 90) # 1.5 hr service
    tech.schedule = {1: [unit1, unit2]} # Day 1 schedule
    
    # Expected fallback calculation (mock travel = 30 mins):
    # Start 8:00
    # Travel to A = 30 mins. Arrive A = 8:30. 
    # Service A = 60 mins. Finish A = 9:30.
    # Travel A->B = 30 mins. Arrive B = 10:00.
    # Service B = 90 mins. Finish B = 11:30.

    # Act
    update_etas_for_schedule(tech, None) # No start times provided, trigger fallback

    # Assert
    mock_availability.assert_called_once_with(tech, 1)
    assert mock_travel_time.call_count == 2
    assert unit1.jobs[0].estimated_sched == DAY_START + timedelta(minutes=30) # Arrive A 8:30
    assert unit2.jobs[0].estimated_sched == DAY_START + timedelta(minutes=120) # Arrive B 10:00

def test_update_etas_fallback_with_fixed_time(mock_travel_time, mock_availability):
    """Test fallback ETA calculation respects fixed times."""
    # Arrange
    tech = Technician(id=1, user_id=uuid.uuid4(), home_address=TECH_HOME, current_location=TECH_HOME)
    fixed_start = DAY_START + timedelta(hours=2) # Fixed at 10:00 AM
    unit_fixed = create_unit("unit_104", LOC_A, 60, fixed_time=fixed_start)
    unit_after = create_unit("unit_105", LOC_B, 30)
    tech.schedule = {1: [unit_fixed, unit_after]} # Fixed job first

    # Expected fallback:
    # Start 8:00
    # Travel to A = 30 mins. Earliest arrival = 8:30.
    # Fixed time is 10:00. Wait until 10:00.
    # Service Fixed = 60 mins. Finish Fixed = 11:00.
    # Travel A->B = 30 mins. Arrive B = 11:30.
    # Service After = 30 mins. Finish After = 12:00.

    # Act
    update_etas_for_schedule(tech, None)

    # Assert
    assert unit_fixed.jobs[0].estimated_sched == fixed_start # ETA matches fixed time
    assert unit_after.jobs[0].estimated_sched == fixed_start + timedelta(minutes=60) + timedelta(minutes=30) # 11:30 