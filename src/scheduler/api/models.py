from pydantic import BaseModel, Field, validator
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid


# --- Enums (matching those in scheduler/models.py) ---

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


# --- API Response Models ---

class AddressResponse(BaseModel):
    """API response model for Address data."""
    id: int
    street_address: str
    lat: float
    lng: float

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "street_address": "123 Main St, City, State 12345",
                "lat": 37.7749,
                "lng": -122.4194
            }
        }

class EquipmentResponse(BaseModel):
    """API response model for Equipment data."""
    id: int
    equipment_type: EquipmentType
    model: str

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "equipment_type": "adas",
                "model": "AUTEL-CSC0602/01"
            }
        }

class VanResponse(BaseModel):
    """API response model for Van data."""
    id: int
    last_service: Optional[datetime] = None
    next_service: Optional[datetime] = None
    vin: Optional[str] = None
    equipment: List[EquipmentResponse] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "last_service": "2023-01-01T12:00:00Z",
                "next_service": "2023-07-01T12:00:00Z",
                "vin": "1HGCM82633A004352",
                "equipment": [
                    {
                        "id": 1,
                        "equipment_type": "adas",
                        "model": "AUTEL-CSC0602/01"
                    }
                ]
            }
        }

class TechnicianResponse(BaseModel):
    """API response model for Technician data."""
    id: int
    user_id: uuid.UUID
    assigned_van_id: Optional[int] = None
    workload: int = Field(ge=0, default=0)
    home_address: AddressResponse
    current_location: Optional[AddressResponse] = None
    assigned_van: Optional[VanResponse] = None

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "assigned_van_id": 1,
                "workload": 3,
                "home_address": {
                    "id": 2,
                    "street_address": "456 Tech St, City, State 12345",
                    "lat": 37.7749,
                    "lng": -122.4194
                },
                "current_location": {
                    "id": 3,
                    "street_address": "789 Job St, City, State 12345",
                    "lat": 37.7749,
                    "lng": -122.4194
                },
                "assigned_van": {
                    "id": 1,
                    "last_service": "2023-01-01T12:00:00Z",
                    "next_service": "2023-07-01T12:00:00Z",
                    "vin": "1HGCM82633A004352",
                    "equipment": [
                        {
                            "id": 1,
                            "equipment_type": "adas",
                            "model": "AUTEL-CSC0602/01"
                        }
                    ]
                }
            }
        }

class ServiceResponse(BaseModel):
    """API response model for Service data."""
    id: int
    service_name: str
    service_category: ServiceCategory

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "service_name": "Front Radar Calibration",
                "service_category": "adas"
            }
        }

class CustomerVehicleResponse(BaseModel):
    """API response model for CustomerVehicle data."""
    id: int
    vin: str = Field(min_length=17, max_length=17)
    make: str
    year: int
    model: str
    ymm_id: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "vin": "1HGCM82633A004352",
                "make": "Honda",
                "year": 2022,
                "model": "Civic",
                "ymm_id": 1
            }
        }

class OrderResponse(BaseModel):
    """API response model for Order data."""
    id: int
    user_id: uuid.UUID
    vehicle_id: int
    repair_order_number: Optional[str] = None
    address_id: int
    earliest_available_time: datetime
    notes: Optional[str] = None
    invoice: Optional[int] = None
    customer_type: CustomerType
    address: AddressResponse
    vehicle: CustomerVehicleResponse
    services: List[ServiceResponse] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "vehicle_id": 1,
                "repair_order_number": "RO12345",
                "address_id": 3,
                "earliest_available_time": "2023-06-01T10:00:00Z",
                "notes": "Customer prefers morning appointments",
                "invoice": 100001,
                "customer_type": "commercial",
                "address": {
                    "id": 3,
                    "street_address": "789 Job St, City, State 12345",
                    "lat": 37.7749,
                    "lng": -122.4194
                },
                "vehicle": {
                    "id": 1,
                    "vin": "1HGCM82633A004352",
                    "make": "Honda",
                    "year": 2022,
                    "model": "Civic",
                    "ymm_id": 1
                },
                "services": [
                    {
                        "id": 1,
                        "service_name": "Front Radar Calibration",
                        "service_category": "adas"
                    }
                ]
            }
        }

class JobResponse(BaseModel):
    """API response model for Job data."""
    id: int
    order_id: int
    service_id: int
    assigned_technician: Optional[int] = None
    address_id: int
    priority: int = Field(ge=0)
    status: JobStatus
    requested_time: Optional[datetime] = None
    estimated_sched: Optional[datetime] = None
    estimated_sched_end: Optional[datetime] = None
    customer_eta_start: Optional[datetime] = None
    customer_eta_end: Optional[datetime] = None
    job_duration: int  # Duration in minutes
    notes: Optional[str] = None
    fixed_assignment: bool = False
    fixed_schedule_time: Optional[datetime] = None
    order_ref: OrderResponse
    address: AddressResponse
    equipment_requirements: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "order_id": 1,
                "service_id": 1,
                "assigned_technician": 1,
                "address_id": 3,
                "priority": 2,
                "status": "assigned",
                "requested_time": "2023-06-01T10:00:00Z",
                "estimated_sched": "2023-06-01T13:00:00Z",
                "estimated_sched_end": "2023-06-01T14:30:00Z",
                "customer_eta_start": "2023-06-01T13:00:00Z",
                "customer_eta_end": "2023-06-01T15:00:00Z",
                "job_duration": 90,
                "notes": "Call customer before arrival",
                "fixed_assignment": False,
                "fixed_schedule_time": None,
                "order_ref": {
                    "id": 1,
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "vehicle_id": 1,
                    "repair_order_number": "RO12345",
                    "address_id": 3,
                    "earliest_available_time": "2023-06-01T10:00:00Z",
                    "notes": "Customer prefers morning appointments",
                    "invoice": 100001,
                    "customer_type": "commercial",
                    "address": {
                        "id": 3,
                        "street_address": "789 Job St, City, State 12345",
                        "lat": 37.7749,
                        "lng": -122.4194
                    },
                    "vehicle": {
                        "id": 1,
                        "vin": "1HGCM82633A004352",
                        "make": "Honda",
                        "year": 2022,
                        "model": "Civic",
                        "ymm_id": 1
                    },
                    "services": []
                },
                "address": {
                    "id": 3,
                    "street_address": "789 Job St, City, State 12345",
                    "lat": 37.7749,
                    "lng": -122.4194
                },
                "equipment_requirements": ["AUTEL-CSC0602/01"]
            }
        }

class EquipmentRequirementResponse(BaseModel):
    """API response model for Equipment Requirements data."""
    service_id: int
    ymm_id: int
    equipment_models: List[str]

    class Config:
        schema_extra = {
            "example": {
                "service_id": 1,
                "ymm_id": 1,
                "equipment_models": ["AUTEL-CSC0602/01"]
            }
        }


# --- API Request Models ---

class JobAssignmentRequest(BaseModel):
    """Request model for updating job assignment."""
    assigned_technician: Optional[int] = None
    status: Optional[JobStatus] = None

    class Config:
        schema_extra = {
            "example": {
                "assigned_technician": 1,
                "status": "assigned"
            }
        }

class JobScheduleRequest(BaseModel):
    """Request model for updating job schedule."""
    fixed_schedule_time: Optional[datetime] = None

    class Config:
        schema_extra = {
            "example": {
                "fixed_schedule_time": "2023-06-01T14:00:00Z"
            }
        }

class JobETAUpdate(BaseModel):
    """Model for a single job's ETA update within a bulk update."""
    job_id: int
    estimated_sched: Optional[datetime] = None
    estimated_sched_end: Optional[datetime] = None
    customer_eta_start: Optional[datetime] = None
    customer_eta_end: Optional[datetime] = None

class JobETABulkRequest(BaseModel):
    """Request model for bulk updating job ETAs."""
    jobs: List[JobETAUpdate]

    class Config:
        schema_extra = {
            "example": {
                "jobs": [
                    {
                        "job_id": 1,
                        "estimated_sched": "2023-06-01T13:00:00Z",
                        "estimated_sched_end": "2023-06-01T14:30:00Z",
                        "customer_eta_start": "2023-06-01T13:00:00Z",
                        "customer_eta_end": "2023-06-01T15:00:00Z"
                    },
                    {
                        "job_id": 2,
                        "estimated_sched": "2023-06-01T15:00:00Z",
                        "estimated_sched_end": "2023-06-01T16:30:00Z",
                        "customer_eta_start": "2023-06-01T15:00:00Z",
                        "customer_eta_end": "2023-06-01T17:00:00Z"
                    }
                ]
            }
        }
