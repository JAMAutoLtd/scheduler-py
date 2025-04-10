import { prepareOptimizationPayload } from '../../src/scheduler/payload';
import { 
    Technician, 
    Job, 
    SchedulableItem, 
    Address,
    JobBundle,
    SchedulableJob,
    JobStatus,
    TechnicianAvailability
} from '../../src/types/database.types';
import { 
    OptimizationRequestPayload, 
    OptimizationLocation, 
    TravelTimeMatrix 
} from '../../src/types/optimization.types';
import * as mapsModule from '../../src/google/maps';
import { LatLngLiteral } from '@googlemaps/google-maps-services-js';

// Mock the maps module
jest.mock('../../src/google/maps', () => ({
    getTravelTime: jest.fn(),
}));

// Mock helper function
const mockGetTravelTime = mapsModule.getTravelTime as jest.Mock;

// Constants and Mock Data
const DEFAULT_DEPOT_COORDS: LatLngLiteral = { lat: 40.0, lng: -75.0 }; // Matches payload.ts
const MOCK_ERROR_PENALTY = 999999; // Matches payload.ts

// Mock Addresses
const address1: Address = { id: 101, street_address: '123 Main St', lat: 40.1, lng: -75.1 };
const address2: Address = { id: 102, street_address: '456 Oak Ave', lat: 40.2, lng: -75.2 };
const address3: Address = { id: 103, street_address: '789 Pine Ln', lat: 40.3, lng: -75.3 };
const homeAddress1: Address = { id: 201, street_address: '1 Home Pl', lat: 40.01, lng: -75.01 };
const homeAddress2: Address = { id: 202, street_address: '2 Home Ave', lat: 40.02, lng: -75.02 };

// Mock Technicians (with availability and location) - USE UTC ISO STRINGS
const techStartTimeISO = '2024-07-26T09:00:00.000Z'; // Example UTC time
const tech1: Technician = { 
    id: 1, user_id: 'uuid1', assigned_van_id: 10, workload: null, 
    current_location: { lat: 40.05, lng: -75.05 }, // Near depot
    earliest_availability: techStartTimeISO, 
    home_location: { lat: homeAddress1.lat!, lng: homeAddress1.lng! } // Added home location with non-null assertions
};
const tech2: Technician = { 
    id: 2, user_id: 'uuid2', assigned_van_id: 11, workload: null,
    current_location: { lat: 40.15, lng: -75.15 }, // Near address 1
    earliest_availability: techStartTimeISO,
    home_location: { lat: homeAddress2.lat!, lng: homeAddress2.lng! } // Added home location with non-null assertions
};
const technicians = [tech1, tech2];

// Mock Schedulable Items (post-eligibility)
const job1: Job = { id: 1, order_id: 100, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, address: address1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
const job2: Job = { id: 2, order_id: 101, address_id: 102, priority: 8, status: 'queued', job_duration: 60, service_id: 2, address: address2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
const job3: Job = { id: 3, order_id: 101, address_id: 102, priority: 2, status: 'queued', job_duration: 15, service_id: 3, address: address2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
const job4_missing_coords: Job = { id: 4, order_id: 102, address_id: 103, priority: 9, status: 'queued', job_duration: 45, service_id: 4, address: { id: 103, street_address: 'No Coords St', lat: null, lng: null }, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };

const schedItem1: SchedulableJob = { is_bundle: false, job: job1, priority: 5, duration: 30, address_id: 101, address: address1, required_equipment_models: ['ToolA'], eligible_technician_ids: [1, 2] };
const schedItemBundle: JobBundle = { order_id: 101, jobs: [job2, job3], total_duration: 75, priority: 8, address_id: 102, address: address2, required_equipment_models: ['ToolB'], eligible_technician_ids: [1] };
const schedItemMissingCoords: SchedulableJob = { is_bundle: false, job: job4_missing_coords, priority: 9, duration: 45, address_id: 103, address: job4_missing_coords.address, required_equipment_models: [], eligible_technician_ids: [1, 2] };

const items: SchedulableItem[] = [schedItem1, schedItemBundle, schedItemMissingCoords];

// Mock Fixed Time Job - USE UTC ISO STRING
const fixedTimeISO = '2024-07-26T14:00:00.000Z'; 
const fixedJob: Job = { 
    id: 1, // Matches job1 
    order_id: 100, address_id: 101, priority: 10, status: 'fixed_time', job_duration: 30, service_id: 1, address: address1, 
    assigned_technician: 1, // Assume fixed assignment
    fixed_assignment: true, 
    fixed_schedule_time: fixedTimeISO,
    estimated_sched: null, notes: null, requested_time: null, technician_notes: null
};
const unrelatedFixedJob: Job = { // This job isn't in the main 'items' list
     id: 5, 
     order_id: 105, address_id: 101, priority: 10, status: 'fixed_time', job_duration: 30, service_id: 1, address: address1, 
     assigned_technician: 1, fixed_assignment: true, fixed_schedule_time: fixedTimeISO,
     estimated_sched: null, notes: null, requested_time: null, technician_notes: null
};

const fixedTimeJobs = [fixedJob, unrelatedFixedJob];

describe('prepareOptimizationPayload', () => {

    beforeEach(() => {
        mockGetTravelTime.mockClear();
        // Mock successful travel time calculation (e.g., 15 mins = 900s)
        mockGetTravelTime.mockImplementation(async (origin: LatLngLiteral, dest: LatLngLiteral) => {
            // Simple mock: return 900s unless origin and dest are same
            if (origin.lat === dest.lat && origin.lng === dest.lng) return 0;
            return 900; 
        });
    });

    it('should build a valid payload structure', async () => {
        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], [fixedJob]); // Exclude missing coords item for this test

        expect(payload).toHaveProperty('locations');
        expect(payload).toHaveProperty('technicians');
        expect(payload).toHaveProperty('items');
        expect(payload).toHaveProperty('fixedConstraints');
        expect(payload).toHaveProperty('travelTimeMatrix');
    });

    it('should define locations correctly (depot, techs, items)', async () => {
        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], []); // No fixed jobs
        const locations = payload.locations;

        // Expected locations: Depot, Tech1 Start, Tech2 Start, Item1 (Job1), Item2 (Bundle)
        expect(locations).toHaveLength(5);

        // Check indexes and coordinates
        expect(locations[0]).toEqual({ id: 'depot', index: 0, coords: DEFAULT_DEPOT_COORDS });
        expect(locations[1]).toEqual({ id: `job_${job1.id}`, index: 1, coords: { lat: address1.lat, lng: address1.lng } });
        expect(locations[2]).toEqual({ id: `bundle_${schedItemBundle.order_id}`, index: 2, coords: { lat: address2.lat, lng: address2.lng } });
        // Tech start locations are added *after* items, so their indices will be 3 and 4
        expect(locations[3]).toEqual({ id: 'tech_start_1', index: 3, coords: tech1.current_location });
        expect(locations[4]).toEqual({ id: 'tech_start_2', index: 4, coords: tech2.current_location });
    });

    it('should skip items with missing coordinates', async () => {
        const payload = await prepareOptimizationPayload(technicians, items, []); // Include item with missing coords
        const locations = payload.locations;
        const optItems = payload.items;

        // Expected locations: Depot, Item1 (Job1), Item2 (Bundle), Tech1 Start, Tech2 Start - Item 4 skipped
        expect(locations).toHaveLength(5);
        expect(locations.find(loc => loc.id === `job_${job4_missing_coords.id}`)).toBeUndefined();

        // Expected items: Item1, Bundle - Item 4 skipped
        expect(optItems).toHaveLength(2);
        expect(optItems.find(item => item.id === `job_${job4_missing_coords.id}`)).toBeUndefined();
    });

    it('should calculate the travel time matrix', async () => {
        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], []);
        const matrix = payload.travelTimeMatrix;
        const n = payload.locations.length; // Should be 5

        expect(Object.keys(matrix).length).toBe(n);
        for (let i = 0; i < n; i++) {
            expect(Object.keys(matrix[i]).length).toBe(n);
            for (let j = 0; j < n; j++) {
                expect(typeof matrix[i][j]).toBe('number');
                if (i === j) {
                    expect(matrix[i][j]).toBe(0);
                } else {
                    expect(matrix[i][j]).toBe(900); // Based on mock implementation
                }
            }
        }
        // Verify mock was called n * (n-1) times (excluding i === j)
        expect(mockGetTravelTime).toHaveBeenCalledTimes(n * (n - 1));
    });

     it('should handle travel time API errors using penalty', async () => {
        // Mock one specific call to fail
        mockGetTravelTime.mockImplementation(async (origin: LatLngLiteral, dest: LatLngLiteral) => {
             if (origin.lat === DEFAULT_DEPOT_COORDS.lat && dest.lat === address1.lat) { // Depot to Job 1 fails
                 return null;
             }
             if (origin.lat === dest.lat && origin.lng === dest.lng) return 0;
             return 900;
        });

        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], []);
        const matrix = payload.travelTimeMatrix;
        const locations = payload.locations;
        const depotIndex = locations.find(l => l.id === 'depot')!.index;
        const job1Index = locations.find(l => l.id === `job_${job1.id}`)!.index;

        expect(matrix[depotIndex][job1Index]).toBe(MOCK_ERROR_PENALTY);
        // Check another value to ensure not all are penalties
        const jobBundleIndex = locations.find(l => l.id === `bundle_${schedItemBundle.order_id}`)!.index;
        expect(matrix[depotIndex][jobBundleIndex]).toBe(900);
     });

    it('should format technicians correctly (using default availability)', async () => {
        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], []);
        const optTechs = payload.technicians;
        const locations = payload.locations;
        
        expect(optTechs).toHaveLength(2);

        const tech1Data = optTechs.find(t => t.id === tech1.id);
        const tech1LocationIndex = locations.find(l=>l.id === 'tech_start_1')?.index;
        expect(tech1Data).toBeDefined();
        expect(tech1Data?.startLocationIndex).toBe(tech1LocationIndex);
        expect(tech1Data?.endLocationIndex).toBe(locations.find(l=>l.id === 'depot')?.index); 
        expect(tech1Data?.earliestStartTimeISO).toBe(tech1.earliest_availability);
        // Check default end time (should be 18:30 UTC on the same day as start)
        const expectedEndTime = new Date(tech1.earliest_availability!); 
        expectedEndTime.setUTCHours(18, 30, 0, 0); // USE UTC!
        expect(tech1Data?.latestEndTimeISO).toBe(expectedEndTime.toISOString());

        const tech2Data = optTechs.find(t => t.id === tech2.id);
        const tech2LocationIndex = locations.find(l=>l.id === 'tech_start_2')?.index;
        expect(tech2Data).toBeDefined();
        expect(tech2Data?.startLocationIndex).toBe(tech2LocationIndex);
    });

    it('should format items correctly', async () => {
        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], []);
        const optItems = payload.items;
        const locations = payload.locations;

        expect(optItems).toHaveLength(2);

        // Check Job 1
        const item1Data = optItems.find(i => i.id === `job_${job1.id}`);
        const job1LocationIndex = locations.find(l => l.id === `job_${job1.id}`)?.index;
        expect(item1Data).toBeDefined();
        expect(item1Data?.locationIndex).toBe(job1LocationIndex);
        expect(item1Data?.durationSeconds).toBe(schedItem1.duration * 60); // 30 * 60 = 1800
        expect(item1Data?.priority).toBe(schedItem1.priority);
        expect(item1Data?.eligibleTechnicianIds).toEqual(schedItem1.eligible_technician_ids);

        // Check Bundle
        const itemBundleData = optItems.find(i => i.id === `bundle_${schedItemBundle.order_id}`);
        const bundleLocationIndex = locations.find(l => l.id === `bundle_${schedItemBundle.order_id}`)?.index;
        expect(itemBundleData).toBeDefined();
        expect(itemBundleData?.locationIndex).toBe(bundleLocationIndex);
        expect(itemBundleData?.durationSeconds).toBe(schedItemBundle.total_duration * 60); // 75 * 60 = 4500
        expect(itemBundleData?.priority).toBe(schedItemBundle.priority);
        expect(itemBundleData?.eligibleTechnicianIds).toEqual(schedItemBundle.eligible_technician_ids);
    });

    it('should format fixed constraints correctly and skip unrelated ones', async () => {
         const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], fixedTimeJobs);
         const constraints = payload.fixedConstraints;

         expect(constraints).toHaveLength(1); // Only fixedJob should match schedItem1

         const constraint1 = constraints[0];
         expect(constraint1.itemId).toBe(`job_${fixedJob.id}`); // job_1
         expect(constraint1.fixedTimeISO).toBe(fixedJob.fixed_schedule_time);

         // Ensure unrelatedFixedJob constraint was skipped
         expect(constraints.find(c => c.itemId === `job_${unrelatedFixedJob.id}`)).toBeUndefined();
    });

    it('should skip fixed constraint if fixed_schedule_time is missing', async () => {
         const jobWithMissingTime: Job = { ...fixedJob, fixed_schedule_time: null };
         const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], [jobWithMissingTime]);
         const constraints = payload.fixedConstraints;
         expect(constraints).toHaveLength(0);
    });

    // New Test Case for TechnicianAvailability
    it('should use technicianAvailability when provided', async () => {
        const futureStartTimeISO = '2024-07-27T09:00:00.000Z';
        const futureEndTimeISO = '2024-07-27T18:30:00.000Z';

        const techAvail: TechnicianAvailability[] = [
            {
                technicianId: tech1.id,
                availabilityStartTimeISO: futureStartTimeISO,
                availabilityEndTimeISO: futureEndTimeISO,
                startLocation: tech1.home_location!, // Use home location
            },
            {
                technicianId: tech2.id,
                availabilityStartTimeISO: futureStartTimeISO,
                availabilityEndTimeISO: futureEndTimeISO,
                startLocation: tech2.home_location!, // Use home location
            },
        ];

        const payload = await prepareOptimizationPayload(technicians, [schedItem1, schedItemBundle], [], techAvail);
        const optTechs = payload.technicians;
        const locations = payload.locations;

        expect(optTechs).toHaveLength(2);

        // Verify Tech 1 uses availability data
        const tech1Data = optTechs.find(t => t.id === tech1.id);
        const tech1HomeLocationIndex = locations.find(l => l.id === 'tech_start_1' && l.coords.lat === tech1.home_location!.lat && l.coords.lng === tech1.home_location!.lng)?.index;
        expect(tech1Data).toBeDefined();
        expect(tech1Data?.startLocationIndex).toBe(tech1HomeLocationIndex); // Should be index of home location
        expect(tech1Data?.earliestStartTimeISO).toBe(futureStartTimeISO);
        expect(tech1Data?.latestEndTimeISO).toBe(futureEndTimeISO);

        // Verify Tech 2 uses availability data
        const tech2Data = optTechs.find(t => t.id === tech2.id);
        const tech2HomeLocationIndex = locations.find(l => l.id === 'tech_start_2' && l.coords.lat === tech2.home_location!.lat && l.coords.lng === tech2.home_location!.lng)?.index;
        expect(tech2Data).toBeDefined();
        expect(tech2Data?.startLocationIndex).toBe(tech2HomeLocationIndex); // Should be index of home location
        expect(tech2Data?.earliestStartTimeISO).toBe(futureStartTimeISO);
        expect(tech2Data?.latestEndTimeISO).toBe(futureEndTimeISO);
        
        // Also verify the locations list includes the home locations for techs
        expect(locations.find(l => l.id === 'tech_start_1' && l.coords.lat === tech1.home_location!.lat)).toBeDefined();
        expect(locations.find(l => l.id === 'tech_start_2' && l.coords.lat === tech2.home_location!.lat)).toBeDefined();

    });

}); 