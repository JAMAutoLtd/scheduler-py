from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Literal

# --- Request Payload Models ---

class LatLngLiteral(BaseModel):
    lat: float
    lng: float

class OptimizationLocation(BaseModel):
    id: Union[str, int] # Original identifier (e.g., address_id, "tech_1_start", "depot")
    index: int          # Integer index used by the solver (0, 1, 2, ...)
    coords: LatLngLiteral

class OptimizationTechnician(BaseModel):
    id: int                 # Technician ID
    startLocationIndex: int # Index of their starting location in the locations array
    endLocationIndex: int   # Index of their ending location (e.g., depot or home base)
    earliestStartTimeISO: str # ISO 8601 string for earliest availability
    latestEndTimeISO: str   # ISO 8601 string for end of work day

class OptimizationItem(BaseModel):
    id: str                 # Unique identifier (e.g., "job_123", "bundle_456")
    locationIndex: int      # Index of the job/bundle location
    durationSeconds: int    # Service duration in seconds
    priority: int
    eligibleTechnicianIds: List[int] # List of tech IDs who can perform this item

class OptimizationFixedConstraint(BaseModel):
    itemId: str             # ID of the OptimizationItem this applies to
    fixedTimeISO: str       # ISO 8601 string for the mandatory start time

# Type alias for the nested dictionary structure
TravelTimeMatrix = Dict[int, Dict[int, int]]

class OptimizationRequestPayload(BaseModel):
    locations: List[OptimizationLocation]
    technicians: List[OptimizationTechnician]
    items: List[OptimizationItem]
    fixedConstraints: List[OptimizationFixedConstraint]
    travelTimeMatrix: TravelTimeMatrix

# --- Response Payload Models ---

class RouteStop(BaseModel):
    itemId: str             # ID of the OptimizationItem (job or bundle)
    arrivalTimeISO: str     # Calculated arrival time
    startTimeISO: str       # Calculated service start time
    endTimeISO: str         # Calculated service end time

class TechnicianRoute(BaseModel):
    technicianId: int
    stops: List[RouteStop]
    totalTravelTimeSeconds: Optional[int] = None # Optional: Total travel time for the route
    totalDurationSeconds: Optional[int] = None   # Optional: Total duration including service and travel

class OptimizationResponsePayload(BaseModel):
    status: Literal['success', 'error', 'partial']
    message: Optional[str] = None # Optional message, especially on error
    routes: List[TechnicianRoute]
    unassignedItemIds: Optional[List[str]] = None # List of item IDs that could not be scheduled 