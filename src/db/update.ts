import { SupabaseClient } from '@supabase/supabase-js';
// NOTE: While the SupabaseClient is often typed with an auto-generated `Database` type,
// this function uses manually defined types from this project for the update payload.
// Ensure consistency if the auto-generated type is used elsewhere.
import { Job, JobStatus } from '../types/database.types'; // Using manual Job interface

// Define the shape of the data used for updating jobs, derived from the manual Job interface
// Allows updating only specific fields relevant to scheduling outcomes.
export type JobUpdatePayload = Partial<Pick<Job, 'assigned_technician' | 'estimated_sched' | 'status'>>;

// Type for defining a single update operation
export interface JobUpdateOperation {
    jobId: number;
    data: JobUpdatePayload;
}

/**
 * Updates multiple jobs in the database with specific data.
 *
 * @param supabase The Supabase client instance.
 * @param updates An array of JobUpdateOperation objects, each specifying a jobId and the data to update.
 * @returns A promise that resolves when all updates are complete.
 * @throws Throws an error if any database update fails, summarizing the number of failures.
 */
export async function updateJobs(
    supabase: SupabaseClient<any>, // Use <any> if Database type isn't available/correct
    updates: JobUpdateOperation[]
): Promise<void> {
    if (!updates || updates.length === 0) {
        console.log('No job updates provided.');
        return;
    }

    console.log(`Attempting to update ${updates.length} jobs...`);

    // Create an array of Supabase update promises
    const updatePromises = updates.map(update => {
        // Double-check that data is not empty or null
        if (!update.data || Object.keys(update.data).length === 0) {
             console.warn(`Skipping update for job ${update.jobId} due to empty update data.`);
             // Return a resolved promise to avoid breaking Promise.all
             // Use a structure similar to Supabase's response for consistency, but signal skipped
             return Promise.resolve({ data: null, error: null, count: null, status: 204, statusText: 'No Content (skipped)' });
        }

        return supabase
            .from('jobs')
            .update(update.data)
            .eq('id', update.jobId);
    });

    // Execute all updates in parallel
    try {
        const updateResults = await Promise.all(updatePromises);

        let successCount = 0;
        let errorCount = 0;
        const failedJobIds: number[] = [];

        // Check results - Supabase returns { data, error, ... }
        updateResults.forEach((result, index) => {
            const jobId = updates[index].jobId;
             // Handle skipped updates (they won't have an error object matching Supabase error structure)
             if (result.status === 204 && result.statusText?.includes('(skipped)')) {
                // Already warned above, do nothing here
                return;
            }

            if (result.error) {
                console.error(`Error updating job ${jobId}:`, result.error);
                errorCount++;
                failedJobIds.push(jobId);
            } else {
                // Supabase update returns data (often null/empty array unless returning Minimal) and no error on success
                successCount++;
            }
        });

        console.log(`Update summary: ${successCount} jobs updated successfully, ${errorCount} updates failed.`);

        if (errorCount > 0) {
            // Throw a single error summarizing the failures
            throw new Error(`${errorCount} database update(s) failed for job IDs: ${failedJobIds.join(', ')}. Check logs for details.`);
        }

    } catch (error) {
        console.error('Error performing batch job updates:', error);
        // Rethrow or handle as appropriate
        if (error instanceof Error) {
            throw error; // Keep the specific error message (like the one with failed IDs)
        }
        throw new Error('An unknown error occurred during database updates.');
    }
} 