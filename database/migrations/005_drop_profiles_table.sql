-- =====================================================
-- FallRisk: Drop Profiles Table
-- Migration 005
-- Removes the profiles table (redundant with users table)
-- Re-points all foreign keys from profiles(id) to auth.users(id)
-- Updates handle_new_user() trigger to create users row instead
-- =====================================================

-- =====================================================
-- 1. DROP RLS POLICIES that reference profiles
-- =====================================================

-- From 002: profiles table policies
DROP POLICY IF EXISTS "Users can view own profile" ON profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON profiles;

-- From 004: caregiver_invitations policies that query profiles
DROP POLICY IF EXISTS "Invitees can view own invitations" ON caregiver_invitations;
DROP POLICY IF EXISTS "Invitees can accept invitations" ON caregiver_invitations;

-- =====================================================
-- 2. DROP TRIGGERS on profiles
-- =====================================================
DROP TRIGGER IF EXISTS set_updated_at ON profiles;

-- =====================================================
-- 3. RE-POINT FOREIGN KEYS from profiles(id) to auth.users(id)
-- =====================================================

-- 003: health_alerts.acknowledged_by
ALTER TABLE health_alerts DROP CONSTRAINT IF EXISTS health_alerts_acknowledged_by_fkey;
ALTER TABLE health_alerts
    ADD CONSTRAINT health_alerts_acknowledged_by_fkey
    FOREIGN KEY (acknowledged_by) REFERENCES auth.users(id);

-- 004: caregiver_invitations.invited_by
ALTER TABLE caregiver_invitations DROP CONSTRAINT IF EXISTS caregiver_invitations_invited_by_fkey;
ALTER TABLE caregiver_invitations
    ADD CONSTRAINT caregiver_invitations_invited_by_fkey
    FOREIGN KEY (invited_by) REFERENCES auth.users(id);

-- 004: ems_calls.initiated_by_user_id
ALTER TABLE ems_calls DROP CONSTRAINT IF EXISTS ems_calls_initiated_by_user_id_fkey;
ALTER TABLE ems_calls
    ADD CONSTRAINT ems_calls_initiated_by_user_id_fkey
    FOREIGN KEY (initiated_by_user_id) REFERENCES auth.users(id);

-- 004: caregiver_tasks.created_by
ALTER TABLE caregiver_tasks DROP CONSTRAINT IF EXISTS caregiver_tasks_created_by_fkey;
ALTER TABLE caregiver_tasks
    ADD CONSTRAINT caregiver_tasks_created_by_fkey
    FOREIGN KEY (created_by) REFERENCES auth.users(id);

-- 004: caregiver_messages.sender_id
ALTER TABLE caregiver_messages DROP CONSTRAINT IF EXISTS caregiver_messages_sender_id_fkey;
ALTER TABLE caregiver_messages
    ADD CONSTRAINT caregiver_messages_sender_id_fkey
    FOREIGN KEY (sender_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- 004: caregiver_messages.recipient_id
ALTER TABLE caregiver_messages DROP CONSTRAINT IF EXISTS caregiver_messages_recipient_id_fkey;
ALTER TABLE caregiver_messages
    ADD CONSTRAINT caregiver_messages_recipient_id_fkey
    FOREIGN KEY (recipient_id) REFERENCES auth.users(id) ON DELETE CASCADE;

-- =====================================================
-- 4. RECREATE RLS POLICIES that queried profiles
-- =====================================================

-- caregiver_invitations: use users.email instead of profiles.email
CREATE POLICY "Invitees can view own invitations" ON caregiver_invitations FOR SELECT
    USING (
        invitee_email IN (SELECT email FROM users WHERE auth_user_id = auth.uid())
    );

CREATE POLICY "Invitees can accept invitations" ON caregiver_invitations FOR UPDATE
    USING (
        invitee_email IN (SELECT email FROM users WHERE auth_user_id = auth.uid())
    );

-- =====================================================
-- 5. UPDATE handle_new_user() TRIGGER
-- =====================================================

-- Replace the old trigger that inserted into profiles
-- with one that creates a users row + optional caregivers row
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (auth_user_id, email, first_name, last_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'last_name', '')
    );

    -- If role is caregiver, also create a caregivers row
    IF COALESCE(NEW.raw_user_meta_data->>'role', 'user') = 'caregiver' THEN
        INSERT INTO public.caregivers (auth_user_id, first_name, last_name, email, user_id)
        VALUES (
            NEW.id,
            COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
            COALESCE(NEW.raw_user_meta_data->>'last_name', ''),
            NEW.email,
            (SELECT user_id FROM public.users WHERE auth_user_id = NEW.id)
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger already exists on auth.users from 002, just re-create to be safe
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- =====================================================
-- 6. DROP THE PROFILES TABLE
-- =====================================================
DROP TABLE IF EXISTS profiles CASCADE;
