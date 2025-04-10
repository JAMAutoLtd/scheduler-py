# TASK.md - Development Plan

**Generated:** {Current Date}

This document tracks the development tasks for the dynamic job scheduling system.

---

## Core Development Tasks

*   **[X] Setup Project Environment** - (Est: 0.5h) - {Current Date}
    *   [X] Initialize Node.js/TypeScript project.
    *   [X] Install core dependencies: `supabase-js`, `ortools-node`, `@googlemaps/google-maps-services-js` (or `axios`), `typescript`, `@types/node`, `ts-node`.
    *   [X] Configure TypeScript (`tsconfig.json`).
    *   [X] Set up basic project structure (e.g., `/src`, `/tests`, `/dist`).
    *   [X] Configure linting/formatting (e.g., ESLint, Prettier).
    *   [X] Update `package.json` scripts.
    *   [X] Create placeholder `src/index.ts`.

*   **[X] Module: Supabase Data Fetching** - (Est: 4h) - {Current Date}
    *   [X] Implement function(s) to fetch active technicians, their assigned vans, and current/home locations (`technicians.ts`).
    *   [X] Implement function(s) to fetch relevant jobs (`queued`, `en_route`, `in_progress`, `fixed_time`) with necessary details (`jobs.ts`).
    *   [X] Implement function(s) to fetch van equipment inventory (`equipment.ts`).
    *   [X] Implement function(s) to fetch equipment requirements based on job service, vehicle (`ymm_id`), and service category (using `getYmmIdForOrder` in `orders.ts` and `getRequiredEquipmentForJob` in `equipment.ts`).
    *   [X] Implement logic to determine technician initial availability (`availability.ts` in `scheduler` module).
    *   [X] Implement function(s) to fetch address coordinates (Included in `jobs.ts` join).
    *   [X] Add basic error handling for Supabase queries (Implemented within each fetch function).
    *   [X] Define TypeScript interfaces for fetched data structures (`database.types.ts`).

*   **[X] Module: Google Maps Travel Time** - (Est: 2h) - {Current Date}
    *   [X] Implement function to call Google Maps Distance Matrix API for travel duration between two points (`maps.ts`).
    *   [X] Implement an in-memory cache (with TTL) for travel time results between static locations (`maps.ts`).
    *   [X] Handle API key management securely (using `.env` in `maps.ts`).
    *   [X] Add error handling for API calls (`maps.ts`).

*   **[X] Logic: Job Bundling** - (Est: 1h) - {Current Date}
    *   [X] Implement logic to group `queued` jobs by `order_id` (`bundling.ts`).
    *   [X] Calculate bundle properties: highest priority, total duration (`bundling.ts`).

*   **[X] Logic: Technician Eligibility** - (Est: 2h) - {Current Date}
    *   [X] Implement logic to determine required equipment for each job/bundle (`eligibility.ts` using `getRequiredEquipmentForJob`).
    *   [X] Implement logic to compare required equipment with each technician's van inventory (`eligibility.ts` using `getEquipmentForVans`).
    *   [X] Generate a list of eligible technicians (`EligibleTechs`) for each job/bundle (`eligibility.ts`).
    *   [X] Implement logic to break bundles into single jobs if no technician is eligible for the bundle (`eligibility.ts`).

*   **[ ] Module: Optimization Service Communication** - (Est: 4h) - {Date} (Replaces OR-Tools Integration)
    *   [X] Define the JSON structure for the request payload to the Python optimization microservice (including technicians, schedulable items, eligibility, travel times, constraints). - {Current Date}
    *   [X] Implement logic in Node.js to gather all required data and format it into the defined request payload (`src/scheduler/payload.ts`). - {Current Date}
    *   [X] Implement function in Node.js to send the payload via HTTP POST to the Python microservice endpoint (`src/scheduler/optimize.ts` - requires endpoint URL). - {Current Date}
    *   [X] Define the JSON structure for the expected response payload from the microservice (containing optimized routes and timings). - {Current Date}
    *   [X] Implement logic in Node.js to receive and parse the response from the microservice (`src/scheduler/results.ts`). - {Current Date}
    *   [X] Add robust error handling for the HTTP request and response parsing (`src/scheduler/optimize.ts`). - {Current Date}
    *   *Note:* Requires the Python optimization microservice (with OR-Tools) to be deployed separately (e.g., on Google Cloud Run) and its endpoint URL to be available.

*   **[X] Module: Result Processing** - (Est: 2h) - {Current Date} (Adjusted scope)
    *   [X] Implement logic to parse the *response payload* from the optimization microservice.
    *   [X] Extract the assigned route (sequence of jobs/bundles) for each technician from the response.
    *   [X] Extract calculated start times (`estimated_sched`) for each scheduled job from the response.
    *   [X] Identify jobs/bundles originally sent that are *not* present in the response routes (overflow).

*   **[X] Module: Database Update** - (Est: 2h) - {Current Date}
    *   [X] Implement function(s) to update `jobs` table in Supabase.
    *   [X] Update `assigned_technician`, `estimated_sched`, and `status` (`scheduled`) for successfully scheduled jobs based on processed results.
    *   [X] Update `status` (`pending_review` or similar) for overflow jobs.
    *   [X] Use batch updates if possible for efficiency.

*   **[X] API/Trigger Mechanism** - (Est: 1h) - {Current Date} (Adjusted orchestration)
    *   [X] Define and implement the main function/entry point that orchestrates the replan process: 
        *   [X] Fetching data (Supabase).
        *   [X] Calculating availability, bundling, eligibility.
        *   [X] Calculating travel times (Google Maps).
        *   [X] Preparing payload and calling the optimization microservice.
        *   [X] Processing the microservice response.
        *   [X] Updating the DB (Supabase).
    *   [X] (Future Consideration) Determine how this process will be triggered.

*   **[ ] Implement Multi-Day Overflow Scheduling** - (Est: 8h) - {Current Date} (Estimate increased due to refinements)
    *   [X] **Type Definitions (`src/types/database.types.ts`):**
        *   [X] Add `home_location: { lat: number; lng: number } | undefined;` to the `Technician` interface. - {Current Date}
        *   [X] Add `'overflow'`, to the `JobStatus` type/enum. - {Current Date} (Already existed, but usage will change)
        *   [X] Add `'pending_review'` to `JobStatus` type/enum if it doesn't exist.
        *   [X] Define `TechnicianAvailability { technicianId: number; availabilityStartTimeISO: string; availabilityEndTimeISO: string; startLocation: { lat: number; lng: number }; }`. - {Current Date}
    *   [X] **DB Update (`src/db/update.ts`):**
        *   [X] Refactor `updateJobStatuses` (or create a new function, e.g., `updateSpecificJobStatuses`) to accept parameters like `jobIds: number[]` and `targetStatus: JobStatus`, allowing targeted updates for different stages (initial overflow, loop scheduled, loop overflow, final unschedulable). - {Current Date} (Created `updateJobs`, function remains flexible for final update).
        *   [X] Implement logic to handle `bundle_...` IDs in the optimization response: When processing results, map bundle IDs back to their constituent `job.id`s before calling the database update function. (This might involve modifying `processOptimizationResults` or adding a pre-processing step in the orchestrator). - {Current Date} (Implemented via `mapItemsToJobIds` helper in orchestrator, still relevant for mapping results before the *final* update).
    *   [X] **Supabase Fetching (`src/supabase/`):**
        *   [X] `technicians.ts`: Modify `getActiveTechnicians` query to join `users` then `addresses` using `home_address_id` to fetch home location coordinates (e.g., `... users!inner ( ..., home_address_id, addresses!inner ( lat, lng ) ) ...`). Store result in `Technician.home_location`. - {Current Date}
        *   [X] `jobs.ts`: Create `getJobsByStatus(statuses: JobStatus[])` function, reusing necessary join logic from `getRelevantJobs`, to fetch jobs by specific status(es) needed for the overflow loop. - {Current Date} (Will primarily fetch `queued` initially, and potentially refetch job details based on internal tracking IDs during the loop).
    *   [X] **Availability Calculation (`src/scheduler/availability.ts`):**
        *   [X] Create `calculateAvailabilityForDay(technicians: Technician[], targetDate: Date): TechnicianAvailability[]`. - {Current Date}
        *   [X] Function should calculate the next valid working day start/end times (9am-6:30pm) based on `targetDate`. - {Current Date}
        *   [X] Implement logic to skip non-working days (initially Sat/Sun). - {Current Date}
        *   [N/A] **New Sub-Task:** Implement/configure holiday checking logic (e.g., fetch from DB table `company_holidays` or use config/library) and integrate into non-working day skipping. - {Current Date} (Handled by upstream availability data)
        *   [X] Function must *not* consider locked jobs for future day calculations. - {Current Date}
        *   [X] Function should use `technician.home_location` as the `startLocation` in the returned `TechnicianAvailability` objects. - {Current Date}
        *   [X] Function should handle cases where no technicians have availability on a given day (return empty array or signal). - {Current Date}
    *   [X] **Payload Preparation (`src/scheduler/payload.ts`):**
        *   [X] Modify `prepareOptimizationPayload` to accept `TechnicianAvailability[]` (from `calculateAvailabilityForDay`) as an input parameter, alongside the base `Technician[]` list. - {Current Date}
        *   [X] Update the logic for creating `OptimizationTechnician`:
            *   [X] Use `technicianAvailability.startLocation` to determine the `startLocationIndex`. - {Current Date}
            *   [X] Use `technicianAvailability.availabilityStartTimeISO` for `earliestStartTimeISO`. - {Current Date}
            *   [X] Use `technicianAvailability.availabilityEndTimeISO` for `latestEndTimeISO`. - {Current Date}
    *   [ ] **Orchestration Refactoring (`src/scheduler/orchestrator.ts`):**
        *   [X] Refactor `runFullReplan` to implement internal overflow tracking:
            *   [X] Maintain internal state for successful assignments (`finalAssignments`: Map<jobId, { techId, schedTime }>) and jobs still needing placement (`jobsToPlan`: Set<jobId>).
            *   [X] Perform Pass 1 (Today): Optimize `jobsToPlan`, update internal state.
            *   [X] Perform Overflow Loop: Iterate up to `MAX_OVERFLOW_ATTEMPTS` days.
                *   [X] Inside loop: Fetch job details for `jobsToPlan`, calculate future availability, bundle, check eligibility, prepare payload, call optimizer.
                *   [X] Update internal state (`finalAssignments`, `jobsToPlan`) based on loop results.
                *   [X] **Do not** perform intermediate DB updates within the loop.
            *   [X] Perform Final DB Update: After loop, call `updateJobs` *once*:
                *   [X] Update jobs in `finalAssignments` to `status: 'queued'`, set `assigned_technician`, `estimated_sched`.
                *   [X] Update jobs remaining in `jobsToPlan` to `status: 'pending_review'`, clear `assigned_technician`, `estimated_sched`.
    *   [ ] **Testing:**
        *   [X] Add unit tests for `getJobsByStatus`. - {Current Date}
        *   [X] Add unit tests for `calculateAvailabilityForDay` (including non-working days, holiday logic). - {Current Date}
        *   [X] Update unit tests for `updateJobStatuses` (or its replacement) to reflect new parameters/logic. - {Current Date} (Tests for `updateJobs` remain relevant).
        *   [X] Add unit tests for `prepareOptimizationPayload` to test passing `TechnicianAvailability`. - {Current Date}
        *   [X] Add/update integration/unit tests for `runFullReplan` to cover the **refactored** overflow loop logic, internal state management, final DB update, and different outcomes (all scheduled, some pending review). - {Current Date}
    *   [ ] **Documentation:** Update `README.md`, `PLANNING.md`, `OVERVIEW.md` and `CHANGELOG.md` to reflect the refactored approach and simplified statuses.

*   **[ ] Refactor Time Handling for UTC Consistency** - (Est: 2h) - {Current Date}
    *   [X] Modify `src/scheduler/availability.ts` (`getAdjustedCurrentTime`, `calculateTechnicianAvailability`, `calculateAvailabilityForDay`) to use UTC methods (`getUTCDay`, `setUTCHours`, etc.) instead of local time methods for all date/time calculations. - {Current Date}
    *   [X] Modify `src/scheduler/payload.ts` (`prepareOptimizationPayload`) to use UTC methods when calculating `latestEndDate` for the fallback logic. - {Current Date}
    *   [X] Rerun/update unit tests for `src/scheduler/availability.ts` (`tests/scheduler/availability.test.ts`) after refactoring to ensure they pass with UTC logic. - {Current Date}
    *   [X] Review and potentially update unit tests for `src/scheduler/payload.ts` (`tests/scheduler/payload.test.ts`) if time calculations were affected. - {Current Date}

*   **[ ] Testing** - (Est: Ongoing - ~12h total) - {Current Date} (Estimate increased)
    *   [X] Set up testing framework (e.g., Jest). - {Current Date}
    *   [X] Write unit tests for Data Fetching module (mocking Supabase client). - {Current Date}
        *   [X] `tests/supabase/jobs.test.ts` (for `src/supabase/jobs.ts`)
        *   [X] `tests/supabase/technicians.test.ts` (for `src/supabase/technicians.ts`)
        *   [X] `tests/supabase/equipment.test.ts` (for `src/supabase/equipment.ts`)
        *   [X] `tests/supabase/orders.test.ts` (for `src/supabase/orders.ts`)
    *   [X] Write unit tests for Travel Time module (mocking Google Maps API). - {Current Date}
    *   [X] Write unit tests for Job Bundling logic. - {Current Date}
    *   [X] Write unit tests for Eligibility logic. - {Current Date}
    *   [X] Write unit tests for Optimization Service Communication (payload creation, request sending - requires mocking HTTP calls). - {Current Date}
    *   [X] Write unit tests for Result Processing logic (parsing the expected microservice response). - {Current Date}
    *   [X] Write unit tests for Database Update module (mocking Supabase client). - {Current Date}
    *   [X] Aim for happy path, edge case, and failure case tests for key functions.
    *   *Note:* Integration tests involving the actual microservice might be needed separately.
    *   [ ] Follow sequential test order for troubleshooting:
        *   [X] **Supabase Data Fetching (`tests/supabase/`)**
            *   [X] `jobs.test.ts`
            *   [X] `technicians.test.ts`
            *   [X] `orders.test.ts`
            *   [X] `equipment.test.ts`
        *   [X] **Google Maps (`tests/google/`)**
            *   [X] `maps.test.ts`
        *   [ ] **Scheduler Logic (Pre-Payload) (`tests/scheduler/`)**
            *   [X] `availability.test.ts` (**Create tests for BOTH `calculateTechnicianAvailability` and `calculateAvailabilityForDay`**) (**Requires update after UTC refactor**) - {Current Date}
            *   [X] `bundling.test.ts`
            *   [X] `eligibility.test.ts`
        *   [X] **Optimization Payload & Call (`tests/scheduler/`)**
            *   [X] `payload.test.ts` (**Update for new parameters/logic; Review after UTC refactor**) - {Current Date}
            *   [X] `optimize.test.ts` - {Current Date}
        *   [X] **Result Processing & DB Update (`tests/scheduler/` & `tests/db/`)**
            *   [X] `results.test.ts` - {Current Date}
            *   [X] `update.test.ts` (`tests/db/`) (**Update for refactored function/logic**)
        *   [X] **Orchestration (`tests/scheduler/`)**
             *   [X] `orchestrator.test.ts` (**Update tests significantly for refactored `runFullReplan` internal logic and final DB update**) - {Current Date}
                 *   [X] Test: Happy Path (Today Only) - All jobs scheduled `queued`.
                 *   [X] Test: Partial Schedule (Today Only) - Some `queued`, some `pending_review`.
                 *   [X] Test: No Schedulable Jobs - No updates or empty update. (Covered by basic tests)
                 *   [X] Test: No Technicians - Exits early, no updates. (Covered by basic tests)
                 *   [X] Test: Overflow Path (Single Future Day) - All overflow scheduled `queued` for Day 2.
                 *   [X] Test: Overflow Path (Multiple Future Days) - Overflow scheduled `queued` for Day 3.
                 *   [X] Test: Full Overflow - All jobs end as `pending_review` after max attempts.
                 *   [X] Test: Mixed Overflow - Some scheduled `queued` on future day, rest `pending_review`.
                 *   [X] Test: Weekend Skip Overflow - Jobs overflow Friday, skip Sat/Sun, scheduled `queued` Mon.
                 *   [X] Test: Bundling Interaction - Successfully scheduled bundle jobs are `queued`.
                 *   [X] Test: Bundling Interaction - Unassigned bundle jobs are `pending_review`.
                 *   [X] Test: Error Handling - `callOptimizationService` fails.
                 *   [X] Test: Error Handling - `getActiveTechnicians` fails.

*   **[ ] Documentation & Finalization** - (Est: 2h) - {Date}
    *   [X] Update `README.md` with setup instructions, how to run, and overview.
    *   [X] Add necessary code comments (docstrings, `# Reason:` where needed).
    *   [ ] Update `PLANNING.md` to reflect refactored approach.
    *   [ ] Update `OVERVIEW.md` (if used) to reflect refactored approach.
    *   [ ] Final review and cleanup.
    *   [ ] Create/update `CHANGELOG.md`.

---

## Discovered During Work (TODOs)

*   (Add items here as they arise)
*   [ ] Address TypeScript linter errors in `src/scheduler/optimize.ts` related to Axios response typing. ({Current Date})
*   **[X] Critical:** Fix floating time epoch in `optimize-service/main.py`. The current `EPOCH` recalculates on service restart, causing inconsistent time conversions. Refactor `iso_to_seconds` and `seconds_to_iso` to use a fixed epoch (e.g., Unix epoch via `datetime.timestamp()` and `datetime.fromtimestamp()`). ({Current Date})
*   [ ] Review travel time error handling in `optimize-service/main.py`. The large penalty (999999) for failed lookups might cause suboptimal routes instead of explicit errors. Consider alternative handling. ({Current Date})
*   [ ] Review priority penalty calculation in `optimize-service/main.py`. Analyze if the current `base_penalty` and scaling formula (`base_penalty * (max_priority - item.priority + 1)`) effectively represent business value. Consider refining based on factors like job revenue, cost, technician rates, or SLA impact. ({Current Date})
*   [ ] Consider implementing starvation protection for low-priority jobs. Investigate dynamically increasing the priority value *sent to the solver* based on job age (e.g., days since order created) without altering the original job record's priority. ({Current Date})
*   [N/A] **New Sub-Task:** Implement configurable holiday checking for `calculateAvailabilityForDay` (e.g., fetch from DB table or config). ({Current Date})
*   [ ] **Integration Testing:** Consider adding integration tests (e.g., using `msw` or `nock`) for `callOptimizationService` to verify the end-to-end handling of real Axios HTTP errors/timeouts, complementing the current unit tests which focus on internal logic branches. - {Current Date}

*   **[ ] Future Enhancement (Low Priority): Convert Optimizer to Value-Based Optimization** - {Current Date}
    *   **Goal:** Shift from minimizing travel time + penalties to maximizing net value (e.g., Job Revenue - Travel Cost).
    *   **Steps:**
        1.  **Data Enhancement:** Add estimated dollar `value` field to `OptimizationItem` inputs (representing potential revenue/profit).
        2.  **Cost Modeling:** Develop a model to convert travel time (seconds) into travel cost (dollars), considering technician wages, vehicle costs (fuel, maintenance, depreciation), etc. This might be an average rate or tech/vehicle specific.
        3.  **Callback Modification:** Update `travel_time_callback` (and the callback used by the arc cost evaluator) in `main.py` to return *dollar cost* instead of time (seconds).
        4.  **Penalty Redefinition:** Change the penalty used in `AddDisjunction` to be the actual estimated `value` (dollars) lost if the job is dropped, instead of the current abstract high number.
        5.  **Validation:** Thoroughly test the new model to ensure it produces financially sensible routes and correctly balances high-value jobs against travel costs.

---

## Completed Tasks

*   (Move completed items here with date)
*   **[X] Generated Initial TASK.md** - {Current Date}
*   **[X] Setup Project Environment** - {Current Date}
*   **[X] Module: Supabase Data Fetching** - {Current Date}
*   **[X] Module: Google Maps Travel Time** - {Current Date}
*   **[X] Logic: Job Bundling** - {Current Date}
*   **[X] Logic: Technician Eligibility** - {Current Date}
*   **[X] Sub-Task: Defined Optimization Request/Response JSON** - {Current Date}
*   **[X] Sub-Task: Implemented Optimization Payload Preparation** (`src/scheduler/payload.ts`) - {Current Date}
*   **[X] Sub-Task: Implemented Optimization Service Call Function** (`src/scheduler/optimize.ts`) - {Current Date}
*   **[X] Sub-Task: Added Error Handling for Service Call** (`src/scheduler/optimize.ts`) - {Current Date}
*   **[X] Module: Result Processing** (`src/scheduler/results.ts`) - {Current Date}
*   **[X] Module: Database Update** (`src/db/update.ts`) - {Current Date}
*   **[X] Time Handling Refactor (UTC)** - {Current Date}
*   **[X] Initial Multi-Day Overflow Implementation** (Parts of `technicians.ts`, `jobs.ts`, `availability.ts`, `payload.ts`, `orchestrator.ts` before current refactor) - {Current Date}

---

**Notes:**

*   Estimates are rough and may change.
*   Tasks depend on each other; generally follow the order listed.
*   Testing should occur alongside development of each module/feature.
*   Remember to update this file and `CHANGELOG.md` regularly.
*   Replace `{Date}` placeholders with actual start/completion dates.
*   Replace `{Current Date}` with today's date.
*   [ ] Review travel time error handling in `optimize-service/main.py`. The large penalty (999999) for failed lookups might cause suboptimal routes instead of explicit errors. Consider alternative handling. ({Current Date})
*   [ ] Review priority penalty calculation in `optimize-service/main.py`. Analyze if the current `base_penalty` and scaling formula (`base_penalty * (max_priority - item.priority + 1)`) effectively represent business value. Consider refining based on factors like job revenue, cost, technician rates, or SLA impact. ({Current Date})
*   [ ] Consider implementing starvation protection for low-priority jobs. Investigate dynamically increasing the priority value *sent to the solver* based on job age (e.g., days since order created) without altering the original job record's priority. ({Current Date})
*   **[ ] Future Enhancement (Low Priority): Convert Optimizer to Value-Based Optimization** - {Current Date}
*   **[ ] Future Enhancement (Low Priority): Convert Optimizer to Value-Based Optimization** - {Current Date} 