import { createContext, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase } from '../lib/supabaseClient';

type AuthContextValue = {
  session: Session | null;
  user: User | null;
  role: string | null;
  loading: boolean;
  roleLoading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (
    email: string,
    password: string,
    firstName: string,
    lastName: string,
  ) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [roleLoading, setRoleLoading] = useState(false);

  async function loadRole(userId: string) {
    setRoleLoading(true);
    const { data, error } = await supabase
      .from('users')
      .select('role')
      .eq('user_id', userId)
      .maybeSingle();
    if (error) {
      setRole(null);
      setRoleLoading(false);
      return;
    }
    setRole(data?.role ?? null);
    setRoleLoading(false);
  }

useEffect(() => {
  supabase.auth.getSession().then(async ({ data }) => {
    setSession(data.session);
    if (data.session?.user) {
      await loadRole(data.session.user.id);
    }
    setLoading(false);
  });

  const { data: listener } = supabase.auth.onAuthStateChange(async (_event, newSession) => {
    setSession(newSession);
    if (newSession?.user) {
      await loadRole(newSession.user.id);
    } else {
      setRole(null);
    }
  });

  return () => listener.subscription.unsubscribe();
}, []);

  async function signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error?.message ?? null };
  }

  async function signUp(email: string, password: string, firstName: string, lastName: string) {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { first_name: firstName, last_name: lastName, role: 'user' },
      },
    });
    return { error: error?.message ?? null };
  }

  async function signOut() {
    await supabase.auth.signOut();
    setRole(null);
  }

  const value: AuthContextValue = {
    session,
    user: session?.user ?? null,
    role,
    loading,
    roleLoading,
    signIn,
    signUp,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
