#!/usr/bin/env python3
import json
import sys
from pathlib import Path

p = Path(
    sys.argv[1]
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[1] / "benchmarks" / "results.json"
)
r = json.loads(p.read_text())
a = r["asmdb"]
n = r["numpy_bruteforce"]
s = r["sqlite_blob_udf_fullscan"]
md = f"""# ASMDB benchmark result\n\nDataset: **{r["dataset"]["n"]:,} x {r["dataset"]["dim"]} float32**, {r["dataset"]["topics"]} synthetic semantic topics, {r["dataset"]["queries"]} queries, top-{r["dataset"]["k"]}.\n\nNative backend selected: **{r["system"]["backend"]["name"]}**. Native loaded: `{r["system"]["backend"]["native"]}`.\n\n| Engine | Mean latency | p95 | Approx. QPS | Recall@{r["dataset"]["k"]} |\n|---|---:|---:|---:|---:|\n| ASMDB nprobe={a["nprobe"]} | {a["mean_ms"]:.4f} ms | {a["p95_ms"]:.4f} ms | {a["qps_from_mean"]:.1f} | {a["mean_recall_at_k"]:.3f} |\n| NumPy brute-force | {n["mean_ms"]:.4f} ms | {n["p95_ms"]:.4f} ms | {n["qps_from_mean"]:.1f} | 1.000 |\n| SQLite BLOB+UDF full scan | {s["mean_ms"]:.4f} ms | {s["p95_ms"]:.4f} ms | {s["qps_from_mean"]:.1f} | 1.000 |\n\nMean latency speedup: **{r["speedups"]["vs_numpy_mean"]:.2f}x vs NumPy full scan**, **{r["speedups"]["vs_sqlite_mean"]:.1f}x vs SQLite full scan**.\n\nASMDB's speed comes primarily from coarse semantic routing + cluster-contiguous layout (estimated scan fraction {a["candidate_fraction_estimate"]:.3%}), then SIMD exact scoring inside selected postings. This is an ANN trade-off, so speedup must be read together with recall.\n\nExact all-cluster ASMDB mean latency: {r["asmdb_exact_all_clusters"]["mean_ms"]:.4f} ms. This is included to separate the indexing win from raw SIMD-kernel speed.\n"""
(p.parent / "RESULTS.md").write_text(md)
print(md)
