LOGICAL OVERVIEW TRACETHROUGH

**1. Starting Point: `src/scheduler/orchestrator.ts` (`runFullReplan`)**

This file orchestrates the main replan process. It imports and calls functions from several modules:

*   **Data Fetching (`src/supabase/`)**:
    *   `technicians.ts`: `getActiveTechnicians` (Gets active technicians and their locations).
    *   `jobs.ts`: `getRelevantJobs` (Gets jobs for today's plan) and `getJobsByStatus` (Gets overflow jobs).
    *   `client.ts`: Provides the Supabase client instance.
*   **Scheduling Logic (`src/scheduler/`)**:
    *   `availability.ts`: `calculateTechnicianAvailability` (For today) and `calculateAvailabilityForDay` (For future overflow days).
    *   `bundling.ts`: `bundleQueuedJobs`.
    *   `eligibility.ts`: `determineTechnicianEligibility`.
    *   `payload.ts`: `prepareOptimizationPayload`.
    *   `optimize.ts`: `callOptimizationService`.
    *   `results.ts`: `processOptimizationResults`.
*   **Database Update (`src/db/`)**:
    *   `update.ts`: `updateJobs`.
*   **Types (`src/types/`)**: Imports various type definitions (`database.types.ts`).



**2. Tracing Dependencies:**

*   **`src/supabase/client.ts`**:
    *   Imports: `@supabase/supabase-js` (external library), `process.env` (Node.js standard).
    *   Purpose: Initializes and exports the Supabase client using environment variables.

*   **`src/supabase/technicians.ts` (`getActiveTechnicians`)**:
    *   Imports: `supabase` (from `client.ts`), `Technician`, `Address`, `User` (types).
    *   Purpose: Queries Supabase `technicians` table, joining `users`, `van_assignments`, `vans`, and `addresses` to get technician details, current van location, and home address coordinates.

*   **`src/supabase/jobs.ts` (`getRelevantJobs`, `getJobsByStatus`)**:
    *   Imports: `supabase` (from `client.ts`), `Job`, `JobStatus`, `Address`, `Service` (types).
    *   Purpose: Queries Supabase `jobs` table, joining `addresses` and `services`, filtering by specified statuses.

*   **`src/db/update.ts` (`updateJobs`)**:
    *   Imports: `supabase` (from `client.ts`), `SupabaseClient`, `JobUpdateOperation` (types).
    *   Purpose: Performs batch updates on the Supabase `jobs` table based on a list of operations.

*   **`src/scheduler/availability.ts` (`calculateTechnicianAvailability`, `calculateAvailabilityForDay`)**:
    *   Imports: `Technician`, `Job`, `TechnicianAvailability` (types).
    *   Purpose: Calculates technician start times, end times, and start locations based on locked jobs (for today) or standard work hours and home locations (for future days), considering working days/hours (currently Mon-Fri, 9am-6:30pm UTC). Uses standard JavaScript `Date` methods (UTC variants).

*   **`src/scheduler/bundling.ts` (`bundleQueuedJobs`)**:
    *   Imports: `Job`, `JobBundle`, `SchedulableJob`, `SchedulableItem` (types).
    *   Purpose: Groups jobs with the same `order_id` into `JobBundle` objects.

*   **`src/scheduler/eligibility.ts` (`determineTechnicianEligibility`)**:
    *   Imports: `SchedulableItem`, `Technician`, `JobBundle`, `SchedulableJob`, `EquipmentRequirement`, `VanEquipment` (types).
    *   Imports: `getRequiredEquipmentForJob`, `getEquipmentForVans` (from `src/supabase/equipment.ts`).
    *   Purpose: Compares equipment required for a job/bundle (fetched via `getRequiredEquipmentForJob`) with the equipment available in each technician's van (fetched via `getEquipmentForVans`) to determine eligibility. Breaks bundles if no single tech is eligible.

*   **`src/scheduler/payload.ts` (`prepareOptimizationPayload`)**:
    *   Imports: `Technician`, `SchedulableItem`, `Job`, `Address`, `OptimizationPayload`, `OptimizationTechnician`, `OptimizationItem`, `OptimizationLocation`, `TechnicianAvailability` (types).
    *   Imports: `getTravelTime` (from `src/google/maps.ts`).
    *   Purpose: Constructs the JSON payload for the external optimization service. This involves:
        *   Indexing all unique locations (depot, technician start, job sites).
        *   Calculating the travel time matrix between all locations using `getTravelTime`.
        *   Formatting technician data (start/end times, start locations - either current or home based on `TechnicianAvailability`).
        *   Formatting schedulable items with their constraints and eligible technician indices.

*   **`src/scheduler/optimize.ts` (`callOptimizationService`)**:
    *   Imports: `axios` (external library), `OptimizationPayload`, `OptimizationResponsePayload` (types).
    *   Purpose: Sends the prepared payload to the optimization microservice URL (from environment variables) via an HTTP POST request using `axios`. Handles response and errors.

*   **`src/scheduler/results.ts` (`processOptimizationResults`)**:
    *   Imports: `OptimizationResponsePayload`, `ScheduledJobUpdate`, `ItemRoute` (types).
    *   Purpose: Parses the JSON response from the optimization service, extracting the planned routes for each technician, calculated start times for scheduled jobs, and a list of unassigned items.

*   **`src/supabase/equipment.ts` (`getRequiredEquipmentForJob`, `getEquipmentForVans`)**:
    *   Imports: `supabase` (from `client.ts`), `EquipmentRequirement`, `VanEquipment`, `Service`, `VehicleYmm` (types).
    *   Imports: `getYmmIdForOrder` (from `src/supabase/orders.ts`).
    *   Purpose:
        *   `getEquipmentForVans`: Fetches equipment currently assigned to specified vans.
        *   `getRequiredEquipmentForJob`: Determines equipment requirements based on job service category, vehicle type (using `getYmmIdForOrder`), and service details by querying `service_equipment_requirements`.

*   **`src/google/maps.ts` (`getTravelTime`)**:
    *   Imports: `@googlemaps/google-maps-services-js` (external library), `Address` (type).
    *   Purpose: Calls the Google Maps Distance Matrix API to get driving travel times between locations. Includes an in-memory cache to avoid redundant API calls for the same origin-destination pairs within a short timeframe. Uses API key from environment variables.

*   **`src/supabase/orders.ts` (`getYmmIdForOrder`)**:
    *   Imports: `supabase` (from `client.ts`), `Order` (type).
    *   Purpose: Fetches the `ymm_id` (Year-Make-Model identifier) associated with a specific `order_id` from the `orders` table.

**3. System Workflow Summary (based on `runFullReplan` Refactored Approach):**

1.  **Initialization:** Start the replan cycle. Initialize internal state: `finalAssignments = new Map()` and `jobsToPlan = new Set()`.
2.  **Fetch Initial Data:** Get active technicians (with current locations) and relevant jobs (initially `queued`, plus `locked`/`fixed_time`). Populate `jobsToPlan` with IDs of `queued` jobs.
3.  **Separate Jobs:** Identify `lockedJobs` and `fixedTimeJobs`.
4.  **Pass 1 (Today):**
    *   If `jobsToPlan` is empty, skip to Final Update.
    *   Calculate today's technician availability using `lockedJobs`.
    *   Fetch job details for IDs in `jobsToPlan`.
    *   Bundle, check eligibility, prepare payload for jobs in `jobsToPlan`.
    *   Call optimization service.
    *   Process results:
        *   For successfully scheduled jobs: Add `{ techId, estimatedSchedISO }` to `finalAssignments` using the `jobId` as the key. Remove `jobId` from `jobsToPlan`.
5.  **Overflow Loop (Pass 2+):**
    *   Loop up to `MAX_OVERFLOW_ATTEMPTS` times as long as `jobsToPlan` is not empty.
    *   Increment the planning date by one day.
    *   Fetch technicians (with **home locations**) and fetch details for jobs still in `jobsToPlan`.
    *   Calculate technician availability for the *future* date (using home locations).
    *   If no availability, skip to the next day in the loop.
    *   Bundle, check eligibility, prepare payload for jobs in `jobsToPlan` using future availability.
    *   Call optimization service.
    *   Process results:
        *   For successfully scheduled jobs: Add `{ techId, estimatedSchedISO }` to `finalAssignments` using the `jobId`. Remove `jobId` from `jobsToPlan`.
6.  **Final Database Update:**
    *   Prepare a list of `JobUpdateOperation`.
    *   Iterate `finalAssignments`: Add update operations to set `status = 'queued'`, `assigned_technician = techId`, `estimated_sched = estimatedSchedISO`.
    *   Iterate remaining `jobId`s in `jobsToPlan`: Add update operations to set `status = 'pending_review'`, `assigned_technician = null`, `estimated_sched = null`.
    *   Execute `updateJobs` with the combined list of operations.
7.  **Completion/Error:** Log success or handle errors.

This trace provides a detailed view of how the modules interact to perform the full replan, including fetching data, applying business logic (bundling, eligibility, availability), interacting with external services (Google Maps, Optimization Service), and updating the database state **using the refactored internal tracking and final update mechanism.**
