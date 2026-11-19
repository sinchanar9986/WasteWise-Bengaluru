-- ============================================================
-- SIMULATED DATA — not verified operational BBMP data
-- For demonstration purposes only (Waste Wise Bengaluru MVP)
-- ============================================================

USE wastewise;

-- --------------------------------------------------------
-- Facilities (6 simulated Bengaluru facilities)
-- remaining_capacity_tons = total_capacity_tons - used_capacity_tons
-- --------------------------------------------------------
INSERT INTO facilities
    (name, accepted_materials, total_capacity_tons, used_capacity_tons, remaining_capacity_tons, status, zone, data_label)
VALUES
    -- 1. Organic/Wet — North Bengaluru (Yelahanka zone), large, partially used
    (
        'Yelahanka Organic Processing Centre',
        'organic,wet',
        400.00,
        160.00,
        240.00,  -- 400.00 - 160.00
        'OPEN',
        'North Bengaluru – Yelahanka',
        'SIMULATED'
    ),
    -- 2. Dry/Plastic — South Bengaluru, medium, mostly empty
    (
        'Bannerghatta Dry Waste Facility',
        'dry,plastic',
        250.00,
        30.00,
        220.00,  -- 250.00 - 30.00
        'OPEN',
        'South Bengaluru – Bannerghatta',
        'SIMULATED'
    ),
    -- 3. E-Waste — East Bengaluru (Whitefield zone), small, nearly full (limited capacity demo)
    (
        'Whitefield E-Waste Collection Hub',
        'e-waste',
        80.00,
        74.00,
        6.00,   -- 80.00 - 74.00
        'OPEN',
        'East Bengaluru – Whitefield',
        'SIMULATED'
    ),
    -- 4. Construction & Demolition — West Bengaluru, large, low usage
    (
        'Rajajinagar C&D Waste Yard',
        'construction',
        500.00,
        55.00,
        445.00,  -- 500.00 - 55.00
        'OPEN',
        'West Bengaluru – Rajajinagar',
        'SIMULATED'
    ),
    -- 5. Mixed/General — Central Bengaluru, medium, 50% used
    (
        'Shivajinagar Mixed Waste Transfer Station',
        'mixed,organic,dry',
        200.00,
        100.00,
        100.00,  -- 200.00 - 100.00
        'OPEN',
        'Central Bengaluru – Shivajinagar',
        'SIMULATED'
    ),
    -- 6. Plastic/Dry — North-East Bengaluru (Hebbal zone), medium, low usage
    (
        'Hebbal Plastic & Dry Waste Depot',
        'plastic,dry',
        180.00,
        25.00,
        155.00,  -- 180.00 - 25.00
        'OPEN',
        'North-East Bengaluru – Hebbal',
        'SIMULATED'
    );

-- --------------------------------------------------------
-- Sample waste_requests (3 historical requests)
-- --------------------------------------------------------
INSERT INTO waste_requests
    (raw_input, waste_type, quantity_tons, origin, created_at)
VALUES
    (
        'Allocate 8 tons of organic waste from Yelahanka',
        'organic',
        8.00,
        'Yelahanka',
        '2026-11-18 09:15:00'
    ),
    (
        'Send 12 tons of plastic waste from Koramangala',
        'plastic',
        12.00,
        'Koramangala',
        '2026-11-18 11:30:00'
    ),
    (
        'Dispose 3 tons of e-waste from Whitefield IT Park',
        'e-waste',
        3.00,
        'Whitefield IT Park',
        '2026-11-18 14:45:00'
    );

-- --------------------------------------------------------
-- Sample allocations (3 pre-seeded, matching the requests above)
-- facility_id references: 1=Yelahanka Organic, 2=Bannerghatta Dry/Plastic, 3=Whitefield E-Waste
-- --------------------------------------------------------
INSERT INTO allocations
    (request_id, facility_id, waste_type, quantity_tons, origin, allocated_at, status)
VALUES
    (
        1,   -- waste_request id 1 (organic, Yelahanka)
        1,   -- Yelahanka Organic Processing Centre
        'organic',
        8.00,
        'Yelahanka',
        '2026-11-18 09:15:05',
        'ALLOCATED'
    ),
    (
        2,   -- waste_request id 2 (plastic, Koramangala)
        2,   -- Bannerghatta Dry Waste Facility
        'plastic',
        12.00,
        'Koramangala',
        '2026-11-18 11:30:08',
        'ALLOCATED'
    ),
    (
        3,   -- waste_request id 3 (e-waste, Whitefield IT Park)
        3,   -- Whitefield E-Waste Collection Hub
        'e-waste',
        3.00,
        'Whitefield IT Park',
        '2026-11-18 14:45:12',
        'ALLOCATED'
    );
