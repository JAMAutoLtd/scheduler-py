import { processOptimizationResults, ProcessedSchedule, ScheduledJobUpdate } from '../../src/scheduler/results';
import { OptimizationResponsePayload, TechnicianRoute, RouteStop } from '../../src/types/optimization.types';

// Mock Data
const mockStartTime1 = new Date('2024-01-01T09:00:00.000Z');
const mockEndTime1 = new Date('2024-01-01T09:30:00.000Z');
const mockStartTime2 = new Date('2024-01-01T10:00:00.000Z');
const mockEndTime2 = new Date('2024-01-01T11:00:00.000Z');
const mockStartTime3 = new Date('2024-01-01T11:30:00.000Z');
const mockEndTime3 = new Date('2024-01-01T12:00:00.000Z');

const stopJob1: RouteStop = { itemId: 'job_123', arrivalTimeISO: mockStartTime1.toISOString(), startTimeISO: mockStartTime1.toISOString(), endTimeISO: mockEndTime1.toISOString() };
const stopBundle1: RouteStop = { itemId: 'bundle_456', arrivalTimeISO: mockStartTime2.toISOString(), startTimeISO: mockStartTime2.toISOString(), endTimeISO: mockEndTime2.toISOString() };
const stopJob2: RouteStop = { itemId: 'job_789', arrivalTimeISO: mockStartTime3.toISOString(), startTimeISO: mockStartTime3.toISOString(), endTimeISO: mockEndTime3.toISOString() };
const stopInvalidJobId: RouteStop = { itemId: 'job_abc', arrivalTimeISO: mockStartTime1.toISOString(), startTimeISO: mockStartTime1.toISOString(), endTimeISO: mockEndTime1.toISOString() };
const stopInvalidDate: RouteStop = { itemId: 'job_999', arrivalTimeISO: 'invalid-date', startTimeISO: 'invalid-date', endTimeISO: 'invalid-date' };

const routeTech1: TechnicianRoute = { technicianId: 1, stops: [stopJob1, stopBundle1] }; // Job 123, Bundle 456
const routeTech2: TechnicianRoute = { technicianId: 2, stops: [stopJob2] }; // Job 789
const routeTech3_Invalid: TechnicianRoute = { technicianId: 3, stops: [stopInvalidJobId, stopInvalidDate] };


describe('processOptimizationResults', () => {

    it('should throw an error if response status is "error"', () => {
        const errorResponse: OptimizationResponsePayload = {
            status: 'error',
            message: 'Solver blew up',
            routes: [],
        };
        expect(() => processOptimizationResults(errorResponse)).toThrow('Optimization failed: Solver blew up');
    });

    it('should return empty scheduledJobs and unassignedItemIds for empty routes', () => {
        const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [],
            unassignedItemIds: [],
        };
        const result = processOptimizationResults(successResponse);
        expect(result.scheduledJobs).toEqual([]);
        expect(result.unassignedItemIds).toEqual([]);
    });

    it('should correctly process job stops and ignore bundle stops', () => {
        const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech1, routeTech2],
            unassignedItemIds: [],
        };
        const result = processOptimizationResults(successResponse);

        expect(result.scheduledJobs).toHaveLength(2); // Job 123 and Job 789

        // Check Job 123 (from routeTech1)
        const scheduledJob1 = result.scheduledJobs.find(j => j.jobId === 123);
        expect(scheduledJob1).toBeDefined();
        expect(scheduledJob1?.technicianId).toBe(1);
        expect(scheduledJob1?.estimatedSchedISO).toBe(mockStartTime1.toISOString());

        // Check Job 789 (from routeTech2)
        const scheduledJob2 = result.scheduledJobs.find(j => j.jobId === 789);
        expect(scheduledJob2).toBeDefined();
        expect(scheduledJob2?.technicianId).toBe(2);
        expect(scheduledJob2?.estimatedSchedISO).toBe(mockStartTime3.toISOString());

        // Ensure bundle 456 was ignored
        expect(result.scheduledJobs.find(j => j.jobId === 456)).toBeUndefined(); 

        expect(result.unassignedItemIds).toEqual([]);
    });

     it('should pass through unassignedItemIds from the response', () => {
        const partialResponse: OptimizationResponsePayload = {
            status: 'partial',
            routes: [routeTech2], // Only contains Job 789
            unassignedItemIds: ['job_123', 'bundle_456'],
        };
        const result = processOptimizationResults(partialResponse);

        expect(result.scheduledJobs).toHaveLength(1); // Only Job 789
        const scheduledJob = result.scheduledJobs[0];
        expect(scheduledJob.jobId).toBe(789);
        expect(scheduledJob.technicianId).toBe(2);

        expect(result.unassignedItemIds).toEqual(['job_123', 'bundle_456']);
    });

    it('should handle missing unassignedItemIds gracefully', () => {
        const successResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech2],
            // unassignedItemIds is omitted
        };
        const result = processOptimizationResults(successResponse);
        expect(result.scheduledJobs).toHaveLength(1);
        expect(result.unassignedItemIds).toEqual([]); // Should default to empty array
    });

    it('should skip stops with invalid job IDs or dates and log warnings', () => {
        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

        const response: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech3_Invalid], // Contains job_abc and job_999 (invalid date)
            unassignedItemIds: [],
        };
        const result = processOptimizationResults(response);

        expect(result.scheduledJobs).toHaveLength(0); // Both stops should be skipped
        expect(consoleWarnSpy).toHaveBeenCalledWith('Could not parse job ID from itemId:', 'job_abc');
        expect(consoleWarnSpy).toHaveBeenCalledWith(expect.stringContaining('Error processing date for job ID 999 from stop job_999'), expect.any(Error));
        
        consoleWarnSpy.mockRestore();
    });

     it('should handle routes with no stops', () => {
        const routeWithNoStops: TechnicianRoute = { technicianId: 4, stops: [] };
        const response: OptimizationResponsePayload = {
            status: 'success',
            routes: [routeTech1, routeWithNoStops, routeTech2], // Mix of routes
            unassignedItemIds: [],
        };
        const result = processOptimizationResults(response);

        // Should still process the valid stops from routeTech1 and routeTech2
        expect(result.scheduledJobs).toHaveLength(2);
        expect(result.scheduledJobs.find(j => j.jobId === 123)).toBeDefined();
        expect(result.scheduledJobs.find(j => j.jobId === 789)).toBeDefined();
        expect(result.unassignedItemIds).toEqual([]);
    });
}); 