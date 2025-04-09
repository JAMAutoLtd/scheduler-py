import { supabase } from '../../src/supabase/client';
import { getYmmIdForOrder } from '../../src/supabase/orders';
import { YmmRef } from '../../src/types/database.types'; // Removed CustomerVehicle

// Mock the Supabase client
jest.mock('../../src/supabase/client', () => ({
  supabase: {
    from: jest.fn().mockImplementation(tableName => ({
        select: jest.fn().mockReturnThis(),
        eq: jest.fn(), // Final method for this test
    })),
  },
}));

// Helper to mock the 'eq' call for the 'orders' table
// We expect select('customer_vehicles(ymm_ref(ymm_id))').eq('id', ...)
// @ts-expect-error - Type instantiation is excessively deep and possibly infinite
const mockSupabaseOrderEq = supabase.from('orders').select('customer_vehicles(ymm_ref(ymm_id))').eq as jest.Mock;

// --- Test Data ---
const mockYmmRef: YmmRef = {
    ymm_id: 12345,
    year: 2022,
    make: 'TestMake',
    model: 'TestModel'
};

// Raw data as returned by Supabase mock
const mockRawOrderDataWithYmm = [
    {
        // Orders table fields aren't needed, just the nested structure
        customer_vehicles: {
            ymm_ref: {
                ymm_id: mockYmmRef.ymm_id
            }
        }
    }
];

// --- Test Suite ---
describe('Supabase Order Fetching (getYmmIdForOrder)', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        (supabase.from as jest.Mock).mockClear(); // Clear calls to from
        mockSupabaseOrderEq.mockReset(); // Reset the eq mock
    });

    it('should return ymm_id for a valid order_id', async () => {
        const orderId = 2001;
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: mockRawOrderDataWithYmm, error: null });

        const ymmId = await getYmmIdForOrder(orderId);

        expect(supabase.from).toHaveBeenCalledWith('orders');
        expect(supabase.from('orders').select).toHaveBeenCalledWith('customer_vehicles(ymm_ref(ymm_id))');
        expect(mockSupabaseOrderEq).toHaveBeenCalledWith('id', orderId);
        expect(ymmId).toBe(mockYmmRef.ymm_id);
    });

    it('should return null if order is not found', async () => {
        const orderId = 9999;
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: [], error: null });

        const ymmId = await getYmmIdForOrder(orderId);

        expect(mockSupabaseOrderEq).toHaveBeenCalledWith('id', orderId);
        expect(ymmId).toBeNull();
    });

    it('should return null if customer_vehicle data is missing', async () => {
        const orderId = 2002;
        const mockRawDataMissingVehicle = [{ customer_vehicles: null }];
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: mockRawDataMissingVehicle, error: null });

        const ymmId = await getYmmIdForOrder(orderId);
        expect(ymmId).toBeNull();
    });

    it('should return null if ymm_ref data is missing', async () => {
        const orderId = 2003;
        const mockRawDataMissingYmmRef = [{ customer_vehicles: { ymm_ref: null } }];
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: mockRawDataMissingYmmRef, error: null });

        const ymmId = await getYmmIdForOrder(orderId);
        expect(ymmId).toBeNull();
    });

    it('should return null if ymm_id is missing', async () => {
        const orderId = 2004;
        const mockRawDataMissingYmmId = [{ customer_vehicles: { ymm_ref: { ymm_id: null } } }];
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: mockRawDataMissingYmmId, error: null });

        const ymmId = await getYmmIdForOrder(orderId);
        expect(ymmId).toBeNull();
    });

    it('should throw an error if Supabase returns an error', async () => {
        const orderId = 2005;
        const mockError = { message: 'Internal Server Error', code: '500' };
        mockSupabaseOrderEq.mockResolvedValueOnce({ data: null, error: mockError });

        await expect(getYmmIdForOrder(orderId)).rejects.toThrow('Failed to fetch ymm_id for order 2005: Internal Server Error');
        expect(mockSupabaseOrderEq).toHaveBeenCalledWith('id', orderId);
    });
}); 