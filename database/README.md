# FallRisk Database

This directory contains all database schemas, migrations, and documentation for the FallRisk: SafeFall Coach App.

## Database Stack
- **Database**: PostgreSQL 15+
- **Hosting**: Supabase
- **Authentication**: Supabase Auth with Row-Level Security

## Quick Start

### Prerequisites
- Supabase account
- PostgreSQL client (optional, for local testing)

### Setup Instructions
1. Create a new Supabase project at https://supabase.com
2. Run migrations in order from `migrations/` directory
3. Verify RLS policies are enabled on all tables

### Running Migrations
In Supabase SQL Editor, run the migration files in order:
1. `001_initial_schema.sql` - Core tables (users, falls, tutorials, caregivers)
2. `002_authentication_integration.sql` - Auth integration and profiles
3. `003_health_tracking_system.sql` - Health stats and medication tracking
4. `004_caregiver_ems_system.sql` - Caregiver management and EMS
5. `005_drop_profiles_table.sql` - Remove profiles table, re-point FKs to auth.users

## Directory Structure
- `migrations/` - SQL migration scripts to be run in order
- `schemas/` - Complete database schema
- `policies/` - Row-Level Security policies
- `documentation/` - Setup guides and schema documentation

## Schema Overview
See `documentation/SCHEMA_OVERVIEW.md` for detailed table descriptions.

## Connection Information
Supabase connection details are stored in environment variables (not committed to repo):
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

## Contact
Database Lead: Diego Quinones
