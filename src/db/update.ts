import { SupabaseClient } from '@supabase/supabase-js';
// NOTE: While the SupabaseClient is often typed with an auto-generated `Database` type,
// this function uses manually defined types from this project for the update payload.
// Ensure consistency if the auto-generated type is used elsewhere.
import { Job } from '../types/database.types'; // Using manual Job interface
import {
    OptimizationResponsePayload,
    TechnicianRoute,
    RouteStop,
} from '../types/optimization.types';
import { PostgrestFilterBuilder } from '@supabase/postgrest-js'; // Import needed type

// Define the shape of the data used for updating jobs, derived from the manual Job interface
type JobUpdateData = Partial<Pick<Job, 'assigned_technician' | 'estimated_sched' | 'status'>>;

// Helper type for tracking updates along with their original IDs
type UpdateTask = {
    id: number | string; // Job ID or Item ID
    type: 'scheduled' | 'overflow';
    // Supabase query builder - explicitly typing it
    query: PostgrestFilterBuilder<any, any, any, any, any>; // Adjust schema/table/return types if known
};

/**
 * Extracts the numeric job ID from an item ID string (e.g., "job_123" -> 123).
 * Returns null if the format is invalid.
 */
function extractJobId(itemId: string): number | null {
    if (itemId?.startsWith('job_')) {
        const idPart = itemId.substring(4);
        const jobId = parseInt(idPart, 10);
        return !isNaN(jobId) ? jobId : null;
    }
    // Handle bundle IDs if they need specific DB updates (currently ignored)
    if (itemId?.startsWith('bundle_')) {
        console.warn(`Skipping database update for bundle ID: ${itemId}`);
        return null;
    }
    console.warn(`Unrecognized item ID format for DB update: ${itemId}`);
    return null;
}

/**
 * Updates the status of jobs in the database based on the scheduling results from the optimization service.
 *
 * @param supabase The Supabase client instance.
 * @param results The OptimizationResponsePayload received from the optimization microservice.
 * @returns A promise that resolves when the updates are complete.
 * @throws Throws an error if any database update fails.
 */
export async function updateJobStatuses(
    supabase: SupabaseClient<any>, // Use <any> if Database type isn't available/correct
    results: OptimizationResponsePayload
): Promise<void> {
    console.log('Updating job statuses in database based on optimization response...');

    if (results.status === 'error') {
        console.error('Optimization service reported an error, skipping database updates:', results.message);
        throw new Error(`Optimization failed: ${results.message || 'Unknown error'}`);
    }

    const updateTasks: UpdateTask[] = [];

    // Prepare updates for scheduled jobs from routes
    results.routes.forEach((route: TechnicianRoute) => {
        route.stops.forEach((stop: RouteStop) => {
            const jobId = extractJobId(stop.itemId);
            if (jobId !== null) {
                const updateData: JobUpdateData = {
                    assigned_technician: route.technicianId,
                    estimated_sched: stop.startTimeISO, // Assuming startTimeISO is the correct field
                    status: 'scheduled',
                };
                const query = supabase
                    .from('jobs')
                    .update(updateData)
                    .eq('id', jobId); // Assuming primary key is 'id'
                updateTasks.push({ id: jobId, type: 'scheduled', query });
            }
        });
    });

    // Prepare updates for overflow jobs (unassigned items)
    (results.unassignedItemIds || []).forEach((itemId: string) => {
        const jobId = extractJobId(itemId);
        if (jobId !== null) {
            const updateData: JobUpdateData = {
                status: 'pending_review',
                assigned_technician: null,
                estimated_sched: null,
            };
            const query = supabase
                .from('jobs')
                .update(updateData)
                .eq('id', jobId); // Assuming primary key is 'id'
            updateTasks.push({ id: jobId, type: 'overflow', query });
        }
    });

    if (updateTasks.length === 0) {
        console.log('No job updates required based on optimization results.');
        return;
    }

    console.log(`Attempting to update ${updateTasks.filter(t => t.type === 'scheduled').length} scheduled jobs and ${updateTasks.filter(t => t.type === 'overflow').length} overflow jobs.`);

    // Execute all updates in parallel
    // Pass the query builders directly to Promise.all
    try {
        const updateResults = await Promise.all(updateTasks.map(task => task.query));

        let scheduledUpdatedCount = 0;
        let overflowUpdatedCount = 0;
        let errorCount = 0;

        // Check results - Supabase returns { data, error }
        updateResults.forEach((result, index) => {
            const task = updateTasks[index];
            if (result.error) {
                console.error(`Error updating job ${task.id} (${task.type}):`, result.error);
                // Collect errors but continue checking others
                errorCount++;
            } else {
                // Log success (optional)
                // console.log(`Successfully updated job ${task.id} (${task.type})`);
                if (task.type === 'scheduled') scheduledUpdatedCount++;
                if (task.type === 'overflow') overflowUpdatedCount++;
            }
        });

        console.log(`Update summary: ${scheduledUpdatedCount} scheduled jobs updated, ${overflowUpdatedCount} overflow jobs updated.`);

        if (errorCount > 0) {
            // Throw a single error summarizing the failures
            throw new Error(`${errorCount} database update(s) failed. Check logs for details.`);
        }

    } catch (error) {
        console.error('Error performing batch job updates:', error);
        // Rethrow or handle as appropriate
        if (error instanceof Error) {
            throw error;
        }
        throw new Error('An unknown error occurred during database updates.');
    }
} 