# scheduler-py

This project implements a dynamic job scheduling system for technicians.

## Project Structure

```
.
├── src/
│   ├── db/               # Database update logic
│   │   └── update.ts
│   ├── google/           # Google Maps API integration
│   │   └── maps.ts
│   ├── scheduler/        # Core scheduling logic
│   │   ├── availability.ts   # Calculate technician availability
│   │   ├── bundling.ts       # Group jobs into bundles
│   │   ├── eligibility.ts    # Determine technician eligibility for items
│   │   ├── optimize.ts       # Call optimization microservice
│   │   ├── orchestrator.ts   # Main replan orchestration function
│   │   ├── payload.ts        # Prepare payload for optimization service
│   │   └── results.ts        # Process results from optimization service
│   ├── supabase/         # Supabase data fetching functions
│   │   ├── client.ts         # Supabase client initialization
│   │   ├── equipment.ts      # Fetch equipment data
│   │   ├── jobs.ts           # Fetch job data
│   │   ├── orders.ts         # Fetch order data (inc. ymm_id helper)
│   │   └── technicians.ts    # Fetch technician data
│   ├── types/            # TypeScript interfaces
│   │   ├── database.types.ts # Interfaces mapping to Supabase schema
│   │   └── optimization.types.ts # Interfaces for optimization payload/response
│   └── index.ts          # Main application entry point
├── tests/              # Unit tests (To be added)
├── .env.example        # Example environment variables
├── .eslintrc.js        # ESLint configuration
├── .gitignore          # Git ignore file
├── .prettierrc.json    # Prettier configuration
├── DB.md               # Database schema description
├── PLANNING.md         # Project planning and architecture details
├── README.md           # This file
├── TASK.md             # Development task tracking
├── package.json        # Project dependencies and scripts
└── tsconfig.json       # TypeScript configuration
```

## Core Modules

*   **`src/supabase/`**: Contains functions dedicated to fetching data directly from the Supabase database (e.g., `getRelevantJobs`, `getActiveTechnicians`, `getEquipmentForVans`, `getRequiredEquipmentForJob`). It also initializes the Supabase client (`client.ts`).
*   **`src/google/`**: Handles interactions with the Google Maps API, specifically fetching travel times (`getTravelTime` in `maps.ts`) with caching.
*   **`src/scheduler/`**: Implements the core business logic for scheduling:
    *   `bundling.ts`: Groups queued jobs by order (`bundleQueuedJobs`).
    *   `availability.ts`: Calculates when technicians are free based on current time and locked jobs (`calculateTechnicianAvailability`).
    *   `eligibility.ts`: Filters technicians based on required equipment for jobs/bundles (`determineTechnicianEligibility`).
    *   `payload.ts`: Gathers all necessary data and formats it into the JSON payload required by the external optimization microservice (`prepareOptimizationPayload`).
    *   `optimize.ts`: Sends the payload to the optimization microservice endpoint and retrieves the result (`callOptimizationService`).
    *   `results.ts`: Parses the response from the optimization service (`processOptimizationResults`).
    *   `orchestrator.ts`: Contains the main `runFullReplan` function that coordinates the entire process.
*   **`src/db/`**: Handles updates *to* the Supabase database based on scheduling results (`updateJobStatuses` in `update.ts`).
*   **`src/types/`**: Defines TypeScript interfaces for database objects (`database.types.ts`) and the optimization service communication (`optimization.types.ts`).
*   **`src/index.ts`**: The main entry point that starts the replan process by calling `runFullReplan`.

## Data Flow / Orchestration (`runFullReplan` in `orchestrator.ts`)

The scheduling process is triggered by running `src/index.ts`, which calls the `runFullReplan` function. This function performs the following steps:

1.  **Fetch Data**: Retrieves active technicians and relevant jobs (queued, en_route, in_progress, fixed_time) from Supabase.
2.  **Separate Jobs**: Divides fetched jobs into `lockedJobs` (cannot be rescheduled) and `schedulableJobs` (status 'queued'). Identifies `fixedTimeJobs`.
3.  **Calculate Availability**: Determines the earliest time each technician is available and their starting location, considering `lockedJobs` (`calculateTechnicianAvailability`).
4.  **Bundle Jobs**: Groups `schedulableJobs` belonging to the same order into `JobBundles` (`bundleQueuedJobs`). Jobs not part of a multi-job order become `SchedulableJob` items.
5.  **Determine Eligibility**: For each bundle or single job, identifies which technicians have the required equipment. Fetches van inventories and equipment requirements from Supabase. Breaks bundles if no single technician is eligible (`determineTechnicianEligibility`).
6.  **Prepare Payload**: Compiles all necessary data (technician availability, items with eligibility, locations, fixed constraints) and calculates the travel time matrix using the Google Maps API (`prepareOptimizationPayload`).
7.  **Call Optimization Service**: Sends the prepared payload via HTTP POST to the external Python optimization microservice (`callOptimizationService`).
8.  **Update Database**: Receives the optimized schedule response and updates the `jobs` table in Supabase (`updateJobStatuses`): sets status to `scheduled`, assigns `assigned_technician`, and `estimated_sched` for successful jobs; sets status to `pending_review` for unassigned/overflow jobs.

## Setup & Running

1.  **Clone the repository.**
2.  **Install dependencies:**
    ```bash
    npm install
    ```
3.  **Create a `.env` file:** Copy `.env.example` to `.env` and fill in your:
    *   Supabase URL and Anon Key
    *   Google Maps API Key
    *   Optimization Service URL
4.  **Build the project:**
    ```bash
    npm run build
    ```
5.  **Run the scheduler:**
    ```bash
    npm start 
    ```
    Or for development (using ts-node):
    ```bash
    npm run dev
    ```

## Testing

Run unit tests using:
```bash
npm test
```
*(Note: Tests need to be implemented)*