-- Part 1: Drop dangerous trigger with hardcoded service_role JWT
DROP TRIGGER IF EXISTS on_caregiver_invitation_created ON caregiver_invitations;
DROP FUNCTION IF EXISTS notify_patient_invitation();

-- Part 2: RPC function for patients to accept/decline caregiver invitations in-app.
-- Called from Flutter: supabase.rpc('accept_invitation', params: {'invitation_id': id})

CREATE OR REPLACE FUNCTION accept_invitation(invitation_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  inv RECORD;
  caller_email TEXT;
BEGIN
  -- Get the calling user's email
  SELECT email INTO caller_email
  FROM users
  WHERE user_id = auth.uid();

  IF caller_email IS NULL THEN
    RETURN jsonb_build_object('success', false, 'reason', 'not_authenticated');
  END IF;

  -- Find the invitation by ID
  SELECT * INTO inv
  FROM caregiver_invitations
  WHERE id = invitation_id
  FOR UPDATE;  -- lock the row to prevent race conditions

  IF NOT FOUND THEN
    RETURN jsonb_build_object('success', false, 'reason', 'not_found');
  END IF;

  -- Check it's meant for this user
  IF inv.invitee_email <> caller_email THEN
    RETURN jsonb_build_object('success', false, 'reason', 'wrong_user');
  END IF;

  -- Check it hasn't already been used
  IF inv.status <> 'pending' THEN
    RETURN jsonb_build_object('success', false, 'reason', 'already_' || inv.status);
  END IF;

  -- Check expiration
  IF inv.expires_at < NOW() THEN
    UPDATE caregiver_invitations SET status = 'expired' WHERE id = inv.id;
    RETURN jsonb_build_object('success', false, 'reason', 'expired');
  END IF;

  -- Accept the invitation
  UPDATE caregiver_invitations
  SET status = 'accepted',
      patient_user_id = auth.uid(),
      accepted_at = NOW()
  WHERE id = inv.id;

  RETURN jsonb_build_object(
    'success', true,
    'caregiver_name', (SELECT first_name || ' ' || last_name FROM users WHERE user_id = inv.invited_by)
  );
END;
$$;
