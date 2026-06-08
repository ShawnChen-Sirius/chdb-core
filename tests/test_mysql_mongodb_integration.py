#!python3
"""Guard tests for the MySQL and MongoDB integrations.

chdb historically shipped without MySQL (disabled on macOS by a 2023 build
workaround) and without MongoDB (never opted in). These were re-enabled in the
build scripts (chdb/build*.sh: ENABLE_MYSQL on all platforms, USE_MONGODB,
ENABLE_USEARCH/ENABLE_SIMSIMD). See issue #82.

These tests assert the integrations are *compiled in*, without needing a live
MySQL/MongoDB server:
  1. the mysql()/mongodb() table functions are registered,
  2. the MySQL table engine, MySQL database engine and MongoDB table engine
     are registered,
  3. invoking them against an unreachable address fails with a runtime
     (connection / argument) error -- NOT a "not compiled in" error
     (Code 46 UNKNOWN_FUNCTION / Code 56 UNKNOWN_STORAGE /
     Code 336 UNKNOWN_DATABASE_ENGINE).

The lite variant intentionally drops these, so the whole class is skipped when
CHDB_LITE=1.
"""

import os
import unittest

import chdb


# Error fragments that mean "the feature was not compiled into this build".
# If we see any of these, the integration is genuinely missing -> test fails.
_NOT_COMPILED_MARKERS = (
    "Code: 46",   # UNKNOWN_FUNCTION (table function not registered)
    "Code: 56",   # UNKNOWN_STORAGE (table engine not registered)
    "Code: 336",  # UNKNOWN_DATABASE_ENGINE
    "Unknown table function",
    "Unknown table engine",
    "Unknown database engine",
)


class TestMySQLMongoDBIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("CHDB_LITE") == "1":
            raise unittest.SkipTest("MySQL/MongoDB are intentionally absent in chdb-core-lite")

    def _count(self, sql):
        # query() returns e.g. '1\n'; parse the single scalar.
        return int(str(chdb.query(sql, "CSV")).strip())

    # ---- registration: table functions ---------------------------------

    def test_mysql_table_function_registered(self):
        self.assertEqual(
            1, self._count("SELECT count() FROM system.table_functions WHERE name = 'mysql'"),
            "mysql() table function is not registered -- MySQL was not compiled in",
        )

    def test_mongodb_table_function_registered(self):
        self.assertEqual(
            1, self._count("SELECT count() FROM system.table_functions WHERE name = 'mongodb'"),
            "mongodb() table function is not registered -- MongoDB was not compiled in",
        )

    # ---- registration: storage / database engines ----------------------

    def test_mysql_table_engine_registered(self):
        self.assertEqual(
            1, self._count("SELECT count() FROM system.table_engines WHERE name = 'MySQL'"),
            "MySQL table engine is not registered",
        )

    def test_mysql_database_engine_registered(self):
        self.assertEqual(
            1, self._count("SELECT count() FROM system.database_engines WHERE name = 'MySQL'"),
            "MySQL database engine is not registered",
        )

    def test_mongodb_table_engine_registered(self):
        self.assertEqual(
            1, self._count("SELECT count() FROM system.table_engines WHERE name = 'MongoDB'"),
            "MongoDB table engine is not registered",
        )

    # ---- proves wired: runtime error, not a "missing feature" error ----

    def _assert_runtime_not_missing(self, sql):
        """The statement must raise, and the error must NOT be a
        'not compiled in' error -- proving the integration is present and
        merely failing to reach the (unreachable) server / validate args."""
        with self.assertRaises(Exception) as ctx:
            chdb.query(sql)
        msg = str(ctx.exception)
        for marker in _NOT_COMPILED_MARKERS:
            self.assertNotIn(
                marker, msg,
                f"got a 'not compiled in' error ({marker!r}) for {sql!r}: {msg[:200]}",
            )

    def test_mysql_table_function_invocable(self):
        # 127.0.0.1:1 refuses immediately -> connection error, not UNKNOWN_FUNCTION.
        self._assert_runtime_not_missing(
            "SELECT * FROM mysql('127.0.0.1:1', 'db', 'tbl', 'user', 'pass')"
        )

    def test_mongodb_table_function_invocable(self):
        self._assert_runtime_not_missing(
            "SELECT * FROM mongodb('127.0.0.1:1', 'db', 'coll', 'user', 'pass', 'id Int32')"
        )


if __name__ == "__main__":
    unittest.main()
