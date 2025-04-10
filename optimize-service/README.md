# Optimize Service

## Overview

This service provides a job scheduling optimization API endpoint. It receives a description of locations, technicians (with their availability and start/end locations), items (jobs with locations, durations, priority, and technician eligibility), fixed time constraints, and a travel time matrix between locations. 

Using Google OR-Tools, it solves the underlying Vehicle Routing Problem (VRP) with Time Windows and constraints to produce optimized routes for each technician, minimizing travel time and respecting constraints while prioritizing jobs.

The primary goal is to determine the best sequence of jobs for each technician to minimize costs (like travel time) and maximize the number of completed jobs within the given constraints.

## Main Endpoint

*   **`POST /optimize-schedule`**: 
    *   Accepts an `OptimizationRequestPayload` JSON body.
    *   Returns an `OptimizationResponsePayload` JSON body containing the status (`success`, `partial`, `error`), a message, a list of optimized `TechnicianRoute` objects (each with a list of `RouteStop`), and a list of `unassignedItemIds`.

## Running Locally

1.  **Install Dependencies**: 
    ```bash
    pip install -r requirements.txt 
    ```
2.  **Run the FastAPI Server**:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The service will be available at `http://127.0.0.1:8000`, and interactive API documentation (Swagger UI) can be accessed at `http://127.0.0.1:8000/docs`.

## Testing

Unit tests are implemented using `pytest` and cover various scenarios to ensure the optimization logic behaves as expected.

**Run Tests**:
Navigate to the `optimize-service` directory in your terminal and run:
```bash
pytest
```

**Test Coverage Includes:**

*   **Helper Functions**: Correct conversion between ISO 8601 time strings and seconds (`iso_to_seconds`, `seconds_to_iso`).
*   **Basic Cases**: 
    *   Handling requests with no items to schedule.
    *   Handling requests with no technicians available.
*   **Successful Scheduling**:
    *   Simple routes with a single stop.
    *   Routes involving travel between multiple stops (2 and 3+ stops tested).
    *   Correct assignment when multiple technicians are available but one is time-constrained.
*   **Constraints**:
    *   Applying fixed time constraints for specific items.
*   **Unassigned Items**:
    *   Items unassigned due to tight technician time windows.
    *   Items unassigned because no eligible technician is available.
    *   Items unassigned due to missing entries in the travel time matrix.
*   **Priority**: Verifying that higher-priority items are scheduled when time/resources are limited.
*   **Route Calculation**:
    *   Correct calculation of arrival, start, and end times for each stop.
    *   Correct calculation of `totalTravelTimeSeconds`, including the final leg from the last stop to the technician's designated `endLocationIndex`.
