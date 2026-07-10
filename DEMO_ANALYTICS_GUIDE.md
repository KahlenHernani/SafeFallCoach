# Demo Guide: Active Learning Access and Analytics

## 1. Access request workflow

Open `/active-learning-access`.

1. Enter a participant ID such as `demo-tomorrow`.
2. Click `Request Active Learning`.
3. Show that the request status is `pending`.
4. In the administrator controls, approve the user.
5. Toggle enable/disable to show admins can immediately control access.

Talking point: Firebase can replace this temporary participant ID with authenticated user IDs and role checks later.

## 2. Server-side enforcement

Open `/practice`.

1. Enter the approved participant ID.
2. Start a session.
3. Explain that the server checks approval, enabled status, 30 minutes/day, and 20 sessions/day before allowing `/session/start`.
4. Go back to `/active-learning-access` and disable the user.
5. Explain that active sessions are also monitored server-side and can be stopped when disabled or when limits are reached.

## 3. Analytics dashboard

Open `/analytics`.

1. DAU, WAU, MAU: show participant activity over daily, weekly, and monthly windows.
2. Growth trend: show whether active users are increasing over the last 30 days.
3. User journey analytics: walk through registration to onboarding, onboarding to first training, first training to week 1 retention, and week 1 to month 1 retention.
4. Engagement heatmap: show which days and times are most active.
5. Session frequency: show how often participants return.
6. Training metrics: show sessions started, sessions completed, average completion rate, and drop-off.

## 4. Live analytics event demo

Open `/training`.

1. Enter the same participant ID.
2. Click `Start` on a training card.
3. Click `Complete`.
4. Return to `/analytics` and click `Refresh`.
5. Point out that training started/completed metrics update through the same analytics event API.

## Current limitation

This is intentionally demo-friendly and not final auth. Admin controls are visible without Firebase role checks. When Firebase is ready, wrap `/admin/*` and `/analytics/*` with admin-role verification and replace `participant_id` with the authenticated Firebase UID.
