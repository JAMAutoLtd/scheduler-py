import { 
    Technician, 
    Job, 
    SchedulableItem, 
    Address,
    JobBundle,
    SchedulableJob
} from '../types/database.types';
import {
    OptimizationLocation,
    OptimizationTechnician,
    OptimizationItem,
    OptimizationFixedConstraint,
    TravelTimeMatrix,
    OptimizationRequestPayload
} from '../types/optimization.types';
import { getTravelTime } from '../google/maps';
import { LatLngLiteral } from '@googlemaps/google-maps-services-js';

const DEFAULT_DEPOT_LOCATION: LatLngLiteral = { lat: 40.0, lng: -75.0 }; // Example: Replace with actual depot/base coords

/**
 * Creates a unique identifier for a SchedulableItem.
 * Prefixes with 'job_' or 'bundle_' based on the type.
 */
function getItemId(item: SchedulableItem): string {
    // Check if it has the 'job' property, which is unique to SchedulableJob
    if ('job' in item) {
        // It's a SchedulableJob
        return `job_${item.job.id}`;
    } else {
        // It must be a JobBundle, which has order_id
        return `bundle_${item.order_id}`;
    }
}

/**
 * Prepares the complete payload required by the optimization microservice.
 *
 * @param {Technician[]} technicians - Array of available technicians (with availability calculated).
 * @param {SchedulableItem[]} items - Array of schedulable jobs/bundles (with eligibility calculated).
 * @param {Job[]} fixedTimeJobs - Array of jobs that have a fixed schedule time.
 * @returns {Promise<OptimizationRequestPayload>} The payload object.
 */
export async function prepareOptimizationPayload(
    technicians: Technician[],
    items: SchedulableItem[],
    fixedTimeJobs: Job[],
): Promise<OptimizationRequestPayload> {
    console.log('Preparing optimization payload...');
    const locationsMap = new Map<string, OptimizationLocation>();
    let currentIndex = 0;

    // Function to add/get location and assign index
    const addOrGetLocation = (id: string | number, coords: LatLngLiteral): OptimizationLocation => {
        const key = `${coords.lat},${coords.lng}`;
        if (!locationsMap.has(key)) {
            locationsMap.set(key, { id: id, index: currentIndex++, coords: coords });
        }
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        return locationsMap.get(key)!;
    };

    // 1. Define Locations (Depot, Tech Starts, Items)
    // Depot (Index 0)
    const depotLocation = addOrGetLocation('depot', DEFAULT_DEPOT_LOCATION);

    // Technician Start Locations
    technicians.forEach(tech => {
        const startCoords = tech.current_location || DEFAULT_DEPOT_LOCATION; // Use tech's current location or depot
        addOrGetLocation(`tech_start_${tech.id}`, startCoords);
    });

    // Item Locations
    items.forEach(item => {
        // Assert item.address exists and has coordinates - should be guaranteed by earlier steps if needed
        if (!item.address?.lat || !item.address?.lng) {
            console.error(`Item ${getItemId(item)} is missing address coordinates. Skipping.`);
            // Potentially throw an error or filter this item out earlier
            return; 
        }
        const itemCoords: LatLngLiteral = { lat: item.address.lat, lng: item.address.lng };
        addOrGetLocation(getItemId(item), itemCoords);
    });

    const finalLocations = Array.from(locationsMap.values()).sort((a, b) => a.index - b.index);
    console.log(`Defined ${finalLocations.length} unique locations for optimization.`);

    // 2. Calculate Travel Time Matrix
    console.log('Calculating travel time matrix...');
    const travelTimeMatrix: TravelTimeMatrix = {};
    for (let i = 0; i < finalLocations.length; i++) {
        travelTimeMatrix[i] = {};
        for (let j = 0; j < finalLocations.length; j++) {
            if (i === j) {
                travelTimeMatrix[i][j] = 0; // Time from a location to itself is 0
                continue;
            }
            const originLoc = finalLocations[i];
            const destLoc = finalLocations[j];
            // console.log(`Fetching time from ${originLoc.id} (${i}) to ${destLoc.id} (${j})`);
            const duration = await getTravelTime(originLoc.coords, destLoc.coords);
            if (duration === null) {
                // Handle error: Maybe use a high penalty value or throw
                console.error(`Failed to get travel time from ${originLoc.id} to ${destLoc.id}. Using high penalty.`);
                travelTimeMatrix[i][j] = 999999; // High penalty value
            } else {
                travelTimeMatrix[i][j] = duration;
            }
        }
    }
    console.log('Travel time matrix calculated.');

    // 3. Format Technicians
    const optimizationTechnicians: OptimizationTechnician[] = technicians.map(tech => {
        const startCoords = tech.current_location || DEFAULT_DEPOT_LOCATION;
        const startLocation = addOrGetLocation(`tech_start_${tech.id}`, startCoords); // Get existing location object
        
        // Define end-of-day time based on the start time (assume same day)
        const earliestStartDate = new Date(tech.earliest_availability || Date.now());
        const latestEndDate = new Date(earliestStartDate);
        latestEndDate.setHours(18, 30, 0, 0); // TODO: Make work hours configurable
        
        return {
            id: tech.id,
            startLocationIndex: startLocation.index,
            endLocationIndex: depotLocation.index, // Assume all techs return to depot
            earliestStartTimeISO: earliestStartDate.toISOString(),
            latestEndTimeISO: latestEndDate.toISOString(),
        };
    });

    // 4. Format Items
    const optimizationItems: OptimizationItem[] = items
        .map(item => {
            // Get the location object previously created
            const itemLocation = addOrGetLocation(getItemId(item), {
                // These checks are needed because we might have skipped items without coords earlier
                lat: item.address?.lat || 0, 
                lng: item.address?.lng || 0
            });
             // Check if the location was actually found/created (it should have been unless coords were missing)
             if (!finalLocations.find(l => l.index === itemLocation.index)) {
                console.warn(`Skipping item ${getItemId(item)} because its location could not be indexed (likely missing coordinates).`);
                return null; 
            }

            const isBundle = !('is_bundle' in item && item.is_bundle === false);
            const duration = isBundle ? (item as JobBundle).total_duration : (item as SchedulableJob).duration;
            
            return {
                id: getItemId(item),
                locationIndex: itemLocation.index,
                durationSeconds: duration * 60, // Convert minutes to seconds
                priority: item.priority,
                eligibleTechnicianIds: item.eligible_technician_ids,
            };
        })
        .filter((item): item is OptimizationItem => item !== null); // Filter out skipped items

    // 5. Format Fixed Constraints
    const optimizationFixedConstraints: OptimizationFixedConstraint[] = fixedTimeJobs
        .map(job => {
            // Find the corresponding OptimizationItem ID
            const itemId = `job_${job.id}`;
            const correspondingItem = optimizationItems.find(optItem => optItem.id === itemId);
            if (!correspondingItem) {
                console.warn(`Fixed time job ${job.id} was not found in the list of schedulable items. Skipping constraint.`);
                return null;
            }
            if (!job.fixed_schedule_time) {
                console.warn(`Job ${job.id} is marked fixed but has no fixed_schedule_time. Skipping constraint.`);
                return null;
            }
            return {
                itemId: itemId,
                fixedTimeISO: new Date(job.fixed_schedule_time).toISOString(),
            };
        })
        .filter((constraint): constraint is OptimizationFixedConstraint => constraint !== null);

    // 6. Construct Final Payload
    const payload: OptimizationRequestPayload = {
        locations: finalLocations,
        technicians: optimizationTechnicians,
        items: optimizationItems,
        fixedConstraints: optimizationFixedConstraints,
        travelTimeMatrix: travelTimeMatrix,
    };

    console.log('Optimization payload prepared successfully.');
    // console.log(JSON.stringify(payload, null, 2)); // Optional: Log the full payload for debugging
    return payload;
}

// Example Usage (complex, requires previous steps)
/*
import { getActiveTechnicians } from '../supabase/technicians';
import { getRelevantJobs } from '../supabase/jobs';
import { bundleQueuedJobs } from './bundling';
import { determineTechnicianEligibility } from './eligibility';
import { calculateTechnicianAvailability } from './availability';

async function runPayloadExample() {
    try {
        console.log('--- Running Payload Preparation Example ---');
        const technicians = await getActiveTechnicians();
        const allJobs = await getRelevantJobs();
        const lockedJobs = allJobs.filter(j => ['en_route', 'in_progress', 'fixed_time'].includes(j.status));
        const queuedJobs = allJobs.filter(j => j.status === 'queued');
        const fixedTimeJobs = allJobs.filter(j => j.status === 'fixed_time' && j.fixed_schedule_time);

        if(technicians.length === 0 || queuedJobs.length === 0) {
            console.log('Need technicians and queued jobs to run example.');
            return;
        }

        calculateTechnicianAvailability(technicians, lockedJobs);
        const bundledItems = bundleQueuedJobs(queuedJobs);
        const eligibleItems = await determineTechnicianEligibility(bundledItems, technicians);

        const payload = await prepareOptimizationPayload(technicians, eligibleItems, fixedTimeJobs);

        console.log('\n--- Payload Prepared (Summary) ---');
        console.log(`Locations: ${payload.locations.length}`);
        console.log(`Technicians: ${payload.technicians.length}`);
        console.log(`Items: ${payload.items.length}`);
        console.log(`Fixed Constraints: ${payload.fixedConstraints.length}`);
        console.log(`Travel Matrix Size: ${Object.keys(payload.travelTimeMatrix).length}`);
        // console.log(JSON.stringify(payload, null, 2)); // Full payload

    } catch (error) {
        console.error('Payload preparation example failed:', error);
    }
}

// runPayloadExample();
*/ 