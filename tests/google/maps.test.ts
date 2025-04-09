import { getTravelTime } from '../../src/google/maps';
import { Client, LatLngLiteral, TravelMode } from '@googlemaps/google-maps-services-js';

// Mock the Google Maps Client
jest.mock('@googlemaps/google-maps-services-js', () => {
    return {
        Client: jest.fn().mockImplementation(() => {
            return {
                distancematrix: jest.fn(),
            };
        }),
        TravelMode: { // Need to provide the enum used in the original file
            driving: 'driving',
        }
    };
});

// Mock process.env
const originalEnv = process.env;
process.env = {
    ...originalEnv,
    GOOGLE_MAPS_API_KEY: 'test-api-key',
};

// Helper to access the mock client instance and its methods
const mockMapsClientInstance = new Client() as jest.Mocked<Client>;
const mockDistanceMatrix = mockMapsClientInstance.distancematrix as jest.Mock;

describe('getTravelTime', () => {
    const origin: LatLngLiteral = { lat: 40.7128, lng: -74.0060 }; // NYC
    const destination: LatLngLiteral = { lat: 34.0522, lng: -118.2437 }; // LA
    const expectedDuration = 15000; // Example duration in seconds

    beforeAll(() => {
        jest.useFakeTimers();
    });

    beforeEach(() => {
        // Clear mocks and cache before each test
        mockDistanceMatrix.mockClear();
        // Clear the internal cache by calling the function again, effectively resetting it
        // We need to reset the cache module state between tests. A simple way is reloading the module.
        jest.resetModules(); // This clears module cache including the internal cache Map
        // Re-import after reset
        require('../../src/google/maps');
        // Restore mock API key as resetModules clears process.env changes within the test scope
        process.env.GOOGLE_MAPS_API_KEY = 'test-api-key';
    });

    afterAll(() => {
        jest.useRealTimers();
        process.env = originalEnv; // Restore original environment variables
    });

    it('should fetch travel time from API on cache miss', async () => {
        mockDistanceMatrix.mockResolvedValueOnce({
            data: {
                status: 'OK',
                rows: [
                    {
                        elements: [
                            {
                                status: 'OK',
                                duration: { value: expectedDuration, text: '4 hours' },
                                distance: { value: 100000, text: '100 km' }
                            }
                        ]
                    }
                ]
            }
        });

        const duration = await getTravelTime(origin, destination);

        expect(duration).toBe(expectedDuration);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
        expect(mockDistanceMatrix).toHaveBeenCalledWith({
            params: {
                origins: [origin],
                destinations: [destination],
                mode: TravelMode.driving,
                key: 'test-api-key',
            },
            timeout: 5000,
        });
    });

    it('should return cached travel time on cache hit', async () => {
        // First call (populates cache)
        mockDistanceMatrix.mockResolvedValueOnce({
            data: { status: 'OK', rows: [{ elements: [{ status: 'OK', duration: { value: expectedDuration } }] }] }
        });
        await getTravelTime(origin, destination);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);

        // Second call (should hit cache)
        const duration = await getTravelTime(origin, destination);
        expect(duration).toBe(expectedDuration);
        // API should not be called again
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
    });

    it('should fetch from API again after cache TTL expires', async () => {
        const CACHE_TTL_MILLISECONDS = 60 * 60 * 1000; // 1 hour (must match the value in maps.ts)

        // First call (populates cache)
        mockDistanceMatrix.mockResolvedValueOnce({
            data: { status: 'OK', rows: [{ elements: [{ status: 'OK', duration: { value: expectedDuration } }] }] }
        });
        await getTravelTime(origin, destination);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);

        // Advance time beyond TTL
        jest.advanceTimersByTime(CACHE_TTL_MILLISECONDS + 1000);

        // Second call (should miss cache and call API again)
         mockDistanceMatrix.mockResolvedValueOnce({
            data: { status: 'OK', rows: [{ elements: [{ status: 'OK', duration: { value: expectedDuration + 5 } }] }] } // Return slightly different duration
        });
        const duration = await getTravelTime(origin, destination);
        expect(duration).toBe(expectedDuration + 5);
        // API should be called again
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(2); // Called once initially, once after expiry
    });

    it('should return null if the API call throws an error', async () => {
        const apiError = new Error('Network error');
        mockDistanceMatrix.mockRejectedValueOnce(apiError);

        const duration = await getTravelTime(origin, destination);

        expect(duration).toBeNull();
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
    });

    it('should return null if the API response status is not OK', async () => {
        mockDistanceMatrix.mockResolvedValueOnce({
            data: {
                status: 'REQUEST_DENIED',
                error_message: 'API key invalid',
                rows: []
            }
        });

        const duration = await getTravelTime(origin, destination);

        expect(duration).toBeNull();
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
    });

    it('should return null if the API element status is not OK', async () => {
        mockDistanceMatrix.mockResolvedValueOnce({
            data: {
                status: 'OK',
                rows: [
                    {
                        elements: [
                            {
                                status: 'ZERO_RESULTS', // e.g., location not found
                            }
                        ]
                    }
                ]
            }
        });

        const duration = await getTravelTime(origin, destination);

        expect(duration).toBeNull();
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
    });
}); 