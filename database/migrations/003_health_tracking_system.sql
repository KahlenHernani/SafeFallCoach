-- =====================================================
-- FallRisk: Health Tracking System
-- Migration 003
-- Creates health statistics and medication tracking tables
-- =====================================================

-- =====================================================
-- HEALTH_STATS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS health_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Vital signs
    heart_rate INTEGER,
    blood_pressure_systolic INTEGER,
    blood_pressure_diastolic INTEGER,
    oxygen_saturation DECIMAL(5,2),
    temperature_celsius DECIMAL(4,2),
    
    -- Activity metrics
    steps_count INTEGER,
    distance_meters DECIMAL(10,2),
    active_minutes INTEGER,
    calories_burned INTEGER,
    
    -- Sleep data
    sleep_hours DECIMAL(4,2),
    sleep_quality TEXT CHECK (sleep_quality IN ('poor', 'fair', 'good', 'excellent')),
    
    -- Balance and mobility
    balance_score INTEGER CHECK (balance_score BETWEEN 0 AND 100),
    gait_speed_meters_per_second DECIMAL(4,2),
    
    -- Fall risk indicators
    dizziness_reported BOOLEAN DEFAULT FALSE,
    weakness_reported BOOLEAN DEFAULT FALSE,
    pain_level INTEGER CHECK (pain_level BETWEEN 0 AND 10),
    
    -- Medication adherence
    medications_taken BOOLEAN DEFAULT TRUE,
    missed_medication_count INTEGER DEFAULT 0,
    
    -- Notes and source
    notes TEXT,
    data_source TEXT,
    recorded_by_caregiver BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- HEALTH_ALERTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS health_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    health_stat_id UUID REFERENCES health_stats(id) ON DELETE SET NULL,
    
    alert_type TEXT NOT NULL,
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')) DEFAULT 'medium',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES profiles(id),
    
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- MEDICATION_SCHEDULE TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS medication_schedule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    medication_name TEXT NOT NULL,
    dosage TEXT NOT NULL,
    frequency TEXT NOT NULL,
    time_of_day TEXT[],
    
    start_date DATE NOT NULL,
    end_date DATE,
    
    is_active BOOLEAN DEFAULT TRUE,
    prescribing_doctor TEXT,
    purpose TEXT,
    side_effects TEXT[],
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- MEDICATION_LOG TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS medication_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medication_schedule_id UUID REFERENCES medication_schedule(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    scheduled_time TIMESTAMPTZ NOT NULL,
    taken_at TIMESTAMPTZ,
    status TEXT CHECK (status IN ('taken', 'missed', 'delayed', 'skipped')) DEFAULT 'taken',
    
    notes TEXT,
    logged_by_caregiver BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- HEALTH_TRENDS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS health_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_type TEXT CHECK (period_type IN ('weekly', 'monthly')) NOT NULL,
    
    -- Aggregated metrics
    avg_heart_rate DECIMAL(6,2),
    avg_blood_pressure_systolic DECIMAL(6,2),
    avg_blood_pressure_diastolic DECIMAL(6,2),
    avg_steps_per_day INTEGER,
    avg_sleep_hours DECIMAL(4,2),
    avg_balance_score DECIMAL(5,2),
    
    -- Fall statistics
    total_falls INTEGER DEFAULT 0,
    falls_with_injury INTEGER DEFAULT 0,
    
    -- Medication adherence
    medication_adherence_rate DECIMAL(5,2),
    
    -- Risk assessment
    fall_risk_trend TEXT CHECK (fall_risk_trend IN ('improving', 'stable', 'declining')),
    
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(user_id, period_start, period_type)
);

-- =====================================================
-- CREATE INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_health_stats_user_id ON health_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_health_stats_recorded_at ON health_stats(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_health_stats_user_date ON health_stats(user_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_health_alerts_user_id ON health_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_health_alerts_severity ON health_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_health_alerts_unacknowledged ON health_alerts(user_id, acknowledged) WHERE NOT acknowledged;

CREATE INDEX IF NOT EXISTS idx_medication_schedule_user_id ON medication_schedule(user_id);
CREATE INDEX IF NOT EXISTS idx_medication_schedule_active ON medication_schedule(user_id, is_active) WHERE is_active;

CREATE INDEX IF NOT EXISTS idx_medication_log_user_id ON medication_log(user_id);
CREATE INDEX IF NOT EXISTS idx_medication_log_schedule_id ON medication_log(medication_schedule_id);
CREATE INDEX IF NOT EXISTS idx_medication_log_status ON medication_log(user_id, status);

CREATE INDEX IF NOT EXISTS idx_health_trends_user_id ON health_trends(user_id);
CREATE INDEX IF NOT EXISTS idx_health_trends_period ON health_trends(user_id, period_start DESC);

-- =====================================================
-- ENABLE ROW LEVEL SECURITY
-- =====================================================
ALTER TABLE health_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE medication_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_trends ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- RLS POLICIES
-- =====================================================

-- HEALTH_STATS POLICIES
CREATE POLICY "Users can view own health stats" ON health_stats FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Users can insert own health stats" ON health_stats FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient health stats" ON health_stats FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can insert patient health stats" ON health_stats FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- HEALTH_ALERTS POLICIES
CREATE POLICY "Users can view own health alerts" ON health_alerts FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient health alerts" ON health_alerts FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can acknowledge alerts" ON health_alerts FOR UPDATE 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "System can insert health alerts" ON health_alerts FOR INSERT 
    WITH CHECK (true);

-- MEDICATION_SCHEDULE POLICIES
CREATE POLICY "Users can view own medication schedule" ON medication_schedule FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Users can manage own medication schedule" ON medication_schedule FOR ALL 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient medication schedule" ON medication_schedule FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can manage patient medication schedule" ON medication_schedule FOR ALL 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- MEDICATION_LOG POLICIES
CREATE POLICY "Users can view own medication log" ON medication_log FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Users can log own medications" ON medication_log FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient medication log" ON medication_log FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can log patient medications" ON medication_log FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- HEALTH_TRENDS POLICIES
CREATE POLICY "Users can view own health trends" ON health_trends FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient health trends" ON health_trends FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "System can insert health trends" ON health_trends FOR INSERT 
    WITH CHECK (true);

-- =====================================================
-- TRIGGER FOR AUTO-UPDATE TIMESTAMPS
-- =====================================================
DROP TRIGGER IF EXISTS set_updated_at ON medication_schedule;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON medication_schedule
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
