import { Technician, Job, JobBundle, SchedulableJob, SchedulableItem, VanEquipment } from '../types/database.types';
import { getRequiredEquipmentForJob, getEquipmentForVans } from '../supabase/equipment';

/**
 * Determines the list of eligible technicians for a given set of required equipment models.
 *
 * @param {string[]} requiredModels - Array of required equipment model strings.
 * @param {Technician[]} technicians - Array of all available technicians.
 * @param {Map<number, VanEquipment[]>} vanEquipmentMap - Map of van ID to its equipment list.
 * @returns {number[]} An array of technician IDs eligible to perform the job/bundle.
 */
function findEligibleTechnicians(
    requiredModels: string[],
    technicians: Technician[],
    vanEquipmentMap: Map<number, VanEquipment[]>
): number[] {
    if (requiredModels.length === 0) {
        // If no specific equipment is required, all technicians are eligible
        return technicians.map(tech => tech.id);
    }

    const eligibleTechIds: number[] = [];
    for (const tech of technicians) {
        if (tech.assigned_van_id === null) continue; // Skip techs without vans

        const techEquipment = vanEquipmentMap.get(tech.assigned_van_id) || [];
        const techModels = new Set(techEquipment.map(e => e.equipment_model).filter(m => !!m)); // Get unique models in the van

        // Check if the technician's van has ALL required models
        const hasAllRequired = requiredModels.every(reqModel => techModels.has(reqModel));

        if (hasAllRequired) {
            eligibleTechIds.push(tech.id);
        }
    }
    return eligibleTechIds;
}

/**
 * Processes schedulable items (bundles and single jobs) to determine required equipment
 * and find eligible technicians for each.
 * Breaks bundles into single jobs if no technician is eligible for the bundle.
 *
 * @param {SchedulableItem[]} initialItems - Array of items from the bundling step.
 * @param {Technician[]} technicians - Array of available technicians.
 * @returns {Promise<SchedulableItem[]>} A promise resolving to the updated array of schedulable items
 *                                        with eligibility information filled in, and potentially broken bundles.
 */
export async function determineTechnicianEligibility(
    initialItems: SchedulableItem[],
    technicians: Technician[],
): Promise<SchedulableItem[]> {
    console.log(`Determining eligibility for ${initialItems.length} schedulable items...`);

    // 1. Fetch equipment for all technicians' vans at once
    const allVanIds = technicians
        .map(tech => tech.assigned_van_id)
        .filter((id): id is number => id !== null && id !== undefined); // Filter out null/undefined van IDs
    const vanEquipmentMap = await getEquipmentForVans(Array.from(new Set(allVanIds))); // Ensure unique IDs

    const finalItems: SchedulableItem[] = [];

    for (const item of initialItems) {
        let requiredModels: string[] = [];
        let eligibleTechIds: number[] = [];
        let isStillBundle = 'is_bundle' in item && item.is_bundle !== false; // Check if it's a JobBundle

        if (isStillBundle) {
            const bundle = item as JobBundle;
            console.log(`Processing Bundle for Order ID: ${bundle.order_id}`);
            // Aggregate required equipment from all jobs in the bundle
            const allRequired = new Set<string>();
            for (const job of bundle.jobs) {
                const jobReqs = await getRequiredEquipmentForJob(job);
                jobReqs.forEach(model => allRequired.add(model));
            }
            requiredModels = Array.from(allRequired);
            bundle.required_equipment_models = requiredModels;

            // Find eligible technicians for the *bundle*
            eligibleTechIds = findEligibleTechnicians(requiredModels, technicians, vanEquipmentMap);
            bundle.eligible_technician_ids = eligibleTechIds;

            if (eligibleTechIds.length === 0 && bundle.jobs.length > 1) {
                // No tech can handle the whole bundle, break it
                console.warn(`No eligible technicians found for Bundle Order ID ${bundle.order_id}. Breaking into single jobs.`);
                isStillBundle = false;
                // Convert each job in the bundle into a SchedulableJob
                for (const job of bundle.jobs) {
                    const singleJobReqs = await getRequiredEquipmentForJob(job);
                    const singleJobEligibleTechs = findEligibleTechnicians(singleJobReqs, technicians, vanEquipmentMap);
                    const schedulableJob: SchedulableJob = {
                        is_bundle: false,
                        job: job,
                        priority: job.priority,
                        duration: job.job_duration,
                        address_id: job.address_id,
                        address: job.address,
                        required_equipment_models: singleJobReqs,
                        eligible_technician_ids: singleJobEligibleTechs,
                    };
                    finalItems.push(schedulableJob);
                     console.log(`  -> Added single Job ID ${job.id} (Order ${bundle.order_id}) individually. Eligible Techs: ${singleJobEligibleTechs.join(', ') || 'None'}`);
                }
            } else {
                 console.log(`Bundle Order ID ${bundle.order_id}. Required: [${requiredModels.join(', ')}]. Eligible Techs: ${eligibleTechIds.join(', ') || 'None'}`);
                finalItems.push(bundle); // Keep the valid bundle
            }

        } else {
            // Process a single SchedulableJob
            const schedJob = item as SchedulableJob;
            console.log(`Processing Single Job ID: ${schedJob.job.id}`);
            requiredModels = await getRequiredEquipmentForJob(schedJob.job);
            eligibleTechIds = findEligibleTechnicians(requiredModels, technicians, vanEquipmentMap);
            schedJob.required_equipment_models = requiredModels;
            schedJob.eligible_technician_ids = eligibleTechIds;
            console.log(`Single Job ID ${schedJob.job.id}. Required: [${requiredModels.join(', ')}]. Eligible Techs: ${eligibleTechIds.join(', ') || 'None'}`);
            finalItems.push(schedJob);
        }
    }

    console.log(`Finished eligibility check. Final item count: ${finalItems.length}`);
    return finalItems;
}

// Example Usage
/*
import { getActiveTechnicians } from '../supabase/technicians';
import { getRelevantJobs } from '../supabase/jobs';
import { bundleQueuedJobs } from './bundling';

async function runEligibilityExample() {
    try {
        console.log('--- Running Eligibility Example ---');
        const technicians = await getActiveTechnicians();
        if (technicians.length === 0) {
            console.log('No technicians found. Exiting example.');
            return;
        }
        const allJobs = await getRelevantJobs();
        const queuedJobs = allJobs.filter(job => job.status === 'queued');
         if (queuedJobs.length === 0) {
            console.log('No queued jobs found. Exiting example.');
            return;
        }

        const initialBundledItems = bundleQueuedJobs(queuedJobs);
        console.log('\n--- Starting Eligibility Determination ---');
        const finalSchedulableItems = await determineTechnicianEligibility(initialBundledItems, technicians);

        console.log('\n--- Final Schedulable Items with Eligibility ---');
        console.log(JSON.stringify(finalSchedulableItems, null, 2));

    } catch (error) {
        console.error('Eligibility example failed:', error);
    }
}

// runEligibilityExample();
*/ 