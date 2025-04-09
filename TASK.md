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

*   **[ ] Testing** - (Est: Ongoing - ~10h total) - {Current Date} (Adjusted scope)
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
    *   [ ] Aim for happy path, edge case, and failure case tests for key functions.
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
            *   [ ] `availability.test.ts` **NYI**
            *   [X] `bundling.test.ts`
            *   [X] `eligibility.test.ts`
        *   [ ] **Optimization Payload & Call (`tests/scheduler/`)**
            *   [ ] `payload.test.ts`
            *   [ ] `optimize.test.ts`
        *   [ ] **Result Processing & DB Update (`tests/scheduler/` & `tests/db/`)**
            *   [ ] `results.test.ts`
            *   [X] `update.test.ts` (`tests/db/`)

*   **[ ] Documentation & Finalization** - (Est: 2h) - {Date}
    *   [X] Update `README.md` with setup instructions, how to run, and overview.
    *   [X] Add necessary code comments (docstrings, `# Reason:` where needed).
    *   [ ] Final review and cleanup.
    *   [ ] Create/update `CHANGELOG.md`.

---

## Discovered During Work (TODOs)

*   (Add items here as they arise)

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

---

**Notes:**

*   Estimates are rough and may change.
*   Tasks depend on each other; generally follow the order listed.
*   Testing should occur alongside development of each module/feature.
*   Remember to update this file and `CHANGELOG.md` regularly.
*   Replace `{Date}` placeholders with actual start/completion dates.
*   Replace `{Current Date}` with today's date. 