# Dynamic Job Scheduler (TypeScript/Node.js Backend)

This project implements the backend logic for a dynamic job scheduling system designed to assign tasks to technicians efficiently. It utilizes a "full replan" approach, considering technician availability, job priorities, required equipment, travel times, and fixed constraints.

## Key Features

*   **Data Fetching**: Interfaces with a Supabase database to retrieve job, technician, equipment, and other relevant data.
*   **Time Handling**: Consistently uses **UTC** for all internal calculations and **ISO 8601 strings** (e.g., `YYYY-MM-DDTHH:mm:ss.sssZ`) for data storage (database fields like `estimated_sched`) and external communication (optimization service payload/response).
*   **Travel Time**: Integrates with the Google Maps Distance Matrix API to calculate travel times between locations, including caching.
*   **Technician Availability**: Calculates technician availability based on work hours, existing locked/fixed jobs, and potentially future days (considering home location).
*   **Job Bundling**: Groups jobs belonging to the same order for potential scheduling as a single unit.
*   **Technician Eligibility**: Determines which technicians can perform a job or bundle based on required equipment in their assigned van.
*   **Optimization Service Integration**: Prepares a detailed payload and communicates with an external Python-based optimization microservice (expected to use OR-Tools) via HTTP to solve the vehicle routing problem.
*   **Multi-Day Planning & Final Update**: The core `runFullReplan` function handles planning for the current day and attempts to schedule unassigned (overflow) jobs on subsequent days (up to a limit). It tracks results internally and performs a **single consolidated database update** at the end, setting successfully placed jobs to `queued` (with assignment details) and unschedulable jobs to `pending_review`.

## Project Structure

```
.
├── src/
│   ├── db/               # Database update logic
│   │   └── update.ts         # Updates job statuses post-optimization
│   ├── google/           # Google Maps API integration
│   │   └── maps.ts           # Fetches travel times with caching
│   ├── scheduler/        # Core scheduling logic
│   │   ├── availability.ts   # Calculates technician availability
│   │   ├── bundling.ts       # Groups jobs into bundles
│   │   ├── eligibility.ts    # Determines technician eligibility for items
│   │   ├── optimize.ts       # Calls the optimization microservice
│   │   ├── orchestrator.ts   # Main replan orchestration function (runFullReplan)
│   │   ├── payload.ts        # Prepares payload for optimization service
│   │   └── results.ts        # Processes results from optimization service
│   ├── supabase/         # Supabase data fetching functions
│   │   ├── client.ts         # Supabase client initialization
│   │   ├── equipment.ts      # Fetches equipment data & requirements
│   │   ├── jobs.ts           # Fetches job data
│   │   ├── orders.ts         # Fetches order data (inc. ymm_id helper)
│   │   └── technicians.ts    # Fetches technician data
│   ├── types/            # TypeScript type definitions
│   │   ├── database.types.ts # Interfaces mapping to Supabase schema
│   │   └── optimization.types.ts # Interfaces for optimization payload/response
│   └── index.ts          # Main application entry point
├── tests/              # Unit tests (mirroring src structure)
│   ├── db/
│   ├── google/
│   ├── scheduler/
│   ├── supabase/
│   └── README.md         # Details about the tests
├── .env                # Local environment variables (gitignored)
├── .env.example        # Example environment variables
├── .eslintrc.js        # ESLint configuration
├── .gitignore          # Git ignore file
├── .prettierrc.js      # Prettier configuration
├── DB.md               # Database schema description
├── PLANNING.md         # Project planning and architecture details
├── README.md           # This file
├── TASK.md             # Development task tracking
├── jest.config.js      # Jest test runner configuration
├── package-lock.json   # Exact dependency versions
├── package.json        # Project dependencies and scripts
└── tsconfig.json       # TypeScript configuration
```

## Core Modules & Data Flow (`runFullReplan`)

The main orchestration logic resides in `src/scheduler/orchestrator.ts`, specifically the `runFullReplan` function. Execute (e.g., by running `npm start` or `npm run dev`) or using a System Trigger.

System Trigger: A full replan calculation is triggered by significant events. Triggering is not handled by this application. Examples include:

A new job arriving with 'queued' status.
A job being completed or cancelled.
A technician changing their availability.
Significant unexpected delays reported.
Periodically (e.g., start of the day).

It performs the following sequence (simplified view):

1.  **Fetch Initial Data (`src/supabase/`)**: Retrieves active technicians (with current locations) and relevant jobs (primarily `queued`, potentially `locked` or `fixed_time`).
2.  **Separate Jobs**: Identifies `lockedJobs`, `fixedTimeJobs`, and the initial set of `jobsToPlan` (e.g., `queued`).
3.  **Pass 1 (Today):**
    *   Calculates today's availability (`src/scheduler/availability.ts`) considering locked jobs.
    *   Bundles (`src/scheduler/bundling.ts`), checks eligibility (`src/scheduler/eligibility.ts` -> `src/supabase/equipment.ts`).
    *   Prepares payload (`src/scheduler/payload.ts` -> `src/google/maps.ts`).
    *   Calls optimization service (`src/scheduler/optimize.ts`).
    *   Processes results (`src/scheduler/results.ts`), updating *internal* state (tracking successful assignments and remaining `jobsToPlan`).
4.  **Overflow Loop (Subsequent Days):**
    *   Loops while `jobsToPlan` is not empty and day limit not reached.
    *   Fetches technician details (with home locations) and job details for remaining `jobsToPlan`.
    *   Calculates availability for the *next day* (`src/scheduler/availability.ts`).
    *   Bundles, checks eligibility, prepares payload for remaining jobs.
    *   Calls optimization service.
    *   Processes results, updating *internal* state.
5.  **Final Database Update (`src/db/update.ts`)**: Performs a **single batch update** based on the final internal state:
    *   Sets successfully assigned jobs to `queued` with `assigned_technician` and `estimated_sched`.
    *   Sets jobs that could not be scheduled to `pending_review`.

## Setup & Running

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    npm install
    ```
3.  **Create a `.env` file:** Copy `.env.example` to `.env` and fill in your necessary environment variables:
    *   `SUPABASE_URL`: Your Supabase project URL.
    *   `SUPABASE_ANON_KEY`: Your Supabase project anon key.
    *   `GOOGLE_MAPS_API_KEY`: Your Google Maps API key (ensure Distance Matrix API is enabled).
    *   `OPTIMIZATION_SERVICE_URL`: The full URL endpoint of your running Python optimization microservice.
4.  **Build the project** (compiles TypeScript to JavaScript in `./dist`):
    ```bash
    npm run build
    ```
5.  **Run the scheduler process:**
    ```bash
    npm start
    ```
    Alternatively, run directly using `ts-node` for development:
    ```bash
    npm run dev
    ```

## Testing

Unit tests are implemented using Jest and cover the core logic modules. Mocks are used for external dependencies like Supabase, Google Maps API, and the optimization microservice.

Run all tests:
```bash
npm test
```

See `tests/README.md` for details on specific test suites and coverage. Tests for `src/scheduler/orchestrator.ts` should specifically cover the refactored internal logic and final update mechanism.

## Key Dependencies

*   `@supabase/supabase-js`: For interacting with the Supabase database.
*   `@googlemaps/google-maps-services-js`: Client library for Google Maps APIs.
*   `axios`: For making HTTP requests to the optimization microservice.
*   `typescript`: Language used.
*   `ts-node`: For running TypeScript directly in development.
*   `jest` & `ts-jest`: For unit testing.
*   `eslint` & `prettier`: For code linting and formatting.

## Further Information

*   **Database Schema**: See `DB.md` for detailed table descriptions.
*   **Planning & Architecture**: See `PLANNING.md` for high-level design (including the refactored approach) and algorithm details.
*   **Task Tracking**: See `TASK.md` for development progress.