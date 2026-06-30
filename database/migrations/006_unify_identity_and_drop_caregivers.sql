-- =====================================================
-- FallRisk: Unify identity model
-- Migration 006
--
-- What this does:
--   1. users.user_id = Supabase auth UUID (was separate)
--   2. Adds role column to users (was only in auth metadata)
--   3. Drops caregivers table (redundant — caregiver is a user with role='caregiver')
--   4. Child tables keep caregiver_id column, re-pointed to users(user_id)
--   5. Caregiver-patient access uses caregiver_invitations (was broken)
--   6. Creates my_patient_ids() helper for DRY RLS policies
--
-- After this migration:
--   - Single identity: auth.uid() = users.user_id everywhere
--   - No _getCaregiverId() lookup needed
--   - Caregiver RLS policies actually work (were broken before)
--   - Flutter uses auth.currentUser!.id for all queries
-- =====================================================

BEGIN;

-- =====================================================
-- 1. Add role column to users, populate from auth metadata
--    (user_role_provider.dart already tries to query this)
-- =====================================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'user';

-- Drop any existing check constraint on role (may have been added manually or by prior migration)
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN ('user', 'caregiver', 'admin'));

UPDATE users u
SET role = COALESCE(
  (SELECT au.raw_user_meta_data->>'role' FROM auth.users au WHERE au.id = u.auth_user_id),
  'user'
);

-- =====================================================
-- 2. Unify users.user_id with auth UUID
--    Add ON UPDATE CASCADE to all FKs → update → remove CASCADE
-- =====================================================

CREATE TEMP TABLE _fk_to_users AS
SELECT
  tc.constraint_name,
  tc.table_name,
  kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema = kcu.table_schema
JOIN information_schema.referential_constraints rc
  ON tc.constraint_name = rc.constraint_name
  AND tc.table_schema = rc.constraint_schema
JOIN information_schema.key_column_usage ccu
  ON rc.unique_constraint_name = ccu.constraint_name
  AND ccu.table_schema = rc.unique_constraint_schema
WHERE ccu.table_name = 'users'
  AND ccu.column_name = 'user_id'
  AND tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public';

-- Add ON UPDATE CASCADE
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT * FROM _fk_to_users LOOP
    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.table_name, r.constraint_name);
    EXECUTE format(
      'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE CASCADE',
      r.table_name, r.constraint_name, r.column_name
    );
  END LOOP;
END $$;

-- The one update — CASCADE propagates to every child table
UPDATE users SET user_id = auth_user_id WHERE auth_user_id IS NOT NULL;

-- Remove ON UPDATE CASCADE (no longer needed)
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT * FROM _fk_to_users LOOP
    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.table_name, r.constraint_name);
    EXECUTE format(
      'ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES users(user_id) ON DELETE CASCADE',
      r.table_name, r.constraint_name, r.column_name
    );
  END LOOP;
END $$;

DROP TABLE _fk_to_users;

-- =====================================================
-- 3. Drop caregivers table
--    a) Drop FKs from child tables to caregivers
--    b) Map caregiver_id values: old UUID → caregiver's auth UUID (= user_id)
--    c) Drop the table
--    d) Re-add FKs pointing to users(user_id)
-- =====================================================

-- 3a. Drop all FK constraints that reference caregivers
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT con.conname, src.relname AS table_name
    FROM pg_constraint con
    JOIN pg_class src ON con.conrelid = src.oid
    JOIN pg_class tgt ON con.confrelid = tgt.oid
    JOIN pg_namespace ns ON src.relnamespace = ns.oid
    WHERE tgt.relname = 'caregivers'
      AND con.contype = 'f'
      AND ns.nspname = 'public'
  LOOP
    EXECUTE format('ALTER TABLE %I DROP CONSTRAINT %I', r.table_name, r.conname);
  END LOOP;
END $$;

-- 3b. Map caregiver_id → auth UUID (which now = users.user_id after step 2)
UPDATE caregiver_notes cn
SET caregiver_id = c.auth_user_id
FROM caregivers c
WHERE cn.caregiver_id = c.caregiver_id;

UPDATE caregiver_shifts cs
SET caregiver_id = c.auth_user_id
FROM caregivers c
WHERE cs.caregiver_id = c.caregiver_id;

UPDATE caregiver_tasks ct
SET assigned_to_caregiver_id = c.auth_user_id
FROM caregivers c
WHERE ct.assigned_to_caregiver_id = c.caregiver_id;

UPDATE audit_log al
SET caregiver_id = c.auth_user_id
FROM caregivers c
WHERE al.caregiver_id = c.caregiver_id;

-- 3c. Drop ALL RLS policies on all affected tables
--     (nuclear approach — avoids name mismatch between migration files and actual DB)
DO $$
DECLARE pol RECORD;
BEGIN
  FOR pol IN
    SELECT policyname, tablename
    FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename IN (
      'users', 'caregivers', 'falls', 'tutorial_progress', 'notifications',
      'audit_log', 'health_stats', 'health_alerts', 'medication_schedule',
      'medication_log', 'health_trends', 'emergency_contacts',
      'caregiver_invitations', 'caregiver_shifts', 'caregiver_notes',
      'caregiver_tasks', 'caregiver_messages', 'ems_calls', 'ems_contacts',
      'bookmarked_videos', 'video_progress', 'downloaded_videos',
      'notification_preferences'
    )
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', pol.policyname, pol.tablename);
  END LOOP;
END $$;

-- Drop link_patient_to_caregiver() if it exists (may reference caregivers table)
DROP FUNCTION IF EXISTS public.link_patient_to_caregiver() CASCADE;

-- 3d. Drop the table
DROP TABLE caregivers CASCADE;

-- 3e. Re-add FK constraints: child tables → users(user_id)
ALTER TABLE caregiver_notes
  ADD CONSTRAINT caregiver_notes_caregiver_id_fkey
  FOREIGN KEY (caregiver_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE caregiver_shifts
  ADD CONSTRAINT caregiver_shifts_caregiver_id_fkey
  FOREIGN KEY (caregiver_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE caregiver_tasks
  ADD CONSTRAINT caregiver_tasks_assigned_to_caregiver_id_fkey
  FOREIGN KEY (assigned_to_caregiver_id) REFERENCES users(user_id) ON DELETE SET NULL;

ALTER TABLE audit_log
  ADD CONSTRAINT audit_log_caregiver_id_fkey
  FOREIGN KEY (caregiver_id) REFERENCES users(user_id) ON DELETE SET NULL;

-- =====================================================
-- 4. Drop auth_user_id from users (redundant — user_id IS the auth UUID now)
-- =====================================================

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_auth_user_id_unique;
DROP INDEX IF EXISTS idx_users_auth_user_id;
ALTER TABLE users DROP COLUMN auth_user_id;

-- =====================================================
-- 5. Helper function for caregiver RLS policies
--    Returns patient user_ids for the current caregiver.
--    Used in policies: user_id IN (SELECT my_patient_ids())
-- =====================================================

CREATE OR REPLACE FUNCTION public.my_patient_ids()
RETURNS SETOF UUID
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT patient_user_id
  FROM caregiver_invitations
  WHERE invited_by = auth.uid()
    AND status = 'accepted'
    AND patient_user_id IS NOT NULL;
$$;

COMMENT ON FUNCTION public.my_patient_ids() IS
  'Returns patient user_ids linked to the current caregiver via accepted invitations. Used in RLS policies.';

-- =====================================================
-- 6. Recreate ALL RLS policies
-- =====================================================

-- ── USERS ──
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Users can insert own data" ON users
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can delete own data" ON users
  FOR DELETE USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient data" ON users
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));

-- ── FALLS ──
CREATE POLICY "Users can view own falls" ON falls
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own falls" ON falls
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient falls" ON falls
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));

-- ── TUTORIAL_PROGRESS ──
CREATE POLICY "Users can view own progress" ON tutorial_progress
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can manage own progress" ON tutorial_progress
  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient progress" ON tutorial_progress
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));

-- ── NOTIFICATIONS ──
CREATE POLICY "Users can view own notifications" ON notifications
  FOR SELECT USING (recipient_user_id = auth.uid());
CREATE POLICY "Users can update own notifications" ON notifications
  FOR UPDATE USING (recipient_user_id = auth.uid());
CREATE POLICY "System can insert notifications" ON notifications
  FOR INSERT WITH CHECK (true);

-- ── AUDIT_LOG ──
CREATE POLICY "Patients can view their audit logs" ON audit_log
  FOR SELECT USING (patient_user_id = auth.uid());
CREATE POLICY "Caregivers can view own audit logs" ON audit_log
  FOR SELECT USING (caregiver_id = auth.uid());
CREATE POLICY "System can insert audit logs" ON audit_log
  FOR INSERT WITH CHECK (true);

-- ── HEALTH_STATS ──
CREATE POLICY "Users can view own health stats" ON health_stats
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own health stats" ON health_stats
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient health stats" ON health_stats
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Caregivers can insert patient health stats" ON health_stats
  FOR INSERT WITH CHECK (user_id IN (SELECT my_patient_ids()));

-- ── HEALTH_ALERTS ──
CREATE POLICY "Users can view own health alerts" ON health_alerts
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient health alerts" ON health_alerts
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Caregivers can acknowledge alerts" ON health_alerts
  FOR UPDATE USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "System can insert health alerts" ON health_alerts
  FOR INSERT WITH CHECK (true);

-- ── MEDICATION_SCHEDULE ──
CREATE POLICY "Users can view own medication schedule" ON medication_schedule
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can manage own medication schedule" ON medication_schedule
  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient medication schedule" ON medication_schedule
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Caregivers can manage patient medication schedule" ON medication_schedule
  FOR ALL USING (user_id IN (SELECT my_patient_ids()));

-- ── MEDICATION_LOG ──
CREATE POLICY "Users can view own medication log" ON medication_log
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can log own medications" ON medication_log
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient medication log" ON medication_log
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Caregivers can log patient medications" ON medication_log
  FOR INSERT WITH CHECK (user_id IN (SELECT my_patient_ids()));

-- ── HEALTH_TRENDS ──
CREATE POLICY "Users can view own health trends" ON health_trends
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient health trends" ON health_trends
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "System can insert health trends" ON health_trends
  FOR INSERT WITH CHECK (true);

-- ── EMERGENCY_CONTACTS ──
CREATE POLICY "Users can manage own emergency contacts" ON emergency_contacts
  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient emergency contacts" ON emergency_contacts
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));

-- ── CAREGIVER_INVITATIONS ──
CREATE POLICY "Patients can manage invitations" ON caregiver_invitations
  FOR ALL USING (patient_user_id = auth.uid());
CREATE POLICY "Caregivers can manage own invitations" ON caregiver_invitations
  FOR ALL USING (invited_by = auth.uid());
CREATE POLICY "Invitees can view own invitations" ON caregiver_invitations
  FOR SELECT USING (invitee_email IN (SELECT email FROM users WHERE user_id = auth.uid()));
CREATE POLICY "Invitees can accept invitations" ON caregiver_invitations
  FOR UPDATE USING (invitee_email IN (SELECT email FROM users WHERE user_id = auth.uid()));

-- ── CAREGIVER_SHIFTS ──
CREATE POLICY "Caregivers can view own shifts" ON caregiver_shifts
  FOR SELECT USING (caregiver_id = auth.uid());
CREATE POLICY "Patients can view caregiver shifts" ON caregiver_shifts
  FOR SELECT USING (patient_user_id = auth.uid());
CREATE POLICY "Caregivers can manage own shifts" ON caregiver_shifts
  FOR ALL USING (caregiver_id = auth.uid());

-- ── CAREGIVER_NOTES ──
CREATE POLICY "Caregivers can manage own notes" ON caregiver_notes
  FOR ALL USING (caregiver_id = auth.uid());
CREATE POLICY "Caregivers can view patient notes" ON caregiver_notes
  FOR SELECT USING (patient_user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Patients can view notes about them" ON caregiver_notes
  FOR SELECT USING (patient_user_id = auth.uid());

-- ── CAREGIVER_TASKS ──
CREATE POLICY "Patients can view own tasks" ON caregiver_tasks
  FOR SELECT USING (patient_user_id = auth.uid());
CREATE POLICY "Caregivers can view assigned tasks" ON caregiver_tasks
  FOR SELECT USING (
    assigned_to_caregiver_id = auth.uid()
    OR patient_user_id IN (SELECT my_patient_ids())
  );
CREATE POLICY "Caregivers can manage patient tasks" ON caregiver_tasks
  FOR ALL USING (patient_user_id IN (SELECT my_patient_ids()));

-- ── CAREGIVER_MESSAGES ──
CREATE POLICY "Users can view own messages" ON caregiver_messages
  FOR SELECT USING (sender_id = auth.uid() OR recipient_id = auth.uid());
CREATE POLICY "Users can send messages" ON caregiver_messages
  FOR INSERT WITH CHECK (sender_id = auth.uid());
CREATE POLICY "Users can update received messages" ON caregiver_messages
  FOR UPDATE USING (recipient_id = auth.uid());

-- ── EMS_CALLS ──
CREATE POLICY "Users can view own ems calls" ON ems_calls
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can create ems calls" ON ems_calls
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient ems calls" ON ems_calls
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "Caregivers can create ems calls for patients" ON ems_calls
  FOR INSERT WITH CHECK (user_id IN (SELECT my_patient_ids()));
CREATE POLICY "System can update ems calls" ON ems_calls
  FOR UPDATE USING (true);

-- ── EMS_CONTACTS ──
CREATE POLICY "Users can manage own ems contacts" ON ems_contacts
  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "Caregivers can view patient ems contacts" ON ems_contacts
  FOR SELECT USING (user_id IN (SELECT my_patient_ids()));

-- ── BOOKMARKED_VIDEOS ──
CREATE POLICY "Users can view own bookmarks" ON bookmarked_videos
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own bookmarks" ON bookmarked_videos
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can delete own bookmarks" ON bookmarked_videos
  FOR DELETE USING (user_id = auth.uid());

-- ── VIDEO_PROGRESS ──
CREATE POLICY "Users can view own progress" ON video_progress
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own progress" ON video_progress
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can update own progress" ON video_progress
  FOR UPDATE USING (user_id = auth.uid());
CREATE POLICY "Users can delete own progress" ON video_progress
  FOR DELETE USING (user_id = auth.uid());

-- ── DOWNLOADED_VIDEOS ──
CREATE POLICY "Users can view own downloads" ON downloaded_videos
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own downloads" ON downloaded_videos
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can delete own downloads" ON downloaded_videos
  FOR DELETE USING (user_id = auth.uid());

-- ── NOTIFICATION_PREFERENCES ──
CREATE POLICY "Users can view own preferences" ON notification_preferences
  FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users can insert own preferences" ON notification_preferences
  FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY "Users can update own preferences" ON notification_preferences
  FOR UPDATE USING (user_id = auth.uid());

-- =====================================================
-- 7. Update handle_new_user() trigger
--    No more caregivers insert — just users with role
-- =====================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.users (user_id, email, first_name, last_name, role)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'first_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'last_name', ''),
        COALESCE(NEW.raw_user_meta_data->>'role', 'user')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

COMMIT;
