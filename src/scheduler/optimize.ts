import axios, { AxiosResponse } from 'axios';
import { 
    OptimizationRequestPayload, 
    OptimizationResponsePayload 
} from '../types/optimization.types';

// Get the microservice URL from environment variables
const serviceUrl = process.env.OPTIMIZATION_SERVICE_URL;
if (!serviceUrl) {
    // Throw an error during startup if the URL isn't configured
    throw new Error('OPTIMIZATION_SERVICE_URL environment variable is not set.');
}

/**
 * Sends the optimization problem payload to the Python microservice 
 * and returns the resulting schedule solution.
 *
 * @param {OptimizationRequestPayload} payload - The prepared payload for the solver.
 * @returns {Promise<OptimizationResponsePayload>} The response payload from the optimization service.
 * @throws {Error} If the request fails or the service returns an error status.
 */
export async function callOptimizationService(
    payload: OptimizationRequestPayload
): Promise<OptimizationResponsePayload> {
    console.log(`Sending optimization request to: ${serviceUrl}`);

    try {
        const response: AxiosResponse<OptimizationResponsePayload> = await axios.post<OptimizationResponsePayload>(
            serviceUrl!,
            payload,
            {
                headers: { 'Content-Type': 'application/json' },
                timeout: 120000 // Set a timeout (e.g., 120 seconds) for the optimization process
            }
        );

        console.log(`Received response from optimization service. Status: ${response.data.status}`);

        // Check the status within the response data
        if (response.data.status === 'error') {
            console.error('Optimization service returned an error:', response.data.message);
            throw new Error(`Optimization service failed: ${response.data.message || 'Unknown error'}`);
        }
        
        // TODO: Handle 'partial' status appropriately if needed
        if (response.data.status === 'partial'){
            console.warn('Optimization service returned a partial solution:', response.data.message);
            // Decide how to proceed - maybe treat as success for now, or specific handling
        }

        // Return the successful (or partial) response data
        return response.data;

    } catch (error: unknown) {
        console.error('Error calling optimization service:');
        if (axios.isAxiosError(error)) {
            console.error(`Status: ${error.response?.status}`);
            console.error('Response Data:', error.response?.data);
            // Re-throw a more specific error
            throw new Error(
                `HTTP error calling optimization service: ${error.response?.status} - ${error.message}. ` +
                `Check microservice logs at ${serviceUrl}.`
            );
        } else if (error instanceof Error) {
            // Non-Axios error (e.g., network issue before request sent)
            console.error(error);
            throw new Error(`Network or other error calling optimization service: ${error.message}`);
        } else {
             // Handle cases where the caught object is not an Error
             console.error('An unexpected non-Error type was caught:', error);
             throw new Error('An unexpected error occurred while calling the optimization service.');
        }
    }
}

// Example Usage (requires a prepared payload)
/*
import { prepareOptimizationPayload } from './payload';
// ... import other necessary functions (getTechs, getJobs, etc.)

async function runOptimizeExample() {
    try {
        // --- Prepare Payload (Requires data fetching etc.) ---
        console.log('Preparing payload for optimization call example...');
        // const technicians = await getActiveTechnicians(); 
        // const allJobs = await getRelevantJobs();
        // ... (rest of payload prep logic as in payload.ts example) ...
        // const payload = await prepareOptimizationPayload(technicians, eligibleItems, fixedTimeJobs);
        
        // Replace with actual payload preparation
        const dummyPayload: OptimizationRequestPayload = { 
            locations: [], technicians: [], items: [], fixedConstraints: [], travelTimeMatrix: {} 
        }; 
        console.log('Payload prepared (dummy). Calling service...');
        // --- Call Service ---
        const result = await callOptimizationService(dummyPayload); 

        console.log('\n--- Optimization Result ---');
        console.log(JSON.stringify(result, null, 2));

    } catch (error) {
        console.error('\nOptimization call example failed:', error);
    }
}

// runOptimizeExample();
*/ 