from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from .dsl import Program, assemble, execute
from .native import backend_info, score_matrix

_DEFAULT_PROGRAM = """
MOV K, $k
MOV P, $nprobe
QLOAD Q0, $query
QNORM Q0
COARSE C0, Q0, P
SCAN S0, C0, Q0
TOPK R0, S0, K
RET R0
"""


class ASMDB:
    def __init__(self, path: str | Path, *, backend="cpu", device=0):
        self.path = Path(path)
        self.manifest = json.loads((self.path / "manifest.json").read_text())
        self.dim = int(self.manifest["dim"])
        self.count = int(self.manifest["count"])
        self.n_clusters = int(self.manifest["n_clusters"])
        if (
            self.manifest.get("format") != "asmdb-1"
            or self.manifest.get("metric") != "cosine"
        ):
            raise ValueError("unsupported database format or metric")
        if self.count <= 0 or self.dim <= 0 or not 1 <= self.n_clusters <= self.count:
            raise ValueError("invalid database dimensions")
        sizes = {
            "vectors.f32": self.count * self.dim * 4,
            "ids.i64": self.count * 8,
            "centroids.f32": self.n_clusters * self.dim * 4,
            "offsets.i64": (self.n_clusters + 1) * 8,
        }
        for name, size in sizes.items():
            if (self.path / name).stat().st_size != size:
                raise ValueError(f"invalid size: {name}")
        self._closed = False
        self._gpu = None
        if backend not in {"cpu", "opencl"}:
            raise ValueError("backend must be cpu or opencl")
        self.backend = backend
        self.vectors = np.memmap(
            self.path / "vectors.f32",
            dtype=np.float32,
            mode="r",
            shape=(self.count, self.dim),
        )
        self.ids = np.memmap(
            self.path / "ids.i64", dtype=np.int64, mode="r", shape=(self.count,)
        )
        self.centroids = np.fromfile(
            self.path / "centroids.f32", dtype=np.float32
        ).reshape(self.n_clusters, self.dim)
        self.offsets = np.fromfile(self.path / "offsets.i64", dtype=np.int64)
        if (
            self.offsets[0] != 0
            or self.offsets[-1] != self.count
            or np.any(self.offsets < 0)
            or np.any(self.offsets > self.count)
            or np.any(np.diff(self.offsets) < 0)
        ):
            raise ValueError("invalid posting offsets")
        if not np.isfinite(self.centroids).all():
            raise ValueError("invalid centroids")
        if backend == "opencl":
            from .gpu import GPUScorer

            self._gpu = GPUScorer(device)
        meta_path = self.path / "metadata.jsonl"
        self.metadata = None
        if meta_path.exists():
            self.metadata = [
                json.loads(x)
                for x in meta_path.read_text(encoding="utf-8").splitlines()
                if x.strip()
            ]
            if len(self.metadata) != self.count:
                raise ValueError("metadata length mismatch")
            self._meta_by_id = {int(m["_id"]): m for m in self.metadata}

    @staticmethod
    def _normalize_rows(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float32)
        n = np.linalg.norm(x.astype(np.float64), axis=1, keepdims=True)
        n[n == 0] = 1.0
        return (x / n).astype(np.float32)

    @classmethod
    def build(
        cls,
        path: str | Path,
        vectors,
        ids=None,
        metadata=None,
        n_clusters=64,
        kmeans_iters=4,
        seed=123,
    ):
        path = Path(path)
        raw = np.asarray(vectors, dtype=np.float32)
        if raw.ndim != 2 or not all(raw.shape) or not np.isfinite(raw).all():
            raise ValueError("vectors must be a nonempty finite 2D matrix")
        x = cls._normalize_rows(raw)
        n, dim = x.shape
        if ids is None:
            ids = np.arange(n, dtype=np.int64)
        original_ids = np.asarray(ids)
        if original_ids.dtype.kind not in "iu" or (
            original_ids.dtype.kind == "u"
            and np.any(original_ids > np.iinfo(np.int64).max)
        ):
            raise ValueError("ids must be signed 64-bit integer values")
        ids = np.asarray(ids, dtype=np.int64)
        if ids.shape != (n,) or np.unique(ids).size != n:
            raise ValueError("ids length mismatch")
        if metadata is not None:
            if len(metadata) != n:
                raise ValueError("metadata length mismatch")
            metadata = [dict(row, _id=int(oid)) for oid, row in zip(ids, metadata)]
            metadata_text = "".join(
                json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n"
                for row in metadata
            )
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            raise FileExistsError(f"database destination is not empty: {path}")
        if int(n_clusters) < 1 or int(kmeans_iters) < 1:
            raise ValueError("cluster and iteration counts must be positive")
        n_clusters = max(1, min(int(n_clusters), n))
        rng = np.random.default_rng(seed)
        centers = x[rng.choice(n, n_clusters, replace=False)].copy()
        labels = np.zeros(n, dtype=np.int32)
        for _ in range(max(1, int(kmeans_iters))):
            for s in range(0, n, 8192):
                e = min(n, s + 8192)
                labels[s:e] = np.argmax(x[s:e] @ centers.T, axis=1)
            new = np.zeros_like(centers)
            counts = np.bincount(labels, minlength=n_clusters)
            np.add.at(new, labels, x)
            nz = counts > 0
            new[nz] /= counts[nz, None]
            if (~nz).any():
                new[~nz] = x[rng.choice(n, (~nz).sum(), replace=False)]
            centers = cls._normalize_rows(new)
        order = np.argsort(labels, kind="stable")
        x2 = np.ascontiguousarray(x[order])
        ids2 = np.ascontiguousarray(ids[order])
        counts = np.bincount(labels, minlength=n_clusters).astype(np.int64)
        offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
        manifest = {
            "format": "asmdb-1",
            "count": int(n),
            "dim": int(dim),
            "n_clusters": int(n_clusters),
            "metric": "cosine",
            "layout": "cluster_contiguous_f32",
            "normalized": True,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{path.name}-", dir=path.parent))
        try:
            x2.tofile(staging / "vectors.f32")
            ids2.tofile(staging / "ids.i64")
            centers.tofile(staging / "centroids.f32")
            offsets.tofile(staging / "offsets.i64")
            (staging / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            if metadata is not None:
                (staging / "metadata.jsonl").write_text(metadata_text, encoding="utf-8")
            for file in staging.iterdir():
                with file.open("r+b") as stream:
                    os.fsync(stream.fileno())
            if path.exists():
                path.rmdir()
            os.replace(staging, path)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return cls(path)

    def _prepare_query(self, query, normalize=True):
        q = np.asarray(query, dtype=np.float32).reshape(-1)
        if not np.isfinite(q).all():
            raise ValueError("query must contain finite values")
        if q.size != self.dim:
            raise ValueError(f"expected query dim={self.dim}, got {q.size}")
        return self._normalize_query(q) if normalize else q

    def _normalize_query(self, q):
        q = np.ascontiguousarray(q, dtype=np.float32)
        n = float(np.linalg.norm(q.astype(np.float64)))
        return q if n == 0 else (q.astype(np.float64) / n).astype(np.float32)

    def _coarse(self, q, nprobe):
        nprobe = max(1, min(int(nprobe), self.n_clusters))
        s = self.centroids @ q
        idx = np.argpartition(s, -nprobe)[-nprobe:]
        return idx[np.argsort(s[idx])[::-1]]

    def _scan(self, cluster_ids, q):
        if self._gpu is not None:
            indices = np.concatenate(
                [np.arange(self.offsets[c], self.offsets[c + 1]) for c in cluster_ids]
            )
            return np.asarray(self.ids[indices]), self._gpu.score(
                self.vectors[indices], q
            )
        ids_parts, score_parts = [], []
        for c in cluster_ids:
            s, e = int(self.offsets[c]), int(self.offsets[c + 1])
            if e <= s:
                continue
            score_parts.append(score_matrix(self.vectors[s:e], q))
            ids_parts.append(np.asarray(self.ids[s:e]))
        if not score_parts:
            return (np.empty(0, np.int64), np.empty(0, np.float32))
        return (np.concatenate(ids_parts), np.concatenate(score_parts))

    def _topk(self, pair, k):
        ids, scores = pair
        k = min(max(0, int(k)), len(scores))
        if k == 0:
            return []
        idx = np.argpartition(scores, -k)[-k:]
        idx = idx[np.argsort(scores[idx])[::-1]]
        out = []
        for i in idx:
            item = {"id": int(ids[i]), "score": float(scores[i])}
            if self.metadata is not None:
                item["metadata"] = self._meta_by_id.get(int(ids[i]), {})
            out.append(item)
        return out

    def _filter_results(self, results, expr: str):
        if self.metadata is None:
            return results
        if ":" not in expr:
            raise ValueError("filter expression must be key:value")
        key, value = expr.split(":", 1)
        return [r for r in results if str(r.get("metadata", {}).get(key)) == value]

    def search(self, query, k=10, nprobe=2, program: str | Program | None = None):
        if self._closed:
            raise RuntimeError("database is closed")
        p = (
            assemble(program or _DEFAULT_PROGRAM)
            if isinstance(program, str) or program is None
            else program
        )
        return execute(p, self, query=query, k=k, nprobe=nprobe)

    def info(self):
        if self._gpu is not None:
            return {
                **self.manifest,
                "backend": "opencl",
                "native": True,
                "device": self._gpu.device.name,
                "dispatch": "NASM",
                "kernel": "OpenCL C 1.2",
            }
        b = backend_info()
        return {
            **self.manifest,
            "backend": b.name,
            "native": b.native,
            "backend_reason": b.reason,
        }

    def close(self):
        if getattr(self, "_closed", True):
            return
        if self._gpu is not None:
            self._gpu.close()
        for name in ("vectors", "ids"):
            array = getattr(self, name, None)
            if array is not None:
                array._mmap.close()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        self.close()
