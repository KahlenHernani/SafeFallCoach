-- Migration 008: Create delete_own_account RPC
-- Deletes the calling user's public.users row (CASCADE handles child rows)
-- then deletes the auth.users row, all in one transaction.
-- user_id = auth UUID (migration 006), but no FK between the tables,
-- so both deletes are needed explicitly.

CREATE OR REPLACE FUNCTION public.delete_own_account()
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  DELETE FROM public.users WHERE user_id = auth.uid();
  DELETE FROM auth.users WHERE id = auth.uid();
$$;

-- Only authenticated users can call this
REVOKE ALL ON FUNCTION public.delete_own_account() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.delete_own_account() TO authenticated;
