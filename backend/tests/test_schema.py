import unittest
from pathlib import Path


class SchemaTests(unittest.TestCase):
    def test_init_schema_contains_core_tables_and_indexes(self):
        schema_path = Path(__file__).resolve().parent.parent / "database" / "init_schema.sql"
        content = schema_path.read_text(encoding="utf-8")

        required_snippets = [
            "SET ANSI_NULLS ON",
            "SET QUOTED_IDENTIFIER ON",
            "SET NUMERIC_ROUNDABORT OFF",
            # Core tables (v1)
            "CREATE TABLE dbo.abbreviations",
            "CREATE TABLE dbo.abbreviation_pending",
            "CREATE TABLE dbo.user_abbreviation_overrides",
            "CREATE TABLE dbo.normalization_history",
            "CREATE TABLE dbo.diacritic_cache",
            "CREATE TABLE dbo.users",
            "CREATE TABLE dbo.roles",
            "CREATE TABLE dbo.annotation_data",
            # v2 tables
            "CREATE TABLE dbo.user_sessions",
            "CREATE TABLE dbo.user_preferences",
            "CREATE TABLE dbo.phrase_overrides",
            "CREATE TABLE dbo.abbreviation_usage_stats",
            # Core indexes (v1)
            "CREATE UNIQUE INDEX UX_abbreviations_active_abbr_domain",
            "CREATE INDEX IX_abbreviation_pending_status_created_at",
            "CREATE INDEX IX_abbreviation_pending_abbr_domain_status",
            "CREATE UNIQUE INDEX UX_user_abbreviation_overrides_active_user_abbr_domain",
            "CREATE INDEX IX_user_abbreviation_overrides_user_domain_abbr",
            # v2 indexes
            "CREATE INDEX IX_user_sessions_token_hash",
            "CREATE INDEX IX_abbreviation_audit_log_created_at",
            "CREATE INDEX IX_system_error_logs_module_created_at",
            "CREATE INDEX IX_annotation_data_domain_split_set",
            "CREATE INDEX IX_diacritic_cache_expires_at",
            # v2 column additions
            "last_login_at DATETIME2 NULL",
            "failed_login_attempts INT NOT NULL DEFAULT 0",
            "locked_until DATETIME2 NULL",
            "input_method NVARCHAR(20) NULL",
            "character_count INT NULL",
            # Columns
            "alternative_expansions_json NVARCHAR(MAX) NULL",
            "suggested_meanings_json NVARCHAR(MAX) NULL",
            # Retention stored procedure
            "CREATE PROCEDURE dbo.sp_cleanup_expired_data",
        ]

        for snippet in required_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, content)

    def test_init_schema_does_not_seed_demo_accounts(self):
        """Demo logins must not ship with the schema every environment runs.

        Their passwords are published in this repository, so creating them from
        init_schema.sql meant any deployment came with a known admin account.
        """
        schema_path = Path(__file__).resolve().parent.parent / "database" / "init_schema.sql"
        content = schema_path.read_text(encoding="utf-8")

        self.assertNotIn("INSERT INTO dbo.users", content)
        for account in ("admin_main", "demo_user_01", "demo_user_02"):
            self.assertNotIn(f"N'{account}'", content)

    def test_demo_seed_script_exists_and_creates_the_demo_accounts(self):
        seed_path = Path(__file__).resolve().parent.parent / "database" / "seed_demo.sql"
        content = seed_path.read_text(encoding="utf-8")

        for account in ("admin_main", "demo_user_01", "demo_user_02"):
            self.assertIn(account, content)
        self.assertIn("INSERT INTO dbo.user_roles", content)


if __name__ == "__main__":
    unittest.main()
