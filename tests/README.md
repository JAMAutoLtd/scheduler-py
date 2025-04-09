# Project Tests

This directory contains unit tests for the scheduler application, mirroring the structure of the `src/` directory.

## Test Setup

Tests are run using Jest (`npm test`), configured via `jest.config.js`. The configuration uses `ts-jest` to handle TypeScript files.

## Current Tests

### Supabase Data Fetching (`tests/supabase/`)

These tests verify the functions responsible for fetching data from the Supabase database. The Supabase client (`@supabase/supabase-js`) is mocked using `jest.mock` to isolate the functions under test from the actual database.

*   **`jobs.test.ts`**: Tests `src/supabase/jobs.ts`
    *   Covers `getRelevantJobs`:
        *   Fetching jobs with relevant statuses (`queued`, `en_route`, `in_progress`, `fixed_time`).
        *   Handling cases where no relevant jobs are found.
        *   Handling errors returned by the Supabase client.
        *   Verifies correct data mapping from raw Supabase response to `Job` interface.
*   **`technicians.test.ts`**: Tests `src/supabase/technicians.ts`
    *   Covers `getActiveTechnicians`:
        *   Fetching technicians with joined user and van details.
        *   Correctly deriving `current_location` from van coordinates.
        *   Handling cases where van location is missing.
        *   Handling cases where no technicians are found.
        *   Handling errors returned by the Supabase client.
*   **`equipment.test.ts`**: Tests `src/supabase/equipment.ts`
    *   Covers `getEquipmentForVans`:
        *   Fetching equipment for multiple specified van IDs.
        *   Correctly grouping fetched equipment into a `Map<vanId, VanEquipment[]>`.
        *   Handling cases where no van IDs are provided.
        *   Handling cases where no equipment is found for given vans.
        *   Handling errors returned by the Supabase client.
    *   Covers `getRequiredEquipmentForJob`:
        *   Mocking the `getYmmIdForOrder` dependency.
        *   Querying the correct equipment requirement table based on job service category.
        *   Returning the correct equipment model(s).
        *   Handling cases where multiple models are required.
        *   Handling edge cases: job missing service category, job missing order ID, unable to determine `ymm_id`.
        *   Handling cases where no requirement is found in the DB.
        *   Handling errors returned by the Supabase client during requirement fetch (logs warning, returns empty array).
*   **`orders.test.ts`**: Tests `src/supabase/orders.ts`
    *   Covers `getYmmIdForOrder`:
        *   Fetching the `ymm_id` using nested Supabase joins (`orders` -> `customer_vehicles` -> `ymm_ref`).
        *   Returning the correct `ymm_id`.
        *   Handling cases where the order is not found.
        *   Handling cases where nested data (`customer_vehicles`, `ymm_ref`, `ymm_id`) is missing/null.
        *   Handling errors returned by the Supabase client.

### Google Maps (`tests/google/`)

*   **`maps.test.ts`**: Tests `src/google/maps.ts`
    *   Covers `getTravelTime`:
        *   Mocking the `@googlemaps/google-maps-services-js` client.
        *   Mocking `process.env.GOOGLE_MAPS_API_KEY`.
        *   Using `jest.useFakeTimers` and `jest.resetModules` to test cache functionality.
        *   Fetching time from API on cache miss.
        *   Returning cached time on cache hit.
        *   Fetching from API again after cache TTL expiry.
        *   Handling API errors (network, request denied, zero results) by returning `null`.

### Scheduler Logic (`tests/scheduler/`)

These tests cover the core scheduling workflow steps.

*   **`bundling.test.ts`**: Tests `src/scheduler/bundling.ts`
    *   Covers `bundleQueuedJobs`:
        *   Handling empty input.
        *   Creating `SchedulableJob` items for single-job orders.
        *   Creating `JobBundle` items for multi-job orders.
        *   Correctly calculating bundle `total_duration` and `priority` (max of jobs).
        *   Handling a mix of single jobs and bundles.
        *   Gracefully handling jobs missing the joined `address` data.
*   **`eligibility.test.ts`**: Tests `src/scheduler/eligibility.ts`
    *   Covers `determineTechnicianEligibility`:
        *   Mocking `getEquipmentForVans` and `getRequiredEquipmentForJob` from `src/supabase/equipment.ts`.
        *   Handling empty input items.
        *   Processing single jobs with no required equipment (all techs eligible).
        *   Processing single jobs with requirements met by one, multiple, or no technicians.
        *   Processing bundles where a technician is eligible for all jobs.
        *   Breaking bundles into individual `SchedulableJob` items when no single tech is eligible for the whole bundle, and calculating eligibility for the individual jobs.
        *   Handling technicians without assigned vans.
        *   Testing a mix of single jobs and bundles (including one broken bundle).
*   **`payload.test.ts`**: Tests `src/scheduler/payload.ts`
    *   Covers `prepareOptimizationPayload`:
        *   Mocking `getTravelTime` from `src/google/maps.ts`.
        *   Defining unique locations (depot, tech starts, item addresses) and assigning correct indices.
        *   Skipping items with missing address coordinates.
        *   Calculating the travel time matrix using the mocked `getTravelTime`.
        *   Handling `getTravelTime` errors by using a penalty value.
        *   Formatting `OptimizationTechnician` data correctly (start/end locations, time windows).
        *   Formatting `OptimizationItem` data correctly (location index, duration in seconds, priority, eligible techs).
        *   Formatting `OptimizationFixedConstraint` correctly for relevant fixed-time jobs.
        *   Skipping fixed constraints for jobs not in the main item list or missing a `fixed_schedule_time`.
*   **`optimize.test.ts`**: Tests `src/scheduler/optimize.ts`
    *   Covers `callOptimizationService`:
        *   Mocking `axios.post`.
        *   Mocking `process.env.OPTIMIZATION_SERVICE_URL`.
        *   Verifying correct call signature (URL, payload, headers, timeout).
        *   Handling successful responses (`status: 'success'` and `status: 'partial'`).
        *   Throwing an error if the service returns `status: 'error' `.
        *   Throwing specific errors for Axios HTTP errors (e.g., 404, 500, timeout).
        *   Throwing a generic error for other network issues.
*   **`results.test.ts`**: Tests `src/scheduler/results.ts`
    *   Covers `processOptimizationResults`:
        *   Throwing an error if input response status is `'error' `.
        *   Handling empty routes and unassigned items.
        *   Correctly extracting `ScheduledJobUpdate` data (jobId, techId, estimatedSchedISO) from job stops (`itemId` starting with `job_`).
        *   Ignoring bundle stops (`itemId` starting with `bundle_`).
        *   Passing through `unassignedItemIds` correctly (handling undefined).
        *   Skipping stops with invalid job IDs or invalid date strings.
        *   Handling routes with no stops.

### Database Update (`tests/db/`)

*   **`update.test.ts`**: Tests `src/db/update.ts`
    *   Covers `updateJobStatuses`:
        *   Mocking the Supabase client (`from`, `update`, `eq`).
        *   Throwing error if input optimization response status is `'error' `.
        *   Handling no updates needed (empty routes/unassigned).
        *   Correctly preparing update payloads for scheduled jobs (`status: 'scheduled'`, `assigned_technician`, `estimated_sched`).
        *   Correctly preparing update payloads for unassigned jobs (`status: 'pending_review'`, `assigned_technician: null`, `estimated_sched: null`).
        *   Handling a mix of scheduled and overflow updates.
        *   Ignoring item IDs that are bundles or have invalid formats.
        *   Executing updates via `Promise.all`.
        *   Throwing a summary error if any mocked DB update returns an error, while ensuring all updates were attempted. 