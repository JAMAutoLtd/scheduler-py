import { supabase } from './client';
import { Job, JobStatus, Address, Service } from '../types/database.types';

// Define the job statuses relevant for the replanning process
const RELEVANT_JOB_STATUSES: JobStatus[] = [
  'queued',
  'en_route',
  'in_progress',
  'fixed_time',
];

/**
 * Fetches jobs with statuses relevant to the replanning process.
 * Includes 'queued', 'en_route', 'in_progress', and 'fixed_time' jobs.
 * Joins address and service details for convenience.
 *
 * @returns {Promise<Job[]>} A promise that resolves to an array of relevant jobs.
 */
export async function getRelevantJobs(): Promise<Job[]> {
  console.log(`Fetching jobs with statuses: ${RELEVANT_JOB_STATUSES.join(', ')}...`);

  const { data, error } = await supabase
    .from('jobs')
    .select(`
      id,
      order_id,
      assigned_technician,
      address_id,
      priority,
      status,
      requested_time,
      estimated_sched,
      job_duration,
      notes,
      technician_notes,
      service_id,
      fixed_assignment,
      fixed_schedule_time,
      addresses ( id, street_address, lat, lng ),
      services ( id, service_name, service_category )
    `)
    // The 'in' filter checks if the status is one of the values in the array
    .in('status', RELEVANT_JOB_STATUSES);

  if (error) {
    console.error('Error fetching jobs:', error);
    throw new Error(`Failed to fetch jobs: ${error.message}`);
  }

  if (!data) {
    console.warn('No relevant jobs found.');
    return [];
  }

  console.log(`Fetched ${data.length} relevant jobs.`);

  // Map the raw data to the Job interface, handling joined data
  const jobs: Job[] = data.map((job: any) => {
    // Supabase returns joined tables as potentially arrays, even for one-to-one joins via foreign key
    const address = Array.isArray(job.addresses) && job.addresses.length > 0 ? job.addresses[0] as Address : undefined;
    const service = Array.isArray(job.services) && job.services.length > 0 ? job.services[0] as Service : undefined;

    return {
      id: job.id,
      order_id: job.order_id,
      assigned_technician: job.assigned_technician,
      address_id: job.address_id,
      priority: job.priority,
      status: job.status as JobStatus, // Assume status matches our enum
      requested_time: job.requested_time,
      estimated_sched: job.estimated_sched,
      job_duration: job.job_duration,
      notes: job.notes,
      technician_notes: job.technician_notes,
      service_id: job.service_id,
      fixed_assignment: job.fixed_assignment,
      fixed_schedule_time: job.fixed_schedule_time,
      address: address,
      service: service,
    };
  });

  return jobs;
}

/**
 * Fetches jobs based on a specific list of statuses.
 * Joins address and service details for convenience.
 *
 * @param {JobStatus[]} statuses - An array of job statuses to filter by.
 * @returns {Promise<Job[]>} A promise that resolves to an array of jobs matching the statuses.
 */
export async function getJobsByStatus(statuses: JobStatus[]): Promise<Job[]> {
  if (!statuses || statuses.length === 0) {
    console.warn('getJobsByStatus called with empty status list. Returning empty array.');
    return [];
  }
  console.log(`Fetching jobs with statuses: ${statuses.join(', ')}...`);

  const { data, error } = await supabase
    .from('jobs')
    .select(`
      id,
      order_id,
      assigned_technician,
      address_id,
      priority,
      status,
      requested_time,
      estimated_sched,
      job_duration,
      notes,
      technician_notes,
      service_id,
      fixed_assignment,
      fixed_schedule_time,
      addresses ( id, street_address, lat, lng ),
      services ( id, service_name, service_category )
    `)
    // Use the provided statuses array for filtering
    .in('status', statuses);

  if (error) {
    console.error(`Error fetching jobs with statuses [${statuses.join(', ')}]:`, error);
    throw new Error(`Failed to fetch jobs by status: ${error.message}`);
  }

  if (!data) {
    console.warn(`No jobs found with statuses: ${statuses.join(', ')}.`);
    return [];
  }

  console.log(`Fetched ${data.length} jobs with statuses: ${statuses.join(', ')}.`);

  // Map the raw data to the Job interface, handling joined data (same logic as getRelevantJobs)
  const jobs: Job[] = data.map((job: any) => {
    const address = Array.isArray(job.addresses) && job.addresses.length > 0 ? job.addresses[0] as Address : undefined;
    const service = Array.isArray(job.services) && job.services.length > 0 ? job.services[0] as Service : undefined;

    return {
      id: job.id,
      order_id: job.order_id,
      assigned_technician: job.assigned_technician,
      address_id: job.address_id,
      priority: job.priority,
      status: job.status as JobStatus, // Assume status matches our enum
      requested_time: job.requested_time,
      estimated_sched: job.estimated_sched,
      job_duration: job.job_duration,
      notes: job.notes,
      technician_notes: job.technician_notes,
      service_id: job.service_id,
      fixed_assignment: job.fixed_assignment,
      fixed_schedule_time: job.fixed_schedule_time,
      address: address,
      service: service,
    };
  });

  return jobs;
}

// Example usage (can be removed later)
/*
getRelevantJobs()
  .then(jobs => {
    console.log('Successfully fetched relevant jobs:');
    console.log(JSON.stringify(jobs, null, 2));
  })
  .catch(err => {
    console.error('Failed to run example:', err);
  });
*/ 