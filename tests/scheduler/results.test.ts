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

    // Define spy outside tests
    let consoleWarnSpy: jest.SpyInstance;

    beforeEach(() => {
        // Mock console.warn before each test and clear previous calls
        consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    });

    afterEach(() => {
        // Restore console.warn after each test
        consoleWarnSpy.mockRestore();
    });

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
        expect(consoleWarnSpy).not.toHaveBeenCalled();
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
        expect(consoleWarnSpy).not.toHaveBeenCalled();
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
        expect(consoleWarnSpy).not.toHaveBeenCalled();
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
        expect(consoleWarnSpy).not.toHaveBeenCalled();
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
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    // Test Case 1: Basic success with scheduled jobs and unassigned items
    it('should correctly process a successful response with scheduled and unassigned items', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 101,
                    stops: [
                        { itemId: 'job_1', arrivalTimeISO: '2024-08-01T10:00:00Z', startTimeISO: '2024-08-01T10:05:00Z', endTimeISO: '2024-08-01T11:05:00Z' },
                        { itemId: 'job_3', arrivalTimeISO: '2024-08-01T11:30:00Z', startTimeISO: '2024-08-01T11:35:00Z', endTimeISO: '2024-08-01T12:35:00Z' }
                    ]
                },
                {
                    technicianId: 102,
                    stops: [
                        { itemId: 'job_2', arrivalTimeISO: '2024-08-01T09:30:00Z', startTimeISO: '2024-08-01T09:35:00Z', endTimeISO: '2024-08-01T10:35:00Z' }
                    ]
                }
            ],
            unassignedItemIds: ['job_4', 'bundle_5']
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 1, technicianId: 101, estimatedSchedISO: '2024-08-01T10:05:00.000Z' },
                { jobId: 3, technicianId: 101, estimatedSchedISO: '2024-08-01T11:35:00.000Z' },
                { jobId: 2, technicianId: 102, estimatedSchedISO: '2024-08-01T09:35:00.000Z' }
            ],
            unassignedItemIds: ['job_4', 'bundle_5']
        };

        // Sort scheduledJobs by jobId for consistent comparison
        const result = processOptimizationResults(mockResponse);
        result.scheduledJobs.sort((a, b) => a.jobId - b.jobId);
        expectedResult.scheduledJobs.sort((a, b) => a.jobId - b.jobId);

        expect(result).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled(); // Ensure no warnings for valid data
    });

    // Test Case 2: Only unassigned items
    it('should handle responses with only unassigned items', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [],
            unassignedItemIds: ['job_10', 'job_11']
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [],
            unassignedItemIds: ['job_10', 'job_11']
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    // Test Case 3: Only scheduled items
    it('should handle responses with only scheduled items and no unassigned', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 103,
                    stops: [
                        { itemId: 'job_5', arrivalTimeISO: '2024-08-01T14:00:00Z', startTimeISO: '2024-08-01T14:05:00Z', endTimeISO: '2024-08-01T15:05:00Z' }
                    ]
                }
            ],
            unassignedItemIds: [] // Explicitly empty
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 5, technicianId: 103, estimatedSchedISO: '2024-08-01T14:05:00.000Z' }
            ],
            unassignedItemIds: []
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

     // Test Case 4: Unassigned Item ID missing
    it('should handle responses with only scheduled items and missing unassignedIds property', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 103,
                    stops: [
                        { itemId: 'job_5', arrivalTimeISO: '2024-08-01T14:00:00Z', startTimeISO: '2024-08-01T14:05:00Z', endTimeISO: '2024-08-01T15:05:00Z' }
                    ]
                }
            ]
            // unassignedItemIds property is missing
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 5, technicianId: 103, estimatedSchedISO: '2024-08-01T14:05:00.000Z' }
            ],
            unassignedItemIds: [] // Expect empty array when property is missing
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    // Test Case 5: Empty successful response
    it('should handle empty successful responses', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [],
            unassignedItemIds: []
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [],
            unassignedItemIds: []
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    // Test Case 6: Error status
    it('should throw an error if the response status is "error"', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'error',
            message: 'Solver timed out',
            routes: [],
            unassignedItemIds: ['job_1', 'job_2'] // May still contain items
        };

        expect(() => processOptimizationResults(mockResponse))
            .toThrow('Optimization failed: Solver timed out');
    });

     // Test Case 7: Error status without message
    it('should throw an error with a default message if status is "error" and message is missing', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'error',
            routes: [],
        };

        expect(() => processOptimizationResults(mockResponse))
            .toThrow('Optimization failed: Unknown error');
    });

    // Test Case 8: Partial status
    it('should process a "partial" status response like a success response', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'partial',
            message: 'Could not schedule low priority items',
            routes: [
                {
                    technicianId: 101,
                    stops: [
                        { itemId: 'job_1', arrivalTimeISO: '2024-08-01T10:00:00Z', startTimeISO: '2024-08-01T10:05:00Z', endTimeISO: '2024-08-01T11:05:00Z' },
                    ]
                }
            ],
            unassignedItemIds: ['job_4']
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 1, technicianId: 101, estimatedSchedISO: '2024-08-01T10:05:00.000Z' }
            ],
            unassignedItemIds: ['job_4']
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled(); // Should not warn for partial status itself
    });

    // Test Case 9: Handles bundle item IDs correctly
    it('should ignore bundle IDs in routes and pass them through in unassignedItemIds', () => {
        const mockResponse: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 101,
                    stops: [
                        // Bundle stops should not result in ScheduledJobUpdate entries
                        { itemId: 'bundle_10', arrivalTimeISO: '2024-08-01T10:00:00Z', startTimeISO: '2024-08-01T10:05:00Z', endTimeISO: '2024-08-01T11:05:00Z' },
                        { itemId: 'job_3', arrivalTimeISO: '2024-08-01T11:30:00Z', startTimeISO: '2024-08-01T11:35:00Z', endTimeISO: '2024-08-01T12:35:00Z' }
                    ]
                }
            ],
            unassignedItemIds: ['job_4', 'bundle_11']
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 3, technicianId: 101, estimatedSchedISO: '2024-08-01T11:35:00.000Z' }
            ],
            unassignedItemIds: ['job_4', 'bundle_11']
        };

        expect(processOptimizationResults(mockResponse)).toEqual(expectedResult);
        expect(consoleWarnSpy).not.toHaveBeenCalled();
    });

    // Test Case 10: Handles invalid date string gracefully
    it('should skip stops with invalid startTimeISO date formats', () => {
         const mockResponseInvalidDate: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 102,
                    stops: [
                        { itemId: 'job_8', arrivalTimeISO: '2024-08-01T09:30:00Z', startTimeISO: 'invalid-date-string', endTimeISO: '2024-08-01T10:35:00Z' },
                        { itemId: 'job_9', arrivalTimeISO: '2024-08-01T11:00:00Z', startTimeISO: '2024-08-01T11:05:00Z', endTimeISO: '2024-08-01T12:05:00Z' }
                    ]
                }
            ],
            unassignedItemIds: []
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                { jobId: 9, technicianId: 102, estimatedSchedISO: '2024-08-01T11:05:00.000Z' }
            ],
            unassignedItemIds: []
        };

        expect(processOptimizationResults(mockResponseInvalidDate)).toEqual(expectedResult);
        // Check that the specific warning for job_8 was logged with the error object
        expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
        expect(consoleWarnSpy).toHaveBeenCalledWith(
            expect.stringContaining('Error processing date for job ID 8 from stop job_8:'),
            expect.any(RangeError) // Expect the second argument to be a RangeError
        );
    });

    // Test Case 11: Handles unparseable job ID gracefully
    it('should skip stops where jobId cannot be parsed from itemId', () => {
        const mockResponseInvalidId: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 103,
                    stops: [
                        { itemId: 'job_abc', arrivalTimeISO: '2024-08-01T13:00:00Z', startTimeISO: '2024-08-01T13:05:00Z', endTimeISO: '2024-08-01T14:05:00Z' },
                        { itemId: 'job_12', arrivalTimeISO: '2024-08-01T14:30:00Z', startTimeISO: '2024-08-01T14:35:00Z', endTimeISO: '2024-08-01T15:35:00Z' }
                    ]
                }
            ],
            unassignedItemIds: []
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                 { jobId: 12, technicianId: 103, estimatedSchedISO: '2024-08-01T14:35:00.000Z' }
            ],
            unassignedItemIds: []
        };

        expect(processOptimizationResults(mockResponseInvalidId)).toEqual(expectedResult);
        expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
        // Check the single string argument for the invalid ID warning
        expect(consoleWarnSpy).toHaveBeenCalledWith('Could not parse job ID from itemId: job_abc');
    });

    // Test Case 12: Handles BOTH invalid date AND invalid ID gracefully
    it('should skip stops with invalid job IDs or dates and log warnings for both', () => {
        const mockResponseBothInvalid: OptimizationResponsePayload = {
            status: 'success',
            routes: [
                {
                    technicianId: 104,
                    stops: [
                        { itemId: 'job_xyz', arrivalTimeISO: '2024-08-01T13:00:00Z', startTimeISO: '2024-08-01T13:05:00Z', endTimeISO: '2024-08-01T14:05:00Z' }, // Invalid ID
                        { itemId: 'job_15', arrivalTimeISO: '2024-08-01T14:30:00Z', startTimeISO: 'completely-wrong-date', endTimeISO: '2024-08-01T15:35:00Z' }, // Invalid Date
                        { itemId: 'job_16', arrivalTimeISO: '2024-08-01T16:00:00Z', startTimeISO: '2024-08-01T16:05:00Z', endTimeISO: '2024-08-01T17:05:00Z' } // Valid
                    ]
                }
            ],
            unassignedItemIds: []
        };

        const expectedResult: ProcessedSchedule = {
            scheduledJobs: [
                 { jobId: 16, technicianId: 104, estimatedSchedISO: '2024-08-01T16:05:00.000Z' }
            ],
            unassignedItemIds: []
        };

        expect(processOptimizationResults(mockResponseBothInvalid)).toEqual(expectedResult);

        // Check that TWO warnings were logged
        expect(consoleWarnSpy).toHaveBeenCalledTimes(2);

        // Check the warning for the invalid ID (expects ONE argument: the combined string)
        expect(consoleWarnSpy).toHaveBeenCalledWith('Could not parse job ID from itemId: job_xyz');

        // Check the warning for the invalid date (expects TWO arguments: string + error object)
        expect(consoleWarnSpy).toHaveBeenCalledWith(
            expect.stringContaining('Error processing date for job ID 15 from stop job_15:'), // Message for invalid date
            expect.any(RangeError) // The actual error object
        );
    });
}); 