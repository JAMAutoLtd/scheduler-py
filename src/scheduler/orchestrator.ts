import { SupabaseClient } from '@supabase/supabase-js';
import { getActiveTechnicians } from '../supabase/technicians';
import { getRelevantJobs, getJobsByStatus } from '../supabase/jobs';
import { Job, JobStatus, Technician, JobBundle, SchedulableItem, TechnicianAvailability, Address } from '../types/database.types';
import { calculateTechnicianAvailability, calculateAvailabilityForDay } from './availability';
import { bundleQueuedJobs } from './bundling';
import { determineTechnicianEligibility } from './eligibility';
import { prepareOptimizationPayload } from './payload';
import { callOptimizationService } from './optimize';
import { processOptimizationResults, ScheduledJobUpdate } from './results';
import { updateJobs, JobUpdateOperation } from '../db/update';

const LOCKED_JOB_STATUSES: JobStatus[] = ['en_route', 'in_progress', 'fixed_time'];
const INITIAL_SCHEDULABLE_STATUS: JobStatus = 'queued';
const PENDING_REVIEW_STATUS: JobStatus = 'pending_review';
const FINAL_SUCCESS_STATUS: JobStatus = 'queued';
const MAX_OVERFLOW_ATTEMPTS = 4;

interface FinalAssignment {
    technicianId: number;
    estimatedSchedISO: string;
}

/**
 * Handles both individual jobs and bundles.
 * Requires a map populated with the SchedulableItems that were *eligible* and sent to the optimizer for the relevant pass.
 *
 * @param {string[]} itemIds - Array of item IDs (e.g., 'job_123', 'bundle_45') reported as unassigned by the optimizer.
 * @param {Map<string, SchedulableItem>} eligibleItemMap - A map where keys are item IDs and values are the corresponding SchedulableItem objects that were *eligible* for the optimization pass.
 * @returns {Set<number>} A Set containing the unique IDs of all constituent jobs belonging to the unassigned items.
 */
function mapItemsToJobIds(itemIds: string[], eligibleItemMap: Map<string, SchedulableItem>): Set<number> {
    const jobIds = new Set<number>();
    for (const itemId of itemIds) {
        const item = eligibleItemMap.get(itemId);
        if (!item) {
            console.warn(`Could not find item details for ID: ${itemId} in eligibleItemMap during mapItemsToJobIds.`);
            continue;
        }

        if (itemId.startsWith('job_')) {
            if ('job' in item) {
                 const jobId = item.job.id;
                 jobIds.add(jobId);
            } else {
                 console.warn(`Expected SchedulableJob but got different item type for ID: ${itemId}`);
            }
        } else if (itemId.startsWith('bundle_') && 'jobs' in item) {
            item.jobs.forEach(job => jobIds.add(job.id));
        } else {
            console.warn(`Could not determine job IDs for item/ID: ${itemId}`);
        }
    }
    return jobIds;
}

/**
 * Orchestrates the full job replanning process for a given day and subsequent overflow days.
 * Fetches necessary data, calculates availability, bundles jobs, determines eligibility,
 * calls an external optimization service, processes results internally, and performs a single
 * final database update.
 *
 * @param {SupabaseClient<any>} dbClient - The Supabase client instance for database interactions.
 * @returns {Promise<void>} A promise that resolves when the replan cycle is complete or rejects if an error occurs.
 * @throws {Error} Throws an error if a critical step fails (e.g., initial data fetch, optimization call, final DB update).
 */
export async function runFullReplan(dbClient: SupabaseClient<any>): Promise<void> {
  console.log('\n--- Starting Full Replan Cycle (Refactored Approach) ---');

  let allTechnicians: Technician[] = [];
  let jobsToPlan = new Set<number>();
  const finalAssignments = new Map<number, FinalAssignment>();
  const eligibleItemMapForPass = new Map<string, SchedulableItem>(); // Map used *per pass* for result mapping
  let allFetchedJobsMap = new Map<number, Job>();

  try {
    // ========================================\n    // == Initial Data Fetch & Setup         ==\n    // ========================================
    console.log('Step 0: Fetching initial technicians and relevant jobs...');
    const [fetchedTechnicians, relevantJobsToday] = await Promise.all([
      getActiveTechnicians(),
      getRelevantJobs(),
    ]);
    allTechnicians = fetchedTechnicians;

    if (allTechnicians.length === 0) {
      console.warn('No active technicians found. Aborting replan.');
      return;
    }
    console.log(`Found ${allTechnicians.length} technicians and ${relevantJobsToday.length} relevant jobs.`);

    relevantJobsToday.forEach(job => {
        allFetchedJobsMap.set(job.id, job);
        if (job.status === INITIAL_SCHEDULABLE_STATUS) {
            jobsToPlan.add(job.id);
        }
    });

    const lockedJobsToday = relevantJobsToday.filter(job => LOCKED_JOB_STATUSES.includes(job.status));
    const fixedTimeJobsToday = lockedJobsToday.filter(job => job.status === 'fixed_time' && job.fixed_schedule_time);
    console.log(`Initial state: ${jobsToPlan.size} jobs to plan, ${lockedJobsToday.length} locked, ${fixedTimeJobsToday.length} fixed time.`);

    // ========================================\n    // == Pass 1: Plan for Today             ==\n    // ========================================
    if (jobsToPlan.size > 0) {
        console.log('\n--- Pass 1: Planning for Today ---');
        eligibleItemMapForPass.clear(); // Ensure map is clear for this pass

        console.log('Step 1.1: Calculating technician availability for today...');
        calculateTechnicianAvailability(allTechnicians, lockedJobsToday);

        const jobsForPass1Details = Array.from(jobsToPlan).map(id => allFetchedJobsMap.get(id)).filter((job): job is Job => !!job);

        console.log('Step 1.2: Bundling jobs for today...');
        const bundledItemsToday: SchedulableItem[] = bundleQueuedJobs(jobsForPass1Details);

        console.log('Step 1.3: Determining eligibility for today...');
        const eligibleItemsToday: SchedulableItem[] = await determineTechnicianEligibility(bundledItemsToday, allTechnicians);
        eligibleItemsToday.forEach(item => eligibleItemMapForPass.set('job' in item ? `job_${item.job.id}` : `bundle_${item.order_id}`, item));

        if (eligibleItemsToday.length > 0) {
            console.log('Step 1.4: Preparing optimization payload for today...');
            const optimizationPayloadToday = await prepareOptimizationPayload(allTechnicians, eligibleItemsToday, fixedTimeJobsToday); // Pass eligible items

            if (optimizationPayloadToday.items.length > 0) {
                 console.log('Step 1.5: Calling optimization microservice for today...');
                 const optimizationResponseToday = await callOptimizationService(optimizationPayloadToday);

                 console.log('Step 1.6: Processing optimization results for today...');
                 const processedResultsToday = processOptimizationResults(optimizationResponseToday);

                 console.log('Step 1.7: Updating internal state...');
                 // Process scheduled items using ScheduledJobUpdate
                 processedResultsToday.scheduledJobs.forEach((update: ScheduledJobUpdate) => {
                     if (jobsToPlan.has(update.jobId)) {
                         finalAssignments.set(update.jobId, {
                             technicianId: update.technicianId,
                             estimatedSchedISO: update.estimatedSchedISO,
                         });
                         jobsToPlan.delete(update.jobId);
                     } else {
                          console.warn(`Job ${update.jobId} scheduled by optimizer but was not in \'jobsToPlan\' set.`);
                     }
                 });

                 // Process unassigned items using mapItemsToJobIds and the map populated with *eligible* items
                 const unassignedJobIdsToday = mapItemsToJobIds(processedResultsToday.unassignedItemIds, eligibleItemMapForPass);
                 unassignedJobIdsToday.forEach(jobId => {
                    if (!jobsToPlan.has(jobId) && allFetchedJobsMap.get(jobId)?.status === INITIAL_SCHEDULABLE_STATUS) {
                        console.warn(`Job ${jobId} reported unassigned but was missing from \'jobsToPlan\' set. Adding back.`);
                        jobsToPlan.add(jobId); // Ensure it remains for overflow/pending
                    }
                 });
                 console.log(`Pass 1 Results: ${finalAssignments.size} jobs assigned, ${jobsToPlan.size} jobs remain.`);

            } else {
                console.log('No items could be prepared for optimization payload for today.');
            }
        } else {
            console.log('No eligible items found for today after bundling and eligibility checks.');
        }
    } else {
        console.log('No initial jobs to plan for today.');
    }
    console.log(`--- Pass 1 Complete. ${jobsToPlan.size} jobs remaining to plan. ---`);

    // ========================================\n    // == Pass 2+: Plan for Overflow        ==\n    // ========================================
    let loopCount = 0;
    let basePlanningDate = new Date();

    while (jobsToPlan.size > 0 && loopCount < MAX_OVERFLOW_ATTEMPTS) {
        loopCount++;
        const currentPlanningDate = new Date(basePlanningDate);
        currentPlanningDate.setUTCDate(basePlanningDate.getUTCDate() + loopCount);
        const planningDateStr = currentPlanningDate.toISOString().split('T')[0];
        console.log(`\n--- Overflow Pass ${loopCount}: Planning for ${planningDateStr} ---`);
        eligibleItemMapForPass.clear(); // Clear map for this pass

        console.log(`Step ${loopCount}.1: Fetching technicians with home locations...`);
        const techsForLoop = await getActiveTechnicians();
        if (techsForLoop.length === 0) {
            console.warn(`No active technicians found for ${planningDateStr}. Cannot plan overflow. Stopping loop.`);
            break;
        }

        const jobsForLoopDetails = Array.from(jobsToPlan)
            .map(id => allFetchedJobsMap.get(id))
            .filter((job): job is Job => {
                if (!job) console.warn(`Missing job detail in allFetchedJobsMap for ID during overflow pass ${loopCount}`);
                return !!job;
            });

        if (jobsForLoopDetails.length === 0 && jobsToPlan.size > 0) {
             console.warn(`Job IDs exist in jobsToPlan but details not found in allFetchedJobsMap for ${planningDateStr}. Ending loop.`);
             jobsToPlan.clear();
             break;
        }
         console.log(`Attempting to plan ${jobsToPlan.size} remaining jobs.`);


        console.log(`Step ${loopCount}.2: Calculating availability for ${planningDateStr}...`);
        const availabilityThisDay: TechnicianAvailability[] = calculateAvailabilityForDay(techsForLoop, currentPlanningDate);
        if (availabilityThisDay.length === 0) {
            console.log(`No technician availability on ${planningDateStr} (Weekend/Holiday?). Skipping day.`);
            continue;
        }
        const availableTechIdsThisDay = new Set(availabilityThisDay.map(a => a.technicianId));
        const availableTechsThisDay = techsForLoop.filter(t => availableTechIdsThisDay.has(t.id));
        console.log(`Found ${availableTechsThisDay.length} technicians available on ${planningDateStr}.`);

        console.log(`Step ${loopCount}.3: Bundling remaining jobs for ${planningDateStr}...`);
        const bundledItemsLoop: SchedulableItem[] = bundleQueuedJobs(jobsForLoopDetails);

        console.log(`Step ${loopCount}.4: Determining eligibility for ${planningDateStr}...`);
        const eligibleItemsLoop: SchedulableItem[] = await determineTechnicianEligibility(bundledItemsLoop, availableTechsThisDay);
        eligibleItemsLoop.forEach(item => eligibleItemMapForPass.set('job' in item ? `job_${item.job.id}` : `bundle_${item.order_id}`, item));

        if (eligibleItemsLoop.length === 0) {
            console.log(`No eligible items for ${planningDateStr} after bundling and eligibility. Continuing loop.`);
            continue;
        }

        console.log(`Step ${loopCount}.5: Preparing optimization payload for ${planningDateStr}...`);
        const optimizationPayloadLoop = await prepareOptimizationPayload(availableTechsThisDay, eligibleItemsLoop, [], availabilityThisDay); // Pass eligible items

        if (optimizationPayloadLoop.items.length === 0) {
            console.log(`No items could be prepared for optimization for ${planningDateStr}. Continuing loop.`);
            continue;
        }

        console.log(`Step ${loopCount}.6: Calling optimization microservice for ${planningDateStr}...`);
        const optimizationResponseLoop = await callOptimizationService(optimizationPayloadLoop);

        console.log(`Step ${loopCount}.7: Processing optimization results for ${planningDateStr}...`);
        const processedResultsLoop = processOptimizationResults(optimizationResponseLoop);

        console.log(`Step ${loopCount}.8: Updating internal state...`);
        // Process scheduled items using ScheduledJobUpdate
        processedResultsLoop.scheduledJobs.forEach((update: ScheduledJobUpdate) => {
             if (jobsToPlan.has(update.jobId)) {
                 finalAssignments.set(update.jobId, {
                     technicianId: update.technicianId,
                     estimatedSchedISO: update.estimatedSchedISO,
                 });
                 jobsToPlan.delete(update.jobId);
             } else {
                  console.warn(`Job ${update.jobId} scheduled by optimizer in overflow pass but was not in \'jobsToPlan\' set.`);
             }
        });

        // Process unassigned items using mapItemsToJobIds and the map populated with *eligible* items
        const unassignedJobIdsLoop = mapItemsToJobIds(processedResultsLoop.unassignedItemIds, eligibleItemMapForPass);
        unassignedJobIdsLoop.forEach(jobId => {
           if (!jobsToPlan.has(jobId) && allFetchedJobsMap.get(jobId)?.status === INITIAL_SCHEDULABLE_STATUS) {
               console.warn(`Job ${jobId} reported unassigned in overflow pass but was missing from \'jobsToPlan\' set. Adding back.`);
               jobsToPlan.add(jobId); // Ensure it remains for pending review
           }
        });

        console.log(`--- Overflow Pass ${loopCount} Complete. ${jobsToPlan.size} jobs remaining to plan. ---`);
    } // End while loop

    // ========================================\n    // == Final Database Update             ==\n    // ========================================
    console.log('\n--- Final Database Update ---');
    const finalUpdates: JobUpdateOperation[] = [];

    finalAssignments.forEach((assignment, jobId) => {
        finalUpdates.push({
            jobId: jobId,
            data: {
                status: FINAL_SUCCESS_STATUS, // 'queued'
                assigned_technician: assignment.technicianId,
                estimated_sched: assignment.estimatedSchedISO,
            }
        });
    });

    jobsToPlan.forEach(jobId => {
        finalUpdates.push({
            jobId: jobId,
            data: {
                status: PENDING_REVIEW_STATUS,
                assigned_technician: null,
                estimated_sched: null,
            }
        });
    });

    if (finalUpdates.length > 0) {
        console.log(`Applying final updates: ${finalAssignments.size} jobs to \'${FINAL_SUCCESS_STATUS}\', ${jobsToPlan.size} jobs to \'${PENDING_REVIEW_STATUS}\'.`);
        await updateJobs(dbClient, finalUpdates);
    } else {
        console.log('No final database updates required (no jobs planned or failed).');
    }

    console.log('--- Full Replan Cycle Completed Successfully ---');

  } catch (error) {
    console.error('--- Full Replan Cycle Failed ---');
    if (error instanceof Error) {
        console.error(`Error Message: ${error.message}`);
        console.error(`Error Stack: ${error.stack}`);
    } else {
        console.error('An unexpected error occurred:', error);
    }
    throw error; // Re-throw
  }
}

/* Example run block remains the same */
/*
import { runFullReplan } from './scheduler/orchestrator';
import { supabase } from './supabase/client';

async function main() {
  if (!supabase) {
      console.error("Supabase client is not initialized. Cannot run replan.");
      process.exit(1);
  }
  try {
    await runFullReplan(supabase);
    console.log("Main execution finished.");
  } catch (error) {
    console.error('Main execution failed.');
    process.exit(1);
  }
}
// main();
*/ 