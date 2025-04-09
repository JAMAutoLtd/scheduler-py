// tests/integration/fullReplan.test.ts
import { runFullReplan } from '../../src/scheduler/orchestrator';
import { supabase } from '../../src/supabase/client'; // We will mock this
import { getTravelTime } from '../../src/google/maps'; // We will mock this
import { callOptimizationService } from '../../src/scheduler/optimize'; // We will mock this
import * as dbUpdater from '../../src/db/update'; // To spy on updateJobStatuses

// Mock external dependencies
jest.mock('../../src/supabase/client', () => ({
    supabase: {
        from: jest.fn().mockReturnThis(),
        select: jest.fn().mockReturnThis(),
        update: jest.fn().mockReturnThis(),
        eq: jest.fn().mockReturnThis(),
        in: jest.fn().mockReturnThis(),
        single: jest.fn().mockReturnThis(),
        // Add other methods used by your data fetching functions if needed
    },
}));

// Mock the individual data fetching functions to control their output
jest.mock('../../src/supabase/technicians');
jest.mock('../../src/supabase/jobs');
jest.mock('../../src/supabase/equipment');
jest.mock('../../src/supabase/orders');

// Mock google maps travel time
jest.mock('../../src/google/maps');

// Mock the optimization service call
jest.mock('../../src/scheduler/optimize');

// Mock the db update function itself to prevent actual DB calls during test
// and verify it's called correctly
jest.mock('../../src/db/update');

// Import the mocked functions AFTER setting up the mocks
import { getActiveTechnicians } from '../../src/supabase/technicians';
import { getRelevantJobs } from '../../src/supabase/jobs';
import { getEquipmentForVans, getRequiredEquipmentForJob } from '../../src/supabase/equipment';
import { getYmmIdForOrder } from '../../src/supabase/orders';
import { OptimizationResponsePayload } from '../../src/types/optimization.types';
import { Technician, Job, VanEquipment, Address, Service, JobStatus } from '../../src/types/database.types';

// Typecast mocks for easier use
const mockGetActiveTechnicians = getActiveTechnicians as jest.MockedFunction<typeof getActiveTechnicians>;
const mockGetRelevantJobs = getRelevantJobs as jest.MockedFunction<typeof getRelevantJobs>;
const mockGetEquipmentForVans = getEquipmentForVans as jest.MockedFunction<typeof getEquipmentForVans>;
const mockGetRequiredEquipmentForJob = getRequiredEquipmentForJob as jest.MockedFunction<typeof getRequiredEquipmentForJob>;
const mockGetYmmIdForOrder = getYmmIdForOrder as jest.MockedFunction<typeof getYmmIdForOrder>;
const mockGetTravelTime = getTravelTime as jest.MockedFunction<typeof getTravelTime>;
const mockCallOptimizationService = callOptimizationService as jest.MockedFunction<typeof callOptimizationService>;
const mockUpdateJobStatuses = dbUpdater.updateJobStatuses as jest.MockedFunction<typeof dbUpdater.updateJobStatuses>;


describe('Full Replan Integration Test - New Job Trigger', () => {

    // --- Test Data Setup ---
    // Define technicians, initial jobs, the new job, equipment, etc.
    // Define expected optimization response and expected DB updates

    const mockTechnicians: Technician[] = [
        // TODO: Add mock technician data
    ];

    const initialJobs: Job[] = [
        // TODO: Add mock jobs representing the state BEFORE the new job
        // Include some locked/fixed jobs
    ];

    const newJob: Job = {
        // TODO: Define the new 'queued' job
        id: 999,
        order_id: 500,
        address_id: 10,
        service_id: 1,
        status: 'queued',
        priority: 5,
        job_duration: 60,
        assigned_technician: null,
        requested_time: null,
        estimated_sched: null,
        notes: 'New job for testing',
        technician_notes: null,
        fixed_assignment: false,
        fixed_schedule_time: null,
        // Include address and service details if needed by mocks/logic
        address: { id: 10, street_address: '123 Test St', lat: 40.1, lng: -75.1 },
        service: { id: 1, service_name: 'Test Service', service_category: 'prog' },
    };

    const allJobsForReplan = [...initialJobs, newJob];

    const mockVanEquipment = new Map<number, VanEquipment[]>();
    // TODO: Populate mockVanEquipment (e.g., mockVanEquipment.set(vanId, [{...}, {...}]))

    const mockOptimizationResponse: OptimizationResponsePayload = {
        // TODO: Define the expected successful response from the optimizer
        status: 'success',
        routes: [
            // Example route structure:
            // { technicianId: 1, stops: [ { itemId: 'job_999', startTimeISO: '...', ... }, ... ] }
        ],
        unassignedItemIds: [], // Assume the new job is scheduled initially
    };

    beforeEach(() => {
        // Reset mocks before each test
        jest.clearAllMocks();

        // --- Setup Mock Implementations ---

        // Mock data fetching functions
        mockGetActiveTechnicians.mockResolvedValue(mockTechnicians);
        mockGetRelevantJobs.mockResolvedValue(allJobsForReplan);
        mockGetEquipmentForVans.mockResolvedValue(mockVanEquipment);
        mockGetRequiredEquipmentForJob.mockImplementation(async (job) => {
            // Basic mock: return specific equipment for the new job's service
            if (job.service_id === newJob.service_id) {
                 return ['prog_tool_1']; // Example equipment model
            }
            return []; // Default to no requirements for other jobs
        });
         mockGetYmmIdForOrder.mockImplementation(async (orderId) => {
            // Basic mock: return a specific ymm_id for the new job's order
            if (orderId === newJob.order_id) {
                 return 123; // Example ymm_id
            }
            return 456; // Default ymm_id for other orders
         });


        // Mock travel time - return a fixed duration for simplicity
        mockGetTravelTime.mockResolvedValue(1800); // 30 minutes in seconds

        // Mock optimization call - return the predefined response
        mockCallOptimizationService.mockResolvedValue(mockOptimizationResponse);

        // Mock DB update - capture the call without doing anything
        mockUpdateJobStatuses.mockResolvedValue(undefined);
    });

    it('should run the full replan process and update the new job status to scheduled', async () => {
        // --- Act ---
        await runFullReplan(supabase); // Pass the (mocked) supabase client

        // --- Assert ---

        // 1. Verify Optimization Service call
        expect(mockCallOptimizationService).toHaveBeenCalledTimes(1);
        const optimizationPayload = mockCallOptimizationService.mock.calls[0][0];
        // TODO: Add specific assertions about the optimizationPayload
        // e.g., expect(optimizationPayload.items).toContainEqual(expect.objectContaining({ id: `job_${newJob.id}` }));
        // e.g., check technician availability, eligibility based on mock data

        // 2. Verify DB Update call
        expect(mockUpdateJobStatuses).toHaveBeenCalledTimes(1);
        const updateCallArgs = mockUpdateJobStatuses.mock.calls[0][1]; // Second argument is the response payload
        expect(updateCallArgs).toEqual(mockOptimizationResponse);

        // If you want to assert the *exact* update queries made *within* updateJobStatuses,
        // you would need to NOT mock updateJobStatuses itself, but instead mock supabase.update
        // more granularly and check its calls. For an integration test, verifying
        // updateJobStatuses was called with the correct *result* payload is often sufficient.

        // Example granular check (if NOT mocking updateJobStatuses directly):
        // const updateMock = supabase.update as jest.Mock;
        // expect(updateMock).toHaveBeenCalledWith(expect.objectContaining({
        //     status: 'scheduled',
        //     // assigned_technician: expected_technician_id,
        //     // estimated_sched: expected_start_time_iso
        // }));
        // expect(supabase.eq).toHaveBeenCalledWith('id', newJob.id);
    });

     // TODO: Add more test cases for different scenarios (e.g., job becomes overflow)

});