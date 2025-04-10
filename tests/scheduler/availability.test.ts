import { calculateTechnicianAvailability, calculateAvailabilityForDay } from '../../src/scheduler/availability';
import { Technician, Job, TechnicianAvailability } from '../../src/types/database.types';
import { describe, it, expect, beforeEach, jest, test } from '@jest/globals';

// Mock Date
const MOCK_WORKDAY_DATE = new Date('2024-07-23T10:00:00.000Z'); // Tuesday 10:00 AM UTC
const MOCK_WEEKEND_DATE = new Date('2024-07-27T10:00:00.000Z'); // Saturday 10:00 AM UTC
const MOCK_MONDAY_DATE = new Date('2024-07-29T00:00:00.000Z'); // Monday Midnight UTC

// Constants for work hours (assuming UTC for simplicity in tests)
const WORK_START_HOUR_UTC = 9;
const WORK_END_HOUR_UTC = 18;
const WORK_END_MINUTE_UTC = 30;

describe('Scheduler Availability Logic', () => {

    beforeEach(() => {
        // Reset date mocks before each test using Jest
        jest.useRealTimers();
    });

    // --- Tests for calculateTechnicianAvailability (Today's Planning) ---
    describe('calculateTechnicianAvailability', () => {
        const mockTech1: Technician = {
            id: 1,
            user_id: 'uuid1',
            assigned_van_id: 101,
            workload: 100,
            current_location: { lat: 40.0, lng: -75.0 }, // Depot
            home_location: { lat: 40.1, lng: -75.1 },
        };
        const mockTech2: Technician = {
            id: 2,
            user_id: 'uuid2',
            assigned_van_id: 102,
            workload: 100,
            current_location: { lat: 40.0, lng: -75.0 }, // Depot
            home_location: { lat: 40.2, lng: -75.2 },
        };

        it('should set availability to current time if no locked jobs and within work hours', () => {
            jest.useFakeTimers(); // Use Jest fake timers
            jest.setSystemTime(MOCK_WORKDAY_DATE); // Set time with Jest
            const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
            const lockedJobs: Job[] = [];

            calculateTechnicianAvailability(techs, lockedJobs);

            const expectedStartTime = new Date(MOCK_WORKDAY_DATE);
            expect(techs[0].earliest_availability).toBe(expectedStartTime.toISOString());
            expect(techs[0].current_location).toEqual(mockTech1.current_location);
        });

        it('should set availability based on the end time of the latest locked job', () => {
            jest.useFakeTimers();
            jest.setSystemTime(MOCK_WORKDAY_DATE); // 10:00 AM
            const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
            const lockedJob: Job = {
                id: 101,
                order_id: 1,
                assigned_technician: 1,
                address_id: 1,
                priority: 1,
                status: 'in_progress',
                requested_time: null,
                estimated_sched: '2024-07-23T09:30:00.000Z', // Started 9:30 AM
                job_duration: 60, // 60 minutes
                notes: null,
                technician_notes: null,
                service_id: 1,
                fixed_assignment: null,
                fixed_schedule_time: null,
                address: { id: 1, street_address: '123 Main St', lat: 40.5, lng: -75.5 },
            };

            calculateTechnicianAvailability(techs, [lockedJob]);

            // Job ends at 10:30 AM (9:30 + 60 mins)
            const expectedEndTime = new Date('2024-07-23T10:30:00.000Z');
            expect(techs[0].earliest_availability).toBe(expectedEndTime.toISOString());
            // Expect only the coordinates, not the full address object
            expect(techs[0].current_location).toEqual({ lat: lockedJob.address!.lat, lng: lockedJob.address!.lng });
        });

        it('should cap availability at the end of the workday if locked jobs finish late', () => {
            jest.useFakeTimers();
            jest.setSystemTime(MOCK_WORKDAY_DATE); // 10:00 AM
            const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
            const lockedJob: Job = {
                id: 102,
                order_id: 2,
                assigned_technician: 1,
                address_id: 2,
                priority: 1,
                status: 'fixed_time',
                requested_time: null,
                estimated_sched: null,
                job_duration: 120, // 120 minutes
                notes: null,
                technician_notes: null,
                service_id: 1,
                fixed_assignment: true,
                fixed_schedule_time: '2024-07-23T17:00:00.000Z', // Fixed at 5:00 PM
                address: { id: 2, street_address: '456 Oak Ave', lat: 40.6, lng: -75.6 },
            };

            calculateTechnicianAvailability(techs, [lockedJob]);

            // Job ends at 7:00 PM (5:00 PM + 120 mins), but workday ends 6:30 PM
            const expectedEndTime = new Date(MOCK_WORKDAY_DATE);
            expectedEndTime.setUTCHours(WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0);
            expect(techs[0].earliest_availability).toBe(expectedEndTime.toISOString());
            // Expect only the coordinates, not the full address object
            expect(techs[0].current_location).toEqual({ lat: lockedJob.address!.lat, lng: lockedJob.address!.lng });
        });
        
        // Add more tests for calculateTechnicianAvailability: edge cases, multiple jobs, etc.
    });

    // --- Tests for calculateAvailabilityForDay (Future/Overflow Planning) ---
    describe('calculateAvailabilityForDay', () => {
        const mockTech1: Technician = {
            id: 1,
            user_id: 'uuid1',
            assigned_van_id: 101,
            workload: 100,
            home_location: { lat: 40.1, lng: -75.1 }, // Valid home location
            current_location: { lat: 40.0, lng: -75.0 }, // Should be ignored
        };
        const mockTech2: Technician = { // Second valid tech
            id: 2,
            user_id: 'uuid2',
            assigned_van_id: 102,
            workload: 100,
            home_location: { lat: 40.2, lng: -75.2 }, // Valid home location
            current_location: { lat: 40.0, lng: -75.0 },
        };
         const mockTech3MissingHome: Technician = {
            id: 3,
            user_id: 'uuid3',
            assigned_van_id: 103,
            workload: 100,
            home_location: undefined, // Missing home location
            current_location: { lat: 40.0, lng: -75.0 },
        };
        const MOCK_SUNDAY_DATE = new Date('2024-07-28T10:00:00.000Z'); // Sunday 10:00 AM UTC

        it('should calculate correct availability window for a weekday using home location', () => {
            const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
            const targetDate = MOCK_MONDAY_DATE; // Monday

            const availability = calculateAvailabilityForDay(techs, targetDate);

            expect(availability).toHaveLength(1);
            const result = availability[0];

            const expectedStart = new Date(targetDate);
            expectedStart.setUTCHours(WORK_START_HOUR_UTC, 0, 0, 0);
            const expectedEnd = new Date(targetDate);
            expectedEnd.setUTCHours(WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0);

            expect(result.technicianId).toBe(mockTech1.id);
            expect(result.availabilityStartTimeISO).toBe(expectedStart.toISOString());
            expect(result.availabilityEndTimeISO).toBe(expectedEnd.toISOString());
            expect(result.startLocation).toEqual(mockTech1.home_location);
        });

        it('should return an empty array for a Saturday date', () => {
             const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
             const targetDate = MOCK_WEEKEND_DATE; // Saturday

             const availability = calculateAvailabilityForDay(techs, targetDate);

             expect(availability).toHaveLength(0);
        });

        it('should return an empty array for a Sunday date', () => {
            const techs = [JSON.parse(JSON.stringify(mockTech1))]; // Deep copy
            const targetDate = MOCK_SUNDAY_DATE; // Sunday

            const availability = calculateAvailabilityForDay(techs, targetDate);

            expect(availability).toHaveLength(0);
        });

        it('should calculate availability for multiple valid technicians', () => {
            const techs = [
                JSON.parse(JSON.stringify(mockTech1)),
                JSON.parse(JSON.stringify(mockTech2))
            ];
            const targetDate = MOCK_MONDAY_DATE; // Monday

            const availability = calculateAvailabilityForDay(techs, targetDate);

            expect(availability).toHaveLength(2);

            const expectedStart = new Date(targetDate);
            expectedStart.setUTCHours(WORK_START_HOUR_UTC, 0, 0, 0);
            const expectedEnd = new Date(targetDate);
            expectedEnd.setUTCHours(WORK_END_HOUR_UTC, WORK_END_MINUTE_UTC, 0, 0);

            // Check Tech 1
            const result1 = availability.find(a => a.technicianId === mockTech1.id);
            expect(result1).toBeDefined();
            expect(result1?.availabilityStartTimeISO).toBe(expectedStart.toISOString());
            expect(result1?.availabilityEndTimeISO).toBe(expectedEnd.toISOString());
            expect(result1?.startLocation).toEqual(mockTech1.home_location);

            // Check Tech 2
            const result2 = availability.find(a => a.technicianId === mockTech2.id);
            expect(result2).toBeDefined();
            expect(result2?.availabilityStartTimeISO).toBe(expectedStart.toISOString());
            expect(result2?.availabilityEndTimeISO).toBe(expectedEnd.toISOString());
            expect(result2?.startLocation).toEqual(mockTech2.home_location);
        });

        it('should skip technicians with missing home locations', () => {
             const techs = [
                 JSON.parse(JSON.stringify(mockTech1)),
                 JSON.parse(JSON.stringify(mockTech3MissingHome))
             ];
             const targetDate = MOCK_MONDAY_DATE; // Monday

             const availability = calculateAvailabilityForDay(techs, targetDate);

             expect(availability).toHaveLength(1); // Only tech1 should be included
             expect(availability[0].technicianId).toBe(mockTech1.id);
        });
        
        it('should return an empty array if all technicians are missing home locations', () => {
            const techs = [
                JSON.parse(JSON.stringify(mockTech3MissingHome))
            ];
            const targetDate = MOCK_MONDAY_DATE; // Monday

            const availability = calculateAvailabilityForDay(techs, targetDate);

            expect(availability).toHaveLength(0);
        });

        // Note: Holiday checking is assumed to be handled by external configuration/DB,
        // treating holidays like weekends, so no specific holiday test needed here.
    });
}); 