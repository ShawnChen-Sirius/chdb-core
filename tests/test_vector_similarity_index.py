#!python3
"""Guard tests for the HNSW vector-similarity (ANN) index.

The `vector_similarity` secondary index (ClickHouse's only ANN index, backed by
USearch) was not compiled into chdb: ENABLE_USEARCH/ENABLE_SIMSIMD were never
opted in, so the index type was unregistered and every CREATE ... TYPE
vector_similarity failed with Code 80 "Unknown Index type". The build scripts
now pass -DENABLE_USEARCH=1 -DENABLE_SIMSIMD=1 on all platforms.

These tests exercise the index end-to-end (create -> insert -> ANN search) and
assert it is registered, accepts the supported method/distance signatures, and
returns the correct nearest neighbours. They run in a stateful Session because
the index lives on a MergeTree table.

The lite variant intentionally drops USearch, so the class is skipped under
CHDB_LITE=1.
"""

import os
import shutil
import tempfile
import unittest

from chdb import session as chs


class TestVectorSimilarityIndex(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("CHDB_LITE") == "1":
            raise unittest.SkipTest("USearch/vector_similarity is intentionally absent in chdb-core-lite")

    def setUp(self):
        self._path = tempfile.mkdtemp(prefix="chdb_vec_")
        self.s = chs.Session(self._path)
        # The index is gated behind an experimental flag in ClickHouse.
        self.s.query("SET allow_experimental_vector_similarity_index = 1")

    def tearDown(self):
        try:
            self.s.close()
        finally:
            shutil.rmtree(self._path, ignore_errors=True)

    def _csv(self, sql):
        return str(self.s.query(sql, "CSV")).strip()

    def test_vector_similarity_index_type_is_registered(self):
        # The whole point of enabling USearch: the index type must exist.
        # Before the fix this raised Code 80 "Unknown Index type 'vector_similarity'".
        self.s.query(
            """
            CREATE TABLE reg (id UInt32, v Array(Float32),
                INDEX idx v TYPE vector_similarity('hnsw', 'L2Distance', 2))
            ENGINE = MergeTree ORDER BY id
            """
        )
        # It must show up as a real data-skipping index on the table.
        # CSV wraps string values in double quotes; strip them for the compare.
        self.assertEqual(
            "vector_similarity",
            self._csv(
                "SELECT type FROM system.data_skipping_indices "
                "WHERE table = 'reg' AND name = 'idx'"
            ).strip('"'),
        )

    def test_hnsw_l2_returns_correct_nearest_neighbours(self):
        self.s.query(
            """
            CREATE TABLE vec_l2 (id UInt32, v Array(Float32),
                INDEX idx v TYPE vector_similarity('hnsw', 'L2Distance', 2) GRANULARITY 2)
            ENGINE = MergeTree ORDER BY id
            """
        )
        # id -> point. Nearest to (0.2, 0.2): id 1 (0,0) then id 2 (1,1).
        self.s.query(
            "INSERT INTO vec_l2 VALUES "
            "(1, [0.0, 0.0]), (2, [1.0, 1.0]), (3, [5.0, 5.0]), "
            "(4, [10.0, 10.0]), (5, [2.5, 2.5])"
        )
        out = self._csv(
            "SELECT id FROM vec_l2 ORDER BY L2Distance(v, [0.2, 0.2]) ASC LIMIT 2"
        )
        self.assertEqual("1\n2", out, "HNSW/L2 nearest-neighbour order is wrong")

    def test_hnsw_cosine_returns_correct_nearest_neighbours(self):
        self.s.query(
            """
            CREATE TABLE vec_cos (id UInt32, v Array(Float32),
                INDEX idx v TYPE vector_similarity('hnsw', 'cosineDistance', 2) GRANULARITY 2)
            ENGINE = MergeTree ORDER BY id
            """
        )
        # Cosine distance is direction-based. Query direction ~ (1, 0.05).
        # id 1 points along (1, 0) -> closest; id 3 along (0, 1) -> farthest.
        self.s.query(
            "INSERT INTO vec_cos VALUES "
            "(1, [1.0, 0.0]), (2, [1.0, 1.0]), (3, [0.0, 1.0])"
        )
        out = self._csv(
            "SELECT id FROM vec_cos ORDER BY cosineDistance(v, [1.0, 0.05]) ASC LIMIT 1"
        )
        self.assertEqual("1", out, "HNSW/cosine nearest-neighbour is wrong")

    def test_six_arg_signature_with_quantization(self):
        # 6-arg form: method, distance, dims, quantization, max_connections, ef_construction.
        self.s.query(
            """
            CREATE TABLE vec6 (id UInt32, v Array(Float32),
                INDEX idx v TYPE vector_similarity('hnsw', 'L2Distance', 2, 'f16', 16, 64))
            ENGINE = MergeTree ORDER BY id
            """
        )
        self.s.query("INSERT INTO vec6 VALUES (1, [0.0, 0.0]), (2, [9.0, 9.0])")
        self.assertEqual(
            "1",
            self._csv("SELECT id FROM vec6 ORDER BY L2Distance(v, [0.1, 0.1]) ASC LIMIT 1"),
        )

    def test_unsupported_method_is_rejected_cleanly(self):
        # Proves the validator is wired (not a "not compiled in" Code 80).
        with self.assertRaises(Exception) as ctx:
            self.s.query(
                "CREATE TABLE bad (id UInt32, v Array(Float32), "
                "INDEX idx v TYPE vector_similarity('ivfflat', 'L2Distance', 2)) "
                "ENGINE = MergeTree ORDER BY id"
            )
        msg = str(ctx.exception)
        self.assertNotIn("Unknown Index type", msg)
        self.assertIn("method", msg.lower())


if __name__ == "__main__":
    unittest.main()
