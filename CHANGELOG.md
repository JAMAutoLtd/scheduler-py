# CHANGELOG

## {Current Date}

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
