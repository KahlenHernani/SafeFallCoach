-- =====================================================
-- FallRisk: Caregiver and EMS System
-- Migration 004
-- Creates caregiver management and emergency services tables
-- =====================================================

-- =====================================================
-- EMERGENCY_CONTACTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS emergency_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    contact_name TEXT NOT NULL,
    relationship TEXT,
    phone_number TEXT NOT NULL,
    alternate_phone TEXT,
    email TEXT,
    
    is_primary BOOLEAN DEFAULT FALSE,
    priority_order INTEGER DEFAULT 1,
    
    can_access_medical_info BOOLEAN DEFAULT FALSE,
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CAREGIVER_INVITATIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregiver_invitations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    invitee_email TEXT NOT NULL,
    invitee_name TEXT,
    relationship TEXT,
    access_level TEXT CHECK (access_level IN ('view_only', 'full_access')) DEFAULT 'view_only',
    
    invitation_token TEXT UNIQUE NOT NULL,
    status TEXT CHECK (status IN ('pending', 'accepted', 'declined', 'expired')) DEFAULT 'pending',
    
    invited_by UUID REFERENCES profiles(id),
    invited_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days'),
    
    accepted_at TIMESTAMPTZ,
    declined_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CAREGIVER_SHIFTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregiver_shifts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    caregiver_id UUID REFERENCES caregivers(caregiver_id) ON DELETE CASCADE,
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    shift_start TIMESTAMPTZ NOT NULL,
    shift_end TIMESTAMPTZ NOT NULL,
    
    shift_type TEXT,
    is_recurring BOOLEAN DEFAULT FALSE,
    recurrence_pattern TEXT,
    
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CAREGIVER_NOTES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregiver_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    caregiver_id UUID REFERENCES caregivers(caregiver_id) ON DELETE CASCADE,
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    note_type TEXT CHECK (note_type IN ('observation', 'incident', 'medication', 'care_plan', 'general')),
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    
    related_fall_id UUID REFERENCES falls(fall_id),
    related_health_stat_id UUID REFERENCES health_stats(id),
    
    is_urgent BOOLEAN DEFAULT FALSE,
    flagged_for_review BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- EMS_CALLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS ems_calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    fall_id UUID REFERENCES falls(fall_id) ON DELETE SET NULL,
    
    call_initiated_at TIMESTAMPTZ DEFAULT NOW(),
    call_initiated_by TEXT,
    initiated_by_user_id UUID REFERENCES profiles(id),
    
    call_type TEXT CHECK (call_type IN ('fall_emergency', 'medical_emergency', 'false_alarm', 'cancelled')),
    emergency_level TEXT CHECK (emergency_level IN ('critical', 'urgent', 'non_urgent')) DEFAULT 'urgent',
    
    location_details TEXT,
    symptoms_reported TEXT[],
    injuries_reported TEXT[],
    patient_conscious BOOLEAN,
    patient_breathing BOOLEAN,
    
    ems_dispatched BOOLEAN DEFAULT FALSE,
    dispatch_time TIMESTAMPTZ,
    ems_arrival_time TIMESTAMPTZ,
    ems_incident_number TEXT,
    
    transported_to_hospital BOOLEAN DEFAULT FALSE,
    hospital_name TEXT,
    outcome_notes TEXT,
    
    call_cancelled BOOLEAN DEFAULT FALSE,
    cancellation_reason TEXT,
    cancelled_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- EMS_CONTACTS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS ems_contacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    service_type TEXT CHECK (service_type IN ('911', 'local_ems', 'fire_department', 'hospital', 'urgent_care', 'poison_control')) NOT NULL,
    service_name TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    address TEXT,
    
    is_preferred BOOLEAN DEFAULT FALSE,
    distance_miles DECIMAL(5,2),
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CAREGIVER_TASKS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregiver_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    assigned_to_caregiver_id UUID REFERENCES caregivers(caregiver_id) ON DELETE SET NULL,
    created_by UUID REFERENCES profiles(id),
    
    task_type TEXT CHECK (task_type IN ('medication_reminder', 'health_check', 'exercise_session', 'tutorial_followup', 'home_safety_check', 'general')),
    title TEXT NOT NULL,
    description TEXT,
    
    priority TEXT CHECK (priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
    status TEXT CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
    
    due_date DATE,
    due_time TIME,
    
    completed_at TIMESTAMPTZ,
    completion_notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CAREGIVER_MESSAGES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS caregiver_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    sender_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    recipient_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    
    subject TEXT,
    message_body TEXT NOT NULL,
    
    is_urgent BOOLEAN DEFAULT FALSE,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMPTZ,
    
    parent_message_id UUID REFERENCES caregiver_messages(id),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =====================================================
-- CREATE INDEXES
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_emergency_contacts_user_id ON emergency_contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_emergency_contacts_primary ON emergency_contacts(user_id, is_primary) WHERE is_primary = TRUE;

CREATE INDEX IF NOT EXISTS idx_caregiver_invitations_email ON caregiver_invitations(invitee_email);
CREATE INDEX IF NOT EXISTS idx_caregiver_invitations_token ON caregiver_invitations(invitation_token);
CREATE INDEX IF NOT EXISTS idx_caregiver_invitations_status ON caregiver_invitations(status, patient_user_id);

CREATE INDEX IF NOT EXISTS idx_caregiver_shifts_caregiver ON caregiver_shifts(caregiver_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_shifts_patient ON caregiver_shifts(patient_user_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_shifts_times ON caregiver_shifts(shift_start, shift_end);

CREATE INDEX IF NOT EXISTS idx_caregiver_notes_caregiver ON caregiver_notes(caregiver_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_notes_patient ON caregiver_notes(patient_user_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_notes_urgent ON caregiver_notes(patient_user_id, is_urgent) WHERE is_urgent = TRUE;

CREATE INDEX IF NOT EXISTS idx_ems_calls_user_id ON ems_calls(user_id);
CREATE INDEX IF NOT EXISTS idx_ems_calls_fall_id ON ems_calls(fall_id);
CREATE INDEX IF NOT EXISTS idx_ems_calls_initiated_at ON ems_calls(call_initiated_at DESC);

CREATE INDEX IF NOT EXISTS idx_ems_contacts_user_id ON ems_contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_ems_contacts_preferred ON ems_contacts(user_id, is_preferred) WHERE is_preferred = TRUE;

CREATE INDEX IF NOT EXISTS idx_caregiver_tasks_patient ON caregiver_tasks(patient_user_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_tasks_assigned ON caregiver_tasks(assigned_to_caregiver_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_tasks_status ON caregiver_tasks(status, patient_user_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_tasks_due ON caregiver_tasks(due_date, status) WHERE status != 'completed';

CREATE INDEX IF NOT EXISTS idx_caregiver_messages_sender ON caregiver_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_messages_recipient ON caregiver_messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_caregiver_messages_unread ON caregiver_messages(recipient_id, is_read) WHERE is_read = FALSE;

-- =====================================================
-- ENABLE ROW LEVEL SECURITY
-- =====================================================
ALTER TABLE emergency_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE ems_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE ems_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE caregiver_messages ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- RLS POLICIES
-- =====================================================

-- EMERGENCY_CONTACTS POLICIES
CREATE POLICY "Users can manage own emergency contacts" ON emergency_contacts FOR ALL 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient emergency contacts" ON emergency_contacts FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- CAREGIVER_INVITATIONS POLICIES
CREATE POLICY "Patients can manage invitations" ON caregiver_invitations FOR ALL 
    USING (
        patient_user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Invitees can view own invitations" ON caregiver_invitations FOR SELECT 
    USING (
        invitee_email IN (SELECT email FROM profiles WHERE id = auth.uid())
    );

CREATE POLICY "Invitees can accept invitations" ON caregiver_invitations FOR UPDATE 
    USING (
        invitee_email IN (SELECT email FROM profiles WHERE id = auth.uid())
    );

-- CAREGIVER_SHIFTS POLICIES
CREATE POLICY "Caregivers can view own shifts" ON caregiver_shifts FOR SELECT 
    USING (
        caregiver_id IN (SELECT caregiver_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Patients can view caregiver shifts" ON caregiver_shifts FOR SELECT 
    USING (
        patient_user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can manage own shifts" ON caregiver_shifts FOR ALL 
    USING (
        caregiver_id IN (SELECT caregiver_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- CAREGIVER_NOTES POLICIES
CREATE POLICY "Caregivers can manage own notes" ON caregiver_notes FOR ALL 
    USING (
        caregiver_id IN (SELECT caregiver_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Patients can view notes about them" ON caregiver_notes FOR SELECT 
    USING (
        patient_user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Other caregivers can view patient notes" ON caregiver_notes FOR SELECT 
    USING (
        patient_user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- EMS_CALLS POLICIES
CREATE POLICY "Users can view own ems calls" ON ems_calls FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Users can create ems calls" ON ems_calls FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient ems calls" ON ems_calls FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can create ems calls for patients" ON ems_calls FOR INSERT 
    WITH CHECK (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "System can update ems calls" ON ems_calls FOR UPDATE 
    USING (true);

-- EMS_CONTACTS POLICIES
CREATE POLICY "Users can manage own ems contacts" ON ems_contacts FOR ALL 
    USING (
        user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view patient ems contacts" ON ems_contacts FOR SELECT 
    USING (
        user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- CAREGIVER_TASKS POLICIES
CREATE POLICY "Patients can view own tasks" ON caregiver_tasks FOR SELECT 
    USING (
        patient_user_id IN (SELECT user_id FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can view assigned tasks" ON caregiver_tasks FOR SELECT 
    USING (
        assigned_to_caregiver_id IN (SELECT caregiver_id FROM caregivers WHERE auth_user_id = auth.uid())
        OR patient_user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Caregivers can manage tasks" ON caregiver_tasks FOR ALL 
    USING (
        patient_user_id IN (SELECT user_id FROM caregivers WHERE auth_user_id = auth.uid())
    );

-- CAREGIVER_MESSAGES POLICIES
CREATE POLICY "Users can view own messages" ON caregiver_messages FOR SELECT 
    USING (sender_id = auth.uid() OR recipient_id = auth.uid());

CREATE POLICY "Users can send messages" ON caregiver_messages FOR INSERT 
    WITH CHECK (sender_id = auth.uid());

CREATE POLICY "Users can update own received messages" ON caregiver_messages FOR UPDATE 
    USING (recipient_id = auth.uid());

-- =====================================================
-- TRIGGER FUNCTIONS
-- =====================================================

DROP TRIGGER IF EXISTS set_updated_at ON emergency_contacts;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON emergency_contacts
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON caregiver_shifts;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON caregiver_shifts
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON caregiver_notes;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON caregiver_notes
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON ems_calls;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON ems_calls
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON ems_contacts;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON ems_contacts
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

DROP TRIGGER IF EXISTS set_updated_at ON caregiver_tasks;
CREATE TRIGGER set_updated_at
    BEFORE UPDATE ON caregiver_tasks
    FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Function to generate invitation tokens
CREATE OR REPLACE FUNCTION generate_invitation_token()
RETURNS TEXT AS $$
BEGIN
    RETURN encode(gen_random_bytes(32), 'base64');
END;
$$ LANGUAGE plpgsql;

-- Trigger to generate invitation token on insert
CREATE OR REPLACE FUNCTION set_invitation_token()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.invitation_token IS NULL THEN
        NEW.invitation_token := generate_invitation_token();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_invitation_token ON caregiver_invitations;
CREATE TRIGGER set_invitation_token
    BEFORE INSERT ON caregiver_invitations
    FOR EACH ROW EXECUTE FUNCTION set_invitation_token();
