# Scheduler Tests (`tests/scheduler/`)

This directory contains unit tests for the core scheduling and routing logic found in `src/scheduler/`.

## Test Files

1. `test_scheduler.py`: Tests for core scheduling logic
2. `test_routing.py`: Tests for routing and ETA calculation utilities

## Purpose

These tests verify the functionality of both the main scheduler components and the routing utilities, ensuring they behave correctly according to the logic defined in `PLANNING.md`, even while using placeholder implementations for external dependencies.

## Structure

### Routing Tests (`test_routing.py`)

Tests for routing-specific utilities with realistic geographic data:

- **Test Data:**
    - Uses real NYC area coordinates for realistic distance calculations
    - Includes mock instances of `Address`, `Job`, `SchedulableUnit`, and `Technician`
    - Provides fixtures for locations, jobs, units, and technicians with availability

- **Test Coverage:**
    1. **`calculate_travel_time`**:
        - Same location travel (minimum time)
        - Known distance calculation using real coordinates
        - Travel time symmetry (A→B = B→A)
        - Triangle inequality verification
    
    2. **`optimize_daily_route_and_get_time`**:
        - Empty route handling
        - Single stop optimization
        - Small route optimization (brute force)
        - Large route optimization (nearest neighbor)
        - Optimization quality verification
    
    3. **`update_etas_for_schedule`**:
        - Empty schedule handling
        - Single day scheduling
        - Availability window respect
        - Missing availability handling
        - Sequential job scheduling

### Scheduler Tests (`test_scheduler.py`)

Tests for core scheduling logic:

- **Mock Data:**
    - Located at the top of `test_scheduler.py`
    - Defines mock classes and instances
    - Uses pytest fixtures for fresh test data
    
- **Test Cases:**
    - Grouped by function (`test_calculate_eta_*`, `test_assign_jobs_*`, etc.)
    - Each test verifies specific scenarios and edge cases

## Running Tests

To run these tests:

1. Ensure you have `pytest` installed:
   ```bash
   pip install pytest
   ```

2. Run all tests from the project root:
   ```bash
   pytest
   ```

   Or run specific test files:
   ```bash
   pytest tests/scheduler/test_routing.py
   pytest tests/scheduler/test_scheduler.py
   ```

## Test Design Principles

1. **Geographic Realism**: Routing tests use real-world coordinates to ensure distance calculations are realistic and meaningful.

2. **Mathematical Properties**: Travel time calculations are verified against mathematical properties (symmetry, triangle inequality) to ensure consistency.

3. **Algorithm Verification**: Route optimization tests verify both the correctness of the algorithm choice (brute force vs. nearest neighbor) and the quality of the optimization.

4. **Edge Cases**: Each function includes tests for edge cases (empty inputs, missing data) and normal operation.

5. **Time Window Respect**: Schedule-related tests verify that all operations respect technician availability windows and job durations.

## Future Improvements

- Add more edge cases for route optimization with different city layouts
- Test route optimization with traffic patterns when implemented
- Add performance benchmarks for large route optimization
- Test integration with real routing APIs when implemented
- Add tests for multi-day route planning scenarios
- Consider adding property-based tests for route optimization quality
- Add stress tests for large numbers of locations/jobs 