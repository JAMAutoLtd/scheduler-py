import { runFullReplan } from '../../src/scheduler/orchestrator';
import { SupabaseClient } from '@supabase/supabase-js';
import { processOptimizationResults, ScheduledJobUpdate } from '../../src/scheduler/results';
import { Job, JobStatus, SchedulableItem, Technician, SchedulableJob, Address, JobBundle } from '../../src/types/database.types';
import { JobUpdateOperation } from '../../src/db/update';

// Mock dependencies
jest.mock('../../src/supabase/technicians');
jest.mock('../../src/supabase/jobs');
jest.mock('../../src/db/update');
jest.mock('../../src/scheduler/availability');
jest.mock('../../src/scheduler/bundling');
jest.mock('../../src/scheduler/eligibility');
jest.mock('../../src/scheduler/payload');
jest.mock('../../src/scheduler/optimize');
jest.mock('../../src/scheduler/results');

// Import mocked functions for type hinting and setting mock implementations
import { getActiveTechnicians } from '../../src/supabase/technicians';
import { getRelevantJobs, getJobsByStatus } from '../../src/supabase/jobs';
import { updateJobs } from '../../src/db/update';
import { calculateTechnicianAvailability, calculateAvailabilityForDay } from '../../src/scheduler/availability';
import { bundleQueuedJobs } from '../../src/scheduler/bundling';
import { determineTechnicianEligibility } from '../../src/scheduler/eligibility';
import { prepareOptimizationPayload } from '../../src/scheduler/payload';
import { callOptimizationService } from '../../src/scheduler/optimize';

// Mock Supabase client instance
const mockDbClient = {} as SupabaseClient;

// Add MAX_OVERFLOW_ATTEMPTS constant at the top level of the describe block for clarity in assertions
const MAX_OVERFLOW_ATTEMPTS = 4; // Match the value in orchestrator.ts

describe('runFullReplan', () => {

    // Reset mocks before each test
    beforeEach(() => {
        jest.clearAllMocks();
        // Default mock implementations
        (getActiveTechnicians as jest.Mock).mockResolvedValue([]);
        (getRelevantJobs as jest.Mock).mockResolvedValue([]);
        (getJobsByStatus as jest.Mock).mockResolvedValue([]);
        (updateJobs as jest.Mock).mockResolvedValue(undefined);
        (calculateTechnicianAvailability as jest.Mock).mockImplementation(() => {});
        (calculateAvailabilityForDay as jest.Mock).mockReturnValue([]);
        // More realistic mock for bundling individual jobs -> returns SchedulableJob[]
        (bundleQueuedJobs as jest.Mock).mockImplementation((jobs: Job[]) => 
            jobs.map((job): SchedulableJob => ({ 
                is_bundle: false,
                job: job, 
                address: job.address,
                address_id: job.address_id, // Use correct field
                priority: job.priority, 
                duration: job.job_duration, // Use correct field
                required_equipment_models: [], 
                eligible_technician_ids: []   
            }))
        );
        (determineTechnicianEligibility as jest.Mock).mockImplementation(async (items: SchedulableItem[]) => 
            // Mark all items as eligible for tech 1 by default
            items.map(item => ({ ...item, eligible_technician_ids: [1] }))
        );
        (prepareOptimizationPayload as jest.Mock).mockResolvedValue({ 
            locations: [{ id: 'depot', index: 0, coords: { lat: 0, lng: 0 } }], 
            technicians: [{ id: 1, startLocationIndex: 0, endLocationIndex: 0, earliestStartTimeISO: '', latestEndTimeISO: '' }], 
            items: [], // This will often be overridden in tests but needs a default
            fixedConstraints: [], 
            travelTimeMatrix: { 0: { 0: 0 } } 
        });
        (callOptimizationService as jest.Mock).mockResolvedValue({ routes: [], unassigned_item_ids: [] }); 
        (processOptimizationResults as jest.Mock).mockReturnValue({ scheduledJobs: [], unassignedItemIds: [] }); 
    });

    test('should handle case with no active technicians', async () => {
        (getActiveTechnicians as jest.Mock).mockResolvedValue([]);

        await runFullReplan(mockDbClient);

        // getRelevantJobs *is* called due to Promise.all
        expect(getRelevantJobs).toHaveBeenCalledTimes(1); 
        expect(calculateTechnicianAvailability).not.toHaveBeenCalled(); // Check subsequent steps not called
        expect(updateJobs).not.toHaveBeenCalled();
        // Add checks for console logs if needed
    });

    test('should handle case with no relevant jobs initially', async () => {
        (getActiveTechnicians as jest.Mock).mockResolvedValue([{ id: 1, name: 'Tech 1' /* add other fields */ }]);
        (getRelevantJobs as jest.Mock).mockResolvedValue([]);

        await runFullReplan(mockDbClient);

        expect(getActiveTechnicians).toHaveBeenCalledTimes(1);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(bundleQueuedJobs).not.toHaveBeenCalled();
        // updateJobs should NOT be called if finalUpdates is empty
        expect(updateJobs).not.toHaveBeenCalled();
    });

    test('should handle case with no schedulable (queued) jobs initially', async () => {
        const mockLockedJob = { id: 1, status: 'en_route' /* add other fields */ };
        (getActiveTechnicians as jest.Mock).mockResolvedValue([{ id: 1, name: 'Tech 1' }]);
        (getRelevantJobs as jest.Mock).mockResolvedValue([mockLockedJob]);

        await runFullReplan(mockDbClient);

        expect(calculateTechnicianAvailability).not.toHaveBeenCalled();
        expect(bundleQueuedJobs).not.toHaveBeenCalled();
        // updateJobs should NOT be called if finalUpdates is empty
        expect(updateJobs).not.toHaveBeenCalled();
    });

    // --- Add tests for the scenarios discussed --- 

    test('Happy Path (Today Only): All jobs scheduled', async () => {
        // --- Arrange --- 
        const mockAddress1: Address = { id: 1, street_address: '1 Main St', lat: 2, lng: 2 };
        const mockAddress2: Address = { id: 2, street_address: '2 Main St', lat: 3, lng: 3 };
        const mockTech: Technician = { 
            id: 1, 
            user_id: 'uuid-1', 
            assigned_van_id: 1, 
            workload: 0, 
            current_location: { lat: 1, lng: 1 },
            // No name directly on Technician
        };
        const mockJobs: Job[] = [
            { id: 101, status: 'queued', address_id: 1, address: mockAddress1, priority: 5, job_duration: 30, order_id: 1 } as Job, // Use job_duration
            { id: 102, status: 'queued', address_id: 2, address: mockAddress2, priority: 5, job_duration: 45, order_id: 2 } as Job, // Use job_duration
        ];
        // This represents the *output* of determineTechnicianEligibility
        const mockEligibleItems: SchedulableJob[] = [
            { is_bundle: false, job: mockJobs[0], address_id: 1, address: mockAddress1, priority: 5, duration: 30, required_equipment_models: [], eligible_technician_ids: [1] }, // Use duration
            { is_bundle: false, job: mockJobs[1], address_id: 2, address: mockAddress2, priority: 5, duration: 45, required_equipment_models: [], eligible_technician_ids: [1] }, // Use duration
        ];
        const mockScheduledResults: ScheduledJobUpdate[] = [
            { jobId: 101, technicianId: 1, estimatedSchedISO: '2024-01-01T10:00:00Z' },
            { jobId: 102, technicianId: 1, estimatedSchedISO: '2024-01-01T11:00:00Z' },
        ];

        // Mock function implementations for this specific test
        (getActiveTechnicians as jest.Mock).mockResolvedValue([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValue(mockJobs);
        // bundleQueuedJobs mock will convert mockJobs to SchedulableJob[]
        (determineTechnicianEligibility as jest.Mock).mockResolvedValue(mockEligibleItems); // Return the eligible items
        (prepareOptimizationPayload as jest.Mock).mockImplementation(async (techs, itemsToOptimize) => {
            // Basic mock: create optimization items based on the eligible items received
            const optimizationItems = itemsToOptimize.map((item: SchedulableItem, index: number) => {
                 if ('job' in item) { // Type guard for SchedulableJob
                    return { id: `job_${item.job.id}`, locationIndex: index + 1, durationSeconds: item.duration * 60, priority: item.priority, eligibleTechnicianIds: item.eligible_technician_ids };
                 }
                 // Handle JobBundle if necessary in other tests
                 return null; 
            }).filter((item: { id: string; locationIndex: number; durationSeconds: number; priority: number; eligibleTechnicianIds: number[]; } | null): item is NonNullable<typeof item> => item !== null);
            return {
                locations: [], // Minimal
                technicians: [], // Minimal
                items: optimizationItems, // Use generated items
                fixedConstraints: [],
                travelTimeMatrix: {}
            };
        });
        (callOptimizationService as jest.Mock).mockResolvedValue({ 
            routes: [ { technician_id: 1, item_ids: ['job_101', 'job_102'] } ], 
            unassigned_item_ids: [] 
        });
        (processOptimizationResults as jest.Mock).mockReturnValue({ 
            scheduledJobs: mockScheduledResults, 
            unassignedItemIds: [] 
        });

        // --- Act --- 
        await runFullReplan(mockDbClient);

        // --- Assert --- 
        expect(getActiveTechnicians).toHaveBeenCalledTimes(1);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1);
        expect(bundleQueuedJobs).toHaveBeenCalledWith(mockJobs);
        // determineTechnicianEligibility is called with the *output* of bundleQueuedJobs
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(1);
        // prepareOptimizationPayload is called with the *output* of determineTechnicianEligibility
        expect(prepareOptimizationPayload).toHaveBeenCalledWith(
            [mockTech], 
            mockEligibleItems, // Pass the eligible items 
            [] // No fixed time jobs in this scenario
        );
        expect(callOptimizationService).toHaveBeenCalledTimes(1);
        expect(processOptimizationResults).toHaveBeenCalledTimes(1);
        
        expect(getJobsByStatus).not.toHaveBeenCalled();
        expect(calculateAvailabilityForDay).not.toHaveBeenCalled();

        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 101,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T10:00:00Z',
                }
            },
            {
                jobId: 102,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T11:00:00Z',
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });
    
    test('Partial Scheduling (Today Only): Some jobs pending review', async () => {
        // --- Arrange ---
        const mockAddress1: Address = { id: 1, street_address: '1 Main St', lat: 2, lng: 2 };
        const mockAddress2: Address = { id: 2, street_address: '2 Main St', lat: 3, lng: 3 };
        const mockAddress3: Address = { id: 3, street_address: '3 Main St', lat: 4, lng: 4 };
        const mockTech1: Technician = { id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0, current_location: { lat: 1, lng: 1 } };
        const mockJobs: Job[] = [
            { id: 201, status: 'queued', address_id: 1, address: mockAddress1, priority: 5, job_duration: 30, order_id: 10 } as Job,
            { id: 202, status: 'queued', address_id: 2, address: mockAddress2, priority: 5, job_duration: 45, order_id: 11 } as Job,
            { id: 203, status: 'queued', address_id: 3, address: mockAddress3, priority: 3, job_duration: 60, order_id: 12 } as Job, // Lower priority, longer duration
        ];
        // Assume bundling results in individual SchedulableJobs, all eligible for Tech 1 initially
        const mockEligibleItems: SchedulableJob[] = mockJobs.map(job => ({
            is_bundle: false,
            job: job,
            address_id: job.address_id,
            address: job.address,
            priority: job.priority,
            duration: job.job_duration,
            required_equipment_models: [],
            eligible_technician_ids: [1]
        }));
        const mockScheduledResults: ScheduledJobUpdate[] = [
            { jobId: 201, technicianId: 1, estimatedSchedISO: '2024-01-01T10:00:00Z' },
            { jobId: 202, technicianId: 1, estimatedSchedISO: '2024-01-01T11:00:00Z' },
        ];
        const mockUnassignedIds = ['job_203']; // Job 203 couldn't be scheduled today

        (getActiveTechnicians as jest.Mock).mockResolvedValue([mockTech1]);
        (getRelevantJobs as jest.Mock).mockResolvedValue(mockJobs);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValue(mockEligibleItems);
        (prepareOptimizationPayload as jest.Mock).mockImplementation(async (techs, itemsToOptimize) => ({
            locations: [], technicians: [], travelTimeMatrix: {}, fixedConstraints: [],
            items: itemsToOptimize.map((item: SchedulableItem, index: number) => 'job' in item ? { id: `job_${item.job.id}`, locationIndex: index + 1, durationSeconds: item.duration * 60, priority: item.priority, eligibleTechnicianIds: item.eligible_technician_ids } : null).filter((i: { id: string; locationIndex: number; durationSeconds: number; priority: number; eligibleTechnicianIds: number[]; } | null): i is NonNullable<typeof i> => i !== null)
        }));
        (callOptimizationService as jest.Mock).mockResolvedValue({ 
            routes: [ { technician_id: 1, item_ids: ['job_201', 'job_202'] } ], // Only jobs 201, 202 assigned
            unassigned_item_ids: mockUnassignedIds 
        });
        (processOptimizationResults as jest.Mock).mockReturnValue({ 
            scheduledJobs: mockScheduledResults, 
            unassignedItemIds: mockUnassignedIds 
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        expect(getActiveTechnicians).toHaveBeenCalledTimes(5); // 1 initial + 4 loops
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); // Only Pass 1

        // These are only called in Pass 1 because the loop continues early due to no availability mock
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(1);
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(1);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(1);
        expect(callOptimizationService).toHaveBeenCalledTimes(1);
        expect(processOptimizationResults).toHaveBeenCalledTimes(1);

        // Verify the overflow loop ran its course, but continued due to no availability
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(MAX_OVERFLOW_ATTEMPTS); // Called 4 times

        // Verify final DB update includes both scheduled and pending_review
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 201,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T10:00:00Z',
                }
            },
            {
                jobId: 202,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T11:00:00Z',
                }
            },
            {
                jobId: 203,
                data: {
                    status: 'pending_review',
                    assigned_technician: null,
                    estimated_sched: null,
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Overflow Path (Single Future Day): All overflow scheduled on Day 2', async () => {
        // --- Arrange ---
        const mockAddress1: Address = { id: 1, street_address: '1 Main St', lat: 2, lng: 2 };
        const mockTech1: Technician = { 
            id: 1, 
            user_id: 'uuid-1', 
            assigned_van_id: 1, 
            workload: 0, 
            current_location: { lat: 1, lng: 1 }, 
            home_location: { lat: 0, lng: 0 } // Add home location for Day 2 planning
        };
        const mockJob: Job = 
            { id: 301, status: 'queued', address_id: 1, address: mockAddress1, priority: 5, job_duration: 30, order_id: 20 } as Job;
        
        // Pass 1 Mocks (Job 301 is unassigned)
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech1]); // Called first time
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob]);
        const mockEligibleItemPass1: SchedulableJob = { 
            is_bundle: false, job: mockJob, address_id: 1, address: mockAddress1, priority: 5, 
            duration: 30, required_equipment_models: [], eligible_technician_ids: [1]
        };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItemPass1]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ 
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [{ id: 'job_301', locationIndex: 1, durationSeconds: 1800, priority: 5, eligibleTechnicianIds: [1] }]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ 
            routes: [], // No routes assigned
            unassigned_item_ids: ['job_301'] // Job 301 is unassigned
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ 
            scheduledJobs: [], // No jobs scheduled
            unassignedItemIds: ['job_301'] 
        });

        // Pass 2 Mocks (Job 301 scheduled on Day 2)
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech1]); // Called second time for loop
        // getJobsByStatus is NOT called because we use the internal jobsToPlan set
        const mockAvailabilityDay2 = [{ technicianId: 1, availabilityStartTimeISO: '2024-01-02T09:00:00Z', availabilityEndTimeISO: '2024-01-02T18:30:00Z', startLocation: mockTech1.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay2);
        const mockEligibleItemPass2: SchedulableJob = { ...mockEligibleItemPass1 }; // Same job, eligible again
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItemPass2]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Called second time
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [{ id: 'job_301', locationIndex: 1, durationSeconds: 1800, priority: 5, eligibleTechnicianIds: [1] }]
        });
        const mockScheduledResultDay2: ScheduledJobUpdate = 
            { jobId: 301, technicianId: 1, estimatedSchedISO: '2024-01-02T10:30:00Z' }; // Day 2 Time
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Called second time
            routes: [{ technician_id: 1, item_ids: ['job_301'] }], // Job 301 assigned
            unassigned_item_ids: [] 
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Called second time
            scheduledJobs: [mockScheduledResultDay2], 
            unassignedItemIds: [] 
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        // Verify functions called correct number of times
        expect(getActiveTechnicians).toHaveBeenCalledTimes(2); // Once initially, once in loop
        expect(getRelevantJobs).toHaveBeenCalledTimes(1); // Only called initially
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); // For Pass 1
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(1); // For Pass 2 (Day 2)
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(2); // Once per pass with jobs
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(2); // Once per pass
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(2); // Once per pass
        expect(callOptimizationService).toHaveBeenCalledTimes(2); // Once per pass
        expect(processOptimizationResults).toHaveBeenCalledTimes(2); // Once per pass
        expect(getJobsByStatus).not.toHaveBeenCalled();

        // Verify final DB update has the Day 2 schedule
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 301,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-02T10:30:00Z',
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Overflow Path (Multiple Future Days): Overflow scheduled on Day 3', async () => {
        // --- Arrange ---
        const mockAddress: Address = { id: 1, street_address: '1 Multi St', lat: 2, lng: 2 };
        const mockTech: Technician = {
            id: 1,
            user_id: 'uuid-1',
            assigned_van_id: 1,
            workload: 0,
            current_location: { lat: 1, lng: 1 },
            home_location: { lat: 0, lng: 0 } // Needed for overflow
        };
        const mockJob: Job =
            { id: 601, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 45, order_id: 50 } as Job;

        // Pass 1 (Today) - Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob]);
        const mockEligibleItem: SchedulableJob = {
            is_bundle: false, job: mockJob, address_id: 1, address: mockAddress, priority: 5,
            duration: 45, required_equipment_models: [], eligible_technician_ids: [1]
        };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItem]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload Day 1
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [{ id: `job_${mockJob.id}`, locationIndex: 1, durationSeconds: mockJob.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] }]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 1 - Unassigned
            routes: [],
            unassigned_item_ids: [`job_${mockJob.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 1 - Unassigned
            scheduledJobs: [],
            unassignedItemIds: [`job_${mockJob.id}`]
        });

        // Pass 2 (Day 2) - Still Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day2 = new Date(Date.UTC(2024, 0, 2)); // Example date
        const mockAvailabilityDay2 = [{ technicianId: 1, availabilityStartTimeISO: day2.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day2.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay2);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItem]); // Eligible again
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload Day 2
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [{ id: `job_${mockJob.id}`, locationIndex: 1, durationSeconds: mockJob.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] }]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 2 - Still Unassigned
            routes: [],
            unassigned_item_ids: [`job_${mockJob.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 2 - Still Unassigned
            scheduledJobs: [],
            unassignedItemIds: [`job_${mockJob.id}`]
        });

        // Pass 3 (Day 3) - Scheduled!
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day3 = new Date(Date.UTC(2024, 0, 3)); // Example date
        const mockAvailabilityDay3 = [{ technicianId: 1, availabilityStartTimeISO: day3.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day3.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay3);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItem]); // Eligible again
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload Day 3
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [{ id: `job_${mockJob.id}`, locationIndex: 1, durationSeconds: mockJob.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] }]
        });
        const mockScheduledResultDay3: ScheduledJobUpdate =
            { jobId: mockJob.id, technicianId: 1, estimatedSchedISO: day3.toISOString().replace(/T.*/, 'T14:00:00Z') }; // Day 3 Time
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 3 - Assigned
            routes: [{ technician_id: 1, item_ids: [`job_${mockJob.id}`] }],
            unassigned_item_ids: []
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 3 - Assigned
            scheduledJobs: [mockScheduledResultDay3],
            unassignedItemIds: []
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        const expectedLoopIterations = 2; // Loop runs for Day 2 and Day 3 planning
        const expectedGetTechCalls = 1 + expectedLoopIterations;
        const expectedCalcAvailDayCalls = expectedLoopIterations;
        const expectedBundleCalls = 1 + expectedLoopIterations;
        const expectedEligibleCalls = 1 + expectedLoopIterations;
        const expectedPayloadCalls = 1 + expectedLoopIterations;
        const expectedOptimizeCalls = 1 + expectedLoopIterations;
        const expectedResultCalls = 1 + expectedLoopIterations;

        expect(getActiveTechnicians).toHaveBeenCalledTimes(expectedGetTechCalls);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); // Only Pass 1
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(expectedCalcAvailDayCalls);
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(expectedBundleCalls);
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(expectedEligibleCalls);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(expectedPayloadCalls);
        expect(callOptimizationService).toHaveBeenCalledTimes(expectedOptimizeCalls);
        expect(processOptimizationResults).toHaveBeenCalledTimes(expectedResultCalls);
        expect(getJobsByStatus).not.toHaveBeenCalled();

        // Final DB Update - Should have job 601 scheduled for Day 3
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: mockJob.id,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: mockScheduledResultDay3.estimatedSchedISO,
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Weekend Skip Overflow: Jobs overflow Friday, skip Sat/Sun, scheduled queued Mon.', async () => {
        // --- Arrange ---
        // Set base date to a Friday (e.g., Jan 5th, 2024)
        const friday = new Date(Date.UTC(2024, 0, 5, 12, 0, 0)); // Use UTC
        const saturday = new Date(Date.UTC(2024, 0, 6));
        const sunday = new Date(Date.UTC(2024, 0, 7));
        const monday = new Date(Date.UTC(2024, 0, 8));

        jest.useFakeTimers().setSystemTime(friday);

        const mockAddress: Address = { id: 1, street_address: '1 Skip St', lat: 5, lng: 5 };
        const mockTech: Technician = { 
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0, 
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const mockJob: Job = 
            { id: 401, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 60, order_id: 30 } as Job;

        // --- Mocks for Pass 1 (Friday) - Job Unassigned ---
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob]);
        const mockEligibleItemFri: SchedulableJob = { is_bundle: false, job: mockJob, address_id: 1, address: mockAddress, priority: 5, duration: 60, required_equipment_models: [], eligible_technician_ids: [1] };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItemFri]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ 
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [{ id: 'job_401', locationIndex: 1, durationSeconds: 3600, priority: 5, eligibleTechnicianIds: [1] }]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ routes: [], unassigned_item_ids: ['job_401'] });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ scheduledJobs: [], unassignedItemIds: ['job_401'] });

        // --- Mocks for Pass 2 (Saturday) - No Availability ---
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]); // Called again
        (calculateAvailabilityForDay as jest.Mock).mockImplementationOnce((techs, date) => {
            // Basic check to ensure it's Saturday we're mocking
            expect(date.getUTCDay()).toBe(6); 
            return []; // No availability
        });

        // --- Mocks for Pass 3 (Sunday) - No Availability ---
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]); // Called again
        (calculateAvailabilityForDay as jest.Mock).mockImplementationOnce((techs, date) => {
            expect(date.getUTCDay()).toBe(0); 
            return []; // No availability
        });

        // --- Mocks for Pass 4 (Monday) - Job Scheduled ---
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]); // Called again
        const mockAvailabilityMon = [{ technicianId: 1, availabilityStartTimeISO: monday.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: monday.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockImplementationOnce((techs, date) => {
             expect(date.getUTCDay()).toBe(1); 
             return mockAvailabilityMon;
        });
        const mockEligibleItemMon: SchedulableJob = { ...mockEligibleItemFri };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItemMon]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload for Monday
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [{ id: 'job_401', locationIndex: 1, durationSeconds: 3600, priority: 5, eligibleTechnicianIds: [1] }]
        });
        const mockScheduledResultMon: ScheduledJobUpdate = 
            { jobId: 401, technicianId: 1, estimatedSchedISO: monday.toISOString().replace(/T.*/, 'T11:00:00Z') }; // Monday Time
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Success on Monday
            routes: [{ technician_id: 1, item_ids: ['job_401'] }], 
            unassigned_item_ids: [] 
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Result for Monday
            scheduledJobs: [mockScheduledResultMon], 
            unassignedItemIds: [] 
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        // Initial fetch + 3 loop iterations
        expect(getActiveTechnicians).toHaveBeenCalledTimes(4);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1); 
        // Pass 1
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); 
        // Pass 2, 3, 4 (Sat, Sun, Mon)
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(3);
        expect(calculateAvailabilityForDay).toHaveBeenNthCalledWith(1, [mockTech], expect.any(Date)); // Saturday
        expect(calculateAvailabilityForDay).toHaveBeenNthCalledWith(2, [mockTech], expect.any(Date)); // Sunday
        expect(calculateAvailabilityForDay).toHaveBeenNthCalledWith(3, [mockTech], expect.any(Date)); // Monday
        // Bundling: Pass 1 (Fri) + Pass 4 (Mon). Not called Sat/Sun due to no availability.
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(2); 
        // Eligibility: Pass 1 (Fri) + Pass 4 (Mon).
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(2); 
        // Payload: Pass 1 (Fri) + Pass 4 (Mon).
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(2); 
        // Optimizer: Pass 1 (Fri) + Pass 4 (Mon).
        expect(callOptimizationService).toHaveBeenCalledTimes(2); 
        // Results: Pass 1 (Fri) + Pass 4 (Mon).
        expect(processOptimizationResults).toHaveBeenCalledTimes(2);
        expect(getJobsByStatus).not.toHaveBeenCalled();

        // Final DB Update
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 401,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: mockScheduledResultMon.estimatedSchedISO,
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);

        jest.useRealTimers(); // Restore real timers
    });

    test('Full Overflow (Pending Review): Jobs remain unassigned after all attempts', async () => {
        // --- Arrange ---
        const MAX_ATTEMPTS = 4; // Align with constant in orchestrator.ts
        const mockAddress: Address = { id: 1, street_address: '1 Fail St', lat: 6, lng: 6 };
        const mockTech: Technician = { 
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0, 
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const mockJob: Job = 
            { id: 501, status: 'queued', address_id: 1, address: mockAddress, priority: 1, job_duration: 120, order_id: 40 } as Job;

        // Mock initial Pass 1 - Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob]);
        const mockEligibleItem: SchedulableJob = { 
            is_bundle: false, job: mockJob, address_id: 1, address: mockAddress, priority: 1, 
            duration: 120, required_equipment_models: [], eligible_technician_ids: [1]
        };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValue([mockEligibleItem]); // Assume eligible for all relevant passes
        (prepareOptimizationPayload as jest.Mock).mockResolvedValue({ // Assume payload prep succeeds
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [{ id: 'job_501', locationIndex: 1, durationSeconds: 7200, priority: 1, eligibleTechnicianIds: [1] }]
        });
        (callOptimizationService as jest.Mock).mockResolvedValue({ // Always returns unassigned
            routes: [], 
            unassigned_item_ids: ['job_501'] 
        });
        (processOptimizationResults as jest.Mock).mockReturnValue({ // Always returns unassigned
            scheduledJobs: [], 
            unassignedItemIds: ['job_501'] 
        });

        // Mock Overflow Loop Behavior (MAX_ATTEMPTS times)
        for (let i = 0; i < MAX_ATTEMPTS; i++) {
            (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]); // Called in each loop
            const loopDate = new Date(Date.UTC(2024, 0, 6 + i)); // Mock consecutive days
            const mockAvailability = [{ 
                technicianId: 1, 
                availabilityStartTimeISO: loopDate.toISOString().replace(/T.*/, 'T09:00:00Z'), 
                availabilityEndTimeISO: loopDate.toISOString().replace(/T.*/, 'T18:30:00Z'), 
                startLocation: mockTech.home_location 
            }];
            (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailability);
            // Other mocks like bundling, eligibility, payload, optimize, results are already set to repeat the failure
        }

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        const expectedLoopIterations = MAX_ATTEMPTS;
        const expectedGetTechCalls = 1 + expectedLoopIterations;
        const expectedCalcAvailDayCalls = expectedLoopIterations;
        const expectedBundleCalls = 1 + expectedLoopIterations;
        const expectedEligibleCalls = 1 + expectedLoopIterations;
        const expectedPayloadCalls = 1 + expectedLoopIterations;
        const expectedOptimizeCalls = 1 + expectedLoopIterations;
        const expectedResultCalls = 1 + expectedLoopIterations;

        expect(getActiveTechnicians).toHaveBeenCalledTimes(expectedGetTechCalls);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1); 
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); // Pass 1 only
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(expectedCalcAvailDayCalls);
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(expectedBundleCalls);
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(expectedEligibleCalls);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(expectedPayloadCalls);
        expect(callOptimizationService).toHaveBeenCalledTimes(expectedOptimizeCalls);
        expect(processOptimizationResults).toHaveBeenCalledTimes(expectedResultCalls);
        expect(getJobsByStatus).not.toHaveBeenCalled();

        // Final DB Update - Should mark job 501 as pending_review
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 501,
                data: {
                    status: 'pending_review',
                    assigned_technician: null,
                    estimated_sched: null,
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Mixed Overflow: Some scheduled queued on future day, rest pending review', async () => {
        // --- Arrange ---
        const mockAddress1: Address = { id: 1, street_address: '1 Mix St', lat: 7, lng: 7 };
        const mockAddress2: Address = { id: 2, street_address: '2 Mix St', lat: 8, lng: 8 };
        const mockTech: Technician = {
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0,
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const mockJob1: Job = { id: 701, status: 'queued', address_id: 1, address: mockAddress1, priority: 5, job_duration: 30, order_id: 60 } as Job;
        const mockJob2: Job = { id: 702, status: 'queued', address_id: 2, address: mockAddress2, priority: 3, job_duration: 90, order_id: 61 } as Job; // Harder to schedule

        // Pass 1 (Today) - Both Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob1, mockJob2]);
        const mockEligibleItems1: SchedulableJob = { is_bundle: false, job: mockJob1, address_id: 1, address: mockAddress1, priority: 5, duration: 30, eligible_technician_ids: [1], required_equipment_models: [] };
        const mockEligibleItems2: SchedulableJob = { is_bundle: false, job: mockJob2, address_id: 2, address: mockAddress2, priority: 3, duration: 90, eligible_technician_ids: [1], required_equipment_models: [] };
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItems1, mockEligibleItems2]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload Day 1
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `job_${mockJob1.id}`, locationIndex: 1, durationSeconds: mockJob1.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] },
                { id: `job_${mockJob2.id}`, locationIndex: 2, durationSeconds: mockJob2.job_duration * 60, priority: 3, eligibleTechnicianIds: [1] },
            ]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 1 - Both Unassigned
            routes: [],
            unassigned_item_ids: [`job_${mockJob1.id}`, `job_${mockJob2.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 1 - Both Unassigned
            scheduledJobs: [],
            unassignedItemIds: [`job_${mockJob1.id}`, `job_${mockJob2.id}`]
        });

        // Pass 2 (Day 2) - Job 1 Scheduled, Job 2 Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day2 = new Date(Date.UTC(2024, 0, 2)); // Example date
        const mockAvailabilityDay2 = [{ technicianId: 1, availabilityStartTimeISO: day2.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day2.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay2);
        // Assume both still eligible if passed to optimizer
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItems1, mockEligibleItems2]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ // Payload Day 2
             locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
             items: [
                { id: `job_${mockJob1.id}`, locationIndex: 1, durationSeconds: mockJob1.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] },
                { id: `job_${mockJob2.id}`, locationIndex: 2, durationSeconds: mockJob2.job_duration * 60, priority: 3, eligibleTechnicianIds: [1] },
             ]
        });
        const mockScheduledResultDay2: ScheduledJobUpdate = { jobId: mockJob1.id, technicianId: 1, estimatedSchedISO: day2.toISOString().replace(/T.*/, 'T10:00:00Z') };
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 2 - Job 1 Assigned, Job 2 Unassigned
            routes: [{ technician_id: 1, item_ids: [`job_${mockJob1.id}`] }],
            unassigned_item_ids: [`job_${mockJob2.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 2 - Job 1 Assigned, Job 2 Unassigned
            scheduledJobs: [mockScheduledResultDay2],
            unassignedItemIds: [`job_${mockJob2.id}`]
        });

        // --- Mocks for Overflow Loop (Pass 3, 4, 5) ---
        // Pass 3 (Day 3) - Job 2 Scheduled, Job 1 Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day3 = new Date(Date.UTC(2024, 0, 3)); // Example date
        const mockAvailabilityDay3 = [{ technicianId: 1, availabilityStartTimeISO: day3.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day3.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay3);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItems2]); // Only job 2 eligible
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ 
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `job_${mockJob2.id}`, locationIndex: 1, durationSeconds: mockJob2.job_duration * 60, priority: 3, eligibleTechnicianIds: [1] }
            ]
        });
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 3 - Job 2 Assigned, Job 1 Unassigned
            routes: [{ technician_id: 1, item_ids: [`job_${mockJob2.id}`] }],
            unassigned_item_ids: [`job_${mockJob1.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 3 - Job 2 Assigned, Job 1 Unassigned
            scheduledJobs: [mockScheduledResultDay2],
            unassignedItemIds: [`job_${mockJob1.id}`]
        });

        // Pass 4 (Day 4) - Job 1 Scheduled, Job 2 Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day4 = new Date(Date.UTC(2024, 0, 4)); // Example date
        const mockAvailabilityDay4 = [{ technicianId: 1, availabilityStartTimeISO: day4.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day4.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay4);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItems1]); // Only job 1 eligible
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ 
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `job_${mockJob1.id}`, locationIndex: 1, durationSeconds: mockJob1.job_duration * 60, priority: 5, eligibleTechnicianIds: [1] }
            ]
        });
        const mockScheduledResultDay4: ScheduledJobUpdate = { jobId: mockJob1.id, technicianId: 1, estimatedSchedISO: day4.toISOString().replace(/T.*/, 'T10:00:00Z') };
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 4 - Job 1 Assigned, Job 2 Unassigned
            routes: [{ technician_id: 1, item_ids: [`job_${mockJob1.id}`] }],
            unassigned_item_ids: [`job_${mockJob2.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 4 - Job 1 Assigned, Job 2 Unassigned
            scheduledJobs: [mockScheduledResultDay4],
            unassignedItemIds: [`job_${mockJob2.id}`]
        });

        // Pass 5 (Day 5) - Job 2 Scheduled, Job 1 Unassigned
        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        const day5 = new Date(Date.UTC(2024, 0, 5)); // Example date
        const mockAvailabilityDay5 = [{ technicianId: 1, availabilityStartTimeISO: day5.toISOString().replace(/T.*/, 'T09:00:00Z'), availabilityEndTimeISO: day5.toISOString().replace(/T.*/, 'T18:30:00Z'), startLocation: mockTech.home_location }];
        (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailabilityDay5);
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItems2]); // Only job 2 eligible
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({ 
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `job_${mockJob2.id}`, locationIndex: 1, durationSeconds: mockJob2.job_duration * 60, priority: 3, eligibleTechnicianIds: [1] }
            ]
        });
        const mockScheduledResultDay5: ScheduledJobUpdate = { jobId: mockJob2.id, technicianId: 1, estimatedSchedISO: day5.toISOString().replace(/T.*/, 'T10:00:00Z') };
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({ // Result Day 5 - Job 2 Assigned, Job 1 Unassigned
            routes: [{ technician_id: 1, item_ids: [`job_${mockJob2.id}`] }],
            unassigned_item_ids: [`job_${mockJob1.id}`]
        });
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({ // Processed Day 5 - Job 2 Assigned, Job 1 Unassigned
            scheduledJobs: [mockScheduledResultDay5],
            unassignedItemIds: [`job_${mockJob1.id}`]
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        const expectedLoopIterations = MAX_OVERFLOW_ATTEMPTS; // Loop runs 4 times because job 702 remains
        const expectedGetTechCalls = 1 + expectedLoopIterations; // 1 initial + 4 loops = 5

        expect(getActiveTechnicians).toHaveBeenCalledTimes(expectedGetTechCalls);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1); // Pass 1
        expect(calculateAvailabilityForDay).toHaveBeenCalledTimes(expectedLoopIterations); // Day 2, 3, 4, 5
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(1 + expectedLoopIterations);
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(1 + expectedLoopIterations);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(1 + expectedLoopIterations);
        expect(callOptimizationService).toHaveBeenCalledTimes(1 + expectedLoopIterations);
        expect(processOptimizationResults).toHaveBeenCalledTimes(1 + expectedLoopIterations);
        expect(getJobsByStatus).not.toHaveBeenCalled();

        // Final DB Update - Job 1 queued for Day 2, Job 2 queued for Day 5
        expect(updateJobs).toHaveBeenCalledTimes(1);
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: mockJob1.id, // 701
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: mockScheduledResultDay2.estimatedSchedISO, // From Day 2 mock
                }
            },
            {
                jobId: mockJob2.id, // 702
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: mockScheduledResultDay5.estimatedSchedISO, // From Day 5 mock
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Bundling Interaction: Successfully scheduled bundle', async () => {
        // --- Arrange ---
        const mockAddress: Address = { id: 1, street_address: '1 Bundle Ave', lat: 9, lng: 9 };
        const mockTech: Technician = {
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0,
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const orderId = 70;
        const mockJob1: Job = { id: 801, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 20, order_id: orderId } as Job;
        const mockJob2: Job = { id: 802, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 25, order_id: orderId } as Job;

        const mockBundle: JobBundle = {
            order_id: orderId,
            jobs: [mockJob1, mockJob2],
            address_id: 1,
            address: mockAddress,
            priority: 5, // Assuming highest priority of constituents
            total_duration: 45, // Use total_duration
            required_equipment_models: [],
            eligible_technician_ids: [1] // Will be set by determineEligibility mock
        };

        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob1, mockJob2]);

        // Mock bundling to return the bundle
        (bundleQueuedJobs as jest.Mock).mockReturnValueOnce([mockBundle]);

        // Mock eligibility to mark the bundle as eligible
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([{ ...mockBundle, eligible_technician_ids: [1] }]);

        // Mock payload preparation to create item for the bundle
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `bundle_${orderId}`, locationIndex: 1, durationSeconds: mockBundle.total_duration * 60, priority: mockBundle.priority, eligibleTechnicianIds: [1] }
            ]
        });

        // Mock optimization service call - assigns the bundle
        (callOptimizationService as jest.Mock).mockResolvedValueOnce({
            routes: [{ technician_id: 1, item_ids: [`bundle_${orderId}`] }],
            unassigned_item_ids: []
        });

        // Mock result processing - returns updates for *constituent jobs*
        const mockScheduledResults: ScheduledJobUpdate[] = [
            { jobId: 801, technicianId: 1, estimatedSchedISO: '2024-01-01T10:00:00Z' },
            { jobId: 802, technicianId: 1, estimatedSchedISO: '2024-01-01T10:20:00Z' }, // Assumes scheduler calculates offset
        ];
        (processOptimizationResults as jest.Mock).mockReturnValueOnce({
            scheduledJobs: mockScheduledResults,
            unassignedItemIds: []
        });

        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        expect(getActiveTechnicians).toHaveBeenCalledTimes(1);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1);
        expect(bundleQueuedJobs).toHaveBeenCalledWith([mockJob1, mockJob2]);
        expect(determineTechnicianEligibility).toHaveBeenCalledWith([mockBundle], [mockTech]);
        expect(prepareOptimizationPayload).toHaveBeenCalledWith([mockTech], [{ ...mockBundle, eligible_technician_ids: [1] }], []);
        expect(callOptimizationService).toHaveBeenCalledTimes(1);
        expect(processOptimizationResults).toHaveBeenCalledTimes(1);
        expect(updateJobs).toHaveBeenCalledTimes(1);

        // Final DB Update - Both jobs 801 and 802 should be queued
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 801,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T10:00:00Z',
                }
            },
            {
                jobId: 802,
                data: {
                    status: 'queued',
                    assigned_technician: 1,
                    estimated_sched: '2024-01-01T10:20:00Z',
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Bundling Interaction: Unassigned bundle becomes pending review', async () => {
        // --- Arrange ---
        const mockAddress: Address = { id: 1, street_address: '1 Unassigned Bundle St', lat: 10, lng: 10 };
        const mockTech: Technician = {
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0,
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const orderId = 80;
        const mockJob1: Job = { id: 901, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 120, order_id: orderId } as Job;
        const mockJob2: Job = { id: 902, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 150, order_id: orderId } as Job;

        const mockBundle: JobBundle = {
            order_id: orderId,
            jobs: [mockJob1, mockJob2],
            address_id: 1,
            address: mockAddress,
            priority: 5,
            total_duration: 270, // Use total_duration
            required_equipment_models: [],
            eligible_technician_ids: [1]
        };

        (getActiveTechnicians as jest.Mock).mockResolvedValue([mockTech]); // Ensure tech is returned for all calls
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob1, mockJob2]);
        (bundleQueuedJobs as jest.Mock).mockReturnValue([mockBundle]); // Return bundle for all relevant passes
        (determineTechnicianEligibility as jest.Mock).mockResolvedValue([{ ...mockBundle, eligible_technician_ids: [1] }]); // Eligible for all passes
        (prepareOptimizationPayload as jest.Mock).mockResolvedValue({ // Assume payload prep succeeds for all passes
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [
                { id: `bundle_${orderId}`, locationIndex: 1, durationSeconds: mockBundle.total_duration * 60, priority: mockBundle.priority, eligibleTechnicianIds: [1] }
            ]
        });

        // Mock optimization service - always returns bundle as unassigned
        (callOptimizationService as jest.Mock).mockResolvedValue({
            routes: [],
            unassigned_item_ids: [`bundle_${orderId}`]
        });

        // Mock result processing - always returns bundle as unassigned
        (processOptimizationResults as jest.Mock).mockReturnValue({
            scheduledJobs: [],
            unassignedItemIds: [`bundle_${orderId}`]
        });

        // Mock Availability for overflow loops (needed because loop will now run)
        for (let i = 0; i < MAX_OVERFLOW_ATTEMPTS; i++) {
            const loopDate = new Date(Date.UTC(2024, 0, 6 + i)); // Mock consecutive days
            const mockAvailability = [{
                technicianId: 1,
                availabilityStartTimeISO: loopDate.toISOString().replace(/T.*/, 'T09:00:00Z'),
                availabilityEndTimeISO: loopDate.toISOString().replace(/T.*/, 'T18:30:00Z'),
                startLocation: mockTech.home_location
            }];
            (calculateAvailabilityForDay as jest.Mock).mockReturnValueOnce(mockAvailability); // Use mockReturnValueOnce if different per loop, or mockReturnValue if same
        }


        // --- Act ---
        await runFullReplan(mockDbClient);

        // --- Assert ---
        const expectedGetTechCalls = 1 + MAX_OVERFLOW_ATTEMPTS; // 1 initial + 4 loops = 5

        expect(getActiveTechnicians).toHaveBeenCalledTimes(expectedGetTechCalls);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1);
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(1 + MAX_OVERFLOW_ATTEMPTS); // Pass 1 + 4 loops
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(1 + MAX_OVERFLOW_ATTEMPTS);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(1 + MAX_OVERFLOW_ATTEMPTS);
        expect(callOptimizationService).toHaveBeenCalledTimes(1 + MAX_OVERFLOW_ATTEMPTS);
        expect(processOptimizationResults).toHaveBeenCalledTimes(1 + MAX_OVERFLOW_ATTEMPTS);
        expect(updateJobs).toHaveBeenCalledTimes(1);

        // Final DB Update - Both jobs 901 and 902 should be pending_review
        const expectedUpdates: JobUpdateOperation[] = [
            {
                jobId: 901,
                data: {
                    status: 'pending_review',
                    assigned_technician: null,
                    estimated_sched: null,
                }
            },
            {
                jobId: 902,
                data: {
                    status: 'pending_review',
                    assigned_technician: null,
                    estimated_sched: null,
                }
            }
        ];
        expect(updateJobs).toHaveBeenCalledWith(mockDbClient, expect.arrayContaining(expectedUpdates));
        const actualUpdates = (updateJobs as jest.Mock).mock.calls[0][1];
        expect(actualUpdates).toHaveLength(expectedUpdates.length);
    });

    test('Error Handling: callOptimizationService fails', async () => {
        // --- Arrange ---
        const mockAddress: Address = { id: 1, street_address: '1 Error St', lat: 11, lng: 11 };
        const mockTech: Technician = {
            id: 1, user_id: 'uuid-1', assigned_van_id: 1, workload: 0,
            current_location: { lat: 1, lng: 1 }, home_location: { lat: 0, lng: 0 }
        };
        const mockJob: Job = { id: 1001, status: 'queued', address_id: 1, address: mockAddress, priority: 5, job_duration: 30, order_id: 90 } as Job;

        const mockEligibleItem: SchedulableJob = {
            is_bundle: false, job: mockJob, address_id: 1, address: mockAddress, priority: 5,
            duration: 30, required_equipment_models: [], eligible_technician_ids: [1]
        };

        (getActiveTechnicians as jest.Mock).mockResolvedValueOnce([mockTech]);
        (getRelevantJobs as jest.Mock).mockResolvedValueOnce([mockJob]);
        // bundleQueuedJobs default mock is fine
        (determineTechnicianEligibility as jest.Mock).mockResolvedValueOnce([mockEligibleItem]);
        (prepareOptimizationPayload as jest.Mock).mockResolvedValueOnce({
            locations: [], technicians: [], fixedConstraints: [], travelTimeMatrix: {},
            items: [{ id: `job_${mockJob.id}`, locationIndex: 1, durationSeconds: 1800, priority: 5, eligibleTechnicianIds: [1] }]
        });

        // Mock optimization service to throw an error
        const optimizationError = new Error('Optimization Service Unavailable');
        (callOptimizationService as jest.Mock).mockRejectedValueOnce(optimizationError);

        // processOptimizationResults should not be called
        // updateJobs should not be called

        // --- Act & Assert ---
        await expect(runFullReplan(mockDbClient)).rejects.toThrow('Optimization Service Unavailable');

        // Verify mocks called up to the error point
        expect(getActiveTechnicians).toHaveBeenCalledTimes(1);
        expect(getRelevantJobs).toHaveBeenCalledTimes(1);
        expect(calculateTechnicianAvailability).toHaveBeenCalledTimes(1);
        expect(bundleQueuedJobs).toHaveBeenCalledTimes(1);
        expect(determineTechnicianEligibility).toHaveBeenCalledTimes(1);
        expect(prepareOptimizationPayload).toHaveBeenCalledTimes(1);
        expect(callOptimizationService).toHaveBeenCalledTimes(1);

        // Verify mocks NOT called after the error
        expect(processOptimizationResults).not.toHaveBeenCalled();
        expect(updateJobs).not.toHaveBeenCalled();
        expect(calculateAvailabilityForDay).not.toHaveBeenCalled(); // Overflow loop should not start
    });

    test('Error Handling: getActiveTechnicians fails', async () => {
        // --- Arrange ---
        const fetchError = new Error('Supabase connection error');
        (getActiveTechnicians as jest.Mock).mockRejectedValueOnce(fetchError);

        // --- Act & Assert ---
        await expect(runFullReplan(mockDbClient)).rejects.toThrow('Supabase connection error');

        // Verify only the failing function was called
        expect(getActiveTechnicians).toHaveBeenCalledTimes(1);

        // Verify subsequent steps were not called (getRelevantJobs *might* have started)
        // Assertion removed as it's unreliable due to Promise.all
        expect(calculateTechnicianAvailability).not.toHaveBeenCalled();
        expect(bundleQueuedJobs).not.toHaveBeenCalled();
        expect(determineTechnicianEligibility).not.toHaveBeenCalled();
        expect(prepareOptimizationPayload).not.toHaveBeenCalled();
        expect(callOptimizationService).not.toHaveBeenCalled();
        expect(processOptimizationResults).not.toHaveBeenCalled();
        expect(updateJobs).not.toHaveBeenCalled();
        expect(calculateAvailabilityForDay).not.toHaveBeenCalled();
    });

}); 