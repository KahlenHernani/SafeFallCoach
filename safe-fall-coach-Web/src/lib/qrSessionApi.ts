import { supabase } from './supabaseClient';

export type QrSessionStatus = 'pending' | 'connected' | 'ended';

export interface QrSessionLink {
  id: string;
  code: string;
  admin_id: string;
  participant_id: string | null;
  status: QrSessionStatus;
  created_at: string;
  connected_at: string | null;
  ended_at: string | null;
}

const CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no ambiguous chars

function generateCode(length = 6): string {
  let code = '';
  for (let i = 0; i < length; i++) {
    code += CODE_ALPHABET[Math.floor(Math.random() * CODE_ALPHABET.length)];
  }
  return code;
}

export async function createQrSessionLink(adminId: string): Promise<QrSessionLink> {
  for (let attempt = 0; attempt < 5; attempt++) {
    const code = generateCode();
    const { data, error } = await supabase
      .from('qr_session_links')
      .insert({ admin_id: adminId, code, status: 'pending' })
      .select('*')
      .single();
    if (!error) return data as QrSessionLink;
    if (!String(error.message).toLowerCase().includes('duplicate')) throw error;
  }
  throw new Error('Unable to generate a unique QR code. Please try again.');
}

export async function endQrSessionLink(id: string): Promise<void> {
  const { error } = await supabase
    .from('qr_session_links')
    .update({ status: 'ended', ended_at: new Date().toISOString() })
    .eq('id', id);
  if (error) throw error;
}

export async function claimQrSessionLink(code: string, participantId: string): Promise<QrSessionLink> {
  const normalized = code.trim().toUpperCase();
  const { data: existing, error: loadError } = await supabase
    .from('qr_session_links')
    .select('*')
    .eq('code', normalized)
    .maybeSingle();
  if (loadError) throw loadError;
  if (!existing) throw new Error('This QR code is invalid or has expired.');
  if (existing.status !== 'pending') {
    throw new Error('This QR code has already been used. Ask your admin for a new one.');
  }

  const { data, error } = await supabase
    .from('qr_session_links')
    .update({
      participant_id: participantId,
      status: 'connected',
      connected_at: new Date().toISOString(),
    })
    .eq('id', existing.id)
    .eq('status', 'pending')
    .select('*')
    .single();

  if (error) throw error;
  return data as QrSessionLink;
}

export function subscribeToQrSessionLink(
  id: string,
  onChange: (link: QrSessionLink) => void,
): () => void {
  const channel = supabase
    .channel(`qr-session-link-${id}`)
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'qr_session_links', filter: `id=eq.${id}` },
      (payload) => onChange(payload.new as QrSessionLink),
    )
    .subscribe();

  return () => {
    void supabase.removeChannel(channel);
  };
}

export async function getAdminParticipantInfo(participantId: string) {
  const { data, error } = await supabase.rpc('admin_get_participant', {
    target_user_id: participantId,
  });
  if (error) throw error;
  return (data?.[0] ?? null) as { first_name: string | null; last_name: string | null; email: string } | null;
}