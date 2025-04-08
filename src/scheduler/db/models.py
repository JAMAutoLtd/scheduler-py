import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean, DateTime, Interval, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

from scheduler.models import CustomerType, ServiceCategory, JobStatus, EquipmentType

# Define the base class for all models
Base = declarative_base()

class Address(Base):
    """SQLAlchemy model for a physical address with coordinates."""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    street_address = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    # Relationships
    technicians_home = relationship("Technician", foreign_keys="Technician.home_address_id", back_populates="home_address")
    technicians_current = relationship("Technician", foreign_keys="Technician.current_location_id", back_populates="current_location")
    jobs = relationship("Job", back_populates="address")
    orders = relationship("Order", back_populates="address")


class Equipment(Base):
    """SQLAlchemy model for a piece of equipment or tool."""
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, index=True)
    equipment_type = Column(Enum(EquipmentType), nullable=False)
    model = Column(String, nullable=False)
    van_id = Column(Integer, ForeignKey("vans.id"), nullable=True)

    # Relationships
    van = relationship("Van", back_populates="equipment")


class Van(Base):
    """SQLAlchemy model for a service van."""
    __tablename__ = "vans"

    id = Column(Integer, primary_key=True, index=True)
    last_service = Column(DateTime, nullable=True)
    next_service = Column(DateTime, nullable=True) 
    vin = Column(String(17), nullable=True)

    # Relationships
    equipment = relationship("Equipment", back_populates="van")
    technicians = relationship("Technician", back_populates="assigned_van")


class Technician(Base):
    """SQLAlchemy model for a technician user."""
    __tablename__ = "technicians"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    assigned_van_id = Column(Integer, ForeignKey("vans.id"), nullable=True)
    workload = Column(Integer, default=0, nullable=False)
    home_address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    current_location_id = Column(Integer, ForeignKey("addresses.id"), nullable=True)

    # Relationships
    home_address = relationship("Address", foreign_keys=[home_address_id], back_populates="technicians_home")
    current_location = relationship("Address", foreign_keys=[current_location_id], back_populates="technicians_current")
    assigned_van = relationship("Van", back_populates="technicians")
    jobs = relationship("Job", back_populates="assigned_technician_rel")


class Service(Base):
    """SQLAlchemy model for a service offered."""
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    service_name = Column(String, nullable=False)
    service_category = Column(Enum(ServiceCategory), nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="service")
    order_services = relationship("OrderService", back_populates="service")


class CustomerVehicle(Base):
    """SQLAlchemy model for a customer's vehicle."""
    __tablename__ = "customer_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), nullable=False)
    make = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    model = Column(String, nullable=False)
    ymm_id = Column(Integer, nullable=True)

    # Relationships
    orders = relationship("Order", back_populates="vehicle")


class Order(Base):
    """SQLAlchemy model for a customer's service order."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("customer_vehicles.id"), nullable=False)
    repair_order_number = Column(String, nullable=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    earliest_available_time = Column(DateTime, nullable=False)
    notes = Column(String, nullable=True)
    invoice = Column(Integer, nullable=True)
    customer_type = Column(Enum(CustomerType), nullable=False)

    # Relationships
    vehicle = relationship("CustomerVehicle", back_populates="orders")
    address = relationship("Address", back_populates="orders")
    jobs = relationship("Job", back_populates="order")
    order_services = relationship("OrderService", back_populates="order")

    # Add services relationship via order_services
    services = relationship("Service", secondary="order_services", viewonly=True)


class OrderService(Base):
    """SQLAlchemy model for the many-to-many relationship between orders and services."""
    __tablename__ = "order_services"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    # Relationships
    order = relationship("Order", back_populates="order_services")
    service = relationship("Service", back_populates="order_services")


class Job(Base):
    """SQLAlchemy model for a single schedulable job, potentially part of an Order."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    assigned_technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False)
    priority = Column(Integer, default=0, nullable=False)
    status = Column(Enum(JobStatus), nullable=False)
    requested_time = Column(DateTime, nullable=True)
    estimated_sched = Column(DateTime, nullable=True)
    estimated_sched_end = Column(DateTime, nullable=True)
    customer_eta_start = Column(DateTime, nullable=True)
    customer_eta_end = Column(DateTime, nullable=True)
    job_duration = Column(Interval, nullable=False)
    notes = Column(String, nullable=True)
    fixed_assignment = Column(Boolean, default=False, nullable=False)
    fixed_schedule_time = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="jobs")
    service = relationship("Service", back_populates="jobs")
    address = relationship("Address", back_populates="jobs")
    assigned_technician_rel = relationship("Technician", back_populates="jobs")

    # Create an alias property for compatibility with the Pydantic model
    @property
    def order_ref(self):
        return self.order
    
    @property
    def assigned_technician(self):
        return self.assigned_technician_id
    
    # Equipment requirements relationship
    equipment_requirements_rel = relationship("JobEquipmentRequirement", back_populates="job")
    
    # Property to get equipment requirements as a list of models
    @property
    def equipment_requirements(self):
        return [eq.equipment_model for eq in self.equipment_requirements_rel]


class JobEquipmentRequirement(Base):
    """SQLAlchemy model for job equipment requirements."""
    __tablename__ = "job_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    equipment_model = Column(String, nullable=False)

    # Relationships
    job = relationship("Job", back_populates="equipment_requirements_rel")


# --- Models from PLANNING.md that were missing ---

class YMMRef(Base):
    """SQLAlchemy model for YMM reference table."""
    __tablename__ = "ymm_ref"

    ymm_id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    make = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint('year', 'make', 'model', name='uq_ymm'),)


class ADASEquipmentRequirement(Base):
    """SQLAlchemy model for ADAS equipment requirements."""
    __tablename__ = "adas_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    ymm_id = Column(Integer, ForeignKey("ymm_ref.ymm_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    equipment_model = Column(String(100), nullable=False)
    has_adas_service = Column(Boolean, default=False) # Specific to ADAS

    ymm = relationship("YMMRef")
    service = relationship("Service")

    __table_args__ = (UniqueConstraint('ymm_id', 'service_id', name='uq_adas_req'),)


class ProgEquipmentRequirement(Base):
    """SQLAlchemy model for Programming equipment requirements."""
    __tablename__ = "prog_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    ymm_id = Column(Integer, ForeignKey("ymm_ref.ymm_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    equipment_model = Column(String, nullable=False, default='prog') # Mapped from Text in planning

    ymm = relationship("YMMRef")
    service = relationship("Service")

    __table_args__ = (UniqueConstraint('ymm_id', 'service_id', name='uq_prog_req'),)


class ImmoEquipmentRequirement(Base):
    """SQLAlchemy model for Immobilizer equipment requirements."""
    __tablename__ = "immo_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    ymm_id = Column(Integer, ForeignKey("ymm_ref.ymm_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    equipment_model = Column(String, nullable=False, default='immo') # Mapped from Text

    ymm = relationship("YMMRef")
    service = relationship("Service")

    __table_args__ = (UniqueConstraint('ymm_id', 'service_id', name='uq_immo_req'),)


class AirbagEquipmentRequirement(Base):
    """SQLAlchemy model for Airbag equipment requirements."""
    __tablename__ = "airbag_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    ymm_id = Column(Integer, ForeignKey("ymm_ref.ymm_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    equipment_model = Column(String, nullable=False, default='airbag') # Mapped from Text

    ymm = relationship("YMMRef")
    service = relationship("Service")

    __table_args__ = (UniqueConstraint('ymm_id', 'service_id', name='uq_airbag_req'),)


class DiagEquipmentRequirement(Base):
    """SQLAlchemy model for Diagnostic equipment requirements."""
    __tablename__ = "diag_equipment_requirements"

    id = Column(Integer, primary_key=True, index=True)
    ymm_id = Column(Integer, ForeignKey("ymm_ref.ymm_id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    equipment_model = Column(String, nullable=False, default='diag') # Mapped from Text

    ymm = relationship("YMMRef")
    service = relationship("Service")

    __table_args__ = (UniqueConstraint('ymm_id', 'service_id', name='uq_diag_req'),) 