# Dynamic Job Scheduler (TypeScript/Node.js Backend)

This project implements the backend logic for a dynamic job scheduling system designed to assign tasks to technicians efficiently. It utilizes a "full replan" approach, considering technician availability, job priorities, required equipment, travel times, and fixed constraints.

## Key Features

*   **Data Fetching**: Interfaces with a Supabase database to retrieve job, technician, equipment, and other relevant data.
*   **Travel Time**: Integrates with the Google Maps Distance Matrix API to calculate travel times between locations, including caching.
*   **Technician Availability**: Calculates technician availability based on work hours and existing locked/fixed jobs.
*   **Job Bundling**: Groups jobs belonging to the same order for potential scheduling as a single unit.
*   **Technician Eligibility**: Determines which technicians can perform a job or bundle based on required equipment in their assigned van.
*   **Optimization Service Integration**: Prepares a detailed payload and communicates with an external Python-based optimization microservice (expected to use OR-Tools) via HTTP to solve the vehicle routing problem.
*   **Result Processing & DB Update**: Parses the schedule provided by the optimization service and updates job statuses, assignments, and estimated schedules in the Supabase database.

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

The main orchestration logic resides in `src/scheduler/orchestrator.ts`, specifically the `runFullReplan` function. When executed (e.g., by running `npm start` or `npm run dev`), it performs the following sequence:

1.  **Fetch Data (`src/supabase/`)**: Retrieves active technicians (`technicians.ts`) and relevant jobs (statuses: `queued`, `en_route`, `in_progress`, `fixed_time`) (`jobs.ts`) from Supabase using the client initialized in `client.ts`.
2.  **Separate Jobs**: Divides fetched jobs into `lockedJobs` (cannot be rescheduled), `schedulableJobs` (status 'queued'), and identifies `fixedTimeJobs` from the locked set.
3.  **Calculate Availability (`src/scheduler/availability.ts`)**: Determines the earliest time each technician is available and their starting location, considering `lockedJobs` and standard work hours.
4.  **Bundle Jobs (`src/scheduler/bundling.ts`)**: Groups `schedulableJobs` belonging to the same order into `JobBundles`. Single jobs become `SchedulableJob` items.
5.  **Determine Eligibility (`src/scheduler/eligibility.ts`)**: For each bundle/job, identifies eligible technicians based on required equipment (`src/supabase/equipment.ts`, `src/supabase/orders.ts`). Fetches van inventories. Breaks bundles if no single technician is eligible.
6.  **Prepare Payload (`src/scheduler/payload.ts`)**: Compiles technician availability, items with eligibility, location data, fixed constraints, and calculates the travel time matrix using `src/google/maps.ts`.
7.  **Call Optimization Service (`src/scheduler/optimize.ts`)**: Sends the prepared payload via HTTP POST to the configured external Python optimization microservice URL (defined in `.env`).
8.  **Update Database (`src/db/update.ts`)**: Parses the response from the optimization service and performs batch updates on the `jobs` table in Supabase: sets `status`, `assigned_technician`, and `estimated_sched` for successful jobs; sets status to `pending_review` for unassigned/overflow jobs.

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

See `tests/README.md` for details on specific test suites and coverage.

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
*   **Planning & Architecture**: See `PLANNING.md` for high-level design and algorithm details.
*   **Task Tracking**: See `TASK.md` for development progress.