/*
    VietNormalizer - DEVELOPMENT / DEMO accounts ONLY
    =================================================
    Run this AFTER init_schema.sql, and ONLY on a development or demo database.

These accounts use passwords that are published in this repository, so any
    environment reachable by other people must NOT run this script. The backend
    transparently upgrades these legacy SHA-256 hashes to bcrypt on first login.

        sqlcmd -S "<SERVER>" -d VietNormalizer -E -I -i backend\database\seed_demo.sql

    To remove them again:

        UPDATE dbo.users SET is_active = 0
        WHERE username IN (N'admin_main', N'demo_user_01', N'demo_user_02');
*/

/*
    Deterministic abbreviation fixtures used by the E2E workspace flow.
    Keep these in the opt-in demo seed so production databases do not receive
    test/demo meanings accidentally.
*/

SET ANSI_NULLS ON
GO

IF NOT EXISTS (
    SELECT 1 FROM dbo.abbreviations
    WHERE abbr = N'đk' AND domain = N'general' AND is_active = 1
)
BEGIN
    INSERT INTO dbo.abbreviations (
        id, abbr, expanded, alternative_expansions_json, domain, source,
        approved, is_active, created_at, updated_at, approved_at, approved_by
    )
    VALUES (
        NEWID(), N'đk', N'đăng ký', N'["đúng không"]', N'general', N'demo_seed',
        1, 1, SYSUTCDATETIME(), SYSUTCDATETIME(), SYSUTCDATETIME(), N'system_seed'
    )
END
GO

IF NOT EXISTS (
    SELECT 1 FROM dbo.abbreviations
    WHERE abbr = N'pk' AND domain = N'general' AND is_active = 1
)
BEGIN
    INSERT INTO dbo.abbreviations (
        id, abbr, expanded, alternative_expansions_json, domain, source,
        approved, is_active, created_at, updated_at, approved_at, approved_by
    )
    VALUES (
        NEWID(), N'pk', N'phải không', N'[]', N'general', N'demo_seed',
        1, 1, SYSUTCDATETIME(), SYSUTCDATETIME(), SYSUTCDATETIME(), N'system_seed'
    )
END
GO
SET QUOTED_IDENTIFIER ON
GO

/*
    ============================================================
    DEMO / DEV LOGIN ACCOUNTS
    ============================================================
    Muc dich:
    - Seed san tai khoan admin va user de phuc vu login UX/UI sau nay.
    - Script nay la idempotent: chay lai khong can drop bang.
    - Mat khau demo duoc hash bang SHA2_256 ngay trong SQL.

    Tai khoan demo hien tai:
    1. admin_main
       email    : admin@vietnormalizer.local
       password : Admin@123

    2. demo_user_01
       email    : user01@vietnormalizer.local
       password : User@123

    3. demo_user_02
       email    : user02@vietnormalizer.local
       password : User@456

    Luu y:
    - Day la tai khoan seed cho moi truong dev/demo.
    - Khi lam auth that, nen doi sang bcrypt/argon2 thay vi SHA2_256.
*/

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = N'admin_main')
BEGIN
    INSERT INTO dbo.users (
        id,
        username,
        email,
        password_hash,
        is_active,
        created_at,
        updated_at
    )
    VALUES (
        NEWID(),
        N'admin_main',
        N'admin@vietnormalizer.local',
        CONVERT(NVARCHAR(256), HASHBYTES('SHA2_256', CONVERT(VARBINARY(4000), N'Admin@123')), 2),
        1,
        SYSUTCDATETIME(),
        SYSUTCDATETIME()
    )
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = N'demo_user_01')
BEGIN
    INSERT INTO dbo.users (
        id,
        username,
        email,
        password_hash,
        is_active,
        created_at,
        updated_at
    )
    VALUES (
        NEWID(),
        N'demo_user_01',
        N'user01@vietnormalizer.local',
        CONVERT(NVARCHAR(256), HASHBYTES('SHA2_256', CONVERT(VARBINARY(4000), N'User@123')), 2),
        1,
        SYSUTCDATETIME(),
        SYSUTCDATETIME()
    )
END
GO

IF NOT EXISTS (SELECT 1 FROM dbo.users WHERE username = N'demo_user_02')
BEGIN
    INSERT INTO dbo.users (
        id,
        username,
        email,
        password_hash,
        is_active,
        created_at,
        updated_at
    )
    VALUES (
        NEWID(),
        N'demo_user_02',
        N'user02@vietnormalizer.local',
        CONVERT(NVARCHAR(256), HASHBYTES('SHA2_256', CONVERT(VARBINARY(4000), N'User@456')), 2),
        1,
        SYSUTCDATETIME(),
        SYSUTCDATETIME()
    )
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.user_roles ur
    INNER JOIN dbo.users u ON u.id = ur.user_id
    INNER JOIN dbo.roles r ON r.id = ur.role_id
    WHERE u.username = N'admin_main' AND r.role_name = N'admin'
)
BEGIN
    INSERT INTO dbo.user_roles (user_id, role_id, assigned_at, assigned_by)
    SELECT u.id, r.id, SYSUTCDATETIME(), N'system_seed'
    FROM dbo.users u
    CROSS JOIN dbo.roles r
    WHERE u.username = N'admin_main'
      AND r.role_name = N'admin';
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.user_roles ur
    INNER JOIN dbo.users u ON u.id = ur.user_id
    INNER JOIN dbo.roles r ON r.id = ur.role_id
    WHERE u.username = N'demo_user_01' AND r.role_name = N'user'
)
BEGIN
    INSERT INTO dbo.user_roles (user_id, role_id, assigned_at, assigned_by)
    SELECT u.id, r.id, SYSUTCDATETIME(), N'system_seed'
    FROM dbo.users u
    CROSS JOIN dbo.roles r
    WHERE u.username = N'demo_user_01'
      AND r.role_name = N'user';
END
GO

IF NOT EXISTS (
    SELECT 1
    FROM dbo.user_roles ur
    INNER JOIN dbo.users u ON u.id = ur.user_id
    INNER JOIN dbo.roles r ON r.id = ur.role_id
    WHERE u.username = N'demo_user_02' AND r.role_name = N'user'
)
BEGIN
    INSERT INTO dbo.user_roles (user_id, role_id, assigned_at, assigned_by)
    SELECT u.id, r.id, SYSUTCDATETIME(), N'system_seed'
    FROM dbo.users u
    CROSS JOIN dbo.roles r
    WHERE u.username = N'demo_user_02'
      AND r.role_name = N'user';
END
GO
