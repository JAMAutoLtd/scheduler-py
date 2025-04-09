Core Goal: To dynamically schedule and assign jobs to technicians using a "full replan" method, maximizing the number of jobs completed daily while strictly respecting priorities, equipment constraints, job bundling rules, and technician availability (including fixed/ongoing jobs).

System Trigger: A full replan calculation is triggered by significant events. Triggering is not handled by this application. Examples include:

A new job arriving with 'queued' status.

A job being completed or cancelled.

Significant unexpected delays reported.

Periodically (e.g., start of the day).

Key Data Inputs (Leveraging db.md Schema):

Technician Status: Real-time location, current job status (if any), assigned van.

Job Details: All jobs with relevant statuses, including order_id, service_id, priority, job_duration, address_id, status ('queued', 'en_route', 'in_progress', 'fixed_time', etc.), fixed_schedule_time.

Equipment & Requirements: Van equipment inventory (van_equipment), service categories (services), vehicle details (customer_vehicles, ymm_ref), and specific equipment needs per service/vehicle (*_equipment_requirements tables).

Travel Estimates: A system (API or matrix) to estimate travel time between locations (addresses).

Full Replan Algorithm:

Step 0: Identify Fixed Constraints

Identify all jobs J_locked that have a status of 'en_route', 'in_progress', or 'fixed_time'. These jobs are not eligible for rescheduling in this cycle.

For each job in J_locked, note its assigned technician, location, and its fixed or estimated completion time. This defines the earliest availability and starting location for that technician for any new assignments considered in this replan.

Step 1: Initialization & Pre-computation

Gather all jobs J_schedulable with the status 'queued'. This is the pool of work to be scheduled.

Gather all available technicians T_available, noting their current location and their earliest available time (considering commitments from J_locked).

Group Jobs: Scan J_schedulable and group jobs by order_id. Create "bundles" (B) for orders with multiple 'queued' jobs and identify single jobs (J_single).

Calculate Properties:

For each bundle B: Determine its overall priority (highest priority of any job within it) and its total duration (sum of job_duration for all jobs within it).

For each single job J_single: Note its priority and duration.

Eligibility Filtering:

For each bundle B: Determine the set of all unique required equipment_models across its jobs. Find the list of technicians EligibleTechs[B] whose vans contain all required equipment [cite: 48, 49, 53-57]. If this list is empty, break the bundle and treat its jobs as J_single for the remainder of the process.

For each single job J_single: Determine its required equipment_model and find the list of technicians EligibleTechs[J_single] whose vans have it.

Step 2: Phase 1 Assignment - Secure High-Priority Work

Create a combined list of all valid bundles and single jobs from Step 1. Sort this list primarily by priority (highest first, using the bundle's overall priority).

Iterate through the sorted list, processing higher-priority items first.

For each item (bundle B or single job J):

Evaluate only technicians T present in the item's eligibility list (EligibleTechs[B] or EligibleTechs[J]).

For each eligible T, calculate the earliest possible completion time if assigned this item, considering T's earliest availability (after J_locked), travel time, item duration, and end-of-workday constraints.

Constraint Check: Ensure assigning this item doesn't push any already tentatively assigned higher-or-equal priority item (from earlier in this Phase 1 loop for this technician) past the end-of-day cutoff if avoidable.

Select the eligible technician T* who provides the earliest valid ETA.

Tentatively assign the item (bundle or job) to T* and update T*'s tentative schedule (location, available time) for this replan cycle.

Step 3: Phase 2 Assignment - Schedule Remaining Work & Optimize Routes

Consider all valid bundles and single jobs remaining after Phase 1.

For each remaining item:

Evaluate only technicians T in its eligibility list.

For each eligible T, find the best "insertion point" into their current tentative schedule (built from J_locked and Phase 1 assignments). The "best" point minimizes travel time increase or achieves the earliest possible ETA for the current item, while respecting end-of-day constraints.

Select the eligible technician T* and insertion point that provides the best valid outcome.

Tentatively assign the item to T* at that position in their schedule.

Route Optimization (TSP Heuristic):

For each technician T:

Take their complete list of assignments for the day (locked jobs, Phase 1, Phase 2).

Treat locked jobs (J_locked) and their times/locations as fixed constraints.

Apply a TSP optimization algorithm (e.g., 2-opt, or using a library) to reorder the schedulable items (bundles/single jobs assigned in Phase 1 & 2) to minimize total daily travel time for T. Remember, a bundle B is treated as a single stop with its total duration.

Recalculate the final estimated_sched based on this optimized route [cite: 25, 29-31].

Step 4: Handle Overflow

Any 'queued' items (bundles or single jobs) that could not be assigned to any technician during Phases 1 or 2 remain in the 'queued' status (or are moved to a specific overflow status like 'pending_scheduling') for the next planning cycle.

Step 5: Update System State

Commit the results: Update the relevant fields (assigned_technician, estimated_sched, etc.) [cite: 25, 29-31] in the jobs table for all jobs that were successfully scheduled or rescheduled in this replan cycle.

This framework provides a robust, dynamic approach to scheduling that incorporates your specific business rules regarding priorities, equipment, job bundling, and handling fixed/ongoing work.



I. Core Goal, Technology Stack & Hosting

Goal: To dynamically schedule and assign 'queued' jobs to technicians using a full replan approach, maximizing the number of jobs completed daily while strictly respecting priorities (1-8), M-F 9:00 AM - 6:30 PM default technician availability, equipment constraints, job bundling (from the same order), and fixed/ongoing job constraints.

Main Backend Language/Runtime: Node.js with TypeScript

Optimization Microservice: Python (e.g., using Flask/FastAPI) leveraging Google OR-Tools library.

Database: Supabase (using supabase-js client from Node.js backend).

Travel Time Calculation: Google Maps Distance Matrix API (called from Node.js backend, using @googlemaps/google-maps-services-js or similar).

Frontend Context: React (TS/JS) - Interacts with the main Node.js backend.

Hosting:

Node.js Backend & Frontend: Vercel (Assumed, based on previous discussion context).

Python Optimization Microservice: Google Cloud Run (Container-based hosting).

II. Interfaces & Data Flow

Trigger: An external event initiates the replan process by calling an API endpoint on the main Node.js backend (hosted on Vercel).

Data Fetching (Node.js -> Supabase):

Node.js backend queries Supabase for all necessary data: relevant jobs ('queued', 'en_route', 'in_progress', 'fixed_time'), active technicians, vans, addresses, equipment inventory, equipment requirements, etc.

Travel Time Estimation (Node.js -> Google Maps API):

Node.js backend compiles required origin-destination pairs and calls the Google Maps Distance Matrix API, caching results where appropriate.

Optimization Request (Node.js -> Python Microservice on Cloud Run):

Node.js backend formats the fetched data (locations, jobs, bundles, technician availability, fixed constraints, travel times, eligible technicians per job/bundle) into a defined JSON payload (or other format like protobuf).

Node.js backend sends this payload via an HTTP request (or gRPC call) to the Python microservice's public endpoint (hosted on Google Cloud Run).

Solving (Python Microservice on Cloud Run with OR-Tools):

The Python microservice receives the request payload.

It parses the data and defines the optimization problem using the Python OR-Tools library (ortools.constraint_solver.routing_enums_pb2, ortools.constraint_solver.pywrapcp).

It applies all constraints (time windows, equipment via technician eligibility, priority via penalties/objectives, bundling).

It invokes the OR-Tools solver.

Optimization Response (Python Microservice on Cloud Run -> Node.js):

The Python microservice formats the solution (assigned routes, job sequences per technician, calculated start times) into a defined response format (e.g., JSON).

It sends this response back to the waiting Node.js backend.

Processing Results (Node.js):

Node.js backend receives the response from the Python microservice.

It parses the optimized routes and calculated estimated_sched times.

Updating Database (Node.js -> Supabase):

For each job included in the solution routes: Update its assigned_technician, calculated estimated_sched, and set status to 'scheduled'.

For any 'queued' job/bundle that was not included in the solution: Update its status to 'pending_review'.

III. Detailed Full Replan Algorithm Steps (Implementation Focus)

Step 0: Identify Fixed Constraints & Technician State (Node.js)

Fetch J_locked jobs ('en_route', 'in_progress', 'fixed_time') from Supabase.

Fetch active technician state (location, van) from Supabase.

Calculate current availability window (M-F 9:00 AM - 6:30 PM default, adjusted for current time and J_locked commitments). Store fixed job times/locations.

Step 1: Initialization & Pre-computation (Node.js)

Fetch J_schedulable jobs ('queued') from Supabase.

Group jobs by order_id into bundles B and singles J_single.

Calculate bundle properties (max(priority), sum(job_duration)).

Perform equipment eligibility checks (querying Supabase) to determine EligibleTechs[item] for each bundle/job. Break bundles if no single tech is eligible.

Prepare unique location data (addresses).

Fetch travel times using Google Maps API for all relevant O-D pairs.

Step 2 & 3: Call Optimization Microservice (Node.js -> Python on Cloud Run -> OR-Tools)

(Node.js): Consolidate all prepared data (technician availability windows/start locations, list of jobs/bundles with durations/priorities/locations/eligible technicians, fixed job constraints, travel time matrix) into a structured request payload (e.g., JSON).

(Node.js): Send an HTTP POST request (or gRPC call) to the Python microservice endpoint hosted on Google Cloud Run with the payload. await fetch('YOUR_CLOUD_RUN_SERVICE_URL/optimize-schedule', { method: 'POST', body: JSON.stringify(payload) }).

(Python Microservice on Cloud Run):

Receive the payload via its web framework (Flask/FastAPI).

Instantiate OR-Tools RoutingIndexManager and RoutingModel.

Register travel time callback using the matrix from the payload.

Add vehicles (technicians) with start/end times from payload.

Add demands (jobs/bundles) with service times, eligibility constraints (AddDisjunction), priority penalties, and fixed time windows (CumulVar().SetRange()).

Set solver parameters and call routing.SolveWithParameters().

Format the resulting assignment (routes, timings) into a JSON response.

Return the response.

(Node.js): Receive and parse the JSON response containing the optimized schedule. Handle potential errors from the microservice.

Step 4: Process Solution & Handle Overflow (Node.js)

Iterate through the routes received in the response.

For each job assigned in the routes, extract its calculated estimated_sched start time.

Identify any original 'queued' jobs/bundles that were not present in the solution routes – these are overflow.

Step 5: Update System State (Node.js -> Supabase)

Use supabase-js to perform batch updates:

For scheduled jobs: Set assigned_technician, estimated_sched, status='scheduled'.

For overflow jobs: Set status='pending_review'.