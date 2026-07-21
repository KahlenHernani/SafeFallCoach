import { supabase } from './supabaseClient';

const accessEmailWebhookUrl = String(import.meta.env.VITE_ACCESS_EMAIL_WEBHOOK_URL || '').trim();

type AccessGrantedEmailInput = {
  userId: string;
  email: string;
  firstName?: string | null;
  lastName?: string | null;
};

function displayName(input: AccessGrantedEmailInput) {
  const name = [input.firstName, input.lastName].filter(Boolean).join(' ').trim();
  return name || input.email;
}

export async function sendAccessGrantedEmail(input: AccessGrantedEmailInput) {
  if (!input.email) return { sent: false, message: 'No email address is available for this user.' };

  const subject = 'SafeFall Coach Active Learning access approved';
  const message = `Hi ${displayName(input)}, your Active Learning practice access has been approved. You can now sign in to SafeFall Coach and open Practice mode.`;

  try {
    await supabase
      .from('notifications')
      .insert({
        id: crypto.randomUUID(),
        recipient_user_id: input.userId,
        type: 'active_learning_access_approved',
        title: subject,
        message,
      });
  } catch {
    // Email delivery should not fail the approval flow if notification inserts are restricted by RLS.
  }

  if (!accessEmailWebhookUrl) {
    return { sent: false, message: 'Access was approved. Set VITE_ACCESS_EMAIL_WEBHOOK_URL to send email.' };
  }

  const { data: sessionData } = await supabase.auth.getSession();
  const response = await fetch(accessEmailWebhookUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(sessionData.session?.access_token
        ? { Authorization: `Bearer ${sessionData.session.access_token}` }
        : {}),
    },
    body: JSON.stringify({
      type: 'active_learning_access_approved',
      user_id: input.userId,
      email: input.email,
      name: displayName(input),
      subject,
      message,
    }),
  });

  if (!response.ok) {
    throw new Error(`Access was approved, but email failed with status ${response.status}.`);
  }

  return { sent: true, message: `Approval email sent to ${input.email}.` };
}
