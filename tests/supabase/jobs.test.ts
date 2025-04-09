import { supabase } from '../../src/supabase/client'; // Adjust path as needed
import { getRelevantJobs } from '../../src/supabase/jobs';
import { Job, JobStatus, Address, Service } from '../../src/types/database.types';

// Mock the Supabase client
jest.mock('../../src/supabase/client', () => ({
  supabase: {
    from: jest.fn().mockReturnThis(), // Chainable '.from()'
    select: jest.fn().mockReturnThis(), // Chainable '.select()'
    in: jest.fn(), // The final method that returns the data/error
  },
}));

// Helper to access the mocked 'in' function for resetting/configuring
// @ts-expect-error - Type instantiation is excessively deep and possibly infinite due to Jest mock chaining
const mockSupabaseIn = supabase.from('jobs').select('...').in as jest.Mock;

// --- Test Data ---
const mockAddress1: Address = {
  id: 101,
  street_address: '123 Test St',
  lat: 40.1,
  lng: -75.1,
};

const mockService1: Service = {
  id: 201,
  service_name: 'ADAS Calibration',
  service_category: 'adas',
};

const mockJobQueued: Job = {
  id: 1,
  order_id: 10,
  assigned_technician: null,
  address_id: 101,
  priority: 5,
  status: 'queued',
  requested_time: new Date('2024-05-10T10:00:00Z').toISOString(),
  estimated_sched: null,
  job_duration: 60,
  notes: 'Test note',
  technician_notes: null,
  service_id: 201,
  fixed_assignment: false,
  fixed_schedule_time: null,
  address: mockAddress1,
  service: mockService1,
};

const mockJobInProgress: Job = {
  ...mockJobQueued,
  id: 2,
  status: 'in_progress',
  assigned_technician: 5,
  estimated_sched: new Date('2024-05-09T14:00:00Z').toISOString(),
};

const mockJobFixedTime: Job = {
    ...mockJobQueued,
    id: 3,
    status: 'fixed_time',
    assigned_technician: 6,
    fixed_schedule_time: new Date('2024-05-10T15:00:00Z').toISOString(),
};

// --- Test Suite ---
describe('Supabase Job Fetching (getRelevantJobs)', () => {
  // Reset mocks before each test
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset the specific mock implementation for the 'in' method using the helper
    mockSupabaseIn.mockReset();
  });

  it('should fetch only relevant job statuses', async () => {
    const mockRawData = [
        { ...mockJobQueued, addresses: [mockAddress1], services: [mockService1] }, // Supabase format
        { ...mockJobInProgress, addresses: [mockAddress1], services: [mockService1] },
        { ...mockJobFixedTime, addresses: [mockAddress1], services: [mockService1] },
    ];
    const expectedStatuses: JobStatus[] = ['queued', 'en_route', 'in_progress', 'fixed_time'];

    // Configure the mock for this specific test case using the helper
    mockSupabaseIn.mockResolvedValueOnce({ data: mockRawData, error: null });

    const jobs = await getRelevantJobs();

    // Check that 'from' was called with 'jobs'
    expect(supabase.from).toHaveBeenCalledWith('jobs');
    // Check that 'select' was called (content doesn't strictly matter for this test)
    expect(supabase.from('jobs').select).toHaveBeenCalled();
    // Check that 'in' was called with the correct statuses using the helper
    expect(mockSupabaseIn).toHaveBeenCalledWith('status', expectedStatuses);
    
    // Check the returned data structure and content
    expect(jobs).toHaveLength(mockRawData.length);
    expect(jobs[0]).toEqual(mockJobQueued);
    expect(jobs[1]).toEqual(mockJobInProgress);
    expect(jobs[2]).toEqual(mockJobFixedTime);
  });

  it('should return an empty array when no relevant jobs are found', async () => {
     // Configure the mock to return empty data using the helper
     mockSupabaseIn.mockResolvedValueOnce({ data: [], error: null });

     const jobs = await getRelevantJobs();

     expect(jobs).toEqual([]);
     expect(supabase.from).toHaveBeenCalledWith('jobs');
     expect(mockSupabaseIn).toHaveBeenCalled();
  });

  it('should throw an error when Supabase returns an error', async () => {
    const mockError = { message: 'Supabase query failed', details: 'Connection error', code: '500' };
    // Configure the mock to return an error using the helper
    mockSupabaseIn.mockResolvedValueOnce({ data: null, error: mockError });

    // Expect the function to throw an error
    await expect(getRelevantJobs()).rejects.toThrow('Failed to fetch jobs: Supabase query failed');

    expect(supabase.from).toHaveBeenCalledWith('jobs');
    expect(mockSupabaseIn).toHaveBeenCalled();
  });
  
   // TODO: Add edge case tests if applicable (e.g., jobs missing address/service?)
   // Note: The current implementation handles missing joined data gracefully, returning undefined.
   // A test could explicitly check this if needed, by providing mockRawData with missing/empty joins.

}); 