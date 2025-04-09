import { supabase } from '../../src/supabase/client';
import { getYmmIdForOrder } from '../../src/supabase/orders';
import { YmmRef } from '../../src/types/database.types'; // Removed CustomerVehicle

// Define the type for the object returned by .eq() that can chain .eq() or end with .single()
interface ChainedQuery {
    eq: jest.Mock<ChainedQuery>; // Returns itself for chaining
    single: jest.Mock<Promise<{ data: any; error: any }>>; // Returns the single result
}

// Mock the Supabase client
const mockSingle = jest.fn<Promise<{ data: any; error: any }>, []>();
// Explicitly type mockEqReturn using ChainedQuery
const mockEqReturn: ChainedQuery = {
    eq: jest.fn(() => mockEqReturn),
    single: mockSingle,
};
// Simplify mockEq definition - it just needs to return the correctly typed mockEqReturn object
const mockEq = jest.fn(() => mockEqReturn);

// Capture the mock select function instance
const mockSelect = jest.fn().mockReturnThis(); 

jest.mock('../../src/supabase/client', () => ({
  supabase: {
    from: jest.fn().mockImplementation(tableName => ({
        // Return the captured select mock
        select: mockSelect, 
        eq: mockEq, 
    })),
  },
}));

// Helper to mock the .single() call results. 
// We only need one mock for .single() as it's the terminal call.
const mockSingleResult = mockSingle as jest.Mock;

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
        (supabase.from as jest.Mock).mockClear();
        mockSelect.mockClear(); // Clear the captured select mock
        mockEq.mockClear();
        (mockEqReturn.eq as jest.Mock).mockClear(); 
        mockSingle.mockClear(); 
    });

    it('should return ymm_id for a valid order_id', async () => {
        const orderId = 2001;
        // Mock the first .single() call (for orders)
        mockSingleResult.mockResolvedValueOnce({ data: { customer_vehicles: { year: 2022, make: 'TestMake', model: 'TestModel' } }, error: null });
        // Mock the second .single() call (for ymm_ref)
        mockSingleResult.mockResolvedValueOnce({ data: { ymm_id: 12345 }, error: null });

        const ymmId = await getYmmIdForOrder(orderId);

        // Check first query chain
        expect(supabase.from).toHaveBeenCalledWith('orders');
        // Assert against the captured mockSelect instance
        expect(mockSelect).toHaveBeenCalledWith(expect.stringContaining('customer_vehicles')); 
        expect(mockEq).toHaveBeenCalledWith('id', orderId);
        
        // Check second query chain
        expect(supabase.from).toHaveBeenCalledWith('ymm_ref');
        // Assert against the captured mockSelect instance again (it's reused)
        expect(mockSelect).toHaveBeenCalledWith('ymm_id'); 
        expect(mockEq).toHaveBeenCalledWith('year', 2022);
        expect(mockEqReturn.eq).toHaveBeenCalledWith('make', 'TestMake');
        expect(mockEqReturn.eq).toHaveBeenCalledWith('model', 'TestModel');
        
        expect(mockSingle).toHaveBeenCalledTimes(2); 
        expect(ymmId).toBe(12345);
    });

    it('should return null if order is not found', async () => {
        const orderId = 9999;
        mockSingleResult.mockResolvedValueOnce({ data: null, error: { message: 'No rows returned', code: 'PGRST0' } });

        const ymmId = await getYmmIdForOrder(orderId);

        expect(mockEq).toHaveBeenCalledWith('id', orderId);
        expect(mockSingle).toHaveBeenCalledTimes(1);
        expect(ymmId).toBeNull();
    });

    it('should return null if customer_vehicle data is missing', async () => {
        const orderId = 2002;
        mockSingleResult.mockResolvedValueOnce({ data: { customer_vehicles: null }, error: null });

        const ymmId = await getYmmIdForOrder(orderId);
        expect(mockSingle).toHaveBeenCalledTimes(1);
        expect(ymmId).toBeNull();
    });

    it('should return null if ymm_ref data is missing', async () => {
        const orderId = 2003;
        mockSingleResult.mockResolvedValueOnce({ data: { customer_vehicles: { year: 2022, make: 'TestMake', model: 'TestModel' } }, error: null }); // Order success
        mockSingleResult.mockResolvedValueOnce({ data: null, error: { message: 'No rows returned', code: 'PGRST0' } }); // YMM fail

        const ymmId = await getYmmIdForOrder(orderId);
        expect(mockSingle).toHaveBeenCalledTimes(2);
        expect(ymmId).toBeNull();
    });

    it('should return null if ymm_id is missing in ymm_ref data', async () => {
        const orderId = 2004;
        mockSingleResult.mockResolvedValueOnce({ data: { customer_vehicles: { year: 2022, make: 'TestMake', model: 'TestModel' } }, error: null }); // Order success
        mockSingleResult.mockResolvedValueOnce({ data: { ymm_id: null }, error: null }); // YMM success but null id

        const ymmId = await getYmmIdForOrder(orderId);
        expect(mockSingle).toHaveBeenCalledTimes(2);
        expect(ymmId).toBeNull();
    });

    it('should throw an error if Supabase returns an error on the first query', async () => {
        const orderId = 2005;
        const mockError = { message: 'Internal Server Error', code: '500' };
        mockSingleResult.mockResolvedValueOnce({ data: null, error: mockError }); // First single fails

        await expect(getYmmIdForOrder(orderId)).rejects.toThrow('Failed to fetch order 2005: Internal Server Error');
        expect(mockEq).toHaveBeenCalledWith('id', orderId);
        expect(mockSingle).toHaveBeenCalledTimes(1);
    });

     it('should throw an error if Supabase returns an error on the second query', async () => {
        const orderId = 2006;
        const mockError = { message: 'YMM lookup failed', code: 'XXX' };
        mockSingleResult.mockResolvedValueOnce({ data: { customer_vehicles: { year: 2022, make: 'TestMake', model: 'TestModel' } }, error: null }); // Order success
        mockSingleResult.mockResolvedValueOnce({ data: null, error: mockError }); // YMM single fails

        await expect(getYmmIdForOrder(orderId)).rejects.toThrow('Failed to fetch ymm_ref: YMM lookup failed');
        expect(mockSingle).toHaveBeenCalledTimes(2);
    });
}); 