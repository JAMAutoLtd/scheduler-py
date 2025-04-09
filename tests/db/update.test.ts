import { SupabaseClient } from '@supabase/supabase-js';
import { updateJobStatuses } from '../../src/db/update';
import { OptimizationResponsePayload, TechnicianRoute, RouteStop } from '../../src/types/optimization.types';

// Mock Supabase Client and its methods
const mockEq = jest.fn();
const mockUpdate = jest.fn(() => ({ eq: mockEq }));
const mockFrom = jest.fn(() => ({ update: mockUpdate }));

const mockSupabaseClient = { // Mock Client object
    from: mockFrom,
} as unknown as SupabaseClient<any>; // Cast to SupabaseClient type

// Mock Data
const mockStartTime1 = new Date('2024-01-01T09:00:00.000Z');
const mockEndTime1 = new Date('2024-01-01T09:30:00.000Z');
const mockStartTime2 = new Date('2024-01-01T10:00:00.000Z');
const mockEndTime2 = new Date('2024-01-01T11:00:00.000Z');

const stopJob1: RouteStop = { itemId: 'job_101', arrivalTimeISO: mockStartTime1.toISOString(), startTimeISO: mockStartTime1.toISOString(), endTimeISO: mockEndTime1.toISOString() };
const stopJob2: RouteStop = { itemId: 'job_102', arrivalTimeISO: mockStartTime2.toISOString(), startTimeISO: mockStartTime2.toISOString(), endTimeISO: mockEndTime2.toISOString() };
const stopBundle: RouteStop = { itemId: 'bundle_201', arrivalTimeISO: '...', startTimeISO: '...', endTimeISO: '...' };

const routeTech1: TechnicianRoute = { technicianId: 1, stops: [stopJob1] };
const routeTech2: TechnicianRoute = { technicianId: 2, stops: [stopJob2] };

describe('updateJobStatuses', () => {

    beforeEach(() => {
        // Reset mocks before each test
        mockFrom.mockClear();
        mockUpdate.mockClear();
        mockEq.mockClear();
        // Default mock for successful updates
        mockEq.mockResolvedValue({ data: [{}], error: null }); 
    });

    it('should throw an error if optimization response status is "error"', async () => {
        const errorResponse: OptimizationResponsePayload = {
            status: 'error',
            message: 'Solver failed',
            routes: [],
        };

        await expect(updateJobStatuses(mockSupabaseClient, errorResponse)).rejects.toThrow('Optimization failed: Solver failed');
        expect(mockFrom).not.toHaveBeenCalled();
    });

    it('should do nothing if there are no routes and no unassigned items', async () => {
        const emptyResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [],
            unassignedItemIds: [],
        };

        await updateJobStatuses(mockSupabaseClient, emptyResponse);
        expect(mockFrom).not.toHaveBeenCalled();
    });

    it('should update scheduled jobs correctly', async () => {
        const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech1, routeTech2],
            unassignedItemIds: [],
        };

        await updateJobStatuses(mockSupabaseClient, successResponse);

        expect(mockFrom).toHaveBeenCalledWith('jobs');
        expect(mockUpdate).toHaveBeenCalledTimes(2);
        expect(mockEq).toHaveBeenCalledTimes(2);

        // Check update call for Job 101
        expect(mockUpdate).toHaveBeenCalledWith({
            assigned_technician: 1,
            estimated_sched: mockStartTime1.toISOString(),
            status: 'scheduled',
        });
        expect(mockEq).toHaveBeenCalledWith('id', 101);

        // Check update call for Job 102
        expect(mockUpdate).toHaveBeenCalledWith({
            assigned_technician: 2,
            estimated_sched: mockStartTime2.toISOString(),
            status: 'scheduled',
        });
        expect(mockEq).toHaveBeenCalledWith('id', 102);
    });

    it('should update unassigned (overflow) jobs correctly', async () => {
        const partialResponse: OptimizationResponsePayload = {
            status: 'partial',
            routes: [],
            unassignedItemIds: ['job_103', 'job_104'],
        };

        await updateJobStatuses(mockSupabaseClient, partialResponse);

        expect(mockFrom).toHaveBeenCalledWith('jobs');
        expect(mockUpdate).toHaveBeenCalledTimes(2);
        expect(mockEq).toHaveBeenCalledTimes(2);

        const expectedOverflowUpdate = {
            status: 'pending_review',
            assigned_technician: null,
            estimated_sched: null,
        };

        // Check update call for Job 103
        expect(mockUpdate).toHaveBeenCalledWith(expectedOverflowUpdate);
        expect(mockEq).toHaveBeenCalledWith('id', 103);

        // Check update call for Job 104
        expect(mockUpdate).toHaveBeenCalledWith(expectedOverflowUpdate);
        expect(mockEq).toHaveBeenCalledWith('id', 104);
    });

    it('should handle a mix of scheduled and unassigned jobs, ignoring bundles and invalid IDs', async () => {
        const mixedResponse: OptimizationResponsePayload = {
            status: 'partial',
            routes: [
                { technicianId: 1, stops: [stopJob1, stopBundle] }, // Job 101 scheduled, Bundle ignored
            ],
            unassignedItemIds: ['job_105', 'bundle_202', 'job_invalid'], // Job 105 overflow, Bundle ignored, invalid ignored
        };

        await updateJobStatuses(mockSupabaseClient, mixedResponse);

        expect(mockFrom).toHaveBeenCalledWith('jobs');
        expect(mockUpdate).toHaveBeenCalledTimes(2); // One scheduled, one overflow
        expect(mockEq).toHaveBeenCalledTimes(2);

        // Check scheduled update (Job 101)
        expect(mockUpdate).toHaveBeenCalledWith({
            assigned_technician: 1,
            estimated_sched: mockStartTime1.toISOString(),
            status: 'scheduled',
        });
        expect(mockEq).toHaveBeenCalledWith('id', 101);

        // Check overflow update (Job 105)
        expect(mockUpdate).toHaveBeenCalledWith({
            status: 'pending_review',
            assigned_technician: null,
            estimated_sched: null,
        });
        expect(mockEq).toHaveBeenCalledWith('id', 105);
    });

    it('should throw an error if any database update fails', async () => {
        const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech1, routeTech2], // Job 101, Job 102
            unassignedItemIds: ['job_103'], // Job 103 overflow
        };

        // Mock one failure (e.g., the second update for job 102)
        const mockError = { message: 'DB constraint violated', code: '23505' };
        mockEq.mockResolvedValueOnce({ data: [{}], error: null }); // Job 101 succeeds
        mockEq.mockResolvedValueOnce({ data: null, error: mockError }); // Job 102 fails
        mockEq.mockResolvedValueOnce({ data: [{}], error: null }); // Job 103 succeeds

        await expect(updateJobStatuses(mockSupabaseClient, successResponse)).rejects.toThrow(
            '1 database update(s) failed. Check logs for details.'
        );

        // Ensure all updates were still attempted
        expect(mockFrom).toHaveBeenCalledWith('jobs');
        expect(mockUpdate).toHaveBeenCalledTimes(3);
        expect(mockEq).toHaveBeenCalledTimes(3);
    });

    it('should throw a correctly counted error if multiple updates fail', async () => {
         const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech1, routeTech2], // Job 101, Job 102
            unassignedItemIds: ['job_103'], // Job 103 overflow
        };

        // Mock multiple failures
        const mockError1 = { message: 'DB error 1', code: '1' };
        const mockError2 = { message: 'DB error 2', code: '2' };
        mockEq.mockResolvedValueOnce({ data: null, error: mockError1 }); // Job 101 fails
        mockEq.mockResolvedValueOnce({ data: [{}], error: null });    // Job 102 succeeds
        mockEq.mockResolvedValueOnce({ data: null, error: mockError2 }); // Job 103 fails

        await expect(updateJobStatuses(mockSupabaseClient, successResponse)).rejects.toThrow(
            '2 database update(s) failed. Check logs for details.'
        );
        expect(mockEq).toHaveBeenCalledTimes(3);
    });
}); 