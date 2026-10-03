import tempfile
import unittest

import numpy as np

from asmdb import ASMDB, assemble
from asmdb.native import score_matrix


class TestASMDB(unittest.TestCase):
    def test_native_scores(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=(37, 67)).astype(np.float32)
        q = rng.normal(size=67).astype(np.float32)
        got = score_matrix(x, q)
        ref = x @ q
        np.testing.assert_allclose(got, ref, rtol=2e-5, atol=2e-5)

    def test_search_and_dsl(self):
        rng = np.random.default_rng(2)
        x = rng.normal(size=(1000, 32)).astype(np.float32)
        with tempfile.TemporaryDirectory() as td:
            db = ASMDB.build(td, x, n_clusters=16, kmeans_iters=2)
            prog = assemble(
                """MOV K, 4\nMOV P, 16\nQLOAD Q0, $query\nQNORM Q0\nCOARSE C0, Q0, P\nSCAN S0, C0, Q0\nTOPK R0, S0, K\nRET R0"""
            )
            got = db.search(x[5], program=prog)
            self.assertEqual(got[0]["id"], 5)
            db.close()


if __name__ == "__main__":
    unittest.main()
