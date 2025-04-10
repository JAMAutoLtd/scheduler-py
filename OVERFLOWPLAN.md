"This was not the intended outcome of this project. I missed a critical piece when designing our documentation.
Phase 1: Secure High-Priority Jobs for Today (Minimize Pushing to Overflow)
Phase 2: Assign Remaining Jobs & Optimize Routes (Focus on Efficiency)
CRITICALLY MISSING: Phase 3: Handle Overflow
Any jobs that could not be assigned to any technician for completion today (due to time constraints, travel impossibility, etc.) are placed in the queue for the next workday.
The planning process for the next day starts, using technicians' home locations as starting points and the overflow jobs as the input queue."


Okay, I understand the requirement. The current system optimizes for the *current* workday based on immediate availability and doesn't explicitly handle rolling over unassigned jobs to the next day's plan using home locations.

To implement this "Phase 3: Handle Overflow" with minimal disruption, we need to adjust the orchestration and potentially some underlying functions. Here's a breakdown after reviewing the codebase:

**Analysis:**

1.  **Overflow Identification:**
    *   `optimize-service/main.py` correctly identifies `unassigned_item_ids` if the solver cannot schedule them within the given constraints (including time windows).
    *   `src/scheduler/optimize.ts` receives this list in the `OptimizationResponsePayload`.
    *   `src/db/update.ts` (`updateJobStatuses`) currently takes `assignedRoutes` and `unassignedIds`. It updates assigned jobs to `scheduled` and unassigned jobs to `pending_review`.

2.  **Next Day Trigger:** The simplest approach is to modify the main orchestrator (`runFullReplan` in `src/scheduler/orchestrator.ts`) to perform a second planning pass if the first pass results in unassigned jobs.

3.  **Next Day Inputs:**
    *   **Jobs:** We need jobs marked specifically from the first pass's overflow. Changing the status in `updateJobStatuses` from `pending_review` to something like `queued_next_day` would facilitate this. Then, `getRelevantJobs` (or a new function) needs to fetch based on this status for the second pass.
    *   **Technicians:**
        *   **Availability:** `calculateTechnicianAvailability` uses `getAdjustedCurrentTime()` based on the *current* time. We need a way to calculate availability starting from the beginning of the *next* workday (e.g., 9 AM tomorrow).
        *   **Start Location:** `calculateTechnicianAvailability` currently uses `tech.current_location` (potentially updated by the last locked job). For the next day, we need to fetch and use the technician's `home_location_id`. Looking at `src/types/database.types.ts` and `src/supabase/technicians.ts`, the `Technician` type includes `home_location_id`, but `getActiveTechnicians` doesn't explicitly fetch the coordinates. We'll need to adjust the Supabase query to join the `addresses` table based on `home_location_id`.
    *   **Time Windows:** `prepareOptimizationPayload` generates ISO time strings based on the calculated availability. This needs to be adjusted to reflect the next workday's 9:00 AM - 6:30 PM window.

**Proposed Plan:**

1.  **Modify `src/db/update.ts`:**
    *   In `updateJobStatuses`, change the status applied to `unassignedIds` from `'pending_review'` to `'queued_next_day'`. Add a check: if an item ID corresponds to a *bundle*, update *all* jobs within that bundle to `'queued_next_day'`.

2.  **Modify `src/supabase/technicians.ts`:**
    *   Update `getActiveTechnicians` to perform a join with the `addresses` table on `home_location_id` to fetch the `lat` and `lng` of the home location. Add an optional parameter (e.g., `useHomeLocationAsCurrent`) to the function, or create a new function.

3.  **Modify `src/supabase/jobs.ts`:**
    *   Update `getRelevantJobs` (or create `getOverflowJobs`) to accept a specific status filter, allowing it to fetch only jobs marked as `'queued_next_day'`.

4.  **Create `src/scheduler/availabilityNextDay.ts` (or modify `availability.ts`):**
    *   Create a new function, e.g., `calculateNextDayTechnicianAvailability(technicians: Technician[])`.
    *   This function will:
        *   Calculate the start and end Date objects for the *next* working day (e.g., tomorrow 9:00 AM and tomorrow 6:30 PM).
        *   Iterate through technicians.
        *   Set `earliest_availability` to the start of the next working day ISO string.
        *   Set `current_location` to the fetched `home_location` coordinates.
        *   Set `latestEndTimeISO` (perhaps add this field to the Technician type temporarily for planning) to the end of the next working day. *Alternatively, handle this directly in the payload step.*

5.  **Modify `src/scheduler/payload.ts`:**
    *   Adjust `prepareOptimizationPayload` to handle the next-day scenario. It might need a flag or different inputs.
    *   When planning for the next day:
        *   Use the technician's `home_location` (passed in via the modified `Technician` object) as the starting point.
        *   Generate `earliestStartTimeISO` and `latestEndTimeISO` based on the next workday's start/end times (provided by the new availability calculation or calculated here).

6.  **Modify `src/scheduler/orchestrator.ts` (`runFullReplan`):**
    *   **Pass 1 (Today):**
        *   Run fetching, availability (`calculateTechnicianAvailability`), bundling, eligibility, payload prep, and optimization call as currently implemented.
        *   Call `updateJobStatuses`, which now marks unassigned jobs as `'queued_next_day'`. Store the returned `unassignedItemIds`.
    *   **Check for Overflow:** If `unassignedItemIds` is not empty:
        *   **Log:** Indicate that overflow exists and next-day planning is starting.
        *   **Pass 2 (Next Day):**
            *   **Fetch Data:** Call `getRelevantJobs` filtering for `'queued_next_day'`. Call `getActiveTechnicians` ensuring home locations are fetched.
            *   **Calculate Availability:** Call the new `calculateNextDayTechnicianAvailability` function.
            *   **Bundle & Eligibility:** Run `bundleQueuedJobs` and `determineTechnicianEligibility` on the overflow jobs.
            *   **Prepare Payload:** Call `prepareOptimizationPayload`, ensuring it uses the next-day availability, home locations, and generates next-day time windows.
            *   **Call Optimization:** Call `callOptimizationService` with the next-day payload.
            *   **Update DB:** Call `updateJobStatuses` again. Jobs successfully scheduled in Pass 2 could get status `scheduled_next_day`. Jobs *still* unassigned after Pass 2 might revert to `pending_review` (indicating they couldn't fit even on the next day).

7.  **Update Documentation (`TASK.md`, `README.md`, `PLANNING.md`):** Add notes about the two-pass planning process, the new job status (`queued_next_day`), and the use of home locations for the second pass. Add tasks to `TASK.md` for these changes.

8.  **Address Python `EPOCH`:** The floating `EPOCH` issue in `optimize-service/main.py` becomes more critical with multi-day planning. Add a task or prioritize fixing this to use a stable reference point (like Unix epoch) for time conversions.

This approach reuses most existing logic modules (`bundling`, `eligibility`, `optimize`, `results`) and primarily modifies the orchestration, data fetching, availability calculation, and payload generation steps for the second pass.

Now, regarding the looping overflow solution: Yes, we can incorporate looping into the overflow handling in `src/scheduler/orchestrator.ts`. Instead of just running a single "Pass 2" for the next day, we can wrap that logic in a loop that attempts planning for subsequent days if overflow persists.

**Refined Plan (incorporating looping):**

1.  **(Done)** Modify `src/db/update.ts` to mark overflow as `'queued_next_day'`.
2.  **(To Do)** Modify `src/supabase/technicians.ts` to fetch home locations.
3.  **(To Do)** Modify `src/supabase/jobs.ts` to filter by status `'queued_next_day'`.
4.  **Modify `src/scheduler/availability.ts` (or create new):**
    *   Create a function `calculateAvailabilityForDay(technicians: Technician[], targetDate: Date)`:
        *   Takes a `targetDate` (representing the start of the day to plan for).
        *   Calculates the start (9:00 AM) and end (6:30 PM) of the *working day* represented by `targetDate`. **Crucially, this needs to skip weekends (Sat/Sun) automatically.** If `targetDate` is a weekend, it should maybe return null or indicate no availability.
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
            *   **Fetch Data:** Get `'queued_next_day'` jobs. Get technicians with home locations.
            *   **Calculate Availability:** Call `calculateAvailabilityForDay(technicians, currentPlanningDate)`.
                *   If it's a non-working day (weekend/holiday - basic weekend check for now), `continue` the loop to the next day.
                *   If no technicians are available (e.g., function returns empty or specific signal), `continue`.
            *   **Bundle & Eligibility:** Run on the *current* set of overflow jobs.
            *   **Prepare Payload:** Call `prepareOptimizationPayload` with the technicians (having future availability/home locations) and the current overflow items.
            *   **Call Optimization:** Call `callOptimizationService`.
            *   **Process Results & Update DB:**
                *   Get the *new* `unassignedItemIds` from this loop's optimization result.
                *   Determine which jobs were *successfully* scheduled in *this loop*.
                *   Call `updateJobStatuses`:
                    *   Update successfully scheduled jobs to `scheduled_future` (or similar).
                    *   Update jobs that are *still* unassigned to remain `'queued_next_day'`.
                *   Update the main `unassignedItemIds` variable with the list returned by the optimizer for the next loop iteration.
    *   **Final Cleanup:** After the loop, any jobs *still* having status `'queued_next_day'` could be updated to `'pending_review'` (or maybe a new status like `'unschedulable_overflow'`) to indicate they couldn't be placed within the N-day window.

**Implementation Order:**

We should proceed with the plan outlined previously, starting with the modifications needed for the single next-day pass, as those are prerequisites for the looping logic:

1.  `src/db/update.ts` (Change overflow status)
2.  `src/supabase/technicians.ts` (Fetch home locations)
3.  `src/supabase/jobs.ts` (Filter by new status)
4.  `src/scheduler/availability.ts` (Create `calculateAvailabilityForDay` with target date and weekend skip)
5.  `src/scheduler/payload.ts` (Adapt to use future availability/locations)
6.  `src/scheduler/orchestrator.ts` (Implement the loop structure)
7.  Documentation updates.

Shall I start with modifying `src/db/update.ts` to change the overflow status?

