import ctypes
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def measure(function):
    for _ in range(5):
        function()
    samples = []
    for _ in range(100):
        start = time.perf_counter_ns()
        function()
        samples.append((time.perf_counter_ns() - start) / 1e6)
    return {
        "median_ms": float(np.median(samples)),
        "p95_ms": float(np.percentile(samples, 95)),
    }


def main():
    from asmdb.gpu import GPUScorer, devices
    from asmdb.native import _candidate_names, _configure, _lib_paths, backend_info

    rng = np.random.default_rng(123)
    results = []
    for rows in (4096, 50000):
        matrix = rng.normal(size=(rows, 128)).astype(np.float32)
        query = rng.normal(size=128).astype(np.float32)
        reference = matrix @ query
        output = np.empty(rows, np.float32)
        pointers = (
            matrix.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            query.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            rows,
            128,
            output.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        )
        for name in _candidate_names():
            path = next((p for p in _lib_paths(name) if p.exists()), None)
            if path is None:
                continue
            library = ctypes.CDLL(str(path))
            function = _configure(library)
            function(*pointers)
            np.testing.assert_allclose(output, reference, atol=8e-5, rtol=8e-5)
            results.append(
                {
                    "backend": name,
                    "rows": rows,
                    "max_abs_error": float(np.max(np.abs(output - reference))),
                    **measure(
                        lambda function=function, pointers=pointers: function(*pointers)
                    ),
                }
            )
        results.append(
            {
                "backend": "numpy",
                "rows": rows,
                **measure(lambda matrix=matrix, query=query: matrix @ query),
            }
        )
        for index, device in enumerate(devices()):
            with GPUScorer(index) as scorer:
                got = scorer.score(matrix, query)
                np.testing.assert_allclose(got, reference, atol=8e-5, rtol=8e-5)
                result = {
                    "backend": "opencl_nasm",
                    "device": device.name,
                    "capability": f"{device.compute_capability_major_nv}.{device.compute_capability_minor_nv}",
                    "pci_bus": device.pci_bus_id_nv,
                    "rows": rows,
                    "max_abs_error": float(np.max(np.abs(got - reference))),
                }
                result["upload_each_call"] = measure(
                    lambda scorer=scorer, matrix=matrix, query=query: scorer.score(
                        matrix, query
                    )
                )
                matrix.flags.writeable = False
                result["resident_matrix"] = measure(
                    lambda scorer=scorer, matrix=matrix, query=query: scorer.score(
                        matrix, query
                    )
                )
                results.append(result)
                matrix.flags.writeable = True
    payload = {
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "selected": backend_info().__dict__,
        "iterations": 100,
        "dim": 128,
        "results": results,
    }
    destination = ROOT / "benchmarks/release-1.0.0"
    destination.mkdir(exist_ok=True)
    (destination / "native_gpu.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
