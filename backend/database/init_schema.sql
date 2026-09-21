/*
    VietNormalizer - SQL Server Express / LocalDB base schema
    Run this script after creating the VietNormalizer database.
*/

SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

SET ANSI_PADDING ON
GO

SET ANSI_WARNINGS ON
GO

SET CONCAT_NULL_YIELDS_NULL ON
GO

SET ARITHABORT ON
GO

SET NUMERIC_ROUNDABORT OFF
GO

IF OBJECT_ID(N'dbo.roles', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.roles (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        role_name NVARCHAR(50) NOT NULL UNIQUE,
        description NVARCHAR(255) NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
END
GO

IF OBJECT_ID(N'dbo.users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.users (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        username NVARCHAR(100) NOT NULL UNIQUE,
        email NVARCHAR(200) NOT NULL UNIQUE,
        password_hash NVARCHAR(256) NOT NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
END
GO

IF OBJECT_ID(N'dbo.user_roles', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.user_roles (
        user_id UNIQUEIDENTIFIER NOT NULL,
        role_id UNIQUEIDENTIFIER NOT NULL,
        assigned_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        assigned_by NVARCHAR(100) NULL,
        CONSTRAINT PK_user_roles PRIMARY KEY (user_id, role_id),
        CONSTRAINT FK_user_roles_users FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_user_roles_roles FOREIGN KEY (role_id) REFERENCES dbo.roles(id)
    )
END
GO

IF OBJECT_ID(N'dbo.dictionary_entries', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.dictionary_entries (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        word NVARCHAR(255) NOT NULL,
        dictionary_name NVARCHAR(100) NOT NULL,
        source NVARCHAR(100) NOT NULL DEFAULT N'json_seed',
        approved BIT NOT NULL DEFAULT 1,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        approved_by NVARCHAR(100) NULL
    )
END
GO

IF OBJECT_ID(N'dbo.abbreviations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.abbreviations (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        abbr NVARCHAR(100) NOT NULL,
        expanded NVARCHAR(500) NOT NULL,
        alternative_expansions_json NVARCHAR(MAX) NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        source NVARCHAR(100) NOT NULL DEFAULT N'manual',
        approved BIT NOT NULL DEFAULT 1,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        approved_at DATETIME2 NULL,
        approved_by NVARCHAR(100) NULL,
        last_synced_at DATETIME2 NULL
    )
END
GO

IF OBJECT_ID(N'dbo.abbreviation_pending', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.abbreviation_pending (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        abbr NVARCHAR(100) NOT NULL,
        suggested NVARCHAR(500) NULL,
        suggested_meanings_json NVARCHAR(MAX) NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        source NVARCHAR(100) NOT NULL DEFAULT N'runtime',
        status NVARCHAR(20) NOT NULL DEFAULT N'PENDING',
        submission_count INT NOT NULL DEFAULT 1,
        first_submitted_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        last_submitted_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        submitted_by NVARCHAR(100) NULL,
        reviewed_by NVARCHAR(100) NULL,
        review_notes NVARCHAR(1000) NULL,
        approved_abbreviation_id UNIQUEIDENTIFIER NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        created_by NVARCHAR(100) NULL,
        updated_by NVARCHAR(100) NULL,
        CONSTRAINT FK_abbreviation_pending_approved_abbreviation
            FOREIGN KEY (approved_abbreviation_id) REFERENCES dbo.abbreviations(id)
    )
END
GO

IF OBJECT_ID(N'dbo.user_abbreviation_overrides', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.user_abbreviation_overrides (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        user_id UNIQUEIDENTIFIER NOT NULL,
        abbr NVARCHAR(100) NOT NULL,
        expanded NVARCHAR(500) NOT NULL,
        alternative_expansions_json NVARCHAR(MAX) NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        source NVARCHAR(100) NOT NULL DEFAULT N'user_personal',
        pending_id UNIQUEIDENTIFIER NULL,
        approved_abbreviation_id UNIQUEIDENTIFIER NULL,
        usage_count BIGINT NOT NULL DEFAULT 0,
        last_used_at DATETIME2 NULL,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        created_by NVARCHAR(100) NULL,
        updated_by NVARCHAR(100) NULL,
        CONSTRAINT FK_user_abbreviation_overrides_user
            FOREIGN KEY (user_id) REFERENCES dbo.users(id),
        CONSTRAINT FK_user_abbreviation_overrides_pending
            FOREIGN KEY (pending_id) REFERENCES dbo.abbreviation_pending(id),
        CONSTRAINT FK_user_abbreviation_overrides_abbreviation
            FOREIGN KEY (approved_abbreviation_id) REFERENCES dbo.abbreviations(id)
    )
END
GO

IF COL_LENGTH(N'dbo.abbreviations', N'alternative_expansions_json') IS NULL
BEGIN
    ALTER TABLE dbo.abbreviations
    ADD alternative_expansions_json NVARCHAR(MAX) NULL
END
GO

IF COL_LENGTH(N'dbo.abbreviation_pending', N'suggested_meanings_json') IS NULL
BEGIN
    ALTER TABLE dbo.abbreviation_pending
    ADD suggested_meanings_json NVARCHAR(MAX) NULL
END
GO

IF OBJECT_ID(N'dbo.abbreviation_audit_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.abbreviation_audit_log (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        pending_id UNIQUEIDENTIFIER NULL,
        abbreviation_id UNIQUEIDENTIFIER NULL,
        action NVARCHAR(30) NOT NULL,
        action_notes NVARCHAR(1000) NULL,
        actor_name NVARCHAR(100) NULL,
        payload_json NVARCHAR(MAX) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_abbreviation_audit_log_pending
            FOREIGN KEY (pending_id) REFERENCES dbo.abbreviation_pending(id),
        CONSTRAINT FK_abbreviation_audit_log_abbreviation
            FOREIGN KEY (abbreviation_id) REFERENCES dbo.abbreviations(id)
    )
END
GO

IF OBJECT_ID(N'dbo.ai_meaning_candidates', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ai_meaning_candidates (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        abbr NVARCHAR(100) NOT NULL,
        meaning NVARCHAR(500) NOT NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        status NVARCHAR(30) NOT NULL DEFAULT N'CANDIDATE',
        provider NVARCHAR(100) NULL,
        model NVARCHAR(200) NULL,
        policy_version NVARCHAR(50) NOT NULL,
        confidence FLOAT NOT NULL,
        evidence_count INT NOT NULL DEFAULT 0,
        is_active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        revoked_at DATETIME2 NULL,
        revoked_by NVARCHAR(100) NULL,
        revision BIGINT NOT NULL DEFAULT 1
    )
END
GO

IF OBJECT_ID(N'dbo.ai_meaning_evidence', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ai_meaning_evidence (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        candidate_id UNIQUEIDENTIFIER NOT NULL,
        request_fingerprint CHAR(64) NOT NULL,
        actor_fingerprint CHAR(64) NOT NULL,
        context_fingerprint CHAR(64) NOT NULL,
        context_snippet NVARCHAR(500) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ai_meaning_evidence_candidate
            FOREIGN KEY (candidate_id) REFERENCES dbo.ai_meaning_candidates(id),
        CONSTRAINT UQ_ai_meaning_evidence_request UNIQUE (candidate_id, request_fingerprint)
    )
END
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ai_meaning_candidates_lookup' AND object_id = OBJECT_ID(N'dbo.ai_meaning_candidates'))
    CREATE INDEX IX_ai_meaning_candidates_lookup ON dbo.ai_meaning_candidates (abbr, domain, status, is_active);
GO

-- Ticket 17: additive migration. Legacy rows have no eligible context scope;
-- they remain unavailable for automatic reuse until reviewed.
IF COL_LENGTH('dbo.ai_meaning_candidates', 'scope_fingerprint') IS NULL
    ALTER TABLE dbo.ai_meaning_candidates ADD scope_fingerprint CHAR(64) NULL;
GO
IF COL_LENGTH('dbo.ai_meaning_evidence', 'user_fingerprint') IS NULL
    ALTER TABLE dbo.ai_meaning_evidence ADD user_fingerprint CHAR(64) NULL;
IF COL_LENGTH('dbo.ai_meaning_evidence', 'session_fingerprint') IS NULL
    ALTER TABLE dbo.ai_meaning_evidence ADD session_fingerprint CHAR(64) NULL;
GO
IF OBJECT_ID(N'dbo.ai_meaning_audit', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ai_meaning_audit (
        id UNIQUEIDENTIFIER NOT NULL PRIMARY KEY,
        candidate_id UNIQUEIDENTIFIER NOT NULL REFERENCES dbo.ai_meaning_candidates(id),
        action NVARCHAR(30) NOT NULL,
        actor NVARCHAR(100) NOT NULL,
        reason NVARCHAR(500) NOT NULL,
        revision BIGINT NOT NULL,
        created_at DATETIME2 NOT NULL
    );
    CREATE INDEX IX_ai_meaning_audit_candidate ON dbo.ai_meaning_audit(candidate_id, created_at);
END
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_ai_meaning_scope' AND object_id = OBJECT_ID(N'dbo.ai_meaning_candidates'))
    CREATE INDEX IX_ai_meaning_scope ON dbo.ai_meaning_candidates(abbr, domain, scope_fingerprint);
GO
-- Legacy rows remain intact for audit. Enforce context uniqueness for every
-- new evidence row, in addition to the transaction-owned application lock.
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'UQ_ai_meaning_evidence_context_v1' AND object_id = OBJECT_ID(N'dbo.ai_meaning_evidence'))
    CREATE UNIQUE INDEX UQ_ai_meaning_evidence_context_v1
        ON dbo.ai_meaning_evidence(candidate_id, context_fingerprint)
        WHERE user_fingerprint IS NOT NULL;
GO

IF OBJECT_ID(N'dbo.normalization_history', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.normalization_history (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        input_text NVARCHAR(MAX) NOT NULL,
        output_text NVARCHAR(MAX) NULL,
        error_types_json NVARCHAR(500) NULL,
        model_used NVARCHAR(100) NULL,
        from_cache BIT NOT NULL DEFAULT 0,
        latency_ms FLOAT NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        source_kind NVARCHAR(100) NOT NULL DEFAULT N'rule_based',
        user_id UNIQUEIDENTIFIER NULL,
        username_snapshot NVARCHAR(100) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_normalization_history_user
            FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
END
GO

IF OBJECT_ID(N'dbo.diacritic_cache', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.diacritic_cache (
        cache_key NVARCHAR(64) NOT NULL PRIMARY KEY,
        input_text NVARCHAR(MAX) NOT NULL,
        output_text NVARCHAR(MAX) NOT NULL,
        model_used NVARCHAR(100) NULL,
        hit_count INT NOT NULL DEFAULT 0,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        last_hit_at DATETIME2 NULL,
        expires_at DATETIME2 NULL
    )
END
GO

IF OBJECT_ID(N'dbo.annotation_data', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.annotation_data (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        raw_text NVARCHAR(MAX) NOT NULL,
        normalized_text NVARCHAR(MAX) NOT NULL,
        error_types_json NVARCHAR(500) NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        split_set NVARCHAR(20) NOT NULL DEFAULT N'train',
        source NVARCHAR(100) NOT NULL DEFAULT N'manual',
        notes NVARCHAR(1000) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
END
GO

IF OBJECT_ID(N'dbo.system_error_logs', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.system_error_logs (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        module NVARCHAR(100) NOT NULL,
        error_message NVARCHAR(MAX) NOT NULL,
        stack_trace NVARCHAR(MAX) NULL,
        payload_json NVARCHAR(MAX) NULL,
        user_id UNIQUEIDENTIFIER NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_system_error_logs_user
            FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_abbreviations_active_abbr_domain'
      AND object_id = OBJECT_ID(N'dbo.abbreviations')
)
BEGIN
    CREATE UNIQUE INDEX UX_abbreviations_active_abbr_domain
        ON dbo.abbreviations (abbr, domain)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_pending_status_created_at'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_pending')
)
BEGIN
    CREATE INDEX IX_abbreviation_pending_status_created_at
        ON dbo.abbreviation_pending (status, created_at DESC);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_pending_abbr_domain_status'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_pending')
)
BEGIN
    CREATE INDEX IX_abbreviation_pending_abbr_domain_status
        ON dbo.abbreviation_pending (abbr, domain, status)
        INCLUDE (submission_count, updated_at)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_user_abbreviation_overrides_active_user_abbr_domain'
      AND object_id = OBJECT_ID(N'dbo.user_abbreviation_overrides')
)
BEGIN
    CREATE UNIQUE INDEX UX_user_abbreviation_overrides_active_user_abbr_domain
        ON dbo.user_abbreviation_overrides (user_id, abbr, domain)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_user_abbreviation_overrides_user_domain_abbr'
      AND object_id = OBJECT_ID(N'dbo.user_abbreviation_overrides')
)
BEGIN
    CREATE INDEX IX_user_abbreviation_overrides_user_domain_abbr
        ON dbo.user_abbreviation_overrides (user_id, domain, abbr)
        INCLUDE (expanded, source, pending_id, approved_abbreviation_id, updated_at)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_normalization_history_created_at_user_id'
      AND object_id = OBJECT_ID(N'dbo.normalization_history')
)
BEGIN
    CREATE INDEX IX_normalization_history_created_at_user_id
        ON dbo.normalization_history (created_at DESC, user_id);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_normalization_history_user_created_at'
      AND object_id = OBJECT_ID(N'dbo.normalization_history')
)
BEGIN
    CREATE INDEX IX_normalization_history_user_created_at
        ON dbo.normalization_history (user_id, created_at DESC);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_dictionary_entries_lookup'
      AND object_id = OBJECT_ID(N'dbo.dictionary_entries')
)
BEGIN
    CREATE INDEX IX_dictionary_entries_lookup
        ON dbo.dictionary_entries (dictionary_name, word);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_dictionary_entries_active_approved_word'
      AND object_id = OBJECT_ID(N'dbo.dictionary_entries')
)
BEGIN
    CREATE INDEX IX_dictionary_entries_active_approved_word
        ON dbo.dictionary_entries (approved, is_active, word);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_diacritic_cache_last_hit_at'
      AND object_id = OBJECT_ID(N'dbo.diacritic_cache')
)
BEGIN
    CREATE INDEX IX_diacritic_cache_last_hit_at
        ON dbo.diacritic_cache (last_hit_at DESC);
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.roles WHERE role_name = N'admin')
BEGIN
    INSERT INTO dbo.roles (role_name, description) VALUES (N'admin', N'Quan tri he thong');
END;
GO

IF NOT EXISTS (SELECT 1 FROM dbo.roles WHERE role_name = N'user')
BEGIN
    INSERT INTO dbo.roles (role_name, description) VALUES (N'user', N'Nguoi dung thong thuong');
END;
GO

/*
    ============================================================
    DEMO / DEV LOGIN ACCOUNTS -> backend/database/seed_demo.sql
    ============================================================
    The demo accounts USED to be created here. That made every deployment of
    this schema — including a public one — ship with a known admin account whose
    password is published in this repository.

    They now live in a separate, opt-in script:

        sqlcmd -S "<SERVER>" -d VietNormalizer -E -I -i backend\database\seed_demo.sql

    Run it ONLY on a development or demo database.
*/


/*
    ============================================================
    SCHEMA UPGRADE v2 — Long-term scalability & missing features
    ============================================================
    Added: 2026-05-23
    Purpose: Bo sung bang/cot/index con thieu cho su dung lau dai.
    - user_sessions: Quan ly JWT token, revoke, denylist
    - user_preferences: Luu tuy chon variant/UI qua nhieu phien
    - phrase_overrides: Chuyen phrase overrides tu JSON sang DB
    - abbreviation_usage_stats: Thong ke su dung tu viet tat
    - Cot moi cho users: last_login_at, failed_login_attempts, locked_until, password_changed_at
    - Cot moi cho normalization_history: input_method, character_count
    - Index bo sung cho audit_log, error_logs, annotation_data, diacritic_cache
    - Stored procedure don dep du lieu cu (retention)
    Tat ca deu idempotent, chay lai an toan.
*/

/* ---- 1. USER SESSIONS (JWT token management & denylist) ---- */
IF OBJECT_ID(N'dbo.user_sessions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.user_sessions (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        user_id UNIQUEIDENTIFIER NOT NULL,
        token_hash NVARCHAR(128) NOT NULL,
        ip_address NVARCHAR(45) NULL,
        user_agent NVARCHAR(500) NULL,
        issued_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        expires_at DATETIME2 NOT NULL,
        revoked_at DATETIME2 NULL,
        revoke_reason NVARCHAR(100) NULL,
        is_active BIT NOT NULL DEFAULT 1,
        last_activity_at DATETIME2 NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_user_sessions_user
            FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_user_sessions_token_hash'
      AND object_id = OBJECT_ID(N'dbo.user_sessions')
)
BEGIN
    CREATE INDEX IX_user_sessions_token_hash
        ON dbo.user_sessions (token_hash)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_user_sessions_user_active'
      AND object_id = OBJECT_ID(N'dbo.user_sessions')
)
BEGIN
    CREATE INDEX IX_user_sessions_user_active
        ON dbo.user_sessions (user_id, is_active)
        INCLUDE (expires_at, revoked_at)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_user_sessions_expires_at'
      AND object_id = OBJECT_ID(N'dbo.user_sessions')
)
BEGIN
    CREATE INDEX IX_user_sessions_expires_at
        ON dbo.user_sessions (expires_at)
        WHERE is_active = 1 AND revoked_at IS NULL;
END
GO

/* ---- 2. USER PREFERENCES (persist variant choices, UI settings) ---- */
IF OBJECT_ID(N'dbo.user_preferences', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.user_preferences (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        user_id UNIQUEIDENTIFIER NOT NULL,
        preference_key NVARCHAR(100) NOT NULL,
        preference_value NVARCHAR(MAX) NOT NULL,
        category NVARCHAR(50) NOT NULL DEFAULT N'general',
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_user_preferences_user
            FOREIGN KEY (user_id) REFERENCES dbo.users(id)
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_user_preferences_user_key'
      AND object_id = OBJECT_ID(N'dbo.user_preferences')
)
BEGIN
    CREATE UNIQUE INDEX UX_user_preferences_user_key
        ON dbo.user_preferences (user_id, preference_key);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_user_preferences_category'
      AND object_id = OBJECT_ID(N'dbo.user_preferences')
)
BEGIN
    CREATE INDEX IX_user_preferences_category
        ON dbo.user_preferences (user_id, category);
END
GO

/* ---- 3. PHRASE OVERRIDES IN DB (scalable phrase management) ---- */
IF OBJECT_ID(N'dbo.phrase_overrides', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.phrase_overrides (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        phrase_key NVARCHAR(500) NOT NULL,
        phrase_value NVARCHAR(500) NOT NULL,
        domain NVARCHAR(100) NOT NULL DEFAULT N'general',
        source NVARCHAR(100) NOT NULL DEFAULT N'manual',
        priority INT NOT NULL DEFAULT 0,
        approved BIT NOT NULL DEFAULT 1,
        approved_by NVARCHAR(100) NULL,
        is_active BIT NOT NULL DEFAULT 1,
        notes NVARCHAR(1000) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        created_by NVARCHAR(100) NULL,
        updated_by NVARCHAR(100) NULL
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_phrase_overrides_active_key_domain'
      AND object_id = OBJECT_ID(N'dbo.phrase_overrides')
)
BEGIN
    CREATE UNIQUE INDEX UX_phrase_overrides_active_key_domain
        ON dbo.phrase_overrides (phrase_key, domain)
        WHERE is_active = 1;
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_phrase_overrides_domain_priority'
      AND object_id = OBJECT_ID(N'dbo.phrase_overrides')
)
BEGIN
    CREATE INDEX IX_phrase_overrides_domain_priority
        ON dbo.phrase_overrides (domain, priority DESC)
        INCLUDE (phrase_key, phrase_value)
        WHERE is_active = 1 AND approved = 1;
END
GO

/* ---- 4. ABBREVIATION USAGE STATS (analytics for admin dashboard) ---- */
IF OBJECT_ID(N'dbo.abbreviation_usage_stats', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.abbreviation_usage_stats (
        id UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID() PRIMARY KEY,
        abbreviation_id UNIQUEIDENTIFIER NULL,
        abbr NVARCHAR(100) NOT NULL,
        expanded_chosen NVARCHAR(500) NOT NULL,
        usage_date DATE NOT NULL DEFAULT CAST(SYSUTCDATETIME() AS DATE),
        usage_count BIGINT NOT NULL DEFAULT 1,
        unique_users INT NOT NULL DEFAULT 1,
        source_kind NVARCHAR(50) NOT NULL DEFAULT N'live',
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_abbreviation_usage_stats_abbreviation
            FOREIGN KEY (abbreviation_id) REFERENCES dbo.abbreviations(id)
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'UX_abbreviation_usage_stats_daily'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_usage_stats')
)
BEGIN
    CREATE UNIQUE INDEX UX_abbreviation_usage_stats_daily
        ON dbo.abbreviation_usage_stats (abbr, expanded_chosen, usage_date, source_kind);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_usage_stats_date'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_usage_stats')
)
BEGIN
    CREATE INDEX IX_abbreviation_usage_stats_date
        ON dbo.abbreviation_usage_stats (usage_date DESC)
        INCLUDE (abbr, usage_count);
END
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_usage_stats_abbr'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_usage_stats')
)
BEGIN
    CREATE INDEX IX_abbreviation_usage_stats_abbr
        ON dbo.abbreviation_usage_stats (abbr)
        INCLUDE (usage_count, usage_date, unique_users);
END
GO

/* ---- 5. ADD COLUMNS TO dbo.users (security & analytics) ---- */
IF COL_LENGTH(N'dbo.users', N'last_login_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD last_login_at DATETIME2 NULL;
END
GO

IF COL_LENGTH(N'dbo.users', N'failed_login_attempts') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD failed_login_attempts INT NOT NULL DEFAULT 0;
END
GO

IF COL_LENGTH(N'dbo.users', N'locked_until') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD locked_until DATETIME2 NULL;
END
GO

IF COL_LENGTH(N'dbo.users', N'password_changed_at') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD password_changed_at DATETIME2 NULL;
END
GO

IF COL_LENGTH(N'dbo.users', N'display_name') IS NULL
BEGIN
    ALTER TABLE dbo.users ADD display_name NVARCHAR(200) NULL;
END
GO

/* ---- 6. ADD COLUMNS TO dbo.normalization_history (analytics) ---- */
IF COL_LENGTH(N'dbo.normalization_history', N'input_method') IS NULL
BEGIN
    ALTER TABLE dbo.normalization_history ADD input_method NVARCHAR(20) NULL;
END
GO

IF COL_LENGTH(N'dbo.normalization_history', N'character_count') IS NULL
BEGIN
    ALTER TABLE dbo.normalization_history ADD character_count INT NULL;
END
GO

/* ---- 7. ADD COLUMNS TO dbo.system_error_logs (severity & context) ---- */
IF COL_LENGTH(N'dbo.system_error_logs', N'severity') IS NULL
BEGIN
    ALTER TABLE dbo.system_error_logs ADD severity NVARCHAR(20) NOT NULL DEFAULT N'ERROR';
END
GO

IF COL_LENGTH(N'dbo.system_error_logs', N'request_path') IS NULL
BEGIN
    ALTER TABLE dbo.system_error_logs ADD request_path NVARCHAR(500) NULL;
END
GO

/* ---- 8. MISSING INDEXES on existing tables ---- */

/* abbreviation_audit_log: query by created_at for recent logs */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_audit_log_created_at'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_audit_log')
)
BEGIN
    CREATE INDEX IX_abbreviation_audit_log_created_at
        ON dbo.abbreviation_audit_log (created_at DESC)
        INCLUDE (action, actor_name);
END
GO

/* abbreviation_audit_log: lookup by pending_id */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_audit_log_pending_id'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_audit_log')
)
BEGIN
    CREATE INDEX IX_abbreviation_audit_log_pending_id
        ON dbo.abbreviation_audit_log (pending_id)
        INCLUDE (action, created_at);
END
GO

/* abbreviation_audit_log: lookup by abbreviation_id */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_abbreviation_audit_log_abbreviation_id'
      AND object_id = OBJECT_ID(N'dbo.abbreviation_audit_log')
)
BEGIN
    CREATE INDEX IX_abbreviation_audit_log_abbreviation_id
        ON dbo.abbreviation_audit_log (abbreviation_id)
        INCLUDE (action, created_at);
END
GO

/* system_error_logs: query by module + time */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_system_error_logs_module_created_at'
      AND object_id = OBJECT_ID(N'dbo.system_error_logs')
)
BEGIN
    CREATE INDEX IX_system_error_logs_module_created_at
        ON dbo.system_error_logs (module, created_at DESC);
END
GO

/* system_error_logs: query by severity */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_system_error_logs_severity_created_at'
      AND object_id = OBJECT_ID(N'dbo.system_error_logs')
)
BEGIN
    CREATE INDEX IX_system_error_logs_severity_created_at
        ON dbo.system_error_logs (severity, created_at DESC);
END
GO

/* annotation_data: query by domain + split_set */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_annotation_data_domain_split_set'
      AND object_id = OBJECT_ID(N'dbo.annotation_data')
)
BEGIN
    CREATE INDEX IX_annotation_data_domain_split_set
        ON dbo.annotation_data (domain, split_set);
END
GO

/* annotation_data: query by source */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_annotation_data_source'
      AND object_id = OBJECT_ID(N'dbo.annotation_data')
)
BEGIN
    CREATE INDEX IX_annotation_data_source
        ON dbo.annotation_data (source, created_at DESC);
END
GO

/* diacritic_cache: cleanup expired entries */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_diacritic_cache_expires_at'
      AND object_id = OBJECT_ID(N'dbo.diacritic_cache')
)
BEGIN
    CREATE INDEX IX_diacritic_cache_expires_at
        ON dbo.diacritic_cache (expires_at)
        WHERE expires_at IS NOT NULL;
END
GO

/* normalization_history: query by input_method for analytics */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_normalization_history_input_method'
      AND object_id = OBJECT_ID(N'dbo.normalization_history')
)
BEGIN
    CREATE INDEX IX_normalization_history_input_method
        ON dbo.normalization_history (input_method, created_at DESC)
        WHERE input_method IS NOT NULL;
END
GO

/* users: lookup active users by last_login for admin dashboard */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_users_last_login_at'
      AND object_id = OBJECT_ID(N'dbo.users')
)
BEGIN
    CREATE INDEX IX_users_last_login_at
        ON dbo.users (last_login_at DESC)
        WHERE is_active = 1;
END
GO

/* users: find locked accounts */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = N'IX_users_locked_until'
      AND object_id = OBJECT_ID(N'dbo.users')
)
BEGIN
    CREATE INDEX IX_users_locked_until
        ON dbo.users (locked_until)
        WHERE locked_until IS NOT NULL;
END
GO

/* ---- 9. DATA RETENTION: cleanup stored procedure ---- */
IF OBJECT_ID(N'dbo.sp_cleanup_expired_data', N'P') IS NOT NULL
    DROP PROCEDURE dbo.sp_cleanup_expired_data;
GO

CREATE PROCEDURE dbo.sp_cleanup_expired_data
    @history_retention_days INT = 365,
    @error_log_retention_days INT = 90,
    @cache_cleanup BIT = 1,
    @session_cleanup BIT = 1,
    @dry_run BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @cutoff_history DATETIME2 = DATEADD(DAY, -@history_retention_days, SYSUTCDATETIME());
    DECLARE @cutoff_errors DATETIME2 = DATEADD(DAY, -@error_log_retention_days, SYSUTCDATETIME());
    DECLARE @now DATETIME2 = SYSUTCDATETIME();

    DECLARE @deleted_history INT = 0;
    DECLARE @deleted_errors INT = 0;
    DECLARE @deleted_cache INT = 0;
    DECLARE @deleted_sessions INT = 0;

    IF @dry_run = 1
    BEGIN
        SELECT
            (SELECT COUNT(*) FROM dbo.normalization_history WHERE created_at < @cutoff_history) AS history_to_delete,
            (SELECT COUNT(*) FROM dbo.system_error_logs WHERE created_at < @cutoff_errors) AS errors_to_delete,
            (SELECT COUNT(*) FROM dbo.diacritic_cache WHERE expires_at IS NOT NULL AND expires_at < @now) AS cache_to_delete,
            CASE WHEN OBJECT_ID(N'dbo.user_sessions', N'U') IS NOT NULL
                THEN (SELECT COUNT(*) FROM dbo.user_sessions WHERE (expires_at < @now AND revoked_at IS NOT NULL) OR (is_active = 0 AND created_at < @cutoff_errors))
                ELSE 0
            END AS sessions_to_delete;
        RETURN;
    END

    /* Normalization history older than retention period */
    DELETE FROM dbo.normalization_history
    WHERE created_at < @cutoff_history;
    SET @deleted_history = @@ROWCOUNT;

    /* System error logs older than retention period */
    DELETE FROM dbo.system_error_logs
    WHERE created_at < @cutoff_errors;
    SET @deleted_errors = @@ROWCOUNT;

    /* Expired diacritic cache entries */
    IF @cache_cleanup = 1
    BEGIN
        DELETE FROM dbo.diacritic_cache
        WHERE expires_at IS NOT NULL AND expires_at < @now;
        SET @deleted_cache = @@ROWCOUNT;
    END

    /* Expired and revoked sessions */
    IF @session_cleanup = 1 AND OBJECT_ID(N'dbo.user_sessions', N'U') IS NOT NULL
    BEGIN
        DELETE FROM dbo.user_sessions
        WHERE (expires_at < @now AND revoked_at IS NOT NULL)
           OR (is_active = 0 AND created_at < @cutoff_errors);
        SET @deleted_sessions = @@ROWCOUNT;
    END

    SELECT
        @deleted_history AS deleted_history_rows,
        @deleted_errors AS deleted_error_log_rows,
        @deleted_cache AS deleted_cache_rows,
        @deleted_sessions AS deleted_session_rows,
        @cutoff_history AS history_cutoff_date,
        @cutoff_errors AS error_log_cutoff_date;
END
GO
