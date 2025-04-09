# Database Schema Validation (`DB.md` vs Actual)

This document compares the schema described in `DB.md` with the actual database schema queried via `information_schema`.

## 1. Schema Overview (from `DB.md`)

*   **`users`**
    *   **Purpose:** Stores all user accounts (customers, admins, technicians). Links to `auth.users`.
    *   **Key Fields:** `id` (PK, UUID, FK->auth.users), `full_name`, `phone`, `home_address_id` (FK->addresses), `is_admin`, `customer_type` (Enum).
*   **`technicians`**
    *   **Purpose:** Technician-specific details, extending `users`.
    *   **Key Fields:** `id` (PK, Int), `user_id` (FK->users), `assigned_van_id` (FK->vans), `workload`.
*   **`vans`**
    *   **Purpose:** Represents service vans.
    *   **Key Fields:** `id` (PK, Int), `vin` (FK->customer_vehicles), `lat`, `lng`, `last_service`, `next_service`.
*   **`addresses`**
    *   **Purpose:** Standardized location information (address + coordinates).
    *   **Key Fields:** `id` (PK, Int), `street_address`, `lat`, `lng`.
*   **`user_addresses`**
    *   **Purpose:** Many-to-many link between `users` and `addresses`.
    *   **Key Fields:** `user_id` (FK->users), `address_id` (FK->addresses). Composite PK on (`user_id`, `address_id`).
*   **`orders`**
    *   **Purpose:** Customer service requests. Can contain multiple jobs.
    *   **Key Fields:** `id` (PK, Int), `user_id` (FK->users), `vehicle_id` (FK->customer_vehicles), `address_id` (FK->addresses), `earliest_available_time`, `repair_order_number`.
*   **`order_services`**
    *   **Purpose:** Junction table linking `orders` to requested `services`.
    *   **Key Fields:** `order_id` (FK->orders), `service_id` (FK->services).
*   **`order_uploads`**
    *   **Purpose:** Tracks file uploads associated with an `order`.
    *   **Key Fields:** `id` (PK, Int), `order_id` (FK->orders), `file_name`, `file_url`.
*   **`jobs`**
    *   **Purpose:** Individual, schedulable work assignments derived from `orders`.
    *   **Key Fields:** `id` (PK, Int), `order_id` (FK->orders), `assigned_technician` (FK->technicians), `address_id` (FK->addresses), `service_id` (FK->services), `priority`, `status` (Enum), `job_duration`, `estimated_sched`, `fixed_assignment`, `fixed_schedule_time`.
*   **`job_services`**
    *   **Purpose:** Links a `job` to the specific `services` it includes.
    *   **Key Fields:** `job_id` (FK->jobs), `service_id` (FK->services). Composite PK on (`job_id`, `service_id`).
*   **`keys`**
    *   **Purpose:** Inventory for key blanks/parts (not directly linked in schema, used by application logic).
    *   **Key Fields:** `sku_id` (PK, Varchar), `quantity`, `part_number`.
*   **`services`**
    *   **Purpose:** Defines offered services.
    *   **Key Fields:** `id` (PK, Int), `service_name` (Unique), `service_category` (Enum: 'adas', 'airbag', 'immo', 'prog', 'diag').
*   **`equipment`**
    *   **Purpose:** Master list of all possible tools/equipment.
    *   **Key Fields:** `id` (PK, Int), `equipment_type` (Enum, matches service_category), `model`.
*   **`van_equipment`**
    *   **Purpose:** Junction table indicating which `equipment` is in which `van`.
    *   **Key Fields:** `van_id` (FK->vans), `equipment_id` (FK->equipment), `equipment_model`. Composite PK on (`van_id`, `equipment_id`).
*   **`customer_vehicles`**
    *   **Purpose:** Information about customer vehicles.
    *   **Key Fields:** `id` (PK, Int), `vin` (Unique), `make`, `year`, `model`.
*   **`ymm_ref`**
    *   **Purpose:** Standardized Year/Make/Model reference.
    *   **Key Fields:** `ymm_id` (PK, Int), `year`, `make`, `model`. Unique constraint on (`year`, `make`, `model`).
*   **`*_equipment_requirements` Tables** (e.g., `adas_equipment_requirements`, `prog_equipment_requirements`, etc.)
    *   **Purpose:** Defines equipment needed for a specific `service` on a specific vehicle (`ymm_ref`). Looked up based on `service.service_category`.
    *   **Key Fields (Common):** `id` (PK, Int), `ymm_id` (FK->ymm_ref), `service_id` (FK->services), `equipment_model`. Unique constraint on (`ymm_id`, `service_id`).

## 2. Validation Summary

The validation process involved querying `information_schema` to list tables and their columns.

*   **Table Existence:** All tables listed in the `DB.md` overview exist *except* `job_services`. Two additional tables, `technician_availability_exceptions` and `technician_default_hours`, were found in the database but not documented in `DB.md`.
*   **Column Validation:** All documented columns were found in the corresponding tables in the actual database. The `services` table contained an undocumented `slug` column.

## 3. Summary of Differences (`DB.md` vs Actual)

*   **Extra Tables in DB (Not in `DB.md`):**
    *   `technician_availability_exceptions`
    *   `technician_default_hours`
    *   *Note:* These tables suggest more granular control over technician schedules than documented or currently implemented in `src/scheduler/availability.ts`.
*   **Undocumented Column:**
    *   `services.slug`: An extra `slug` column (text, nullable) exists in the `services` table.

## 4. Impact Assessment

*   The extra availability tables (`technician_availability_exceptions`, `technician_default_hours`) represent potential future enhancements or undocumented features for technician scheduling. The current availability logic (`src/scheduler/availability.ts`) does not use them.
*   The `services.slug` column does not appear to affect the current application logic but should be documented correctly in `DB.md`.

This validated overview provides a more accurate reference for development and testing.