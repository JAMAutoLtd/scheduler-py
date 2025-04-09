import { bundleQueuedJobs } from '../../src/scheduler/bundling';
import { Job, JobBundle, SchedulableJob, SchedulableItem, Address } from '../../src/types/database.types';

// Mock Address data
const mockAddress1: Address = { id: 101, street_address: '123 Main St', lat: 40.0, lng: -75.0 };
const mockAddress2: Address = { id: 102, street_address: '456 Oak Ave', lat: 41.0, lng: -76.0 };
const mockAddress3: Address = { id: 103, street_address: '789 Pine Ln', lat: 42.0, lng: -77.0 };

describe('bundleQueuedJobs', () => {

  it('should return an empty array if no queued jobs are provided', () => {
    const queuedJobs: Job[] = [];
    const result = bundleQueuedJobs(queuedJobs);
    expect(result).toEqual([]);
  });

  it('should create SchedulableJob items for jobs with unique order_ids', () => {
    const job1: Job = { id: 1, order_id: 10, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const job2: Job = { id: 2, order_id: 11, address_id: 102, priority: 3, status: 'queued', job_duration: 45, service_id: 2, address: mockAddress2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const queuedJobs: Job[] = [job1, job2];

    const result = bundleQueuedJobs(queuedJobs);

    expect(result).toHaveLength(2);
    // Check Job 1
    const schedulableJob1 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 1) as SchedulableJob;
    expect(schedulableJob1).toBeDefined();
    expect(schedulableJob1.is_bundle).toBe(false);
    expect(schedulableJob1.job).toEqual(job1);
    expect(schedulableJob1.priority).toBe(5);
    expect(schedulableJob1.duration).toBe(30);
    expect(schedulableJob1.address_id).toBe(101);
    expect(schedulableJob1.address).toEqual(mockAddress1);
    expect(schedulableJob1.required_equipment_models).toEqual([]);
    expect(schedulableJob1.eligible_technician_ids).toEqual([]);

    // Check Job 2
    const schedulableJob2 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 2) as SchedulableJob;
    expect(schedulableJob2).toBeDefined();
    expect(schedulableJob2.is_bundle).toBe(false);
    expect(schedulableJob2.job).toEqual(job2);
    expect(schedulableJob2.priority).toBe(3);
    expect(schedulableJob2.duration).toBe(45);
    expect(schedulableJob2.address_id).toBe(102);
    expect(schedulableJob2.address).toEqual(mockAddress2);
  });

  it('should create a JobBundle for multiple jobs with the same order_id', () => {
    const job1: Job = { id: 1, order_id: 20, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const job2: Job = { id: 2, order_id: 20, address_id: 101, priority: 8, status: 'queued', job_duration: 60, service_id: 3, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const job3: Job = { id: 3, order_id: 20, address_id: 101, priority: 2, status: 'queued', job_duration: 15, service_id: 4, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const queuedJobs: Job[] = [job1, job2, job3];

    const result = bundleQueuedJobs(queuedJobs);

    expect(result).toHaveLength(1);
    const bundle = result[0] as JobBundle;

    // Check if it's a bundle (presence of 'jobs' array)
    expect(bundle.jobs).toBeDefined();
    expect(bundle.order_id).toBe(20);
    expect(bundle.jobs).toHaveLength(3);
    expect(bundle.jobs).toEqual(expect.arrayContaining([job1, job2, job3]));
    expect(bundle.total_duration).toBe(30 + 60 + 15); // 105
    expect(bundle.priority).toBe(8); // Highest priority
    expect(bundle.address_id).toBe(101);
    expect(bundle.address).toEqual(mockAddress1);
    expect(bundle.required_equipment_models).toEqual([]);
    expect(bundle.eligible_technician_ids).toEqual([]);
  });

  it('should handle a mix of single jobs and bundles', () => {
    const job1: Job = { id: 1, order_id: 30, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, address: mockAddress1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Single
    const job2: Job = { id: 2, order_id: 31, address_id: 102, priority: 8, status: 'queued', job_duration: 60, service_id: 3, address: mockAddress2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Bundle part 1
    const job3: Job = { id: 3, order_id: 31, address_id: 102, priority: 2, status: 'queued', job_duration: 15, service_id: 4, address: mockAddress2, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Bundle part 2
    const job4: Job = { id: 4, order_id: 32, address_id: 103, priority: 9, status: 'queued', job_duration: 75, service_id: 5, address: mockAddress3, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Single
    const queuedJobs: Job[] = [job1, job2, job3, job4];

    const result = bundleQueuedJobs(queuedJobs);

    expect(result).toHaveLength(3); // One single (30), one bundle (31), one single (32)

    // Check single job 1 (order 30)
    const schedulableJob1 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 1) as SchedulableJob;
    expect(schedulableJob1).toBeDefined();
    expect(schedulableJob1.is_bundle).toBe(false);
    expect(schedulableJob1.job).toEqual(job1);
    expect(schedulableJob1.priority).toBe(5);
    expect(schedulableJob1.duration).toBe(30);

    // Check bundle (order 31)
    const bundle = result.find(item => (item as JobBundle).order_id === 31) as JobBundle;
    expect(bundle).toBeDefined();
    expect(bundle.jobs).toHaveLength(2);
    expect(bundle.jobs).toEqual(expect.arrayContaining([job2, job3]));
    expect(bundle.total_duration).toBe(60 + 15); // 75
    expect(bundle.priority).toBe(8);
    expect(bundle.address_id).toBe(102);
    expect(bundle.address).toEqual(mockAddress2);

    // Check single job 4 (order 32)
    const schedulableJob4 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 4) as SchedulableJob;
    expect(schedulableJob4).toBeDefined();
    expect(schedulableJob4.is_bundle).toBe(false);
    expect(schedulableJob4.job).toEqual(job4);
    expect(schedulableJob4.priority).toBe(9);
    expect(schedulableJob4.duration).toBe(75);
    expect(schedulableJob4.address_id).toBe(103);
    expect(schedulableJob4.address).toEqual(mockAddress3);
  });

   it('should correctly set the bundle priority to the max priority of its jobs', () => {
    const jobLow: Job = { id: 1, order_id: 40, address_id: 101, priority: 1, status: 'queued', job_duration: 30, service_id: 1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const jobHigh: Job = { id: 2, order_id: 40, address_id: 101, priority: 10, status: 'queued', job_duration: 60, service_id: 3, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const jobMid: Job = { id: 3, order_id: 40, address_id: 101, priority: 5, status: 'queued', job_duration: 15, service_id: 4, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null };
    const queuedJobs: Job[] = [jobLow, jobHigh, jobMid];

    const result = bundleQueuedJobs(queuedJobs);
    expect(result).toHaveLength(1);
    const bundle = result[0] as JobBundle;
    expect(bundle.priority).toBe(10);
  });

   it('should handle jobs without attached address data gracefully', () => {
    const job1: Job = { id: 1, order_id: 50, address_id: 101, priority: 5, status: 'queued', job_duration: 30, service_id: 1, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // No address object
    const job2: Job = { id: 2, order_id: 51, address_id: 102, priority: 8, status: 'queued', job_duration: 60, service_id: 3, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Bundle part 1, no address
    const job3: Job = { id: 3, order_id: 51, address_id: 102, priority: 2, status: 'queued', job_duration: 15, service_id: 4, assigned_technician: null, estimated_sched: null, fixed_assignment: null, fixed_schedule_time: null, notes: null, requested_time: null, technician_notes: null }; // Bundle part 2, no address
    const queuedJobs: Job[] = [job1, job2, job3];

    const result = bundleQueuedJobs(queuedJobs);
    expect(result).toHaveLength(2);

    const schedulableJob1 = result.find(item => !(item as JobBundle).jobs && (item as SchedulableJob).job.id === 1) as SchedulableJob;
    expect(schedulableJob1).toBeDefined();
    expect(schedulableJob1.address_id).toBe(101);
    expect(schedulableJob1.address).toBeUndefined();

    const bundle = result.find(item => (item as JobBundle).order_id === 51) as JobBundle;
    expect(bundle).toBeDefined();
    expect(bundle.address_id).toBe(102);
    expect(bundle.address).toBeUndefined();
  });
}); 