import unittest

from app.config import Settings
from app.data_manager.db import build_odbc_connection_string, build_server_name


class DatabaseConfigTests(unittest.TestCase):
    def test_build_server_name_for_sqlexpress(self):
        settings = Settings(sql_mode="sqlexpress", sql_host="localhost", sql_instance="SQLEXPRESS")
        self.assertEqual(build_server_name(settings), "localhost\\SQLEXPRESS")

    def test_build_server_name_for_localdb(self):
        settings = Settings(sql_mode="localdb", sql_instance="MSSQLLocalDB")
        self.assertEqual(build_server_name(settings), "(localdb)\\MSSQLLocalDB")

    def test_build_odbc_connection_string_for_sqlexpress(self):
        settings = Settings(
            sql_mode="sqlexpress",
            sql_auth="sql",
            sql_host="localhost",
            sql_instance="SQLEXPRESS",
            sql_database="VietNormalizer",
            sql_username="normalizer_app",
            sql_password="secret",
        )
        conn = build_odbc_connection_string(settings)
        self.assertIn("SERVER=localhost\\SQLEXPRESS", conn)
        self.assertIn("UID=normalizer_app", conn)
        self.assertIn("PWD=secret", conn)

    def test_build_odbc_connection_string_for_sqlexpress_windows_auth(self):
        settings = Settings(
            sql_mode="sqlexpress",
            sql_auth="windows",
            sql_host="DESKTOP-75UB0LS",
            sql_instance="SQLEXPRESS",
            sql_database="VietNormalizer",
        )

        conn = build_odbc_connection_string(settings)

        self.assertIn("SERVER=DESKTOP-75UB0LS\\SQLEXPRESS", conn)
        self.assertIn("Trusted_Connection=yes", conn)
        self.assertNotIn("UID=", conn)
        self.assertNotIn("PWD=", conn)

    def test_build_odbc_connection_string_includes_encrypt_setting(self):
        settings = Settings(
            sql_mode="sqlexpress",
            sql_host="localhost",
            sql_instance="SQLEXPRESS",
            sql_database="VietNormalizer",
            sql_username="normalizer_app",
            sql_password="secret",
            sql_encrypt="no",
        )

        conn = build_odbc_connection_string(settings)

        self.assertIn("Encrypt=no", conn)

    def test_build_odbc_connection_string_for_localdb(self):
        settings = Settings(
            sql_mode="localdb", sql_instance="MSSQLLocalDB", sql_database="VietNormalizer"
        )
        conn = build_odbc_connection_string(settings)
        self.assertIn("SERVER=(localdb)\\MSSQLLocalDB", conn)
        self.assertIn("Trusted_Connection=yes", conn)


if __name__ == "__main__":
    unittest.main()
