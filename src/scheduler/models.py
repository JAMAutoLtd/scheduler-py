import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field, validator


# --- Enums based on DATABASE.md ---

class CustomerType(str, Enum):
    RESIDENTIAL = 'residential'
    COMMERCIAL = 'commercial'
    INSURANCE = 'insurance'

class ServiceCategory(str, Enum):
    ADAS = 'adas'
    AIRBAG = 'airbag'
    IMMO = 'immo'
    PROG = 'prog'
    DIAG = 'diag'

class JobStatus(str, Enum):
    PENDING_REVIEW = 'pending_review'
    ASSIGNED = 'assigned'
    SCHEDULED = 'scheduled'
    PENDING_REVISIT = 'pending_revisit'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'

class EquipmentType(str, Enum):
    ADAS = 'adas'
    AIRBAG = 'airbag'
    IMMO = 'immo'
    PROG = 'prog'
    DIAG = 'diag'

# --- Core Models ---

class Address(BaseModel):
    """Represents a physical address with coordinates."""
    id: int
    street_address: str
    lat: float
    lng: float

class Equipment(BaseModel):
    """Represents a piece of equipment or tool."""
    id: int
    equipment_type: EquipmentType
    model: str # Represents the specific model, e.g., 'AUTEL-CSC0602/01'

class Van(BaseModel):
    """Represents a service van."""
    id: int
    last_service: Optional[datetime] = None
    next_service: Optional[datetime] = None
    vin: Optional[str] = None # Can be null according to schema, FK deferred
    equipment: List[Equipment] = Field(default_factory=list) # Loaded separately

class Technician(BaseModel):
    """Represents a technician user."""
    id: int
    user_id: uuid.UUID
    assigned_van_id: Optional[int] = None # Could be unassigned
    workload: int = Field(ge=0, default=0)
    home_address: Address # Assuming home address is always available for scheduling
    current_location: Optional[Address] = None # Track current location if available
    assigned_van: Optional[Van] = None # Populated during data fetching
    availability: Dict[int, 'DailyAvailability'] = Field(default_factory=dict) # day_number: Availability
    schedule: Dict[int, List['SchedulableUnit']] = Field(default_factory=dict) # day_number: [Unit1, Unit2] - Stores the multi-day plan

    def has_equipment(self, required_equipment_model: str) -> bool:
        """Checks if the technician's assigned van has a specific equipment model."""
        if not self.assigned_van:
            return False
        return any(eq.model == required_equipment_model for eq in self.assigned_van.equipment)

    def has_all_equipment(self, jobs: List['Job']) -> bool:
        """Checks if the technician's van has all equipment needed for a list of jobs."""
        if not self.assigned_van:
            # If any job requires equipment, and tech has no van, return False
            return not any(job.equipment_requirements for job in jobs)

        required_models = set()
        for job in jobs:
            required_models.update(job.equipment_requirements)

        van_models = {eq.model for eq in self.assigned_van.equipment}
        return required_models.issubset(van_models)

class Service(BaseModel):
    """Represents a service offered."""
    id: int
    service_name: str
    service_category: ServiceCategory

class CustomerVehicle(BaseModel):
    """Represents a customer's vehicle."""
    id: int
    vin: str = Field(min_length=17, max_length=17)
    make: str
    year: int
    model: str
    ymm_id: Optional[int] = None # FK to ymm_ref, might need separate loading

class Order(BaseModel):
    """Represents a customer's service order."""
    id: int
    user_id: uuid.UUID
    vehicle_id: int
    repair_order_number: Optional[str] = None
    address_id: int
    earliest_available_time: datetime
    notes: Optional[str] = None
    invoice: Optional[int] = None # Assuming this is a reference number
    # Related objects loaded separately
    customer_type: CustomerType # Need user info to determine this
    address: Address
    vehicle: CustomerVehicle
    services: List[Service] = Field(default_factory=list) # Populated from order_services

class Job(BaseModel):
    """Represents a single schedulable job, potentially part of an Order."""
    id: int
    order_id: int
    service_id: int # Foreign key to the specific service this job performs
    assigned_technician: Optional[int] = None  # Changed from assigned_technician_id to match DB schema
    address_id: int
    priority: int = Field(ge=0)
    status: JobStatus
    requested_time: Optional[datetime] = None 
    estimated_sched: Optional[datetime] = None # Calculated by scheduler
    estimated_sched_end: Optional[datetime] = None # End time of scheduled job
    customer_eta_start: Optional[datetime] = None # Start of customer-facing ETA window
    customer_eta_end: Optional[datetime] = None # End of customer-facing ETA window
    job_duration: timedelta # Estimated duration (use timedelta)
    notes: Optional[str] = None
    fixed_assignment: bool = False # Is this assignment fixed/manual?
    fixed_schedule_time: Optional[datetime] = None # If set, mandatory start time
    # Related objects loaded separately
    order_ref: Order # Reference back to the full order details
    address: Address
    equipment_requirements: List[str] = Field(default_factory=list) # List of required equipment models

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Job):
            return False
        return self.id == other.id

    @validator('job_duration', pre=True)
    def ensure_timedelta(cls, v):
        if isinstance(v, int):
            # Assuming integer value from DB is minutes
            return timedelta(minutes=v)
        if isinstance(v, timedelta):
            return v
        raise ValueError("job_duration must be an integer (minutes) or timedelta")

# --- Scheduler Specific Models ---

class DailyAvailability(BaseModel):
    """Represents a technician's availability for a single day."""
    day_number: int # Relative day (1 = today, 2 = tomorrow)
    start_time: datetime # Start of work window
    end_time: datetime # End of work window
    total_duration: timedelta # Total available work time (end - start - breaks?)

    @validator('total_duration', pre=True, always=True)
    def calculate_duration(cls, v, values):
        if 'start_time' in values and 'end_time' in values:
            if values['end_time'] > values['start_time']:
                return values['end_time'] - values['start_time']
            return timedelta(0)
        return v or timedelta(0) # Handle case where duration might be pre-calculated

class SchedulableUnit(BaseModel):
    """Represents a block of one or more jobs assigned to the same technician, treated as a single unit for routing."""
    id: str = Field(default_factory=lambda: f"unit_{uuid.uuid4().hex[:8]}") # Unique ID for the unit
    order_id: int
    jobs: List[Job]
    priority: int # Highest priority of jobs within the unit
    location: Address # The single address for all jobs in this unit/order
    duration: timedelta # Total duration for all jobs in the unit (sum of job_duration)
    assigned_technician: Optional[int] = None # Changed from assigned_technician_id to match DB schema
    fixed_assignment: bool = False # If any job in the unit has fixed_assignment=true
    fixed_schedule_time: Optional[datetime] = None # If any job in the unit has a fixed time, this holds that time.

    # Optional fields for tracking during scheduling/routing
    estimated_start_time: Optional[datetime] = None
    estimated_end_time: Optional[datetime] = None


# --- Forward References Update ---
# Allows models to refer to types defined later in the file
Technician.update_forward_refs() 