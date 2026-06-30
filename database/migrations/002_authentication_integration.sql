-- =====================================================
-- FallRisk: Authentication Integration
-- Migration 002
-- Integrates Supabase Auth with application tables
-- =====================================================

-- =====================================================
-- ADD auth_user_id to users table
-- =====================================================
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS auth_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'users_auth_user_id_unique'
    ) THEN
        ALTER TABLE users ADD CONSTRAINT users_auth_user_id_unique UNIQUE (auth_user_id);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_auth_user_id ON users(auth_user_id);

-- =====================================================
-- ADD auth_user_id to caregivers table
-- =====================================================
ALTER TABLE caregivers 
ADD COLUMN IF NOT EXISTS auth_user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_caregivers_auth_user_id ON caregivers(auth_user_id);

-- =====================================================
-- CREATE profiles table
-- =====================================================
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    phone_number TEXT,
    profile_picture_url TEXT,
    account_type TEXT CHECK (account_type IN ('user', 'caregiver', 'admin')) DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- CREATE notifications table
-- =====================================================
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_fall_id UUID REFERENCES falls(fall_id) ON DELETE CASCADE,
    is_read BOOLEAN DEFAULT FALSE,
    is_dismissed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_user_id);
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- CREATE audit_log table
-- =====================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    caregiver_id UUID REFERENCES caregivers(caregiver_id) ON DELETE SET NULL,
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    resource_type TEXT,
    resource_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_caregiver ON audit_log(caregiver_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_patient ON audit_log(patient_user_id);
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- UPDATE RLS POLICIES
-- =====================================================

-- Drop old basic policies
DROP POLICY IF EXISTS "Users can view own data" ON users;
DROP POLICY IF EXISTS "Users can view own falls" ON falls;
DROP POLICY IF EXISTS "Users can view own progress" ON tutorial_progress;
DROP POLICY IF EXISTS "Caregivers can view relationships" ON caregivers;

-- PROFILES POLICIES
CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can insert own profile" ON profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- USERS POLICIES
CREATE POLICY "Users can view own user data" ON users FOR SELECT 
    USING (auth_user_id = auth.uid());

CREATE POLICY "Users can update own user data" ON users FOR UPDATE 
    USING (auth_user_id = auth.uid());

CREATE POLICY "Users can insert own user data" ON users FOR INSERT 
    WITH CHECK (auth_user_id = auth.uid());

CREATE POLICY "Caregivers can view patient data" ON users FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM caregivers
            WHERE auth_user_id = auth.uid()
        )
    );

-- CAREGIVERS POLICIES
CREATE POLICY "Caregivers can view own relationships" ON caregivers FOR SELECT 
    USING (auth_user_id = auth.uid());

CREATE POLICY "Patients can view their caregivers" ON caregivers FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Caregivers can insert relationships" ON caregivers FOR INSERT 
    WITH CHECK (auth_user_id = auth.uid());

-- FALLS POLICIES
CREATE POLICY "Users can view own falls" ON falls FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert own falls" ON falls FOR INSERT 
    WITH CHECK (
        user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Caregivers can view patient falls" ON falls FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid()
        )
    );

-- TUTORIAL_PROGRESS POLICIES
CREATE POLICY "Users can view own progress" ON tutorial_progress FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own progress" ON tutorial_progress FOR ALL 
    USING (
        user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Caregivers can view patient progress" ON tutorial_progress FOR SELECT 
    USING (
        user_id IN (
            SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid()
        )
    );

-- NOTIFICATIONS POLICIES
CREATE POLICY "Users can view own notifications" ON notifications FOR SELECT 
    USING (
        recipient_user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own notifications" ON notifications FOR UPDATE 
    USING (
        recipient_user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "System can insert notifications" ON notifications FOR INSERT 
    WITH CHECK (true);

-- AUDIT_LOG POLICIES
CREATE POLICY "Caregivers can view own audit logs" ON audit_log FOR SELECT 
    USING (
        caregiver_id IN (
            SELECT caregiver_id FROM caregivers WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "Patients can view their audit logs" ON audit_log FOR SELECT 
    USING (
        patient_user_id IN (
            SELECT user_id FROM users WHERE auth_user_id = auth.uid()
        )
    );

CREATE POLICY "System can insert audit logs" ON audit_log FOR INSERT 
    WITH CHECK (true);

-- =====================================================
-- CREATE TRIGGER FUNCTIONS
-- =====================================================

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, account_type)
    VALUES (NEW.id, NEW.email, 'user');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at ON profiles;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();
