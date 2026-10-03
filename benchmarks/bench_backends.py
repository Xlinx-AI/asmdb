from __future__ import annotations

import ctypes
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from asmdb.native import _candidate_names, _lib_paths

    rng = np.random.default_rng(123)
    x = np.ascontiguousarray(rng.normal(size=(4096, 128)).astype(np.float32))
    q = np.ascontiguousarray(rng.normal(size=128).astype(np.float32))
    ref = x @ q
    rows, dim = x.shape
    result = {}
    for name in _candidate_names():
        p = next((path for path in _lib_paths(name) if path.exists()), None)
        if p is None:
            continue
        lib = ctypes.CDLL(str(p))
        f = lib.asmdb_scores
        f.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_float),
        ]
        f.restype = None
        out = np.empty(rows, np.float32)
        args = (
            x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            q.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            rows,
            dim,
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
        for _ in range(10):
            f(*args)
        ts = []
        for _ in range(100):
            t = time.perf_counter_ns()
            f(*args)
            ts.append((time.perf_counter_ns() - t) / 1e6)
        result[name] = {
            "median_ms": float(np.median(ts)),
            "mean_ms": float(np.mean(ts)),
            "p95_ms": float(np.percentile(ts, 95)),
            "max_abs_error": float(np.max(np.abs(out - ref))),
        }
    payload = {
        "platform": platform.platform(),
        "matrix_shape": [rows, dim],
        "iterations": 100,
        "results": result,
    }
    (ROOT / "benchmarks" / "release-1.0.0" / "backend_micro.json").write_text(
        json.dumps(payload, indent=2)
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
