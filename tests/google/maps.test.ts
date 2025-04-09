import { getTravelTime } from '../../src/google/maps';
import { Client, LatLngLiteral, TravelMode } from '@googlemaps/google-maps-services-js';

// Define the mock function *before* using it in jest.mock
const mockDistanceMatrix = jest.fn();

// Mock the Google Maps Client
jest.mock('@googlemaps/google-maps-services-js', () => {
    // Return a factory function for the Client mock
    const mockClientImplementation = jest.fn().mockImplementation(() => {
        // Each new Client instance will get this distancematrix mock
        return {
            distancematrix: mockDistanceMatrix, // Use the mock function defined above
        };
    });

    return {
        // Export the mocked Client constructor
        Client: mockClientImplementation,
        // Export the TravelMode enum
        TravelMode: {
            driving: 'driving',
        }
    };
});

// NOTE: process.env.GOOGLE_MAPS_API_KEY is now loaded via jest.setup.ts and dotenv

// No longer need a separate instance variable for the mock client
// const mockMapsClientInstance = new Client() as jest.Mocked<Client>;
// We will interact directly with mockDistanceMatrix defined above

describe('getTravelTime', () => {
    // We need to dynamically import the module *inside* describe/beforeEach
    // to ensure it picks up the mocked Client and the env variable loaded by setup
    let getTravelTimeFunc: typeof getTravelTime;

    const origin: LatLngLiteral = { lat: 40.7128, lng: -74.0060 }; // NYC
    const destination: LatLngLiteral = { lat: 34.0522, lng: -118.2437 }; // LA
    const expectedDuration = 15000; // Example duration in seconds

    beforeAll(() => {
        jest.useFakeTimers();
    });

    beforeEach(async () => {
        // Clear the mock function's call history and reset its implementation behavior if needed
        mockDistanceMatrix.mockClear();
        // Optional: Reset mock implementation if necessary between tests
        // mockDistanceMatrix.mockReset(); 

        // Reset modules to ensure a fresh state for the cache and client
        jest.resetModules();

        // Dynamically import the module *after* resetting modules and *after* mocks/env are set
        // This will cause src/google/maps.ts to run again, creating a new Client
        // which will use the mocked implementation defined above.
        const mapsModule = await import('../../src/google/maps');
        getTravelTimeFunc = mapsModule.getTravelTime;
    });

    afterAll(() => {
        jest.useRealTimers();
        // No need to restore originalEnv, Jest handles this
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

        // Use the dynamically imported function
        const duration = await getTravelTimeFunc(origin, destination);

        expect(duration).toBe(expectedDuration);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
        expect(mockDistanceMatrix).toHaveBeenCalledWith({
            params: {
                origins: [origin],
                destinations: [destination],
                mode: TravelMode.driving,
                // Key is now read from process.env loaded by dotenv
                key: process.env.GOOGLE_MAPS_API_KEY, // Verify it's read correctly
            },
            timeout: 5000,
        });
    });

    it('should return cached travel time on cache hit', async () => {
        // First call (populates cache)
        mockDistanceMatrix.mockResolvedValueOnce({
            data: { status: 'OK', rows: [{ elements: [{ status: 'OK', duration: { value: expectedDuration } }] }] }
        });
        await getTravelTimeFunc(origin, destination);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);

        // Second call (should hit cache)
        const duration = await getTravelTimeFunc(origin, destination);
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
        await getTravelTimeFunc(origin, destination);
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);

        // Advance time beyond TTL
        jest.advanceTimersByTime(CACHE_TTL_MILLISECONDS + 1000);

        // Second call (should miss cache and call API again)
         mockDistanceMatrix.mockResolvedValueOnce({
            data: { status: 'OK', rows: [{ elements: [{ status: 'OK', duration: { value: expectedDuration + 5 } }] }] } // Return slightly different duration
        });
        const duration = await getTravelTimeFunc(origin, destination);
        expect(duration).toBe(expectedDuration + 5);
        // API should be called again
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(2); // Called once initially, once after expiry
    });

    it('should return null if the API call throws an error', async () => {
        const apiError = new Error('Network error');
        mockDistanceMatrix.mockRejectedValueOnce(apiError);

        const duration = await getTravelTimeFunc(origin, destination);

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

        const duration = await getTravelTimeFunc(origin, destination);

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

        const duration = await getTravelTimeFunc(origin, destination);

        expect(duration).toBeNull();
        expect(mockDistanceMatrix).toHaveBeenCalledTimes(1);
    });
}); 