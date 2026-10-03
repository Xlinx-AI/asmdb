from __future__ import annotations

import ctypes
import os
import platform
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class BackendInfo:
    name: str
    library: str | None
    native: bool
    reason: str


_LOAD_LOCK = threading.Lock()
_LIB = None
_INFO: BackendInfo | None = None


def _cpu_features() -> set[str]:
    try:
        from numpy._core._multiarray_umath import __cpu_features__
    except ImportError:
        from numpy.core._multiarray_umath import __cpu_features__
    feats = {key.lower() for key, enabled in __cpu_features__.items() if enabled}
    aliases = {
        "sse4_1": "sse41",
        "sse4.1": "sse41",
        "avx512f": "avx512f",
        "avx2": "avx2",
        "avx": "avx",
        "sse3": "sse3",
        "pni": "sse3",
    }
    for k, v in list(aliases.items()):
        if k in feats:
            feats.add(v)
    return feats


def _candidate_names() -> list[str]:
    machine = platform.machine().lower()
    bits = ctypes.sizeof(ctypes.c_void_p) * 8
    feats = _cpu_features()
    force = os.getenv("ASMDB_BACKEND", "").strip().lower()
    if machine in {"arm64", "aarch64"} and bits == 64:
        if force and force != "arm64_neon":
            raise ValueError("ARM64 requires the arm64_neon backend")
        return ["arm64_neon"]
    if bits == 32 or machine in {"i386", "i486", "i586", "i686", "x86"}:
        if force and force != "x86":
            raise ValueError("A 32-bit process requires the x86 backend")
        return ["x86"]
    if machine not in {"amd64", "x86_64"}:
        if force:
            raise ValueError("NASM backends require an x86 CPU")
        return []
    order: list[str] = []
    if "avx512f" in feats and "sse41" in feats:
        order.append("x64_avx512_sse41")
    if "avx2" in feats and ("sse41" in feats or "sse4_1" in feats):
        order.append("x64_avx2_sse4")
    if "avx" in feats and "sse3" in feats:
        order.append("x64_avx1_sse3")
    order.append("x64")
    if force:
        if force not in order:
            raise ValueError(f"Backend {force!r} is unknown or unsafe on this CPU")
        return [force]
    return order


def _lib_paths(name: str) -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    ext = (
        ".dll"
        if os.name == "nt"
        else (".dylib" if platform.system() == "Darwin" else ".so")
    )
    return [
        Path(__file__).resolve().parent / "_native" / f"libasmdb_{name}{ext}",
        root / "build" / f"libasmdb_{name}{ext}",
    ]


def _configure(lib):
    fn = lib.asmdb_scores
    fn.argtypes = [
        ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.POINTER(ctypes.c_float),
    ]
    fn.restype = None
    return fn


def _autotune(candidates):
    rng = np.random.default_rng(0xA5DB)
    x = np.ascontiguousarray(rng.normal(size=(8192, 128)).astype(np.float32))
    q = np.ascontiguousarray(rng.normal(size=128).astype(np.float32))
    out = np.empty(8192, dtype=np.float32)
    xp = x.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    qp = q.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    op = out.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
    ranked = []
    for name, p, lib in candidates:
        fn = _configure(lib)
        fn(xp, qp, 8192, 128, op)
        samples = []
        for _ in range(7):
            t0 = time.perf_counter_ns()
            fn(xp, qp, 8192, 128, op)
            samples.append(time.perf_counter_ns() - t0)
        ranked.append((min(samples), name, p, lib))
    ranked.sort(key=lambda z: z[0])
    return ranked[0], [(name, ns / 1e3) for ns, name, _, _ in ranked]


def _load_unlocked() -> tuple[ctypes.CDLL | None, BackendInfo]:
    global _LIB, _INFO
    if _INFO is not None:
        return _LIB, _INFO
    errors = []
    loaded = []
    forced = bool(os.getenv("ASMDB_BACKEND", "").strip())
    for name in _candidate_names():
        for p in _lib_paths(name):
            if not p.exists():
                continue
            try:
                lib = ctypes.CDLL(str(p))
                _configure(lib)
                loaded.append((name, p, lib))
                break
            except OSError as e:
                errors.append(f"{p}: {e}")
    if loaded:
        if forced or len(loaded) == 1 or os.getenv("ASMDB_AUTOTUNE", "1") == "0":
            name, p, lib = loaded[0]
            reason = "SIMD assembly backend loaded by ISA priority"
        else:
            (_ns, name, p, lib), ranking = _autotune(loaded)
            reason = (
                "SIMD assembly backend selected by safe ISA filter + startup micro-autotune: "
                + ", ".join(f"{n}={us:.1f}us" for n, us in ranking)
            )
        _LIB = lib
        _INFO = BackendInfo(name, str(p), True, reason)
        return _LIB, _INFO
    if forced:
        raise RuntimeError(
            "Requested native backend is not available: " + os.environ["ASMDB_BACKEND"]
        )
    _INFO = BackendInfo(
        "numpy_fallback",
        None,
        False,
        "No compatible native library found"
        + (": " + "; ".join(errors) if errors else ""),
    )
    return None, _INFO


def _load():
    with _LOAD_LOCK:
        return _load_unlocked()


def backend_info() -> BackendInfo:
    return _load()[1]


def _validate_arrays(matrix, query, *, check_matrix=True):
    matrix = np.ascontiguousarray(matrix, dtype=np.float32)
    query = np.ascontiguousarray(query, dtype=np.float32)
    if matrix.ndim != 2 or query.ndim != 1 or matrix.shape[1] != query.shape[0]:
        raise ValueError("shape mismatch")
    if (check_matrix and not np.isfinite(matrix).all()) or not np.isfinite(query).all():
        raise ValueError("scores require finite vectors")
    return matrix, query


def score_matrix(matrix: np.ndarray, query: np.ndarray) -> np.ndarray:
    matrix, query = _validate_arrays(matrix, query)
    lib, _ = _load()
    if lib is None:
        return (matrix @ query).astype(np.float32, copy=False)
    out = np.empty(matrix.shape[0], dtype=np.float32)
    lib.asmdb_scores(
        matrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        query.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        matrix.shape[0],
        matrix.shape[1],
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
    )
    return out
