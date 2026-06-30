-- =====================================================
-- FallRisk: Initial Database Schema
-- Migration 001
-- Creates core tables: users, falls, tutorial_progress, caregivers
-- =====================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- USERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    date_of_birth DATE,
    risk_level TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- FALLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS falls (
    fall_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    location TEXT,
    severity TEXT,
    camera_id TEXT,
    notes TEXT
);

-- =====================================================
-- TUTORIAL_PROGRESS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS tutorial_progress (
    progress_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    tutorial_name TEXT NOT NULL,
    completed BOOLEAN DEFAULT FALSE,
    completion_date TIMESTAMPTZ
);

-- =====================================================
-- CAREGIVERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregivers (
    caregiver_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- CREATE INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_falls_user_id ON falls(user_id);
CREATE INDEX IF NOT EXISTS idx_falls_timestamp ON falls(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tutorial_progress_user_id ON tutorial_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_caregivers_user_id ON caregivers(user_id);

-- =====================================================
-- ENABLE ROW LEVEL SECURITY
-- =====================================================
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE falls ENABLE ROW LEVEL SECURITY;
ALTER TABLE tutorial_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregivers ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- INITIAL RLS POLICIES (Basic - will be updated in migration 002)
-- =====================================================
CREATE POLICY "Users can view own data" ON users FOR SELECT USING (true);
CREATE POLICY "Users can view own falls" ON falls FOR SELECT USING (true);
CREATE POLICY "Users can view own progress" ON tutorial_progress FOR SELECT USING (true);
CREATE POLICY "Caregivers can view relationships" ON caregivers FOR SELECT USING (true);
