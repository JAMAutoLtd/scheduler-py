import { SupabaseClient } from '@supabase/supabase-js';
import { updateJobs, JobUpdateOperation, JobUpdatePayload } from '../../src/db/update';
import { JobStatus } from '../../src/types/database.types'; // Import JobStatus

// Mock Supabase Client and its methods
const mockEq = jest.fn();
const mockUpdate = jest.fn(() => ({ eq: mockEq }));
const mockFrom = jest.fn(() => ({ update: mockUpdate }));

const mockSupabaseClient = { // Mock Client object
    from: mockFrom,
} as unknown as SupabaseClient<any>; // Cast to SupabaseClient type

// --- Test Suite for updateJobs ---
describe('updateJobs', () => {

    beforeEach(() => {
        // Reset mocks before each test
        mockFrom.mockClear();
        mockUpdate.mockClear();
        mockEq.mockClear();
        // Default mock for successful updates (eq returns success)
        mockEq.mockResolvedValue({ data: [{}], error: null, status: 200, statusText: 'OK' }); 
    });

    it('should do nothing if the updates array is empty', async () => {
        const updates: JobUpdateOperation[] = [];
        await updateJobs(mockSupabaseClient, updates);
        expect(mockFrom).not.toHaveBeenCalled();
    });

    it('should correctly update a single job with status, tech, and time', async () => {
        const jobId = 101;
        const technicianId = 5;
        const scheduledTime = new Date('2024-08-01T10:00:00.000Z').toISOString();
        const updates: JobUpdateOperation[] = [
            {
                jobId: jobId,
                data: {
                    status: 'scheduled',
                    assigned_technician: technicianId,
                    estimated_sched: scheduledTime,
                }
            }
        ];

        await updateJobs(mockSupabaseClient, updates);

        expect(mockFrom).toHaveBeenCalledTimes(1);
        expect(mockFrom).toHaveBeenCalledWith('jobs');
        expect(mockUpdate).toHaveBeenCalledTimes(1);
        expect(mockUpdate).toHaveBeenCalledWith(updates[0].data);
        expect(mockEq).toHaveBeenCalledTimes(1);
        expect(mockEq).toHaveBeenCalledWith('id', jobId);
    });

    it('should correctly update multiple jobs with different statuses', async () => {
        const update1: JobUpdateOperation = {
            jobId: 101,
            data: { status: 'scheduled_future', assigned_technician: 6, estimated_sched: '2024-08-02T09:00:00Z' }
        };
        const update2: JobUpdateOperation = {
            jobId: 102,
            data: { status: 'overflow', assigned_technician: null, estimated_sched: null }
        };
        const update3: JobUpdateOperation = {
            jobId: 103,
            data: { status: 'unschedulable_overflow', assigned_technician: null, estimated_sched: null }
        };

        const updates = [update1, update2, update3];
        await updateJobs(mockSupabaseClient, updates);

        expect(mockFrom).toHaveBeenCalledTimes(updates.length); // `from` is called in each map iteration
        expect(mockUpdate).toHaveBeenCalledTimes(updates.length);
        expect(mockEq).toHaveBeenCalledTimes(updates.length);

        // Check calls for each update
        expect(mockUpdate).toHaveBeenCalledWith(update1.data);
        expect(mockEq).toHaveBeenCalledWith('id', update1.jobId);

        expect(mockUpdate).toHaveBeenCalledWith(update2.data);
        expect(mockEq).toHaveBeenCalledWith('id', update2.jobId);
        
        expect(mockUpdate).toHaveBeenCalledWith(update3.data);
        expect(mockEq).toHaveBeenCalledWith('id', update3.jobId);
    });

    it('should skip updates where the data payload is empty or null', async () => {
        const update1: JobUpdateOperation = {
            jobId: 101,
            data: { status: 'scheduled' } // Valid
        };
        const update2: JobUpdateOperation = {
            jobId: 102,
            data: {} // Empty data
        };
        const update3: JobUpdateOperation = {
            jobId: 103,
            data: null as any // Null data (cast needed for test)
        };
         const update4: JobUpdateOperation = {
            jobId: 104,
            data: { assigned_technician: 8 } // Valid
        };

        const updates = [update1, update2, update3, update4];
        // Mock console.warn to check if it's called
        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

        await updateJobs(mockSupabaseClient, updates);

        // Should only call Supabase update for the valid operations (1 and 4)
        expect(mockFrom).toHaveBeenCalledTimes(2);
        expect(mockUpdate).toHaveBeenCalledTimes(2);
        expect(mockEq).toHaveBeenCalledTimes(2);

        // Check calls for valid updates
        expect(mockUpdate).toHaveBeenCalledWith(update1.data);
        expect(mockEq).toHaveBeenCalledWith('id', update1.jobId);
        expect(mockUpdate).toHaveBeenCalledWith(update4.data);
        expect(mockEq).toHaveBeenCalledWith('id', update4.jobId);

        // Check that warnings were issued for skipped updates
        expect(consoleWarnSpy).toHaveBeenCalledTimes(2); 
        expect(consoleWarnSpy).toHaveBeenCalledWith(`Skipping update for job ${update2.jobId} due to empty update data.`);
        expect(consoleWarnSpy).toHaveBeenCalledWith(`Skipping update for job ${update3.jobId} due to empty update data.`);

        consoleWarnSpy.mockRestore(); // Restore console.warn
    });

    it('should throw an error summarizing failures if one update fails', async () => {
        const update1: JobUpdateOperation = { jobId: 101, data: { status: 'scheduled' } };
        const update2: JobUpdateOperation = { jobId: 102, data: { status: 'overflow' } };
        const update3: JobUpdateOperation = { jobId: 103, data: { status: 'scheduled' } };
        const updates = [update1, update2, update3];

        const mockError = { message: 'DB error', details: 'Constraint violation', code: '23505' };
        // Mock .eq to fail for the second update (jobId 102)
        mockEq
            .mockResolvedValueOnce({ data: [{}], error: null, status: 200, statusText: 'OK' }) // Success for 101
            .mockResolvedValueOnce({ data: null, error: mockError, status: 500, statusText: 'Internal Server Error' }) // Fail for 102
            .mockResolvedValueOnce({ data: [{}], error: null, status: 200, statusText: 'OK' }); // Success for 103

        await expect(updateJobs(mockSupabaseClient, updates)).rejects.toThrow(
            `1 database update(s) failed for job IDs: 102. Check logs for details.`
        );

        // Ensure all updates were attempted
        expect(mockFrom).toHaveBeenCalledTimes(updates.length);
        expect(mockUpdate).toHaveBeenCalledTimes(updates.length);
        expect(mockEq).toHaveBeenCalledTimes(updates.length);
    });

    it('should throw an error summarizing failures if multiple updates fail', async () => {
        const update1: JobUpdateOperation = { jobId: 101, data: { status: 'scheduled' } };
        const update2: JobUpdateOperation = { jobId: 102, data: { status: 'overflow' } };
        const update3: JobUpdateOperation = { jobId: 103, data: { status: 'scheduled' } };
        const updates = [update1, update2, update3];

        const mockError1 = { message: 'DB error 1', details: '...', code: '1' };
        const mockError2 = { message: 'DB error 2', details: '...', code: '2' };
        // Mock .eq to fail for the first and third updates
        mockEq
            .mockResolvedValueOnce({ data: null, error: mockError1, status: 500, statusText: 'Error' }) // Fail for 101
            .mockResolvedValueOnce({ data: [{}], error: null, status: 200, statusText: 'OK' }) // Success for 102
            .mockResolvedValueOnce({ data: null, error: mockError2, status: 500, statusText: 'Error' }); // Fail for 103

        await expect(updateJobs(mockSupabaseClient, updates)).rejects.toThrow(
            `2 database update(s) failed for job IDs: 101, 103. Check logs for details.`
        );

        // Ensure all updates were attempted
        expect(mockFrom).toHaveBeenCalledTimes(updates.length);
        expect(mockUpdate).toHaveBeenCalledTimes(updates.length);
        expect(mockEq).toHaveBeenCalledTimes(updates.length);
    });
}); 