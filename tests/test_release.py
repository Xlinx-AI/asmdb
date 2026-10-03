import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import numpy as np

from asmdb import ASMDB
from asmdb.native import _candidate_names, backend_info, score_matrix


class ReleaseTests(unittest.TestCase):
    def test_concurrent_search(self):
        matrix = np.random.default_rng(12).normal(size=(101, 17)).astype(np.float32)
        with tempfile.TemporaryDirectory() as td:
            with ASMDB.build(Path(td) / "db", matrix, n_clusters=8) as db:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(
                        pool.map(
                            lambda index: db.search(matrix[index], nprobe=8)[0]["id"],
                            range(20),
                        )
                    )
                self.assertEqual(results, list(range(20)))

    def test_native_tails(self):
        self.assertTrue(backend_info().native)
        rng = np.random.default_rng(91)
        for dim in (0, 1, 3, 7, 8, 9, 15, 16, 17, 31, 32, 33, 67, 128, 769):
            for rows in (0, 1, 37):
                matrix = rng.normal(size=(rows, dim)).astype(np.float32)
                query = rng.normal(size=dim).astype(np.float32)
                np.testing.assert_allclose(
                    score_matrix(matrix, query), matrix @ query, atol=8e-5, rtol=8e-5
                )

    def test_unsafe_backend(self):
        with patch("asmdb.native._cpu_features", return_value={"avx", "sse3"}):
            for name in ("x64_avx2_sse4", "x64_avx512_sse41", "invalid"):
                with patch.dict(os.environ, ASMDB_BACKEND=name):
                    with self.assertRaises(ValueError):
                        _candidate_names()

    def test_invalid_vectors(self):
        for matrix in ([], [1, 2], np.empty((0, 3)), [[np.nan]], [[np.inf]]):
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaises(ValueError):
                    ASMDB.build(Path(td) / "db", matrix)
                self.assertFalse((Path(td) / "db").exists())

    def test_ids_and_large_norms(self):
        with tempfile.TemporaryDirectory() as td:
            for ids in ([1, 1], [1.5, 2.5], np.array([0, 2**63], dtype=np.uint64)):
                with self.assertRaises(ValueError):
                    ASMDB.build(Path(td) / "invalid", np.ones((2, 2)), ids=ids)
            with ASMDB.build(
                Path(td) / "db",
                np.array([[3e38, 3e38], [1, 0]], dtype=np.float32),
                n_clusters=1,
            ) as db:
                result = db.search([3e38, 3e38], nprobe=1)
                self.assertEqual(result[0]["id"], 0)
                self.assertAlmostEqual(result[0]["score"], 1.0, places=5)

    def test_storage_and_lifecycle(self):
        rng = np.random.default_rng(10)
        matrix = rng.normal(size=(101, 17)).astype(np.float32)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "db"
            with ASMDB.build(
                path, matrix, metadata=[{"tag": "Кирилл"}] * 101, n_clusters=8
            ) as db:
                rows = db.search(matrix[19], nprobe=8)
                self.assertEqual(rows[0]["id"], 19)
                self.assertEqual(rows[0]["metadata"]["tag"], "Кирилл")
                with self.assertRaises(FileExistsError):
                    ASMDB.build(path, matrix)
                with self.assertRaises(ValueError):
                    db.search(np.full(17, np.nan))
            with self.assertRaises(RuntimeError):
                db.search(matrix[0])
            offsets = np.fromfile(path / "offsets.i64", dtype=np.int64)
            offsets[-1] = 999
            offsets.tofile(path / "offsets.i64")
            with self.assertRaises(ValueError):
                ASMDB(path)

    @unittest.skipUnless(
        os.environ.get("ASMDB_TEST_GPU") == "1", "GPU checks require ASMDB_TEST_GPU=1"
    )
    def test_gpu(self):
        from asmdb.gpu import GPUScorer, devices

        rng = np.random.default_rng(11)
        for device in range(len(devices())):
            with GPUScorer(device) as scorer:
                for dim in (0, 1, 3, 7, 32, 67, 128, 769):
                    matrix = rng.normal(size=(37, dim)).astype(np.float32)
                    query = rng.normal(size=dim).astype(np.float32)
                    np.testing.assert_allclose(
                        scorer.score(matrix, query),
                        matrix @ query,
                        atol=8e-5,
                        rtol=8e-5,
                    )
                    matrix *= 2
                    np.testing.assert_allclose(
                        scorer.score(matrix, query),
                        matrix @ query,
                        atol=8e-5,
                        rtol=8e-5,
                    )
                    matrix.flags.writeable = False
                    for _ in range(2):
                        np.testing.assert_allclose(
                            scorer.score(matrix, query),
                            matrix @ query,
                            atol=8e-5,
                            rtol=8e-5,
                        )
            with self.assertRaises(RuntimeError):
                scorer.score(np.ones((1, 1)), np.ones(1))
            with tempfile.TemporaryDirectory() as td:
                matrix = rng.normal(size=(101, 17)).astype(np.float32)
                ASMDB.build(Path(td) / "db", matrix, n_clusters=8).close()
                with ASMDB(Path(td) / "db", backend="opencl", device=device) as db:
                    self.assertEqual(db.search(matrix[19], nprobe=8)[0]["id"], 19)


if __name__ == "__main__":
    unittest.main()
