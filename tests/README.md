# Scheduler Testing

This directory contains tests for the scheduler components.

## Modules

*   `test_scheduler.py`: Tests for the main scheduling logic (`assign_jobs`, `update_job_queues_and_routes`).
*   `test_routing.py`: Tests for routing utilities (`optimize_daily_route_and_get_time`, `update_etas_for_schedule`).
*   `test_availability.py`: Tests for availability calculations.
*   `test_utils.py`: Tests for general utility functions.
*   `api/`: Tests for the scheduler API endpoints. See [API README](scheduler/api/README.md) for details.

## Strategy

*   **Unit Tests:** Focus on isolating individual functions and classes.
*   **Mocking:** Uses `pytest` fixtures and `unittest.mock` (`@patch`, `MagicMock`) to mock dependencies like:
    *   Data interface / API calls
    *   `calculate_travel_time` (for deterministic routing tests)
    *   `get_technician_availability`
    *   OR-Tools solver (`pywrapcp`) for routing tests.
*   **Integration Tests:** (Potentially in separate files or marked) to test the interaction between different scheduler components (e.g., how `assign_jobs` calls `calculate_eta` and influences `update_job_queues_and_routes`).
*   **API Tests:** Tests for the API endpoints, verifying authentication, request/response formats, and error handling.

## Running Tests

Use `pytest` from the root directory:

```bash
# Run all tests
pytest tests/

# Run only API tests
pytest tests/scheduler/api/

# Use the run_tests.py script (from project root)
python run_tests.py --api --verbose
```

## Test Environment

A test environment configuration is available in `.env.test`. This can be used to run tests with a separate configuration:

```bash
ENV_FILE=.env.test pytest
```

## Specifics for `test_routing.py`

*   Tests for `optimize_daily_route_and_get_time` mock the OR-Tools solver (`SolveWithParameters`) and index manager to verify:
    *   Correct data preparation for OR-Tools.
    *   Correct handling of time constraints passed to the solver.
    *   Correct parsing of the mocked OR-Tools solution (sequence, total time, start times).
    *   Correct handling of solver failures (no solution).
*   Tests for `update_etas_for_schedule` verify:
    *   Correct calculation using pre-defined start times (simulating output from the optimizer).
    *   Correct fallback calculation when start times are not provided.
    *   Correct handling of fixed schedule times in the fallback calculation. 