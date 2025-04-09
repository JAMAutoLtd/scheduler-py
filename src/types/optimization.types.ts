// Types defining the payload sent TO the Python optimization microservice

import { LatLngLiteral } from '@googlemaps/google-maps-services-js';

/**
 * Represents a location used in the optimization problem.
 * Includes its original ID (e.g., address ID) and its index in the matrix/solver.
 */
export interface OptimizationLocation {
  id: string | number; // Original identifier (e.g., address_id, "tech_1_start", "depot")
  index: number; // Integer index used by the solver (0, 1, 2, ...)
  coords: LatLngLiteral;
}

/**
 * Information about a technician sent to the optimization service.
 */
export interface OptimizationTechnician {
  id: number; // Technician ID
  startLocationIndex: number; // Index of their starting location in the locations array
  endLocationIndex: number; // Index of their ending location (e.g., depot or home base)
  earliestStartTimeISO: string; // ISO 8601 string for earliest availability
  latestEndTimeISO: string; // ISO 8601 string for end of work day
}

/**
 * Information about a schedulable item (job or bundle) sent to the optimization service.
 */
export interface OptimizationItem {
  id: string; // Unique identifier (e.g., "job_123", "bundle_456")
  locationIndex: number; // Index of the job/bundle location
  durationSeconds: number; // Service duration in seconds
  priority: number;
  eligibleTechnicianIds: number[]; // List of tech IDs who can perform this item
}

/**
 * Represents a job with a fixed time constraint.
 */
export interface OptimizationFixedConstraint {
    itemId: string; // ID of the OptimizationItem this applies to
    fixedTimeISO: string; // ISO 8601 string for the mandatory start time
}

/**
 * The structure of the travel time matrix sent to the optimization service.
 * Maps origin_index -> destination_index -> duration_seconds.
 */
export type TravelTimeMatrix = {
  [originIndex: number]: {
    [destinationIndex: number]: number;
  };
};

/**
 * The complete request payload sent to the Python optimization microservice.
 */
export interface OptimizationRequestPayload {
  locations: OptimizationLocation[]; // Array mapping indices to original IDs and coordinates
  technicians: OptimizationTechnician[];
  items: OptimizationItem[];
  fixedConstraints: OptimizationFixedConstraint[];
  travelTimeMatrix: TravelTimeMatrix;
}

// ----- Types defining the response FROM the Python optimization microservice -----

/**
 * Represents a single stop in a technician's route.
 */
export interface RouteStop {
    itemId: string; // ID of the OptimizationItem (job or bundle)
    arrivalTimeISO: string; // Calculated arrival time
    startTimeISO: string; // Calculated service start time (after arrival + wait time if any)
    endTimeISO: string; // Calculated service end time
}

/**
 * Represents the optimized route for a single technician.
 */
export interface TechnicianRoute {
    technicianId: number;
    stops: RouteStop[];
    totalTravelTimeSeconds?: number; // Optional: Total travel time for the route
    totalDurationSeconds?: number; // Optional: Total duration including service and travel
}

/**
 * The expected response payload from the Python optimization microservice.
 */
export interface OptimizationResponsePayload {
    status: 'success' | 'error' | 'partial';
    message?: string; // Optional message, especially on error
    routes: TechnicianRoute[];
    unassignedItemIds?: string[]; // List of item IDs that could not be scheduled
} 