import {
    OptimizationResponsePayload,
    TechnicianRoute,
    RouteStop
} from '../types/optimization.types';

// Define the ETA window in minutes (e.g., +/- 30 minutes for a 1-hour window)
// const ETA_WINDOW_MINUTES = 30; // Removed

/**
 * Represents the processed results of an optimization run,
 * ready for database updates.
 */
export interface ProcessedSchedule {
    scheduledJobs: ScheduledJobUpdate[];
    unassignedItemIds: string[]; // IDs of OptimizationItems (job_XXX or bundle_YYY)
}

/**
 * Information needed to update a single scheduled job in the database.
 */
export interface ScheduledJobUpdate {
    jobId: number; // The original database job ID
    technicianId: number;
    estimatedSchedISO: string; // Calculated service start time
    // estimatedSchedEndISO: string; // Calculated service end time // Removed
    // customerEtaStartISO: string; // Calculated ETA window start // Removed
    // customerEtaEndISO: string; // Calculated ETA window end // Removed
}

/**
 * Processes the raw response from the optimization service into structured
 * data for updating the database.
 *
 * @param {OptimizationResponsePayload} response - The payload received from the optimization service.
 * @returns {ProcessedSchedule} - Structured results including jobs to update and unassigned items.
 * @throws {Error} If the response status is 'error'.
 */
export function processOptimizationResults(
    response: OptimizationResponsePayload
): ProcessedSchedule {
    console.log('Processing optimization results...');

    if (response.status === 'error') {
        console.error('Cannot process results: Optimization service returned an error.', response.message);
        throw new Error(`Optimization failed: ${response.message || 'Unknown error'}`);
    }

    const scheduledJobs: ScheduledJobUpdate[] = [];

    response.routes.forEach((route: TechnicianRoute) => {
        route.stops.forEach((stop: RouteStop) => {
            // Extract the job ID from the itemId (e.g., "job_123")
            if (stop.itemId.startsWith('job_')) {
                const jobId = parseInt(stop.itemId.split('_')[1], 10);
                if (!isNaN(jobId)) {
                    try {
                        const scheduledStartTime = new Date(stop.startTimeISO);
                        // const scheduledEndTime = new Date(stop.endTimeISO); // Removed

                        // Calculate ETA window - Removed
                        // const etaStart = new Date(scheduledStartTime);
                        // etaStart.setMinutes(etaStart.getMinutes() - ETA_WINDOW_MINUTES);
                        // const etaEnd = new Date(scheduledStartTime);
                        // etaEnd.setMinutes(etaEnd.getMinutes() + ETA_WINDOW_MINUTES);

                        scheduledJobs.push({
                            jobId: jobId,
                            technicianId: route.technicianId,
                            estimatedSchedISO: scheduledStartTime.toISOString(),
                            // estimatedSchedEndISO: scheduledEndTime.toISOString(), // Removed
                            // customerEtaStartISO: etaStart.toISOString(), // Removed
                            // customerEtaEndISO: etaEnd.toISOString(), // Removed
                        });
                    } catch (e) {
                        console.warn(`Error processing date for job ID ${jobId} from stop ${stop.itemId}:`, e);
                    }
                } else {
                    console.warn(`Could not parse job ID from itemId: ${stop.itemId}`);
                }
            }
            // Bundles are handled implicitly by scheduling their constituent jobs
        });
    });

    console.log(`Processed ${scheduledJobs.length} scheduled jobs from ${response.routes.length} routes.`);
    if (response.unassignedItemIds && response.unassignedItemIds.length > 0) {
        console.log(`Identified ${response.unassignedItemIds.length} unassigned items.`);
    }

    return {
        scheduledJobs: scheduledJobs,
        unassignedItemIds: response.unassignedItemIds || [],
    };
} 