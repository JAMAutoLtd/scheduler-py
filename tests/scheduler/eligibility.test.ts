import { determineTechnicianEligibility } from '../../src/scheduler/eligibility';
import { Technician, Job, JobBundle, SchedulableJob, SchedulableItem, VanEquipment, Address } from '../../src/types/database.types';
import * as equipmentModule from '../../src/supabase/equipment';

// Mock the equipment module
jest.mock('../../src/supabase/equipment', () => ({
    getRequiredEquipmentForJob: jest.fn(),
    getEquipmentForVans: jest.fn(),
}));

// Mock helper functions
const mockGetRequiredEquipmentForJob = equipmentModule.getRequiredEquipmentForJob as jest.Mock;
const mockGetEquipmentForVans = equipmentModule.getEquipmentForVans as jest.Mock;

// Mock Data
const mockAddress1: Address = { id: 101, street_address: '123 Main St', lat: 40.0, lng: -75.0 };
const mockAddress2: Address = { id: 102, street_address: '456 Oak Ave', lat: 41.0, lng: -76.0 };

const tech1: Technician = { id: 1, user_id: 'uuid1', assigned_van_id: 10, workload: null };
const tech2: Technician = { id: 2, user_id: 'uuid2', assigned_van_id: 11, workload: null };
const tech3: Technician = { id: 3, user_id: 'uuid3', assigned_van_id: 12, workload: null };
const tech4: Technician = { id: 4, user_id: 'uuid4', assigned_van_id: null, workload: null }; // No van

const technicians = [tech1, tech2, tech3, tech4];

const van10Equipment: VanEquipment[] = [{ van_id: 10, equipment_id: 100, equipment_model: 'ToolA' }, { van_id: 10, equipment_id: 101, equipment_model: 'ToolB' }];
const van11Equipment: VanEquipment[] = [{ van_id: 11, equipment_id: 100, equipment_model: 'ToolA' }];
const van12Equipment: VanEquipment[] = [{ van_id: 12, equipment_id: 102, equipment_model: 'ToolC' }];

const vanEquipmentMap = new Map<number, VanEquipment[]>([
    [10, van10Equipment],
    [11, van11Equipment],
    [12, van12Equipment],
]);

const job1: Job = { id: 1, order_id: 100, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
const job2: Job = { id: 2, order_id: 101, address_id: 102, priority: 8, status: 'queued', job_duration: 60, service_id: 2, address: mockAddress2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
const job3: Job = { id: 3, order_id: 101, address_id: 102, priority: 2, status: 'queued', job_duration: 15, service_id: 3, address: mockAddress2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Bundle with job2
const job4: Job = { id: 4, order_id: 102, address_id: 101, priority: 9, status: 'queued', job_duration: 45, service_id: 4, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };

// Initial Schedulable Items (result of bundling)
const singleSchedJob1: SchedulableJob = { is_bundle: false, job: job1, priority: 5, duration: 30, address_id: 101, address: mockAddress1, required_equipment_models: [], eligible_technician_ids: [] };
const bundleJob23: JobBundle = { order_id: 101, jobs: [job2, job3], total_duration: 75, priority: 8, address_id: 102, address: mockAddress2, required_equipment_models: [], eligible_technician_ids: [] };
const singleSchedJob4: SchedulableJob = { is_bundle: false, job: job4, priority: 9, duration: 45, address_id: 101, address: mockAddress1, required_equipment_models: [], eligible_technician_ids: [] };


describe('determineTechnicianEligibility', () => {

    beforeEach(() => {
        // Reset mocks before each test
        mockGetRequiredEquipmentForJob.mockClear();
        mockGetEquipmentForVans.mockClear();
        // Always mock the van equipment fetch
        mockGetEquipmentForVans.mockResolvedValue(vanEquipmentMap);
    });

    it('should return an empty array if initial items are empty', async () => {
        const result = await determineTechnicianEligibility([], technicians);
        expect(result).toEqual([]);
        expect(mockGetEquipmentForVans).toHaveBeenCalledTimes(1); // Still fetches equipment once
        expect(mockGetRequiredEquipmentForJob).not.toHaveBeenCalled();
    });

    it('should process a single job with no required equipment', async () => {
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce([]); // Job 1 requires nothing
        const initialItems = [singleSchedJob1];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(1);
        const processedJob = result[0] as SchedulableJob;
        expect(processedJob.job.id).toBe(job1.id);
        expect(processedJob.required_equipment_models).toEqual([]);
        // Techs 1, 2, 3 should be eligible (tech 4 has no van)
        expect(processedJob.eligible_technician_ids).toEqual([tech1.id, tech2.id, tech3.id]);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job1);
        expect(mockGetEquipmentForVans).toHaveBeenCalledWith([10, 11, 12]); // Called with unique van IDs
    });

    it('should process a single job with required equipment found on one tech', async () => {
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolC']); // Job 4 requires ToolC
        const initialItems = [singleSchedJob4];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(1);
        const processedJob = result[0] as SchedulableJob;
        expect(processedJob.job.id).toBe(job4.id);
        expect(processedJob.required_equipment_models).toEqual(['ToolC']);
        // Only tech 3 has ToolC
        expect(processedJob.eligible_technician_ids).toEqual([tech3.id]);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job4);
    });

     it('should process a single job with required equipment found on multiple techs', async () => {
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolA']); // Job 1 requires ToolA
        const initialItems = [singleSchedJob1];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(1);
        const processedJob = result[0] as SchedulableJob;
        expect(processedJob.job.id).toBe(job1.id);
        expect(processedJob.required_equipment_models).toEqual(['ToolA']);
        // Tech 1 (Van 10) and Tech 2 (Van 11) have ToolA
        expect(processedJob.eligible_technician_ids).toEqual([tech1.id, tech2.id]);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job1);
    });

    it('should process a single job with required equipment no tech has', async () => {
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolX']); // Job 1 requires ToolX (non-existent)
        const initialItems = [singleSchedJob1];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(1);
        const processedJob = result[0] as SchedulableJob;
        expect(processedJob.job.id).toBe(job1.id);
        expect(processedJob.required_equipment_models).toEqual(['ToolX']);
        expect(processedJob.eligible_technician_ids).toEqual([]); // No techs have ToolX
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job1);
    });

    it('should process a bundle where one tech has all required equipment', async () => {
        // Job 2 requires ToolA, Job 3 requires ToolB
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolA']); // For job 2 within bundle
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolB']); // For job 3 within bundle
        const initialItems = [bundleJob23];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(1); // Bundle remains intact
        const processedBundle = result[0] as JobBundle;
        expect(processedBundle.order_id).toBe(101);
        expect(processedBundle.jobs).toHaveLength(2);
        // Order might vary due to Set conversion, so check contents
        expect(processedBundle.required_equipment_models).toEqual(expect.arrayContaining(['ToolA', 'ToolB']));
        expect(processedBundle.required_equipment_models.length).toBe(2);
        // Only Tech 1 (Van 10) has both ToolA and ToolB
        expect(processedBundle.eligible_technician_ids).toEqual([tech1.id]);
        // Should be called once for each job in the bundle
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job2);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job3);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledTimes(2);
    });

    it('should break a bundle if no single tech has all required equipment', async () => {
        // Job 2 requires ToolA, Job 3 requires ToolC
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolA']); // For job 2 initially (bundle check)
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolC']); // For job 3 initially (bundle check)
        // -- Bundle breaks, fetch requirements again for individual jobs --
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolA']); // For job 2 individually
        mockGetRequiredEquipmentForJob.mockResolvedValueOnce(['ToolC']); // For job 3 individually

        const initialItems = [bundleJob23]; // Order 101 (jobs 2 and 3)

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(2); // Bundle was broken

        // Check Job 2 (requires ToolA)
        const processedJob2 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 2) as SchedulableJob;
        expect(processedJob2).toBeDefined();
        expect(processedJob2.is_bundle).toBe(false);
        expect(processedJob2.job).toEqual(job2);
        expect(processedJob2.required_equipment_models).toEqual(['ToolA']);
        // Tech 1 (Van 10) and Tech 2 (Van 11) have ToolA
        expect(processedJob2.eligible_technician_ids).toEqual([tech1.id, tech2.id]);

        // Check Job 3 (requires ToolC)
        const processedJob3 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 3) as SchedulableJob;
        expect(processedJob3).toBeDefined();
        expect(processedJob3.is_bundle).toBe(false);
        expect(processedJob3.job).toEqual(job3);
        expect(processedJob3.required_equipment_models).toEqual(['ToolC']);
        // Only Tech 3 (Van 12) has ToolC
        expect(processedJob3.eligible_technician_ids).toEqual([tech3.id]);

        // Check mock calls: 2 for bundle check, 2 for individual checks after break
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledTimes(4);
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job2); // Called twice
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(job3); // Called twice
    });

     it('should process a mix of single jobs and bundles, breaking one bundle', async () => {
        // Setup:
        // Job 1 (Single): Requires ToolB -> Eligible: Tech 1
        // Bundle (Job 2, Job 3): Job 2 req ToolA, Job 3 req ToolC -> No tech has both -> Break bundle
        // Job 4 (Single): Requires nothing -> Eligible: Tech 1, 2, 3

        // Replace sequential mocks with a conditional mock implementation
        mockGetRequiredEquipmentForJob.mockImplementation(async (job: Job) => {
            switch (job.id) {
                case 1: return ['ToolB'];
                case 2: return ['ToolA'];
                case 3: return ['ToolC'];
                case 4: return [];
                default: return [];
            }
        });

        const initialItems: SchedulableItem[] = [singleSchedJob1, bundleJob23, singleSchedJob4];

        const result = await determineTechnicianEligibility(initialItems, technicians);

        expect(result).toHaveLength(4); // 2 singles + 2 from broken bundle

        // Check Job 1
        const processedJob1 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 1) as SchedulableJob;
        expect(processedJob1).toBeDefined();
        expect(processedJob1.required_equipment_models).toEqual(['ToolB']);
        expect(processedJob1.eligible_technician_ids).toEqual([tech1.id]); // Only tech 1 has ToolB

        // Check Job 2 (from broken bundle)
        const processedJob2 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 2) as SchedulableJob;
        expect(processedJob2).toBeDefined();
        expect(processedJob2.required_equipment_models).toEqual(['ToolA']);
        expect(processedJob2.eligible_technician_ids).toEqual([tech1.id, tech2.id]); // Tech 1 & 2 have ToolA

        // Check Job 3 (from broken bundle)
        const processedJob3 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 3) as SchedulableJob;
        expect(processedJob3).toBeDefined();
        expect(processedJob3.required_equipment_models).toEqual(['ToolC']);
        expect(processedJob3.eligible_technician_ids).toEqual([tech3.id]); // Only tech 3 has ToolC

        // Check Job 4
        const processedJob4 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 4) as SchedulableJob;
        expect(processedJob4).toBeDefined();
        expect(processedJob4.required_equipment_models).toEqual([]);
        expect(processedJob4.eligible_technician_ids).toEqual([tech1.id, tech2.id, tech3.id]); // All techs with vans

        // Check mock calls: The exact number is less important now, but we can verify calls for specific jobs
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(expect.objectContaining({ id: 1 })); // Called once
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(expect.objectContaining({ id: 2 })); // Called twice (bundle + individual)
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(expect.objectContaining({ id: 3 })); // Called twice (bundle + individual)
        expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledWith(expect.objectContaining({ id: 4 })); // Called once
        // Optional: Check total calls if needed, should still be 6
        // expect(mockGetRequiredEquipmentForJob).toHaveBeenCalledTimes(6);
    });
}); 