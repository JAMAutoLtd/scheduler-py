import { supabase } from '../../src/supabase/client';
import { getActiveTechnicians } from '../../src/supabase/technicians';
import { Technician, Van, User, Address } from '../../src/types/database.types';

// Mock the Supabase client
jest.mock('../../src/supabase/client', () => ({
  supabase: {
    from: jest.fn().mockReturnThis(),
    select: jest.fn(), // The final method for technicians fetch
  },
}));

// Helper to access the mocked 'select' function
const mockSupabaseSelect = supabase.from('technicians').select as jest.Mock;

// --- Test Data ---
const mockVan1: Van = {
    id: 301,
    vin: 'VAN123',
    lat: 40.2,
    lng: -75.2,
    last_service: new Date().toISOString(),
    next_service: new Date().toISOString(),
};

const mockUser1: User = {
    id: 'user-uuid-1',
    full_name: 'Tech One',
    phone: '111-222-3333',
    home_address_id: 102,
    is_admin: false,
    customer_type: null, // Not relevant for technicians
};

const mockTech1: Technician = {
    id: 5,
    user_id: 'user-uuid-1',
    assigned_van_id: 301,
    workload: 0,
    user: mockUser1,
    van: mockVan1,
    current_location: { lat: 40.2, lng: -75.2 },
    earliest_availability: undefined, // Calculated later
};

// Raw data format as returned by Supabase mock
const mockRawTechData = [
    {
        id: mockTech1.id,
        user_id: mockTech1.user_id,
        assigned_van_id: mockTech1.assigned_van_id,
        workload: mockTech1.workload,
        users: [mockUser1], // Supabase returns joined data as arrays
        vans: [mockVan1],
    },
];

// --- Test Suite ---
describe('Supabase Technician Fetching (getActiveTechnicians)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        mockSupabaseSelect.mockReset();
    });

    it('should fetch active technicians with user and van details', async () => {
        mockSupabaseSelect.mockResolvedValueOnce({ data: mockRawTechData, error: null });

        const technicians = await getActiveTechnicians();

        expect(supabase.from).toHaveBeenCalledWith('technicians');
        expect(mockSupabaseSelect).toHaveBeenCalledWith(expect.any(String)); // Check select was called
        expect(technicians).toHaveLength(1);
        // Check mapping and structure
        expect(technicians[0]).toEqual(mockTech1);
        expect(technicians[0].current_location).toEqual({ lat: mockVan1.lat, lng: mockVan1.lng });
    });

    it('should handle technicians with missing van location', async () => {
        const mockVanNoLocation = { ...mockVan1, lat: null, lng: null };
        const mockRawDataNoLoc = [{
            ...mockRawTechData[0],
            vans: [mockVanNoLocation]
        }];
        mockSupabaseSelect.mockResolvedValueOnce({ data: mockRawDataNoLoc, error: null });

        const technicians = await getActiveTechnicians();

        expect(technicians).toHaveLength(1);
        expect(technicians[0].van?.lat).toBeNull();
        expect(technicians[0].current_location).toBeUndefined(); // Should be undefined if van coords are null
    });

    it('should return an empty array when no technicians are found', async () => {
        mockSupabaseSelect.mockResolvedValueOnce({ data: [], error: null });

        const technicians = await getActiveTechnicians();

        expect(technicians).toEqual([]);
        expect(supabase.from).toHaveBeenCalledWith('technicians');
        expect(mockSupabaseSelect).toHaveBeenCalled();
    });

    it('should throw an error when Supabase returns an error', async () => {
        const mockError = { message: 'DB connection failed', code: '503' };
        mockSupabaseSelect.mockResolvedValueOnce({ data: null, error: mockError });

        await expect(getActiveTechnicians()).rejects.toThrow('Failed to fetch technicians: DB connection failed');

        expect(supabase.from).toHaveBeenCalledWith('technicians');
        expect(mockSupabaseSelect).toHaveBeenCalled();
    });
}); 