-- ==============================================================================
-- ATS Resume Scorer - Supabase Database Schema
-- Run this SQL in your Supabase Dashboard: SQL Editor -> New Query -> Run
-- ==============================================================================

-- 1. Create the analyses table
CREATE TABLE IF NOT EXISTS public.analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    ats_score NUMERIC(5, 2) DEFAULT 0,
    keyword_match NUMERIC(5, 2) DEFAULT 0,
    missing_keywords JSONB DEFAULT '[]'::jsonb,
    analysis_result JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Create index on user_id and created_at for fast history queries
CREATE INDEX IF NOT EXISTS idx_analyses_user_id ON public.analyses (user_id);
CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON public.analyses (created_at DESC);

-- 3. Enable Row Level Security (RLS)
ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;

-- 4. Set up RLS Policies

-- Allow authenticated users to view their own analyses
CREATE POLICY "Users can view their own analyses"
ON public.analyses
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Allow authenticated users to insert their own analyses
CREATE POLICY "Users can insert their own analyses"
ON public.analyses
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Allow authenticated users to delete their own analyses
CREATE POLICY "Users can delete their own analyses"
ON public.analyses
FOR DELETE
TO authenticated
USING (auth.uid() = user_id);

-- Allow backend service_role key full access (bypasses RLS by default, but explicitly granting)
CREATE POLICY "Service role full access"
ON public.analyses
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
