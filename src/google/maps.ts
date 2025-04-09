import { Client, LatLngLiteral, TravelMode } from '@googlemaps/google-maps-services-js';

// Basic in-memory cache for travel times
// Key format: "originLat,originLng:destLat,destLng"
// Value: duration in seconds
const travelTimeCache = new Map<string, number>();
const CACHE_TTL = 60 * 60 * 1000; // 1 hour in milliseconds
const cacheTimeStamps = new Map<string, number>();

// Load Google Maps API Key from environment variable
const apiKey = process.env.GOOGLE_MAPS_API_KEY;
if (!apiKey) {
  throw new Error('GOOGLE_MAPS_API_KEY must be provided in environment variables.');
}

const mapsClient = new Client({});

/**
 * Generates a cache key from origin and destination coordinates.
 */
function getCacheKey(origin: LatLngLiteral, destination: LatLngLiteral): string {
  return `${origin.lat},${origin.lng}:${destination.lat},${destination.lng}`;
}

/**
 * Cleans expired entries from the cache.
 */
function cleanExpiredCache(): void {
    const now = Date.now();
    for (const [key, timestamp] of cacheTimeStamps.entries()) {
        if (now - timestamp > CACHE_TTL) {
            travelTimeCache.delete(key);
            cacheTimeStamps.delete(key);
            console.log(`Cache entry expired and removed: ${key}`);
        }
    }
}
// Clean cache periodically (e.g., every hour)
setInterval(cleanExpiredCache, CACHE_TTL);

/**
 * Fetches travel time between two points using Google Maps Distance Matrix API.
 * Uses a simple in-memory cache with TTL.
 *
 * @param {LatLngLiteral} origin - The starting point coordinates.
 * @param {LatLngLiteral} destination - The ending point coordinates.
 * @returns {Promise<number | null>} A promise resolving to the travel duration in seconds, or null if an error occurs.
 */
export async function getTravelTime(origin: LatLngLiteral, destination: LatLngLiteral): Promise<number | null> {
  const cacheKey = getCacheKey(origin, destination);

  // Check cache first
  if (travelTimeCache.has(cacheKey)) {
    const cachedTime = travelTimeCache.get(cacheKey);
    // Check if cache entry is still valid (redundant with setInterval cleanup, but good practice)
    if (Date.now() - (cacheTimeStamps.get(cacheKey) || 0) <= CACHE_TTL) {
        console.log(`Cache hit for ${cacheKey}. Duration: ${cachedTime}s`);
        return cachedTime as number;
    } else {
        // Entry expired, remove it
        travelTimeCache.delete(cacheKey);
        cacheTimeStamps.delete(cacheKey);
        console.log(`Cache expired for ${cacheKey}.`);
    }
  }

  console.log(`Cache miss for ${cacheKey}. Fetching from Google Maps API...`);

  try {
    const response = await mapsClient.distancematrix({
      params: {
        origins: [origin],
        destinations: [destination],
        mode: TravelMode.driving,
        key: apiKey!,
        // Add other parameters like departure_time: 'now' if needed for traffic estimates
      },
      timeout: 5000, // Timeout in milliseconds
    });

    if (response.data.status === 'OK' && response.data.rows[0].elements[0].status === 'OK') {
      const durationSeconds = response.data.rows[0].elements[0].duration.value;
      console.log(`Successfully fetched travel time for ${cacheKey}: ${durationSeconds}s`);
      
      // Store in cache with timestamp
      travelTimeCache.set(cacheKey, durationSeconds);
      cacheTimeStamps.set(cacheKey, Date.now());

      return durationSeconds;
    } else {
      console.error(
        `Error fetching distance matrix for ${cacheKey}: ` +
        `Response status: ${response.data.status}, Element status: ${response.data.rows[0]?.elements[0]?.status}`
      );
      return null;
    }
  } catch (error: any) {
    console.error(`Error calling Google Maps API for ${cacheKey}:`, error.response?.data || error.message || error);
    return null;
  }
}

// Example usage
/*
async function runMapsExample() {
  const originPoint = { lat: 40.7128, lng: -74.0060 }; // Example: NYC
  const destinationPoint = { lat: 34.0522, lng: -118.2437 }; // Example: LA

  try {
    console.log(`Fetching travel time from ${JSON.stringify(originPoint)} to ${JSON.stringify(destinationPoint)}`);
    const duration1 = await getTravelTime(originPoint, destinationPoint);
    console.log(`Attempt 1 - Duration: ${duration1 !== null ? `${duration1} seconds` : 'Error'}`);

    console.log('\nFetching same route again (should hit cache)...');
    const duration2 = await getTravelTime(originPoint, destinationPoint);
    console.log(`Attempt 2 - Duration: ${duration2 !== null ? `${duration2} seconds` : 'Error'}`);

  } catch (err) {
      console.error('Maps example failed:', err);
  }
}

// runMapsExample();
*/ 