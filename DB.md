# Database Description

## 1. Users (users)

**Purpose:** Stores all user accounts in the system, including customers, admins, and technicians.

**Fields**

- **id** (uuid, PK) - Primary key, also references auth.users, e.g.: `1c12912d-111f-4ac6-8aff-07cca81c4e5b`
- **full_name** (varchar(100)) - User's full name, e.g.: `Jacob`
- **phone** (varchar(100)) - Contact phone number, e.g.: `5877155524`
- **home_address_id** (int, FK → addresses.id) - Reference to user's home address, e.g.: 3
- **is_admin** (boolean) - Indicates if the user is an administrator (default: false)
- **customer_type** (enum: 'residential', 'commercial', 'insurance') - Defines the type of customer

**Key Points**

- Any user—customer, technician, or admin—exists here.
- CustomerType is used for determining job priority.
- Links to the auth.users table for authentication.

---

## 2. Technicians (technicians)

**Purpose:** Extends the `Users` table for technician-specific details, including which van they drive and their current workload.

**Fields**

- **id** (int, PK)
- **user_id** (uuid, FK → users.id) - References the main user record
- **assigned_van_id** (int, FK → vans.id) - Which van they currently use
- **workload** (int) - A numeric indicator of workload (must be >= 0)

**Key Points**

- Every technician is also a user.
- The technician is associated with a single van at a time.
- Workload can help with scheduling to see who is most available.

---

## 3. Vans (vans)

**Purpose:** Represents each service van in the fleet. Basic info includes last/next service dates.

**Fields**

- **id** (int, PK)
- **last_service** (timestamp with time zone)
- **next_service** (timestamp with time zone)
- **vin** (varchar, FK → customer_vehicles.vin) - Vehicle identification number
- **lat** (numeric) - Latitude coordinate
- **lng** (numeric) - Longitude coordinate

**Key Points**

- Detailed equipment is tracked separately in `van_equipment`.
- A technician is assigned to one van at a time.

---

## 4. Addresses (addresses)

**Purpose:** Standardizes location information (street addresses plus coordinates) used by orders, users, and jobs for routing.

**Fields**

- **id** (int, PK)
- **street_address** (varchar(255)), e.g.: `5342 72 Ave SE, Calgary, AB T2C 4X5, Canada`
- **lat** (numeric) - Latitude coordinate
- **lng** (numeric) - Longitude coordinate

**Key Points**

- Coordinates enable route optimization (e.g., traveling salesman problem).
- Multiple users (or orders/jobs) can reference the same address.
- Has an index on coordinates for efficient geospatial queries.

---

## 5. User Addresses (user_addresses)

**Purpose:** A many-to-many link between `Users` and `Addresses`, so one user can have multiple addresses, and one address can belong to multiple users.

**Fields**

- **user_id** (uuid, FK → users.id)
- **address_id** (int, FK → addresses.id)

**Key Points**

- Useful for shared addresses (e.g., multiple customers using the same body shop).
- Has a composite primary key of (user_id, address_id).

---

## 6. Orders (orders)

**Purpose:** Records a customer's service request (an order). An order may be split into multiple jobs if needed.

**Fields**

- **id** (int, PK)
- **user_id** (uuid, FK → users.id) - The customer placing the order
- **vehicle_id** (int, FK → customer_vehicles.id) - The vehicle being serviced
- **repair_order_number** (varchar(50)) - Used by insurance or external reference
- **address_id** (int, FK → addresses.id) - Where service is requested
- **earliest_available_time** (timestamp with time zone) - Earliest time the vehicle is available
- **notes** (text) - Any additional instructions from the customer
- **invoice** (int) - Placeholder for QuickBooks or accounting reference

**Key Points**

- Captures all high-level info about the request.
- Detailed services for the order go into `order_services`.
- File uploads are tracked in `order_uploads`.

---

## 7. Order Services (order_services)

**Purpose:** A junction table listing which services the customer requested for a particular order.

**Fields**

- **order_id** (int, FK → orders.id)
- **service_id** (int, FK → services.id)

**Key Points**

- One order can request multiple services.
- Used by logic to determine if a single van can handle all requested services or if multiple jobs are required.

---

## 8. Order Uploads (order_uploads)

**Purpose:** Tracks file uploads associated with an order.

**Fields**

- **id** (int, PK)
- **order_id** (int, FK → orders.id)
- **file_name** (varchar(255))
- **file_type** (varchar(100))
- **file_url** (text)
- **uploaded_at** (timestamp with time zone) - Defaults to current timestamp

**Key Points**

- Stores metadata about uploaded files (photos, scans, etc.)
- Links back to the original order

---

## 9. Jobs (jobs)

**Purpose:** Represents an individual work assignment that can be scheduled and dispatched to a single technician.

**Fields**

- **id** (int, PK)
- **order_id** (int, FK → orders.id) - Links back to the original order
- **assigned_technician** (int, FK → technicians.id) - Who will perform this job
- **address_id** (int, FK → addresses.id) - Service location
- **priority** (int) - Scheduling priority, 1 is highest (must be >= 0)
- **status** (USER-DEFINED) - e.g., `queued`, `en_route`, `in_progress`, `fixed_time`, `pending_review`, `pending_revisit`, `cancelled`, `completed`, `paid`
- **requested_time** (timestamp with time zone) - Customer's requested time, e.g. `2025-03-18 23:00:00+00`
- **estimated_sched** (timestamp with time zone, nullable) - The start time calculated by the scheduling algorithm.
- **job_duration** (int) - Estimated minutes to complete (must be > 0)
- **notes** (text, nullable) - General notes about the job.
- **technician_notes** (text, nullable) - Notes specifically for or from the technician.
- **service_id** (int, FK → services.id)
- **fixed_assignment** (boolean, default: false) - Indicates if the job assignment is manually fixed and should not be changed by the dynamic scheduler. Needed to support manual overrides.
- **fixed_schedule_time** (timestamp with time zone, nullable) - If set, specifies a mandatory start time for the job. The scheduler must plan other dynamic jobs around this constraint.

**Key Points**

- An order can be split into multiple jobs if no single van can handle all services.
- Each job is assigned to exactly one technician (and thus one van).
- Has indexes on status and estimated_sched for efficient querying.

---

## 11. Keys (keys)

**Purpose:** Tracks inventory of car key blanks and related key parts for immobilizer jobs.

**Fields**

- **sku_id** (varchar(50), PK)
- **quantity** (int) - Must be >= 0
- **min_quantity** (int) - Must be >= 0
- **part_number** (varchar(50))
- **purchase_price** (numeric)
- **sale_price** (numeric)
- **supplier** (varchar(100))
- **fcc_id** (varchar(50))

**Key Points**

- This table is not directly linked to the Orders/Jobs schema, but the logic layer checks key availability when scheduling key/immobilizer jobs.
- Helps decide if you need to order new keys before scheduling.

---

## 12. Services (services)

**Purpose:** Defines the various services offered (e.g., ADAS calibration, module programming, key programming, etc.).

**Fields**

- **id** (int, PK)
- **service_name** (varchar(100)) - Must be unique
- **service_category** (enum: 'adas', 'airbag', 'immo', 'prog', 'diag') - Type of service

**Key Points**

- Basic service definitions.
- Required equipment is defined in the specialized `*_equipment_requirements` tables based on service and vehicle.
- Service categories are strictly controlled via enum.

---

## 13. Equipment (equipment)

**Purpose:** A master list of all possible equipment/tools needed to perform services (e.g., cones, calibration plates, doppler, etc.).

**Fields**

- **id** (int, PK)
- **equipment_type** (enum: 'adas', 'airbag', 'immo', 'prog', 'diag') - Must be unique
- **model** (text) e.g.: `AUTEL-CSC0602/01`, `immo` (placeholder encompassing all immo equipment)

**Key Points**

- Used in `van_equipment` to specify which van has which gear.
- Equipment requirements for specific services and vehicles are defined in the specialized `*_equipment_requirements` tables.
- Equipment types align with service categories for consistency.

---

## 14. Van Equipment (van_equipment)

**Purpose:** Indicates which equipment items are available in each service van.

**Fields**

- **van_id** (int, FK → vans.id)
- **equipment_id** (int, FK → equipment.id)

**Key Points**

- Has a composite primary key on (van_id, equipment_id).

---

## 15. Customer Vehicles (customer_vehicles)

**Purpose:** Stores information about customer vehicles that can be serviced.

**Fields**

- **id** (int, PK)
- **vin** (varchar(17)) - Vehicle identification number, must be unique
- **make** (varchar(100))
- **year** (smallint)
- **model** (varchar)

**Key Points**

- Referenced by orders to identify which vehicle needs service
- Referenced by vans to identify service vehicles

---

## 16. YMM Reference (ymm_ref)

**Purpose:** Standardized reference table for year/make/model combinations used across the system.

**Fields**
- **ymm_id** (int, PK)
- **year** (smallint) NOT NULL
- **make** (varchar(50)) NOT NULL
- **model** (varchar(100)) NOT NULL
- Unique constraint on (year, make, model)

**Key Points**
- Used for vehicle identification across the system
- Provides consistent vehicle information for both customer vehicles and service vans
- Used by equipment requirements tables to determine required equipment for specific vehicles

---

## 17. Equipment Requirements Tables

The system uses separate tables for different types of equipment requirements, each following a similar structure but specialized for different service categories. Used to look up equipment requirements by referencing the correct table using the service category of the service requested in the job, (e.g. `immo` category will look up `immo_equipment_requirements`,) by the `ymm_ref` entry, (matching the `year` `make` `model` of the `customer_vehicles` of an order,) and the `service_id` of the service requested in the job, to return an `equipment_model`, which we check against `van_equipment` to determine eligible vans and corresponding technicians for a job.

### ADAS Equipment Requirements (adas_equipment_requirements)

**Purpose:** Defines ADAS-specific equipment requirements for vehicle models and services.

**Fields**
- **id** (int, PK)
- **ymm_id** (int, FK → ymm_ref.ymm_id)
- **service_id** (int, FK → services.id)
- **equipment_model** (varchar(100)) NOT NULL  (should match an `equipment` entry)
- **has_adas_service** (boolean) - Default: false
- Unique constraint on (ymm_id, service_id)

### Programming Equipment Requirements (prog_equipment_requirements)

**Purpose:** Defines programming-specific equipment requirements for vehicle models and services.

**Fields**
- **id** (int, PK)
- **ymm_id** (int, FK → ymm_ref.ymm_id)
- **service_id** (int, FK → services.id)
- **equipment_model** (text) NOT NULL - Default: 'prog'
- Unique constraint on (ymm_id, service_id)

### Immobilizer Equipment Requirements (immo_equipment_requirements)

**Purpose:** Defines immobilizer-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'immo'

### Airbag Equipment Requirements (airbag_equipment_requirements)

**Purpose:** Defines airbag-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'airbag'

### Diagnostic Equipment Requirements (diag_equipment_requirements)

**Purpose:** Defines diagnostic-specific equipment requirements for vehicle models and services.

**Fields**
- Same structure as prog_equipment_requirements
- equipment_model defaults to 'diag'

**Key Points for All Equipment Requirement Tables**
- Each table links vehicles and services to required equipment
- Used for scheduling and equipment allocation
- Helps determine if a specific van has the right equipment for a job
- Each maintains a unique constraint on (ymm_id, service_id)

---

## 18. Enums

The database uses several enum types to ensure data consistency:

1. **customer_type**
   - Values: 'residential', 'commercial', 'insurance'
   - Used in: users table

2. **job_status**
   - Values: 'pending_review', 'assigned', 'scheduled', 'pending_revisit', 'completed', 'cancelled'
   - Used in: jobs table

3. **service_category**
   - Values: 'adas', 'airbag', 'immo', 'prog', 'diag'
   - Used in: services table and equipment table
