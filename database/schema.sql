-- SalesOps AI Platform - Enterprise Database Schema
-- PostgreSQL 14+ with pgvector extension

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- MULTI-TENANCY & ORGANIZATIONS
-- ============================================================================

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    domain VARCHAR(255),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    
    -- Subscription & Billing
    subscription_tier VARCHAR(50) DEFAULT 'trial' CHECK (subscription_tier IN ('trial', 'starter', 'professional', 'enterprise')),
    subscription_status VARCHAR(50) DEFAULT 'active' CHECK (subscription_status IN ('active', 'suspended', 'cancelled')),
    subscription_start_date TIMESTAMP,
    subscription_end_date TIMESTAMP,
    monthly_call_limit INTEGER DEFAULT 100,
    monthly_calls_used INTEGER DEFAULT 0,
    
    -- CRM Integration
    primary_crm VARCHAR(50) CHECK (primary_crm IN ('salesforce', 'hubspot', 'pipedrive', 'none')),
    crm_connected BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_deleted ON organizations(deleted_at) WHERE deleted_at IS NULL;

-- ============================================================================
-- USERS & AUTHENTICATION
-- ============================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Identity
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    
    -- Authentication (if not using external auth like Clerk/Auth0)
    password_hash TEXT,
    email_verified BOOLEAN DEFAULT FALSE,
    
    -- Role & Permissions
    role VARCHAR(50) NOT NULL DEFAULT 'rep' CHECK (role IN ('admin', 'manager', 'rep')),
    permissions JSONB DEFAULT '[]',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    
    -- Metadata
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- ============================================================================
-- CALLS & RECORDINGS
-- ============================================================================

CREATE TABLE calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Call Metadata
    call_type VARCHAR(50) DEFAULT 'sales' CHECK (call_type IN ('sales', 'support', 'discovery', 'demo', 'follow_up')),
    call_date TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Recording & Transcription
    audio_file_url TEXT,
    audio_file_size_bytes BIGINT,
    transcript_url TEXT,
    raw_transcript TEXT,
    
    -- Processing Status
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (
        processing_status IN ('pending', 'transcribing', 'analyzing', 'completed', 'failed')
    ),
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    error_message TEXT,
    
    -- Participants
    participants JSONB DEFAULT '[]', -- [{name, email, role: "rep"|"prospect"}]
    
    -- Metadata
    source VARCHAR(50), -- 'zoom', 'google_meet', 'manual_upload', 'loom'
    external_id VARCHAR(255), -- ID from source platform
    metadata JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_calls_organization ON calls(organization_id);
CREATE INDEX idx_calls_user ON calls(user_id);
CREATE INDEX idx_calls_status ON calls(processing_status);
CREATE INDEX idx_calls_date ON calls(call_date DESC);
CREATE INDEX idx_calls_deleted ON calls(deleted_at) WHERE deleted_at IS NULL;

-- ============================================================================
-- CALL ANALYSIS (AI-Generated Insights)
-- ============================================================================

CREATE TABLE call_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Prospect Information
    prospect_name VARCHAR(255),
    prospect_company VARCHAR(255),
    prospect_email VARCHAR(255),
    prospect_phone VARCHAR(50),
    prospect_title VARCHAR(255),
    
    -- Analysis Results
    summary TEXT,
    pain_points JSONB DEFAULT '[]', -- ["pain point 1", "pain point 2"]
    next_steps JSONB DEFAULT '[]',
    objections JSONB DEFAULT '[]', -- [{objection, response, handled_well}]
    
    -- Sentiment & Scoring
    sentiment_score INTEGER CHECK (sentiment_score >= 1 AND sentiment_score <= 10),
    engagement_score INTEGER CHECK (engagement_score >= 1 AND engagement_score <= 10),
    buying_intent_score INTEGER CHECK (buying_intent_score >= 1 AND buying_intent_score <= 10),
    
    -- Quality Metrics
    call_quality_score INTEGER CHECK (call_quality_score >= 1 AND call_quality_score <= 5),
    methodology_score JSONB DEFAULT '{}', -- {meddic: {metrics: 8, economic_buyer: 6}, overall: 7}
    asked_for_meeting BOOLEAN,
    
    -- Talk Ratios
    rep_talk_ratio DECIMAL(5,2), -- Percentage (e.g., 35.50 = 35.5%)
    prospect_talk_ratio DECIMAL(5,2),
    dead_air_ratio DECIMAL(5,2),
    
    -- Strengths & Improvements
    strengths JSONB DEFAULT '[]',
    improvements JSONB DEFAULT '[]',
    
    -- Follow-up Content
    follow_up_email TEXT,
    meeting_notes TEXT,
    
    -- Strategic Recommendations
    strategic_advice TEXT,
    deal_risk_level VARCHAR(50) CHECK (deal_risk_level IN ('low', 'medium', 'high')),
    recommended_actions JSONB DEFAULT '[]',
    
    -- Vector Embeddings for RAG
    summary_embedding vector(1536), -- OpenAI ada-002 or similar
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analysis_call ON call_analysis(call_id);
CREATE INDEX idx_analysis_organization ON call_analysis(organization_id);
CREATE INDEX idx_analysis_prospect_company ON call_analysis(prospect_company);
CREATE INDEX idx_analysis_sentiment ON call_analysis(sentiment_score);
-- Vector similarity search index
CREATE INDEX idx_analysis_embedding ON call_analysis USING ivfflat (summary_embedding vector_cosine_ops);

-- ============================================================================
-- CRM INTEGRATIONS
-- ============================================================================

CREATE TABLE crm_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Integration Details
    crm_type VARCHAR(50) NOT NULL CHECK (crm_type IN ('salesforce', 'hubspot', 'pipedrive')),
    instance_url TEXT,
    
    -- OAuth Tokens (encrypted)
    access_token_encrypted TEXT,
    refresh_token_encrypted TEXT,
    token_expires_at TIMESTAMP,
    
    -- Configuration
    field_mappings JSONB DEFAULT '{}', -- Map our fields to CRM fields
    sync_settings JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at TIMESTAMP,
    last_sync_status VARCHAR(50),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_crm_connections_org ON crm_connections(organization_id);

CREATE TABLE crm_sync_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    crm_connection_id UUID NOT NULL REFERENCES crm_connections(id) ON DELETE CASCADE,
    
    -- Sync Details
    action VARCHAR(50) CHECK (action IN ('create_contact', 'update_contact', 'create_activity', 'create_opportunity')),
    crm_entity_type VARCHAR(100), -- 'Contact', 'Lead', 'Opportunity'
    crm_entity_id VARCHAR(255), -- ID in the CRM
    
    -- Status
    status VARCHAR(50) CHECK (status IN ('pending', 'success', 'failed')),
    error_message TEXT,
    
    -- Payload
    request_payload JSONB,
    response_payload JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_crm_sync_call ON crm_sync_logs(call_id);
CREATE INDEX idx_crm_sync_status ON crm_sync_logs(status);

-- ============================================================================
-- PLAYBOOKS & METHODOLOGIES
-- ============================================================================

CREATE TABLE playbooks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Playbook Details
    name VARCHAR(255) NOT NULL,
    methodology VARCHAR(50) CHECK (methodology IN ('MEDDIC', 'SPIN', 'BANT', 'Challenger', 'custom')),
    description TEXT,
    
    -- Framework Definition
    criteria JSONB NOT NULL, -- Structured scoring criteria
    -- Example: {"MEDDIC": {"Metrics": {"weight": 20, "questions": [...]}, ...}}
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_playbooks_org ON playbooks(organization_id);

-- ============================================================================
-- KNOWLEDGE BASE (RAG)
-- ============================================================================

CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Content
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_type VARCHAR(50) CHECK (content_type IN ('best_practice', 'objection_handler', 'product_info', 'competitor_analysis')),
    
    -- Categorization
    tags JSONB DEFAULT '[]',
    category VARCHAR(100),
    
    -- Vector Embedding
    content_embedding vector(1536),
    
    -- Usage Tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX idx_knowledge_org ON knowledge_base(organization_id);
CREATE INDEX idx_knowledge_type ON knowledge_base(content_type);
CREATE INDEX idx_knowledge_embedding ON knowledge_base USING ivfflat (content_embedding vector_cosine_ops);

-- ============================================================================
-- ANALYTICS & REPORTING
-- ============================================================================

CREATE TABLE team_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Time Period
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    
    -- Call Metrics
    total_calls INTEGER DEFAULT 0,
    avg_call_duration INTEGER,
    avg_sentiment_score DECIMAL(4,2),
    avg_quality_score DECIMAL(4,2),
    
    -- Performance Metrics
    meetings_scheduled INTEGER DEFAULT 0,
    opportunities_created INTEGER DEFAULT 0,
    win_rate DECIMAL(5,2),
    
    -- Talk Ratios
    avg_rep_talk_ratio DECIMAL(5,2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_team_metrics_org ON team_metrics(organization_id);
CREATE INDEX idx_team_metrics_user ON team_metrics(user_id);
CREATE INDEX idx_team_metrics_period ON team_metrics(period_start, period_end);

-- ============================================================================
-- TASK QUEUE & JOBS
-- ============================================================================

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Job Definition
    job_type VARCHAR(100) NOT NULL, -- 'transcribe_call', 'analyze_call', 'sync_crm'
    priority INTEGER DEFAULT 5,
    
    -- Payload
    payload JSONB NOT NULL,
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- Execution
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result JSONB,
    
    -- Worker Info
    worker_id VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_jobs_status ON jobs(status, priority DESC, created_at ASC);
CREATE INDEX idx_jobs_type ON jobs(job_type);

-- ============================================================================
-- AUDIT LOG
-- ============================================================================

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Event Details
    action VARCHAR(100) NOT NULL, -- 'call.analyzed', 'user.created', 'crm.synced'
    entity_type VARCHAR(50), -- 'call', 'user', 'organization'
    entity_id UUID,
    
    -- Context
    ip_address INET,
    user_agent TEXT,
    
    -- Changes
    old_values JSONB,
    new_values JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_org ON audit_logs(organization_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Active calls with analysis
CREATE VIEW v_calls_with_analysis AS
SELECT 
    c.*,
    ca.prospect_name,
    ca.prospect_company,
    ca.sentiment_score,
    ca.call_quality_score,
    ca.summary,
    u.full_name as rep_name,
    u.email as rep_email
FROM calls c
LEFT JOIN call_analysis ca ON c.id = ca.call_id
LEFT JOIN users u ON c.user_id = u.id
WHERE c.deleted_at IS NULL;

-- Organization dashboard metrics
CREATE VIEW v_organization_dashboard AS
SELECT 
    o.id,
    o.name,
    o.subscription_tier,
    COUNT(DISTINCT c.id) as total_calls,
    COUNT(DISTINCT CASE WHEN c.processing_status = 'completed' THEN c.id END) as completed_calls,
    COUNT(DISTINCT u.id) as total_users,
    AVG(ca.sentiment_score) as avg_sentiment,
    AVG(ca.call_quality_score) as avg_quality
FROM organizations o
LEFT JOIN calls c ON o.id = c.organization_id AND c.deleted_at IS NULL
LEFT JOIN users u ON o.id = u.organization_id AND u.deleted_at IS NULL
LEFT JOIN call_analysis ca ON c.id = ca.call_id
WHERE o.deleted_at IS NULL
GROUP BY o.id, o.name, o.subscription_tier;

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_calls_updated_at BEFORE UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SEED DATA FOR DEVELOPMENT
-- ============================================================================

-- Insert demo organization
INSERT INTO organizations (name, slug, domain, subscription_tier, primary_crm)
VALUES ('Demo Corp', 'demo-corp', 'democorp.com', 'professional', 'salesforce');

-- Insert demo users
INSERT INTO users (organization_id, email, full_name, role)
SELECT 
    id,
    'admin@democorp.com',
    'Admin User',
    'admin'
FROM organizations WHERE slug = 'demo-corp';

INSERT INTO users (organization_id, email, full_name, role)
SELECT 
    id,
    'rep@democorp.com',
    'Sales Rep',
    'rep'
FROM organizations WHERE slug = 'demo-corp';