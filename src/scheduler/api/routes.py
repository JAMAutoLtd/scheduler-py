from fastapi import APIRouter, Depends, HTTPException, Path, Body, Query, status as http_status
from typing import List, Optional

# Import SQLAlchemy models and session
from sqlalchemy.orm import Session, selectinload 
from sqlalchemy import select

# Import the original Pydantic models for the API responses
from ..models import JobStatus as PydanticJobStatus

# Import the SQLAlchemy models
from ..db.models import Technician, Job, Order, Service, Equipment, Address, CustomerVehicle, Van, JobEquipmentRequirement, OrderService
from ..db.models import JobStatus, CustomerType, ServiceCategory, EquipmentType
from ..db.database import get_db

from .models import (
    TechnicianResponse, JobResponse, EquipmentRequirementResponse, AddressResponse,
    EquipmentResponse, VanResponse, CustomerVehicleResponse, ServiceResponse, OrderResponse,
    JobAssignmentRequest, JobScheduleRequest, JobETABulkRequest, JobStatus as APIJobStatus # Alias for clarity
)
# Import the database dependency
from .deps import get_api_key
# Import the lookup function
from .lookups import get_required_equipment

router = APIRouter()


def convert_technician_to_response(technician: Technician) -> TechnicianResponse:
    """
    Convert an SQLAlchemy Technician model to a TechnicianResponse model.
    """
    # Convert home address
    home_address_response = AddressResponse(
        id=technician.home_address.id,
        street_address=technician.home_address.street_address,
        lat=technician.home_address.lat,
        lng=technician.home_address.lng
    )
    
    # Convert current location if it exists
    current_location_response = None
    if technician.current_location:
        current_location_response = AddressResponse(
            id=technician.current_location.id,
            street_address=technician.current_location.street_address,
            lat=technician.current_location.lat,
            lng=technician.current_location.lng
        )
    
    # Convert assigned van if it exists
    assigned_van_response = None
    if technician.assigned_van:
        # Convert equipment list
        equipment_responses = [
            EquipmentResponse(
                id=eq.id,
                equipment_type=eq.equipment_type,
                model=eq.model
            )
            for eq in technician.assigned_van.equipment
        ]
        
        assigned_van_response = VanResponse(
            id=technician.assigned_van.id,
            last_service=technician.assigned_van.last_service,
            next_service=technician.assigned_van.next_service,
            vin=technician.assigned_van.vin,
            equipment=equipment_responses
        )
    
    # Create and return the TechnicianResponse
    return TechnicianResponse(
        id=technician.id,
        user_id=technician.user_id,
        assigned_van_id=technician.assigned_van_id,
        workload=technician.workload,
        home_address=home_address_response,
        current_location=current_location_response,
        assigned_van=assigned_van_response
    )


def convert_job_to_response(job: Job) -> JobResponse:
    """
    Convert an SQLAlchemy Job model to a JobResponse model.
    """
    # Convert address
    address_response = AddressResponse(
        id=job.address.id,
        street_address=job.address.street_address,
        lat=job.address.lat,
        lng=job.address.lng
    )
    
    # Convert order and its nested components
    vehicle_response = CustomerVehicleResponse(
        id=job.order.vehicle.id,
        vin=job.order.vehicle.vin,
        make=job.order.vehicle.make,
        year=job.order.vehicle.year,
        model=job.order.vehicle.model,
        ymm_id=job.order.vehicle.ymm_id
    )
    
    order_address_response = AddressResponse(
        id=job.order.address.id,
        street_address=job.order.address.street_address,
        lat=job.order.address.lat,
        lng=job.order.address.lng
    )
    
    # Convert services if any
    service_responses = []
    if hasattr(job.order, 'services') and job.order.services:
        for service in job.order.services:
            service_responses.append(ServiceResponse(
                id=service.id,
                service_name=service.service_name,
                service_category=service.service_category
            ))
    
    order_response = OrderResponse(
        id=job.order.id,
        user_id=job.order.user_id,
        vehicle_id=job.order.vehicle_id,
        repair_order_number=job.order.repair_order_number,
        address_id=job.order.address_id,
        earliest_available_time=job.order.earliest_available_time,
        notes=job.order.notes,
        invoice=job.order.invoice,
        customer_type=job.order.customer_type,
        address=order_address_response,
        vehicle=vehicle_response,
        services=service_responses
    )
    
    # Calculate job_duration in minutes for API response
    # SQLAlchemy Interval field comes as a timedelta object
    job_duration_minutes = int(job.job_duration.total_seconds() / 60)
    
    # Create the JobResponse
    return JobResponse(
        id=job.id,
        order_id=job.order_id,
        service_id=job.service_id,
        assigned_technician=job.assigned_technician_id,
        address_id=job.address_id,
        priority=job.priority,
        status=job.status.value,
        requested_time=job.requested_time,
        estimated_sched=job.estimated_sched,
        estimated_sched_end=job.estimated_sched_end,
        customer_eta_start=job.customer_eta_start,
        customer_eta_end=job.customer_eta_end,
        job_duration=job_duration_minutes,
        notes=job.notes,
        fixed_assignment=job.fixed_assignment,
        fixed_schedule_time=job.fixed_schedule_time,
        order_ref=order_response,
        address=address_response,
        equipment_requirements=job.equipment_requirements
    )


async def fetch_job_by_id(job_id: int, db: Session):
    """
    Helper function to fetch a job by ID using SQLAlchemy.
    """
    stmt = (
        select(Job)
        .where(Job.id == job_id)
        .options(
            selectinload(Job.address),
            selectinload(Job.order).selectinload(Order.address),
            selectinload(Job.order).selectinload(Order.vehicle),
            selectinload(Job.order).selectinload(Order.services),
            selectinload(Job.equipment_requirements_rel)
        )
    )
    
    result = await db.execute(stmt)
    return result.scalars().first()


@router.get("/technicians", response_model=List[TechnicianResponse], tags=["technicians"])
async def get_technicians(db: Session = Depends(get_db), api_key: dict = Depends(get_api_key)):
    """
    Fetch all active technicians with their associated van, equipment, home address,
    and current location directly from the database.
    """
    try:
        # Query the database directly using SQLAlchemy models
        stmt = (
            select(Technician)
            .options(
                selectinload(Technician.home_address),
                selectinload(Technician.current_location),
                selectinload(Technician.assigned_van).selectinload(Van.equipment)
            )
            # TODO: Add filtering for 'active' technicians if applicable (e.g., based on a status field)
        )
        result = await db.execute(stmt)
        db_technicians = result.scalars().all()
        
        # Convert DB models to API response models using the existing helper
        technician_responses = [
            convert_technician_to_response(tech)
            for tech in db_technicians
        ]
        
        return technician_responses
    except Exception as e:
        # Log the error (would use a proper logger in production)
        print(f"Error fetching technicians: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch technicians: {str(e)}"
        )


@router.get("/jobs/schedulable", response_model=List[JobResponse], tags=["jobs"])
async def get_schedulable_jobs(db: Session = Depends(get_db), api_key: dict = Depends(get_api_key)):
    """
    Fetch all pending/dynamic jobs eligible for scheduling.
    """
    try:
        # Query for pending jobs using SQLAlchemy models
        stmt = (
            select(Job)
            .where(Job.status.in_([JobStatus.PENDING_REVIEW, JobStatus.ASSIGNED]))
            .options(
                selectinload(Job.address),
                selectinload(Job.order).selectinload(Order.address),
                selectinload(Job.order).selectinload(Order.vehicle),
                selectinload(Job.order).selectinload(Order.services),
                selectinload(Job.equipment_requirements_rel)
            )
        )
        
        result = await db.execute(stmt)
        db_jobs = result.scalars().all()
        
        # Convert SQLAlchemy models to API response models
        job_responses = [
            convert_job_to_response(job)
            for job in db_jobs
        ]
        
        return job_responses
    except Exception as e:
        # Log the error (would use a proper logger in production)
        print(f"Error fetching schedulable jobs: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch schedulable jobs: {str(e)}"
        )


@router.get("/equipment/requirements", response_model=EquipmentRequirementResponse, tags=["equipment"])
async def get_equipment_requirements(
    service_id: int = Query(..., description="ID of the service"),
    ymm_id: int = Query(..., description="Year-Make-Model ID from ymm_ref table"),
    db: Session = Depends(get_db),
    api_key: dict = Depends(get_api_key)
):
    """
    Fetch the required equipment model for a specific service and YMM combination.
    """
    try:
        # Call the lookup function
        required_model = get_required_equipment(db=db, service_id=service_id, ymm_id=ymm_id)

        # Prepare the response
        equipment_models = [required_model] if required_model else []

        return EquipmentRequirementResponse(
            service_id=service_id,
            ymm_id=ymm_id,
            equipment_models=equipment_models
        )
    except Exception as e:
        # Log the error (would use a proper logger in production)
        print(f"Error fetching equipment requirements: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch equipment requirements: {str(e)}"
        )


@router.patch("/jobs/{job_id}/assignment", response_model=JobResponse, tags=["jobs"])
async def update_job_assignment(
    job_id: int = Path(..., description="The ID of the job to update"),
    assignment_data: JobAssignmentRequest = Body(..., description="The assignment data to update"),
    db: Session = Depends(get_db),
    api_key: dict = Depends(get_api_key)
):
    """
    Update a job's assignment (technician and status).
    """
    try:
        # Verify the job exists
        job = await fetch_job_by_id(job_id, db)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Update the job with the provided data
        if assignment_data.assigned_technician is not None:
            job.assigned_technician_id = assignment_data.assigned_technician
        
        if assignment_data.status is not None:
            job.status = assignment_data.status
        
        # Commit the changes to the database
        await db.commit()
        await db.refresh(job)
        
        # Convert the updated job to a response model and return it
        return convert_job_to_response(job)
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error
        print(f"Error updating job assignment: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job assignment: {str(e)}"
        )


@router.patch("/jobs/etas", tags=["jobs"])
async def update_job_etas(
    eta_data: JobETABulkRequest = Body(...),
    api_key: dict = Depends(get_api_key)
):
    """
    Bulk update job ETAs based on provided data.
    """
    try:
        # Structure data for data_interface function
        job_etas = {}
        for job_eta in eta_data.jobs:
            # Create a dictionary of fields to update for this job
            eta_fields = {}
            
            if job_eta.estimated_sched is not None:
                eta_fields['estimated_sched'] = job_eta.estimated_sched
                
            if job_eta.estimated_sched_end is not None:
                eta_fields['estimated_sched_end'] = job_eta.estimated_sched_end
                
            if job_eta.customer_eta_start is not None:
                eta_fields['customer_eta_start'] = job_eta.customer_eta_start
                
            if job_eta.customer_eta_end is not None:
                eta_fields['customer_eta_end'] = job_eta.customer_eta_end
            
            # Only add to job_etas if we have fields to update
            if eta_fields:
                job_etas[job_eta.job_id] = eta_fields
        
        # Skip update if no valid data
        if not job_etas:
            return {"message": "No valid ETA updates provided"}
        
        # Update the job ETAs using data_interface
        success = update_job_etas(job_etas)
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update job ETAs"
            )
        
        # Return success message
        return {"message": f"Updated ETAs for {len(job_etas)} jobs"}
    except Exception as e:
        # Log the error (would use a proper logger in production)
        print(f"Error updating job ETAs: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job ETAs: {str(e)}"
        )


@router.patch("/jobs/{job_id}/schedule", response_model=JobResponse, tags=["jobs"])
async def update_job_schedule(
    job_id: int = Path(..., description="The ID of the job to update"),
    schedule_data: JobScheduleRequest = Body(..., description="The schedule data to update"),
    db: Session = Depends(get_db),
    api_key: dict = Depends(get_api_key)
):
    """
    Update a job's schedule (fixed times, durations, etc.).
    """
    try:
        # Verify the job exists
        job = await fetch_job_by_id(job_id, db)
        if not job:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Job with ID {job_id} not found"
            )
        
        # Update the job with the provided schedule data
        for field, value in schedule_data.dict(exclude_unset=True).items():
            setattr(job, field, value)
        
        # Commit the changes to the database
        await db.commit()
        await db.refresh(job)
        
        # Convert the updated job to a response model and return it
        return convert_job_to_response(job)
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error
        print(f"Error updating job schedule: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update job schedule: {str(e)}"
        )


@router.get("/addresses/{address_id}", response_model=AddressResponse, tags=["addresses"])
async def get_address(
    address_id: int = Path(..., description="The ID of the address to fetch"),
    db: Session = Depends(get_db),  # Inject the DB session
    api_key: dict = Depends(get_api_key)
):
    """
    Fetch a specific address by its ID directly from the database.
    """
    try:
        # Query the database for the address
        stmt = select(Address).where(Address.id == address_id)
        result = await db.execute(stmt)
        db_address = result.scalars().first()

        if not db_address:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Address with ID {address_id} not found"
            )

        # Convert to API response model
        return AddressResponse(
            id=db_address.id,
            street_address=db_address.street_address,
            lat=db_address.lat,
            lng=db_address.lng
        )
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        raise http_exc
    except Exception as e:
        # Log the error (replace with proper logging)
        print(f"Error fetching address {address_id}: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch address: {str(e)}"
        )


@router.get("/jobs", response_model=List[JobResponse], tags=["jobs"])
async def get_jobs(
    technician_id: Optional[int] = Query(None, description="Filter jobs by assigned technician ID"),
    status: Optional[APIJobStatus] = Query(None, description="Filter jobs by status"),
    db: Session = Depends(get_db),
    api_key: dict = Depends(get_api_key)
):
    """
    Get all jobs with optional filtering by technician ID and/or status.
    """
    try:
        # Normal operation - real SQLAlchemy with database
        # Base query for the Job model
        statement = select(Job)

        # Apply filters conditionally
        if technician_id is not None:
            statement = statement.where(Job.assigned_technician_id == technician_id)
        if status is not None:
            # Ensure we compare with the value of the enum member
            statement = statement.where(Job.status == status.value)

        # Eager load related data needed for the response model to avoid N+1 queries
        statement = statement.options(
            selectinload(Job.address),
            selectinload(Job.order).selectinload(Order.address),
            selectinload(Job.order).selectinload(Order.vehicle),
            selectinload(Job.order).selectinload(Order.services),
            selectinload(Job.equipment_requirements_rel)
        )

        # Execute the query
        result = await db.execute(statement)
        db_jobs = result.scalars().all()
        
        # Convert DB models to response models
        job_responses = [convert_job_to_response(job) for job in db_jobs]
        return job_responses
        
    except Exception as e:
        # Log the error
        print(f"Error getting jobs: {str(e)}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}"
        )
