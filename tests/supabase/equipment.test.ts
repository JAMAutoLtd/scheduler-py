import { supabase } from '../../src/supabase/client';
import { getEquipmentForVans, getRequiredEquipmentForJob } from '../../src/supabase/equipment';
import { VanEquipment, Equipment, Job, Service } from '../../src/types/database.types';
// Mock the imported function from orders.ts
import { getYmmIdForOrder } from '../../src/supabase/orders';

// --- Mock Setup ---

// Mock the entire orders module
jest.mock('../../src/supabase/orders', () => ({
    getYmmIdForOrder: jest.fn(),
}));

// Define reusable mock functions for the Supabase chain
const mockIn = jest.fn();
const mockSelect = jest.fn();
// Define separate mocks for the chained eq calls
const firstEqMock = jest.fn();
const finalEqMock = jest.fn();


// Mock the Supabase client
jest.mock('../../src/supabase/client', () => ({
    supabase: {
        from: jest.fn().mockImplementation((tableName: string) => {
            // Return an object that allows chaining .select().in() or .select().eq().eq()
            // We reset the implementations of select, in, eq mocks in beforeEach
            return {
                select: mockSelect.mockImplementation(() => ({
                    in: mockIn, // Used by getEquipmentForVans
                    // First eq() call returns an object containing the second eq mock
                    eq: firstEqMock.mockImplementation(() => ({
                        eq: finalEqMock, // The final call that should resolve the promise
                    })),
                })),
            };
        }),
    },
}));

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
        // Reset mocks specifically used in this suite
        mockIn.mockReset();
        mockSelect.mockReset(); // Reset select implementation/calls if needed
        (supabase.from as jest.Mock).mockClear(); // Clear calls to the main 'from' mock
    });

    it('should fetch equipment for multiple van IDs and group correctly', async () => {
        const vanIdsToFetch = [301, 302];
        // Mock the resolution of the 'in' method for this specific test
        mockIn.mockResolvedValueOnce({ data: mockRawVanEquipmentData, error: null });

        const equipmentMap = await getEquipmentForVans(vanIdsToFetch);

        // Assertions
        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSelect).toHaveBeenCalledWith(expect.stringContaining('equipment (')); // Check if select includes join
        expect(mockIn).toHaveBeenCalledWith('van_id', vanIdsToFetch);
        expect(mockIn).toHaveBeenCalledTimes(1); // Ensure it was called

        // Check results
        expect(equipmentMap.size).toBe(2);
        expect(equipmentMap.has(301)).toBe(true);
        expect(equipmentMap.get(301)).toEqual(expect.arrayContaining([mockVanEquipment1, mockVanEquipment2]));
        expect(equipmentMap.has(302)).toBe(true);
        expect(equipmentMap.get(302)).toEqual([mockVanEquipment3]);
    });

    it('should return an empty map if no van IDs are provided', async () => {
        const equipmentMap = await getEquipmentForVans([]);
        expect(equipmentMap.size).toBe(0);
        expect(supabase.from).not.toHaveBeenCalled();
        expect(mockSelect).not.toHaveBeenCalled();
        expect(mockIn).not.toHaveBeenCalled();
    });

    it('should return an empty map if no equipment is found for the given vans', async () => {
        // Mock 'in' resolving with empty data
        mockIn.mockResolvedValueOnce({ data: [], error: null });

        const equipmentMap = await getEquipmentForVans([999]);

        expect(equipmentMap.size).toBe(0);
        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSelect).toHaveBeenCalled();
        expect(mockIn).toHaveBeenCalledWith('van_id', [999]);
    });

     it('should return an empty map if Supabase returns data as null', async () => {
        // Test the !data condition specifically
        mockIn.mockResolvedValueOnce({ data: null, error: null });

        const equipmentMap = await getEquipmentForVans([998]);

        expect(equipmentMap.size).toBe(0);
        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSelect).toHaveBeenCalled();
        expect(mockIn).toHaveBeenCalledWith('van_id', [998]);
    });

    it('should throw an error if Supabase returns an error', async () => {
        const mockError = { message: 'Query failed', code: '400', details: '', hint: '' };
        // Mock 'in' resolving with an error
        mockIn.mockResolvedValueOnce({ data: null, error: mockError });

        await expect(getEquipmentForVans([301])).rejects.toThrow('Failed to fetch van equipment: Query failed');

        expect(supabase.from).toHaveBeenCalledWith('van_equipment');
        expect(mockSelect).toHaveBeenCalled();
        expect(mockIn).toHaveBeenCalledWith('van_id', [301]);
    });
});

// --- Test Suite: getRequiredEquipmentForJob ---
describe('Supabase Equipment Fetching (getRequiredEquipmentForJob)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        // Reset mocks used in this suite
        (getYmmIdForOrder as jest.Mock).mockReset();
        // Reset *both* eq mocks
        firstEqMock.mockReset();
        finalEqMock.mockReset();
        mockSelect.mockReset();
        (supabase.from as jest.Mock).mockClear();
    });

    it('should return required equipment model for a valid job', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        const expectedModel = 'ADAS-CAM-TOOL-Z3';

        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        // Mock the resolution of the FINAL 'eq' call
        finalEqMock.mockResolvedValueOnce({ data: [{ equipment_model: expectedModel }], error: null });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(getYmmIdForOrder).toHaveBeenCalledWith(mockJobAdas.order_id);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(mockSelect).toHaveBeenCalledWith('equipment_model');
        // Check that each eq mock was called once
        expect(firstEqMock).toHaveBeenCalledTimes(1);
        expect(finalEqMock).toHaveBeenCalledTimes(1);
        // Check the arguments of the eq calls
        expect(firstEqMock).toHaveBeenCalledWith('ymm_id', ymmId);
        // The mock implementation means the *second* call is on finalEqMock
        expect(finalEqMock).toHaveBeenCalledWith('service_id', mockJobAdas.service_id);
        expect(requiredModels).toEqual([expectedModel]);
    });

    it('should return multiple models if required', async () => {
         const ymmId = 12345;
         const expectedRequirementTable = 'adas_equipment_requirements';
         const expectedModels = ['MODEL-A', 'MODEL-B'];
         (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
         // Mock the final eq call resolving with multiple models
         finalEqMock.mockResolvedValueOnce({
             data: [{ equipment_model: 'MODEL-A' }, { equipment_model: 'MODEL-B' }],
             error: null
            });

         const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

         expect(getYmmIdForOrder).toHaveBeenCalledWith(mockJobAdas.order_id);
         expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
         expect(mockSelect).toHaveBeenCalledWith('equipment_model');
         // Check call counts
         expect(firstEqMock).toHaveBeenCalledTimes(1);
         expect(finalEqMock).toHaveBeenCalledTimes(1);
         // Check arguments
         expect(firstEqMock).toHaveBeenCalledWith('ymm_id', ymmId);
         expect(finalEqMock).toHaveBeenCalledWith('service_id', mockJobAdas.service_id);
         expect(requiredModels).toEqual(expectedModels);
    });

    it('should return an empty array if job has no service category', async () => {
        const jobNoCategory = { ...mockJobAdas, service: { ...mockServiceAdas, service_category: undefined } };
        const requiredModels = await getRequiredEquipmentForJob(jobNoCategory as any);

        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).not.toHaveBeenCalled();
        expect(supabase.from).not.toHaveBeenCalled();
        expect(mockSelect).not.toHaveBeenCalled();
        expect(firstEqMock).not.toHaveBeenCalled();
        expect(finalEqMock).not.toHaveBeenCalled();
    });

    it('should return an empty array if job has no order_id', async () => {
        const jobNoOrder = { ...mockJobAdas, order_id: null };
        const requiredModels = await getRequiredEquipmentForJob(jobNoOrder as any);

        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).not.toHaveBeenCalled();
        expect(supabase.from).not.toHaveBeenCalled();
        expect(mockSelect).not.toHaveBeenCalled();
        expect(firstEqMock).not.toHaveBeenCalled();
        expect(finalEqMock).not.toHaveBeenCalled();
    });

    it('should return an empty array if ymm_id cannot be determined', async () => {
        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(null);

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(requiredModels).toEqual([]);
        expect(getYmmIdForOrder).toHaveBeenCalledWith(mockJobAdas.order_id);
        expect(supabase.from).not.toHaveBeenCalled();
        expect(mockSelect).not.toHaveBeenCalled();
        expect(firstEqMock).not.toHaveBeenCalled();
        expect(finalEqMock).not.toHaveBeenCalled();
    });

    it('should return an empty array if no requirement is found in the database', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        // Mock final eq call resolving with empty data array
        finalEqMock.mockResolvedValueOnce({ data: [], error: null });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(requiredModels).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(mockSelect).toHaveBeenCalledWith('equipment_model');
        expect(firstEqMock).toHaveBeenCalledTimes(1);
        expect(finalEqMock).toHaveBeenCalledTimes(1);
        expect(firstEqMock).toHaveBeenCalledWith('ymm_id', ymmId);
        expect(finalEqMock).toHaveBeenCalledWith('service_id', mockJobAdas.service_id);
    });

     it('should return an empty array if requirement data is null', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        // Mock final eq call resolving with null data
        finalEqMock.mockResolvedValueOnce({ data: null, error: null });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(requiredModels).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(mockSelect).toHaveBeenCalledWith('equipment_model');
        expect(firstEqMock).toHaveBeenCalledTimes(1);
        expect(finalEqMock).toHaveBeenCalledTimes(1);
    });


    it('should return an empty array and warn if Supabase returns an error during requirement fetch', async () => {
        const ymmId = 12345;
        const expectedRequirementTable = 'adas_equipment_requirements';
        const mockError = { message: 'Permission denied', code: '403', details: '', hint: '' };
        const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation(); // Suppress console output

        (getYmmIdForOrder as jest.Mock).mockResolvedValueOnce(ymmId);
        // Mock final eq call resolving with an error
        finalEqMock.mockResolvedValueOnce({ data: null, error: mockError });

        const requiredModels = await getRequiredEquipmentForJob(mockJobAdas);

        expect(requiredModels).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith(expectedRequirementTable);
        expect(mockSelect).toHaveBeenCalledWith('equipment_model');
        expect(firstEqMock).toHaveBeenCalledTimes(1);
        expect(finalEqMock).toHaveBeenCalledTimes(1);
        expect(consoleWarnSpy).toHaveBeenCalledWith(
            expect.stringContaining(`Could not fetch equipment requirements from ${expectedRequirementTable} for ymm_id ${ymmId}, service_id ${mockJobAdas.service_id}: ${mockError.message}`)
        );

        consoleWarnSpy.mockRestore();
    });
}); 