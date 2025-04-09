import axios from 'axios';
import { callOptimizationService } from '../../src/scheduler/optimize';
import { OptimizationRequestPayload, OptimizationResponsePayload } from '../../src/types/optimization.types';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock environment variable
const MOCK_SERVICE_URL = 'http://test-optimizer.local/optimize';
const originalEnv = process.env;

beforeAll(() => {
    // Set the required env var before tests
    process.env = {
        ...originalEnv,
        OPTIMIZATION_SERVICE_URL: MOCK_SERVICE_URL,
    };
});

afterAll(() => {
    // Restore original env vars after tests
    process.env = originalEnv;
});

// Mock Data - Corrected Response Structures
const mockRequestPayload: OptimizationRequestPayload = {
    locations: [],
    technicians: [],
    items: [],
    fixedConstraints: [],
    travelTimeMatrix: {},
};

const mockSuccessResponse: OptimizationResponsePayload = {
    status: 'success',
    message: 'Optimization successful.',
    // routes is an array
    routes: [
        { technicianId: 1, stops: [], totalDurationSeconds: 0, totalTravelTimeSeconds: 0 }
    ],
    unassignedItemIds: [], // Corrected name
    // metrics were not part of the defined type, removing them
};

const mockPartialResponse: OptimizationResponsePayload = {
    status: 'partial',
    message: 'Could not assign all items.',
    // routes is an array
    routes: [
         { technicianId: 1, stops: [], totalDurationSeconds: 0, totalTravelTimeSeconds: 0 }
    ],
    unassignedItemIds: ['job_5'], // Corrected name
     // metrics were not part of the defined type, removing them
};

const mockErrorResponse: OptimizationResponsePayload = {
    status: 'error',
    message: 'Invalid input data format.',
    routes: [], // Use empty array instead of null
    unassignedItemIds: [], // Use empty array instead of null
     // metrics were not part of the defined type, removing them
};

describe('callOptimizationService', () => {

    beforeEach(() => {
        // Clear mocks before each test
        mockedAxios.post.mockClear();
    });

    it('should call axios.post with the correct URL, payload, and config', async () => {
        mockedAxios.post.mockResolvedValueOnce({ data: mockSuccessResponse });

        await callOptimizationService(mockRequestPayload);

        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
        expect(mockedAxios.post).toHaveBeenCalledWith(
            MOCK_SERVICE_URL,
            mockRequestPayload,
            {
                headers: { 'Content-Type': 'application/json' },
                timeout: 120000 // Check timeout is set
            }
        );
    });

    it('should return the response data on successful call with status "success"', async () => {
        mockedAxios.post.mockResolvedValueOnce({ data: mockSuccessResponse });

        const result = await callOptimizationService(mockRequestPayload);

        expect(result).toEqual(mockSuccessResponse);
    });

    it('should return the response data on successful call with status "partial"', async () => {
        // Partial is still considered a success in terms of the API call itself
        mockedAxios.post.mockResolvedValueOnce({ data: mockPartialResponse });

        const result = await callOptimizationService(mockRequestPayload);

        expect(result).toEqual(mockPartialResponse);
        // Optionally, check for console.warn if important
    });

    it('should throw an error if the response data status is "error"', async () => {
        mockedAxios.post.mockResolvedValueOnce({ data: mockErrorResponse });

        await expect(callOptimizationService(mockRequestPayload)).rejects.toThrow(
            `Optimization service failed: ${mockErrorResponse.message}`
        );
        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });

    it('should throw an error on Axios HTTP error (e.g., 404)', async () => {
        const mockError = {
            isAxiosError: true,
            response: {
                status: 404,
                data: { detail: 'Not Found' },
            },
            message: 'Request failed with status code 404',
        };
        mockedAxios.post.mockRejectedValueOnce(mockError);

        await expect(callOptimizationService(mockRequestPayload)).rejects.toThrow(
            `HTTP error calling optimization service: 404 - ${mockError.message}. Check microservice logs at ${MOCK_SERVICE_URL}.`
        );
        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });

     it('should throw an error on Axios timeout error', async () => {
        const mockError = {
            isAxiosError: true,
            code: 'ECONNABORTED',
            message: 'timeout of 120000ms exceeded',
            response: undefined, // No response on timeout
        };
        mockedAxios.post.mockRejectedValueOnce(mockError);

        // The error message construction might vary slightly depending on how Axios formats timeout errors
        // We check for the core parts.
         await expect(callOptimizationService(mockRequestPayload)).rejects.toThrow(
             /HTTP error calling optimization service: undefined - .*timeout/i // Check for status undefined and timeout message
         );
        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });

    it('should throw an error on generic network error', async () => {
        const genericError = new Error('Network Error');
        mockedAxios.post.mockRejectedValueOnce(genericError);

        await expect(callOptimizationService(mockRequestPayload)).rejects.toThrow(
            `Network or other error calling optimization service: ${genericError.message}`
        );
        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
    });
}); 