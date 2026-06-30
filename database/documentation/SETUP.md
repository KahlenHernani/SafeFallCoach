# Database Setup Guide

## Initial Setup

### 1. Create Supabase Project
1. Go to https://supabase.com
2. Create a new project
3. Note your project URL and API keys

### 2. Enable Extensions
Run this first in SQL Editor:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 3. Run Migrations
Execute the migration files in the `migrations/` directory in numerical order:

#### Migration 001: Initial Schema
- Creates core tables: users, falls, tutorial_progress, caregivers
- Sets up basic foreign key relationships
- Enables UUID generation

#### Migration 002: Authentication Integration
- Adds auth_user_id columns to link with Supabase Auth
- Creates profiles table
- Sets up authentication triggers
- Implements initial RLS policies

#### Migration 003: Health Tracking System
- Creates health_stats table for vital signs and activity
- Implements medication tracking (schedule and log)
- Adds health_alerts for automated monitoring
- Creates health_trends for statistical summaries

#### Migration 004: Caregiver and EMS System
- Implements caregiver invitation workflow
- Adds shift scheduling and task management
- Creates EMS call tracking system
- Sets up secure messaging between caregivers

#### Migration 005: Drop Profiles Table
- Removes redundant profiles table (user data lives in users table)
- Re-points foreign keys from profiles(id) to auth.users(id)
- Updates handle_new_user() trigger to create users row directly

### 4. Verify Setup
After running all migrations, verify:
```sql
-- Check all tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
ORDER BY table_name;

-- Verify RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public';
```

### 5. Configure Authentication
1. In Supabase Dashboard → Authentication → Providers
2. Enable Email provider
3. Configure email templates (optional)
4. Set up redirect URLs for your app

## Environment Variables

Add these to your application's `.env` file:
```
SUPABASE_URL=your-project-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

## Testing

### Test Authentication Flow
1. Sign up a test user through Supabase Auth
2. Verify user row is auto-created in users table
3. Check that user can only see their own data

### Test RLS Policies
```sql
-- Impersonate a user
SET request.jwt.claim.sub = 'user-uuid-here';

-- Try to query data
SELECT * FROM users;

-- Should only return that user's data
```

## Troubleshooting

### Common Issues

**Issue**: Trigger not creating user row on signup
- Check that `handle_new_user()` function exists
- Verify trigger is attached to `auth.users` table

**Issue**: RLS policies blocking legitimate access
- Use `auth.uid()` in SQL Editor to check current user
- Verify user has correct auth_user_id in users/caregivers table

**Issue**: Slow queries
- Check indexes are created on foreign keys
- Use `EXPLAIN ANALYZE` to identify bottlenecks

## Backup and Recovery

Supabase automatically backs up your database. To manually backup:
1. Go to Database → Backups in Supabase Dashboard
2. Click "Create Backup"

To restore from backup:
1. Contact Supabase support or use their restore feature
2. Backup data is retained based on your plan tier
