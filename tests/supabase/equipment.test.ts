import { supabase } from '../../src/supabase/client';
import { getEquipmentForVans, getRequiredEquipmentForJob } from '../../src/supabase/equipment';
import { VanEquipment, Equipment, Job, Service } from '../../src/types/database.types';
// Mock the imported function from orders.ts
import { getYmmIdForOrder } from '../../src/supabase/orders';

// Mock the entire orders module
jest.mock('../../src/supabase/orders', () => ({
    getYmmIdForOrder: jest.fn(),
}));

// Mock the Supabase client
jest.mock('../../src/supabase/client', () => ({
  supabase: {
    // We need a more flexible mock for 'from' now
    from: jest.fn().mockImplementation(tableName => ({
        select: jest.fn().mockReturnThis(),
        in: jest.fn(), // For getEquipmentForVans
        eq: jest.fn().mockReturnThis(), // For requirement tables
        // Add mockReturnThis for chained eq calls
    })),
  },
}));

// --- Mock Helpers ---
// Helper for the mocked 'in' function specific to van_equipment
// @ts-expect-error - Complex mock type
const mockSupabaseVanEquipIn = supabase.from('van_equipment').select('...').in as jest.Mock;

// We need a more dynamic way to mock the 'eq' calls for different requirement tables
const mockSupabaseEq = (tableName: string): jest.Mock => {
    const fromMock = supabase.from(tableName) as any; // Get the mocked 'from' result
    // This assumes the chain is always select().eq().eq()
    // If the actual implementation changes, this mock structure needs updating
    return fromMock.select().eq().eq as jest.Mock;
};

// --- Test Data (Additions for getRequiredEquipmentForJob) ---
const mockServiceAdas: Service = {
    id: 501,
    service_name: 'Lane Keep Assist Cal',
    service_category: 'adas',
};

const mockJobAdas: Job = {
  id: 1001,
  order_id: 2001,
  assigned_technician: null,
  address_id: 101,
  priority: 5,
  status: 'queued',
  requested_time: null,
  estimated_sched: null,
  job_duration: 45,
  notes: null,
  technician_notes: null,
  service_id: 501,
  fixed_assignment: false,
  fixed_schedule_time: null,
  address: undefined,
  service: mockServiceAdas,
};

// --- Test Data ---
const mockEquipment1: Equipment = {
    id: 401,
    equipment_type: 'adas',
    model: 'ADAS-CAM-CALIBRATOR-X1'
};
const mockEquipment2: Equipment = {
    id: 402,
    equipment_type: 'prog',
    model: 'PROG-TOOL-Y2'
};

const mockVanEquipment1: VanEquipment = {
    van_id: 301,
    equipment_id: 401,
    equipment_model: 'ADAS-CAM-CALIBRATOR-X1',
    equipment: mockEquipment1,
};

const mockVanEquipment2: VanEquipment = {
    van_id: 301,
    equipment_id: 402,
    equipment_model: 'PROG-TOOL-Y2',
    equipment: mockEquipment2,
};

const mockVanEquipment3: VanEquipment = {
    van_id: 302,
    equipment_id: 401,
    equipment_model: 'ADAS-CAM-CALIBRATOR-X1',
    equipment: mockEquipment1,
};

// Raw Supabase data format
const mockRawVanEquipmentData = [
    {
        van_id: 301,
        equipment_id: 401,
        equipment_model: 'ADAS-CAM-CALIBRATOR-X1',
        equipment: [mockEquipment1] // Joined data as array
    },
    {
        van_id: 301,
        equipment_id: 402,
        equipment_model: 'PROG-TOOL-Y2',
        equipment: [mockEquipment2]
    },
    {
        van_id: 302,
        equipment_id: 401,
        equipment_model: 'ADAS-CAM-CALIBRATOR-X1',
        equipment: [mockEquipment1]
    },
];

// --- Test Suite: getEquipmentForVans ---
describe('Supabase Equipment Fetching (getEquipmentForVans)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockSupabaseVanEquipIn.mockReset();
    });

    it('should fetch equipment for multiple van IDs and group correctly', async () => {
        const vanIdsToFetch = [301, 302];
        mockSupabaseVanEquipIn.mockResolvedValueOnce({ data: mockRawVanEquipmentData, error: null });

        const equipmentMap = await getEquipmentForVans(vanIdsToFetch);

        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(supabase.from('van_equipment').select).toHaveBeenCalled();
        expect(mockSupabaseVanEquipIn).toHaveBeenCalledWith('van_id', vanIdsToFetch);

        expect(equipmentMap.size).toBe(2);
        // Check Van 301
        expect(equipmentMap.has(301)).toBe(true);
        expect(equipmentMap.get(301)).toHaveLength(2);
        expect(equipmentMap.get(301)).toEqual(expect.arrayContaining([mockVanEquipment1, mockVanEquipment2]));
        // Check Van 302
        expect(equipmentMap.has(302)).toBe(true);
        expect(equipmentMap.get(302)).toHaveLength(1);
        expect(equipmentMap.get(302)).toEqual([mockVanEquipment3]);
    });

    it('should return an empty map if no van IDs are provided', async () => {
        const equipmentMap = await getEquipmentForVans([]);
        expect(equipmentMap.size).toBe(0);
        expect(supabase.from).not.toHaveBeenCalled(); // Should not query if no IDs
    });

    it('should return an empty map if no equipment is found for the given vans', async () => {
        mockSupabaseVanEquipIn.mockResolvedValueOnce({ data: [], error: null });
        const equipmentMap = await getEquipmentForVans([999]);
        expect(equipmentMap.size).toBe(0);
        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSupabaseVanEquipIn).toHaveBeenCalledWith('van_id', [999]);
    });

    it('should throw an error if Supabase returns an error', async () => {
        const mockError = { message: 'Query failed', code: '400' };
        mockSupabaseVanEquipIn.mockResolvedValueOnce({ data: null, error: mockError });

        await expect(getEquipmentForVans([301])).rejects.toThrow('Failed to fetch van equipment: Query failed');
        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSupabaseVanEquipIn).toHaveBeenCalledWith('van_id', [301]);
    });
});

// --- Test Suite: getRequiredEquipmentForJob ---
describe('Supabase Equipment Fetching (getRequiredEquipmentForJob)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        // Reset mocks for both dependencies
        (getYmmIdForOrder as jest.Mock).mockReset();
        // Need to reset the underlying mock function created by mockImplementation
        (supabase.from as jest.Mock).mockClear(); // Clear calls to from itself
        // Clear mocks on the chained methods (might need more specific resets if tests interfere)
        const adasEqMock = mockSupabaseEq('adas_equipment_requirements');
        if (adasEqMock) adasEqMock.mockReset(); 
        // Add resets for other tables if needed by tests
    });

    it('should return required equipment model for a valid job', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        const expectedModel = 'ADAS-CAM-TOOL-Z3';

        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        // Configure the mock for the specific table and filters
        const eqMock = mockSupabaseEq(expectedRequirementTable);
        eqMock.mockResolvedValueOnce({ data: [{ equipment_model: expectedModel }], error: null });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(getYmmIdForOrder).toHaveBeenCalledWith(mockJobAdas.order_id);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        // Check that eq was called twice (for ymm_id and service_id)
        expect(supabase.from(expectedRequirementTable).select().eq).toHaveBeenCalledTimes(2);
        expect(supabase.from(expectedRequirementTable).select().eq).toHaveBeenCalledWith('ymm_id', ymmId);
        expect(supabase.from(expectedRequirementTable).select().eq).toHaveBeenCalledWith('service_id', mockJobAdas.service_id);
        expect(requiredModels).toEqual([expectedModel]);
    });

    it('should return multiple models if required', async () => {
         const ymmId = 12345;
         const expectedRequirementTable = 'adas_equipment_requirements';
         const expectedModels = ['MODEL-A', 'MODEL-B'];
         (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
         mockSupabaseEq(expectedRequirementTable).mockResolvedValueOnce({ 
             data: [{ equipment_model: 'MODEL-A' }, { equipment_model: 'MODEL-B' }], 
             error: null 
            });

         const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);
         expect(requiredModels).toEqual(expectedModels);
    });

    it('should return an empty array if job has no service category', async () => {
        const jobNoCategory = { ...mockJobAdas, service: { ...mockServiceAdas, service_category: undefined } };
        const requiredModels = await getRequiredEquipmentForJob(jobNoCategory as any);
        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).not.toHaveBeenCalled();
        expect(supabase.from).not.toHaveBeenCalled();
    });

    it('should return an empty array if job has no order_id', async () => {
        const jobNoOrder = { ...mockJobAdas, order_id: null };
        const requiredModels = await getRequiredEquipmentForJob(jobNoOrder as any);
        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).not.toHaveBeenCalled();
        expect(supabase.from).not.toHaveBeenCalled();
    });

    it('should return an empty array if ymm_id cannot be determined', async () => {
        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(null);

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);
        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).toHaveBeenCalledWith(mockJobAdas.order_id);
        expect(supabase.from).not.toHaveBeenCalled();
    });

    it('should return an empty array if no requirement is found in the database', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        mockSupabaseEq(expectedRequirementTable).mockResolvedValueOnce({ data: [], error: null });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);
        expect(requiredModels).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(supabase.from(expectedRequirementTable).select().eq).toHaveBeenCalledTimes(2);
    });

    it('should return an empty array and warn if Supabase returns an error during requirement fetch', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        const mockError = { message: 'Permission denied', code: '403' };
        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(); // Suppress console output

        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        mockSupabaseEq(expectedRequirementTable).mockResolvedValueOnce({ data: null, error: mockError });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);
        expect(requiredModels).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(consoleWarnSpy).toHaveBeenCalledWith(expect.stringContaining('Could not fetch equipment requirements'));
        
        consoleWarnSpy.mockRestore();
    });
}); 