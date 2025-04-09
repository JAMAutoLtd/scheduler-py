import { SupabaseClient } from '@supabase/supabase-js';
import { getActiveTechnicians } from '../supabase/technicians';
import { getRelevantJobs } from '../supabase/jobs';
import { Job, JobStatus, Technician } from '../types/database.types';
import { calculateTechnicianAvailability } from './availability';
import { bundleQueuedJobs } from './bundling';
import { determineTechnicianEligibility } from './eligibility';
import { prepareOptimizationPayload } from './payload';
import { callOptimizationService } from './optimize';
import { processOptimizationResults } from './results';
import { updateJobStatuses } from '../db/update';
import { supabase } from '../supabase/client'; // Assuming supabase client is exported from here

const LOCKED_JOB_STATUSES: JobStatus[] = ['en_route', 'in_progress', 'fixed_time'];
const SCHEDULABLE_JOB_STATUS: JobStatus = 'queued';
const FIXED_TIME_JOB_STATUS: JobStatus = 'fixed_time';

/**
 * Orchestrates the entire job replanning process.
 *
 * @param {SupabaseClient<any>} dbClient - The Supabase client instance.
 * @returns {Promise<void>} Resolves when the replan is complete, or rejects on error.
 */
export async function runFullReplan(dbClient: SupabaseClient<any>): Promise<void> {
  console.log('\n--- Starting Full Replan Cycle ---');
  try {
    // 1. Fetch Data
    console.log('Step 1: Fetching data from Supabase...');
    const [technicians, allJobs] = await Promise.all([
      getActiveTechnicians(),
      getRelevantJobs(),
    ]);

    if (technicians.length === 0) {
      console.warn('No active technicians found. Aborting replan.');
      return;
    }
    console.log(`Found ${technicians.length} technicians and ${allJobs.length} relevant jobs.`);

    // 2. Separate Jobs
    console.log('Step 2: Separating locked and schedulable jobs...');
    const lockedJobs = allJobs.filter(job => LOCKED_JOB_STATUSES.includes(job.status));
    const schedulableJobs = allJobs.filter(job => job.status === SCHEDULABLE_JOB_STATUS);
    const fixedTimeJobs = lockedJobs.filter(job => job.status === FIXED_TIME_JOB_STATUS && job.fixed_schedule_time);
    console.log(`Found ${lockedJobs.length} locked jobs, ${schedulableJobs.length} schedulable jobs, ${fixedTimeJobs.length} with fixed times.`);

    if (schedulableJobs.length === 0) {
      console.log('No queued jobs to schedule. Replan cycle complete.');
      return;
    }

    // 3. Calculate Availability
    console.log('Step 3: Calculating technician availability...');
    calculateTechnicianAvailability(technicians, lockedJobs);

    // 4. Bundle Jobs
    console.log('Step 4: Bundling queued jobs...');
    const bundledItems = bundleQueuedJobs(schedulableJobs);

    // 5. Determine Eligibility
    console.log('Step 5: Determining technician eligibility...');
    const eligibleItems = await determineTechnicianEligibility(bundledItems, technicians);

    if (eligibleItems.length === 0) {
      console.log('No eligible items remaining after eligibility check. Replan cycle complete.');
      // Potentially update originally queued jobs to 'pending_review' here if needed
      return;
    }

    // 6. Prepare Payload
    console.log('Step 6: Preparing optimization payload (including travel times)...');
    const optimizationPayload = await prepareOptimizationPayload(technicians, eligibleItems, fixedTimeJobs);

    if (optimizationPayload.items.length === 0) {
        console.log('No items could be prepared for optimization (e.g., missing coords). Replan cycle complete.');
        // Handle jobs that were in eligibleItems but not in payload.items (likely set to pending_review)
        // This might require comparing eligibleItems IDs with payload.items IDs
        // For now, just exit.
        return;
    }

    // 7. Call Optimization Service
    console.log('Step 7: Calling optimization microservice...');
    const optimizationResponse = await callOptimizationService(optimizationPayload);

    // 8. Process Results (Handled within updateJobStatuses for now)
    // const processedResults = processOptimizationResults(optimizationResponse);

    // 9. Update Database
    console.log('Step 9: Updating database with optimization results...');
    await updateJobStatuses(dbClient, optimizationResponse);

    console.log('--- Full Replan Cycle Completed Successfully ---');

  } catch (error) {
    console.error('--- Full Replan Cycle Failed ---');
    console.error(error);
    // Add more robust error handling/reporting as needed
    // Potentially update job statuses to a specific 'error' or 'retry' state
    throw error; // Re-throw to indicate failure
  }
}

// Example of how to run it (e.g., from index.ts or a trigger script)
/*
import { runFullReplan } from './scheduler/orchestrator';
import { supabase } from './supabase/client';

async function main() {
  try {
    await runFullReplan(supabase);
  } catch (error) {
    console.error('Main execution failed:', error);
    process.exit(1); // Exit with error code
  }
}

main();
*/ 