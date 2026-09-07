-- ==============================================================================
-- Recraftr Production PostgreSQL Schema (Supabase)
-- ==============================================================================

-- 1. Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Trigger function to automatically update `updated_at` timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ==============================================================================
-- 3. Profiles Table
-- Syncs with Supabase auth.users or functions as standalone user profile table
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- 4. Resumes Table
-- Stores resume metadata and extracted text. Storage file path points to Supabase Storage bucket
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    text TEXT NOT NULL,
    storage_path TEXT,
    char_count INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumes_user_id ON public.resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_resumes_created_at ON public.resumes(created_at DESC);

-- ==============================================================================
-- 5. Analyses Table
-- Stores resume analyses, ATS breakdown scores, and recrafted versions
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES public.resumes(id) ON DELETE SET NULL,
    resume_filename TEXT,
    job_title TEXT NOT NULL,
    job_description TEXT NOT NULL,
    analysis JSONB,
    model TEXT DEFAULT 'gemini-3.5-flash',
    optimized_resume TEXT,
    predicted_ats_score INT,
    changes_summary JSONB DEFAULT '[]'::jsonb,
    cover_letter TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON public.analyses(user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_resume_id ON public.analyses(resume_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON public.analyses(created_at DESC);

DROP TRIGGER IF EXISTS trg_analyses_updated_at ON public.analyses;
CREATE TRIGGER trg_analyses_updated_at
    BEFORE UPDATE ON public.analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- 6. Applications Table
-- Manages job applications for the Job Tracker (Kanban / Table view)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    job_title TEXT NOT NULL,
    company_name TEXT NOT NULL DEFAULT 'Target Company',
    location TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'applied',
    ats_score INT,
    job_description TEXT DEFAULT '',
    optimized_resume TEXT DEFAULT '',
    cover_letter TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    resume_filename TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_applications_user_id ON public.applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_user_status ON public.applications(user_id, status);
CREATE INDEX IF NOT EXISTS idx_applications_updated_at ON public.applications(updated_at DESC);

DROP TRIGGER IF EXISTS trg_applications_updated_at ON public.applications;
CREATE TRIGGER trg_applications_updated_at
    BEFORE UPDATE ON public.applications
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- 7. Purchases Table
-- Tracks PayMongo checkout transactions
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.purchases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    paymongo_payment_id TEXT UNIQUE,
    amount NUMERIC(10, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'PHP',
    package_name TEXT NOT NULL,
    credits_granted INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purchases_user_id ON public.purchases(user_id);
CREATE INDEX IF NOT EXISTS idx_purchases_payment_id ON public.purchases(paymongo_payment_id);

-- ==============================================================================
-- 8. Credit Transactions Table
-- Atomic ledger tracking credit additions and deductions
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.credit_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    amount INT NOT NULL,
    action_type TEXT NOT NULL,
    balance_after INT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_created ON public.credit_transactions(user_id, created_at DESC);
