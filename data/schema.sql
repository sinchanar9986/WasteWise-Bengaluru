-- ============================================================
-- Waste Wise Bengaluru — Database Schema
-- MySQL 8.x compatible
-- ============================================================

CREATE DATABASE IF NOT EXISTS wastewise;
USE wastewise;

-- --------------------------------------------------------
-- Table: facilities
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS facilities (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    name                    VARCHAR(100)                    NOT NULL,
    accepted_materials      VARCHAR(255)                    NOT NULL,  -- comma-separated e.g. "organic,wet"
    total_capacity_tons     DECIMAL(10,2)                   NOT NULL,
    used_capacity_tons      DECIMAL(10,2)                   NOT NULL DEFAULT 0,
    remaining_capacity_tons DECIMAL(10,2)                   NOT NULL,  -- stored; updated on each allocation
    status                  ENUM('OPEN','CLOSED')           NOT NULL DEFAULT 'OPEN',
    zone                    VARCHAR(100)                    NOT NULL,
    data_label              VARCHAR(50)                     NOT NULL DEFAULT 'SIMULATED'
);

-- --------------------------------------------------------
-- Table: waste_requests
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS waste_requests (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    raw_input       TEXT,
    waste_type      VARCHAR(50)                     NOT NULL,
    quantity_tons   DECIMAL(10,2)                   NOT NULL,
    origin          VARCHAR(100)                    NOT NULL,
    created_at      TIMESTAMP                       DEFAULT CURRENT_TIMESTAMP
);

-- --------------------------------------------------------
-- Table: allocations
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS allocations (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    request_id      INT,
    facility_id     INT                             DEFAULT NULL,  -- NULL for UNALLOCATED records
    waste_type      VARCHAR(50)                     NOT NULL,
    quantity_tons   DECIMAL(10,2)                   NOT NULL,
    origin          VARCHAR(100)                    NOT NULL,
    allocated_at    TIMESTAMP                       DEFAULT CURRENT_TIMESTAMP,
    status          ENUM('ALLOCATED','UNALLOCATED','REALLOCATED') NOT NULL DEFAULT 'ALLOCATED'
);
