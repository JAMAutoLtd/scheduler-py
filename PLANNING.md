# PLANNING.md - Project Architecture & Design Notes

## Overview

This document outlines the architecture, core logic, and design decisions for the dynamic job scheduling system backend.

**Time Standard:** All internal date/time calculations should be performed assuming **UTC**. All timestamps exchanged with the database or external services (like the optimization microservice) must be formatted as **ISO 8601 strings with UTC timezone indication** (e.g., `2024-07-23T10:30:00Z` or `2024-07-23T10:30:00+00:00`). Avoid using local timezone-dependent methods (`.getDay()`, `.setHours()`) for calculations; use UTC equivalents (`.getUTCDay()`, `.setUTCHours()`) instead.

## Core Algorithm: Full Replan with Overflow (Refactored Approach)

The system employs a "full replan" strategy. Instead of incrementally modifying an existing schedule, it recalculates the optimal schedule for relevant jobs based on the current state whenever triggered. The multi-day overflow handling is managed *internally* within the main orchestration function (`runFullReplan`), and only the final results are written to the database.

**Key Principles of Refactored Approach:**

1.  **Simplified DB Statuses:**
    *   Jobs successfully assigned a technician and `estimated_sched` time by the optimizer (regardless of the planned day) have their status set to `queued`.
    *   Jobs that cannot be assigned after attempting planning for `MAX_OVERFLOW_ATTEMPTS` days (currently 4) have their status set to `pending_review`.
    *   Temporary statuses like `overflow` or `scheduled_future` are **not** written to the database.
2.  **Internal State Management:**
    *   `runFullReplan` maintains internal data structures (e.g., a Map for successful assignments, a Set for jobs still needing placement) throughout its execution.
    *   The multi-day loop iterates, calling the optimizer for jobs still needing placement, and updates this internal state.
3.  **Single Final DB Update:**
    *   Database updates (`updateJobs`) are performed only **once** at the very end of `runFullReplan`.
    *   This single update applies the final `queued` or `pending_review` status, along with `assigned_technician` and `estimated_sched` based on the internally stored results.

**Rationale:** This approach simplifies the database schema and reflects the dynamic nature of the system. Since any `queued` job is potentially re-optimized on the next run (unless locked or fixed), distinguishing between 'scheduled today' vs. 'scheduled future' in the database is less critical. `pending_review` clearly flags jobs requiring attention.

**Time Standard:** All internal date/time calculations should be performed assuming **UTC**. All timestamps exchanged with the database or external services (like the optimization microservice) must be formatted as **ISO 8601 strings with UTC timezone indication** (e.g., `2024-07-23T10:30:00Z` or `2024-07-23T10:30:00+00:00`). Avoid using local timezone-dependent methods (`.getDay()`, `.setHours()`) for calculations; use UTC equivalents (`.getUTCDay()`, `.setUTCHours()`) instead.

## Previous Design Notes (Pre-Refactor - Retained for Context)

"This was not the intended outcome of this project. I missed a critical piece when designing our documentation.
Phase 1: Secure High-Priority Jobs for Today (Minimize Pushing to Overflow)
Phase 2: Assign Remaining Jobs & Optimize Routes (Focus on Efficiency)
CRITICALLY MISSING: Phase 3: Handle Overflow
Any jobs that could not be assigned to any technician for completion today (due to time constraints, travel impossibility, etc.) are placed in the queue for the next workday.
The planning process for the next day starts, using technicians' home locations as starting points and the overflow jobs as the input queue."


Okay, I understand the requirement. The current system optimizes for the *current* workday based on immediate availability and doesn't explicitly handle rolling over unassigned jobs to the next day's plan using home locations.

To implement this "Phase 3: Handle Overflow" with minimal disruption, we need to adjust the orchestration and potentially some underlying functions. Here's a breakdown after reviewing the codebase:

1.  **Overflow Identification:**
    *   `optimize-service/main.py` correctly identifies `unassigned_item_ids` if the solver cannot schedule them within the given constraints (including time windows).
    *   `src/scheduler/optimize.ts` receives this list in the `OptimizationResponsePayload`.
    *   `src/db/update.ts` (`updateJobStatuses`) currently takes `assignedRoutes` and `unassignedIds`. It updates assigned jobs to `queued` and unassigned jobs to `overflow`.

2.  **Next Day Trigger:** The simplest approach is to modify the main orchestrator (`runFullReplan` in `src/scheduler/orchestrator.ts`) to perform a second planning pass if the first pass results in unassigned jobs.


This approach reuses most existing logic modules (`bundling`, `eligibility`, `optimize`, `results`) and primarily modifies the orchestration, data fetching, availability calculation, and payload generation steps for the second pass.

Now, regarding the looping overflow solution: Yes, we can incorporate looping into the overflow handling in `src/scheduler/orchestrator.ts`. Instead of just running a single "Pass 2" for the next day, we can wrap that logic in a loop that attempts planning for subsequent days if overflow persists.

**Refined Plan (incorporating looping):**

3.  **Next Day Inputs:**
    *   **Jobs:** We need jobs marked specifically from the first pass's overflow. Changing the status in `updateJobStatuses` from `queued` to something like `overflow` would facilitate this. Then, `getRelevantJobs` (or a new function) needs to fetch based on this status for the second pass.
    *   **Technicians:**
        *   **Availability:** `calculateTechnicianAvailability` uses `getAdjustedCurrentTime()` based on the *current* time. We need a way to calculate availability starting from the beginning of the *next* workday (e.g., 9 AM tomorrow).
        *   **Start Location:** `calculateTechnicianAvailability` currently uses `tech.current_location` (potentially updated by the last locked job). For the next day, we need to fetch and use the technician's `home_location_id`. Looking at `src/types/database.types.ts` and `src/supabase/technicians.ts`, the `Technician` type includes `home_location_id`, but `getActiveTechnicians` doesn't explicitly fetch the coordinates. We'll need to adjust the Supabase query to join the `addresses` table based on `home_location_id`.
    *   **Time Windows:** `prepareOptimizationPayload` generates ISO time strings based on the calculated availability. This needs to be adjusted to reflect the next workday's 9:00 AM - 6:30 PM window.

1.  ** Modify `src/db/update.ts` to mark overflow as `'overflow'`.
2.  **(To Do)** Modify `src/supabase/technicians.ts` to fetch home locations.
3.  **(To Do)** Modify `src/supabase/jobs.ts` to filter by status `'queued_next_day'`.
4.  **Modify `src/scheduler/availability.ts` (or create new):**
    *   Create a function `calculateAvailabilityForDay(technicians: Technician[], targetDate: Date)`:
        *   Takes a `targetDate` (representing the start of the day to plan for).
        *   Calculates the start (9:00 AM) and end (6:30 PM) of the *working day* represented by `targetDate`. **There needs to be a check for if any technicians are available that day because sometimes we choose to work weekends**
        *   Sets `earliest_availability` to the calculated start ISO string for that working day.
        *   Sets `current_location` to the fetched `home_location`.
        *   Returns the modified technicians list or an indication of non-working day.
5.  **Modify `src/scheduler/payload.ts`:**
    *   Ensure `prepareOptimizationPayload` correctly uses the technician start/end times passed into it (which will now potentially be for future days). No major change might be needed if it already derives start/end ISO times from the `Technician` object's `earliest_availability` and a calculated `latestEndTimeISO`. We'll need a helper to calculate `latestEndTimeISO` based on the `earliest_availability` date.
6.  **Modify `src/scheduler/orchestrator.ts` (`runFullReplan`):**
    *   **Pass 1 (Today):**
        *   Run as before.
        *   Call `updateJobStatuses`, storing `unassignedItemIds`.
    *   **Overflow Loop (e.g., `maxAttempts = 4`):**
        *   Initialize `currentPlanningDate = new Date()` (today).
        *   Initialize `loopCount = 0`.
        *   `while (unassignedItemIds.length > 0 && loopCount < maxAttempts)`:
            *   `loopCount++`.
            *   Increment `currentPlanningDate` by one day.
            *   **Fetch Data:** Get `'overflow'` jobs. Get technicians with home locations.
            *   **Calculate Availability:** Call `calculateAvailabilityForDay(technicians, currentPlanningDate)`.
                *   If it's a non-working day (no technician availability), `continue` the loop to the next day.
            *   **Bundle & Eligibility:** Run on the *current* set of overflow jobs.
            *   **Prepare Payload:** Call `prepareOptimizationPayload` with the technicians (having future availability/home locations) and the current overflow items.
            *   **Call Optimization:** Call `callOptimizationService`.
            *   **Process Results & Update DB:**
                *   Get the *new* `unassignedItemIds` from this loop's optimization result.
                *   Determine which jobs were *successfully* scheduled in *this loop*.
                *   Call `updateJobStatuses`:
                    *   Update successfully scheduled jobs to `queued`.
                    *   Update jobs that are *still* unassigned to remain `'overflow'`.
                *   Update the main `unassignedItemIds` variable with the list returned by the optimizer for the next loop iteration.
    *   **Final Cleanup:** After the loop, any jobs *still* having status `'overflow'` could be updated to `'unschedulable_overflow'` to indicate they couldn't be placed within the N-day window.

**Implementation Order:**

We should proceed with the plan outlined previously, starting with the modifications needed for the single next-day pass, as those are prerequisites for the looping logic:

1.  `src/db/update.ts` (Change overflow status)
2.  `src/supabase/technicians.ts` (Fetch home locations)
3.  `src/supabase/jobs.ts` (Filter by new status)
4.  `src/scheduler/availability.ts` (Create `calculateAvailabilityForDay` with target date and weekend skip)
5.  `src/scheduler/payload.ts` (Adapt to use future availability/locations)
6.  `src/scheduler/orchestrator.ts` (Implement the loop structure)
7.  Documentation updates.


**File Reading Plan:**

1.  `src/db/update.ts` (for `updateJobStatuses`)
2.  `src/supabase/technicians.ts` (for `getActiveTechnicians`)
3.  `src/supabase/jobs.ts` (for `getRelevantJobs` or similar)
4.  `src/scheduler/availability.ts` (for availability calculation logic)
5.  `src/scheduler/payload.ts` (for `prepareOptimizationPayload`)
6.  `src/scheduler/orchestrator.ts` (for `runFullReplan`)
7.  `src/types/database.types.ts` (to check the `Technician` type)


Okay, I've read `src/db/update.ts`. Here are the key points regarding `updateJobStatuses`:

*   It correctly updates jobs based on the `routes` and `unassignedItemIds` from the optimization response.
*   It sets the status to `'scheduled'` for assigned jobs and `'overflow'` for unassigned ones, nullifying `assigned_technician` and `estimated_sched` for the latter. This matches the initial requirement in `TASK.md`.
*   It currently skips updating database records for items identified as bundles (e.g., `bundle_...`). This needs refinement; if a bundle is scheduled or becomes overflow, its constituent jobs need updating.
*   The function operates on a single optimization result. For the multi-day loop, it will need to be called iteratively. We'll need to adjust the logic to handle different statuses (`'scheduled_future'`, retaining `'overflow'`, final `'unschedulable_overflow'`) based on which loop iteration the job is processed in and its outcome.


Okay, I have examined `src/supabase/technicians.ts`.

*   The function `getActiveTechnicians` currently fetches `home_address_id` from the joined `users` table.
*   However, it **does not** perform the necessary subsequent join to the `addresses` table to retrieve the actual latitude and longitude coordinates for that `home_address_id`.
*   The `Technician` type definition will also need to be updated to include a `home_location` field containing the coordinates.

This confirms the requirement noted in `TASK.md`. I will refine the task description later to be more specific about the nested join required.


Okay, I've reviewed `src/supabase/jobs.ts`.

*   The existing `getRelevantJobs` function fetches jobs based on a predefined list of statuses (`RELEVANT_JOB_STATUSES`).
*   It already includes the necessary joins for `addresses` and `services`.
*   It uses the `.in()` filter for statuses.

To fetch `'overflow'` jobs for the second pass, we have two options:

1.  **Modify `getRelevantJobs`:** Add an optional `statusFilter` parameter. If provided, it uses that filter; otherwise, it defaults to `RELEVANT_JOB_STATUSES`.
2.  **Create `getJobsByStatus`:** Duplicate the core logic of `getRelevantJobs` but make the status filter mandatory via a parameter.

Given that fetching by specific status will be required for the overflow loop, creating a dedicated function `getJobsByStatus` seems cleaner and adheres better to the single responsibility principle. This aligns with the suggestion in `TASK.md`.


Okay, I've reviewed `src/scheduler/availability.ts`.

*   The current `calculateTechnicianAvailability` function correctly determines the earliest available time for technicians *for the current day* by considering locked jobs (`en_route`, `in_progress`, `fixed_time`) and standard work hours (9:00 AM - 6:30 PM, Mon-Fri).
*   It uses a helper `getAdjustedCurrentTime` to ensure calculations start within the workday window.
*   It updates the `earliest_availability` (as ISO string) and `current_location` (based on last locked job or van location) properties of the `Technician` objects *in place*.

The plan in `TASK.md` to create a new function `calculateAvailabilityForDay(technicians, targetDate)` is appropriate. This new function will:

*   Take a `targetDate` as input.
*   Determine the start (9:00 AM) and end (6:30 PM) of the *working day* for that `targetDate`.
*   **Refinement:** Implement logic to skip non-working days (currently weekends, but should be flexible for holidays). The task list mentions this, but I'll add a note to make it explicit.
*   **Refinement:** Instead of modifying technicians in place, it should probably return a *new* list of `TechnicianAvailability` objects (or similar structure) containing the `technicianId`, the calculated `availabilityStartTimeISO`, `availabilityEndTimeISO`, and the `startLocation` (which will be the `home_location`). This avoids side effects and makes the flow clearer, especially within the loop.
*   It will **not** need to consider `lockedJobs` because the next-day planning starts fresh from the technician's home base at the beginning of the *next* working day.


Okay, I have reviewed `src/scheduler/payload.ts`. Here's how it relates to the overflow implementation:

*   **Input Structure:** It takes `technicians`, `items`, and `fixedTimeJobs` as input.
*   **Locations:** It maps unique coordinates (depot, items, tech start locations) to indices.
    *   It uses `tech.current_location` for the technician's starting point for the *first* pass (today). For the next day passes, this will need to use the `home_location` fetched earlier.
    *   It includes logic to slightly perturb technician start locations if they clash exactly with an item location. This logic should remain.
*   **Travel Matrix:** Calculates travel times between all indexed locations using `getTravelTime`. This will work correctly for future days as long as the locations (including home locations) are properly indexed.
*   **Technician Formatting:** It creates `OptimizationTechnician` objects.
    *   It currently uses `tech.earliest_availability` (which is for *today* based on `calculateTechnicianAvailability`). This needs to be replaced with the start time calculated by the new `calculateAvailabilityForDay` for the target planning day.
    *   It calculates `latestEndTimeISO` based on the start time and hardcoded work hours (6:30 PM). This calculation logic needs to be adjusted to use the end time derived from `calculateAvailabilityForDay` for the target day.
    *   It uses the index of the technician's `current_location` (or depot/perturbed location) as `startLocationIndex`. This needs to be changed to use the index corresponding to the `home_location` for future day passes.
    *   It assumes technicians return to the depot (`endLocationIndex: depotLocation.index`). This assumption should hold for next-day planning as well.
*   **Item Formatting:** Formats `SchedulableItem` into `OptimizationItem`, linking them to their location index. This should work fine for overflow items.
*   **Fixed Constraints:** Handles `fixedTimeJobs`. This logic likely won't apply directly to overflow jobs unless a specific overflow job *also* had a fixed time constraint originally, which seems unlikely but possible. The current filtering should handle this.

**Refinement:** The `prepareOptimizationPayload` function is quite complex. Instead of modifying it directly to handle both "today" and "future day" scenarios, it might be cleaner to pass the required `startLocation`, `earliestStartTimeISO`, and `latestEndTimeISO` explicitly for each technician, rather than having the function derive them from the `Technician` object. This would make the function's behavior more predictable when called within the overflow loop.

Here are the key findings and refinements:

1.  **`src/db/update.ts` (`updateJobStatuses`):**
    *   Needs modification to handle different statuses (`'scheduled_future'`, `'unschedulable_overflow'`) depending on the context (initial pass vs. overflow loop vs. final cleanup).
    *   Needs logic to update constituent jobs when a *bundle* is scheduled or becomes overflow.
    *   Suggest refactoring to accept a specific list of job IDs and a target status, making it more flexible for iterative calls.
2.  **`src/supabase/technicians.ts` (`getActiveTechnicians`):**
    *   Confirmed the need for a nested join to fetch `addresses` via `users` using `home_address_id` to get home location coordinates.
3.  **`src/supabase/jobs.ts` (`getRelevantJobs`):**
    *   Confirmed that creating a new function `getJobsByStatus` is the cleanest approach for fetching overflow jobs.
4.  **`src/scheduler/availability.ts`:**
    *   Confirmed the plan to create `calculateAvailabilityForDay`.
    *   Refined that it should *not* use locked jobs and should return a new data structure (e.g., `TechnicianAvailability[]`) instead of modifying input technicians.
    *   Highlighted the need for holiday logic beyond simple weekend skipping.
5.  **`src/scheduler/payload.ts` (`prepareOptimizationPayload`):**
    *   Needs modification to accept explicit start/end times and the specific start location (home location for future days) for each technician, rather than relying solely on the `Technician` object's state from the first pass. Passing the `TechnicianAvailability[]` structure seems suitable.
6.  **`src/scheduler/orchestrator.ts` (`runFullReplan`):**
    *   The loop logic needs careful implementation regarding fetching the correct data (overflow jobs, techs with home locations), calculating availability for the *target* day, preparing the payload with future context, and calling the refactored `updateJobStatuses` with the appropriate target status based on the loop iteration and outcome.


The key changes include:

*   Adding specific sub-tasks for updating type definitions (`src/types/database.types.ts`).
*   Specifying the need to refactor `updateJobStatuses` in `src/db/update.ts` to be more flexible and handle bundle ID mapping.
*   Detailing the required Supabase query modification in `src/supabase/technicians.ts` and the creation of `getJobsByStatus` in `src/supabase/jobs.ts`.
*   Refining the requirements for the new `calculateAvailabilityForDay` function in `src/scheduler/availability.ts`, including adding a new sub-task for holiday logic and specifying the return type.
*   Clarifying the necessary modifications to `prepareOptimizationPayload` in `src/scheduler/payload.ts` to accept future availability data.
*   Providing a more detailed step-by-step breakdown of the overflow loop logic required in `src/scheduler/orchestrator.ts`.
*   Updating the corresponding testing tasks to reflect the new/modified functions and logic.
*   Adding the holiday implementation as a new item in the "Discovered During Work" section.
*   Increasing the time estimate for the main task to reflect the added detail and complexity.