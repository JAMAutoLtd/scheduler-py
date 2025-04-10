# CHANGELOG

## {Current Date} - Python Optimization Service Debugging

### Fixed
- **Arrival Time Calculation (`optimize-service/main.py`):** Corrected the calculation of `arrivalTimeISO` for the first stop in a route when a subsequent stop has a fixed time constraint. 
    - **Problem:** The physical arrival time (departure from previous + travel) was being reported incorrectly as the *scheduled* start time (dictated by the fixed constraint) in these specific scenarios.
    - **Troubleshooting:** Initial attempts to use `time_dimension.SlackVar` to derive physical arrival from scheduled start caused C++ crashes (`Windows fatal exception: access violation`). Analysis revealed that `assignment.Value(time_dimension.CumulVar(start_node_index))` seemed to return a value influenced by downstream fixed constraints, leading to an incorrect departure time calculation for the *first* segment.
    - **Solution:** Modified the loop processing the assignment to treat the first segment uniquely. Departure time for the first segment is now calculated based on the technician's `earliestStartTimeISO`. Subsequent segments correctly calculate departure based on the previous stop's completion (`CumulVar(previous) + ServiceTime(previous)`).
    - **Result:** This ensures `arrivalTimeISO` accurately reflects the physical arrival time, while `startTimeISO` reflects the potentially later scheduled start time due to constraints.
- **OR-Tools Time Handling (`optimize-service/main.py`):** Resolved `CP Solver fail` exceptions by refactoring the `optimize_schedule` function to use relative time:
    - Calculated a `planning_epoch_seconds` based on the earliest technician start time.
    - Converted absolute Unix timestamps (technician windows, fixed constraints) to seconds relative to the `planning_epoch_seconds` before passing them to OR-Tools `TimeDimension.SetRange`.
    - Adjusted the `TimeDimension` horizon calculation to be relative.
    - Converted relative times from the solver results back to absolute Unix timestamps before generating output ISO strings.
- **OR-Tools `AddDimensionWithVehicleCapacity` (`optimize-service/main.py`):** Fixed a `TypeError: 'int' object is not iterable` by providing the calculated time horizon as a list (`[horizon_with_buffer] * num_vehicles`) instead of a single integer.

### Changed
- **Time Conversion Utilities (`optimize-service/main.py`):** Made minor robustness improvements to `iso_to_seconds` (handling 'Z' suffix more explicitly) and `seconds_to_iso` (using `strftime` to output 'Z' suffix for UTC).

### Discovered / To Do
- [ ] **Investigate Remaining Test Failures (`tests/test_main.py`):**
    - `test_iso_to_seconds_conversion` and `test_seconds_to_iso_conversion` still fail with a one-hour discrepancy. This might be related to timezone handling differences between the test environment and the function logic, or issues in the test assertions themselves.
    - `test_optimize_schedule_final_travel_leg` fails on asserting `arrivalTimeISO`. The expected value (`1970-01-01T08:00:00Z`) appears incorrect, potentially using a relative time value instead of the expected absolute Unix timestamp. Needs test logic review.

## {Previous Date - e.g., 2024-07-29}

### Added
- **Testing:** Completed implementation of all placeholder unit tests in `tests/scheduler/orchestrator.test.ts`, covering various scenarios like multi-day overflow, weekend skips, bundling, and error handling for the refactored `runFullReplan`.
- **Testing:** Implemented test cases for `orchestrator.test.ts`: Happy Path (Today Only), Partial Schedule (Today Only), and Single Day Overflow (Scheduled Day 2).
- **Multi-Day Overflow:**
  - Added `home_location` field to `Technician` type (`src/types/database.types.ts`).
  - Added `TechnicianAvailability` interface (`src/types/database.types.ts`).
  - Added `getJobsByStatus` function to fetch jobs by specific statuses (`src/supabase/jobs.ts`).

### Changed
- **Refactored Orchestration (`src/scheduler/orchestrator.ts`):** Verified that the refactoring of `runFullReplan` (using internal state and a single final DB update) is complete and matches the planned approach.
- **Simplified Job Statuses:** The final database update now only uses `queued` (for successfully scheduled jobs with assigned tech/time) or `pending_review` (for jobs that could not be scheduled within the multi-day window). Statuses `overflow`, `scheduled_future`, `unschedulable_overflow` are no longer written by this process.
- **Simplified Availability Logic (`src/scheduler/availability.ts`):** Removed explicit holiday checking logic. Non-working days (including holidays) are expected to be reflected in the upstream technician availability data (e.g., database or external system) rather than being handled specifically within the scheduler's `calculateAvailabilityForDay` function.
- **Documentation:** Updated `README.md`, `PLANNING.md`, `OVERVIEW.md`, and `TASK.md` to reflect the refactored orchestration logic and simplified status management.

### Fixed
- **Testing:** Fixed linter errors in `tests/scheduler/orchestrator.test.ts` related to `JobBundle` type usage in mocks.
- **Testing:** Corrected assertions and mock logic in `tests/scheduler/orchestrator.test.ts` based on detailed execution flow analysis, ensuring all tests pass.

### Removed
- N/A

## [Unreleased]

### Added
- Start implementation of multi-day overflow scheduling:
  - Added `calculateAvailabilityForDay` function in `src/scheduler/availability.ts` to determine technician availability for future dates based on home locations and working hours.
  - Modified `prepareOptimizationPayload` (`src/scheduler/payload.ts`) to accept and use future availability data.
  - Implemented multi-day overflow loop logic in `runFullReplan` (`src/scheduler/orchestrator.ts`):
    - Handles initial planning for today, marking unassigned jobs as 'overflow'.
    - Iteratively attempts to schedule 'overflow' jobs on subsequent days (up to `MAX_OVERFLOW_ATTEMPTS`).
    - Fetches data (techs w/ home locations, overflow jobs), calculates future availability, bundles, checks eligibility, prepares payload, calls optimizer for each future day.
    - Updates job statuses to 'scheduled_future' or keeps 'overflow' based on loop results.
    - Marks remaining overflow jobs as 'unschedulable_overflow' after loop.
    - Added helper `mapItemsToJobIds` to correctly handle job/bundle IDs during result processing.

### Fixed
- N/A

### Changed
- **Time Handling:** Refactored `src/scheduler/availability.ts` and `src/scheduler/payload.ts` to use UTC date/time methods (`getUTCDay`, `setUTCHours`, etc.) for internal calculations, ensuring consistency with the project's UTC standard.

### Discovered / To Do
- **Inconsistent Time Handling:** Identified that several modules (`availability`, `payload`) use local timezone methods (`.getDay()`, `.setHours()`) for date/time calculations, while the standard format for data exchange and storage is ISO 8601 UTC. This causes inconsistencies and test failures. (Completed)
- [ ] **Integration Testing:** Consider adding integration tests (e.g., using `msw` or `nock`) for `callOptimizationService` to verify the end-to-end handling of real Axios HTTP errors/timeouts, complementing the current unit tests which focus on internal logic branches. - {Current Date}
