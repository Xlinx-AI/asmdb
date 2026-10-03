from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def ns_ms(ns):
    return ns / 1e6


def pct(xs, p):
    return float(np.percentile(np.asarray(xs), p))


def synth(n, dim, topics, qn, seed=77):
    rng = np.random.default_rng(seed)
    centers = rng.normal(size=(topics, dim)).astype(np.float32)
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    labels = rng.integers(0, topics, size=n)
    x = centers[labels] + 0.19 * rng.normal(size=(n, dim)).astype(np.float32)
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    qlabels = rng.integers(0, topics, size=qn)
    q = centers[qlabels] + 0.10 * rng.normal(size=(qn, dim)).astype(np.float32)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return x.astype(np.float32), q.astype(np.float32), labels, qlabels


def topk_numpy(x, q, k):
    s = x @ q
    idx = np.argpartition(s, -k)[-k:]
    return idx[np.argsort(s[idx])[::-1]], s[idx]


def timeit(fn, warm=2, reps=5):
    for _ in range(warm):
        fn()
    vals = []
    out = None
    for _ in range(reps):
        t = time.perf_counter_ns()
        out = fn()
        vals.append(ns_ms(time.perf_counter_ns() - t))
    return float(np.median(vals)), out


def summarize(lat):
    return {
        "mean_ms": float(statistics.mean(lat)),
        "median_ms": float(statistics.median(lat)),
        "p95_ms": pct(lat, 95),
        "qps_from_mean": float(1000 / statistics.mean(lat)),
    }


def sqlite_setup(path, x):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.execute("CREATE TABLE vectors(id INTEGER PRIMARY KEY, vec BLOB NOT NULL)")
    con.executemany(
        "INSERT INTO vectors(id,vec) VALUES (?,?)",
        ((int(i), memoryview(row.tobytes())) for i, row in enumerate(x)),
    )
    con.commit()
    return con


def sqlite_query(con, q, k):
    q = np.ascontiguousarray(q, np.float32)

    def dot(blob):
        return float(np.dot(np.frombuffer(blob, dtype=np.float32), q))

    con.create_function("v_dot", 1, dot)
    return con.execute(
        "SELECT id, v_dot(vec) AS score FROM vectors ORDER BY score DESC LIMIT ?", (k,)
    ).fetchall()


def main():
    from asmdb import ASMDB, backend_info

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30000)
    ap.add_argument("--dim", type=int, default=128)
    ap.add_argument("--topics", type=int, default=64)
    ap.add_argument("--queries", type=int, default=50)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--nprobe", type=int, default=2)
    ap.add_argument("--sqlite-queries", type=int, default=5)
    ap.add_argument("--out", default=str(ROOT / "benchmarks" / "results.json"))
    args = ap.parse_args()
    x, qs, _, _ = synth(args.n, args.dim, args.topics, args.queries)
    with tempfile.TemporaryDirectory(prefix="asmdb-bench-") as td:
        dbdir = Path(td) / "db"
        t0 = time.perf_counter()
        db = ASMDB.build(dbdir, x, n_clusters=args.topics, kmeans_iters=4, seed=5)
        build_s = time.perf_counter() - t0
        gt = []
        np_lat = []
        for q in qs:
            ms, out = timeit(lambda q=q: topk_numpy(x, q, args.k), warm=1, reps=5)
            np_lat.append(ms)
            gt.append(set(map(int, out[0])))
        as_lat = []
        recalls = []
        for qi, q in enumerate(qs):
            ms, out = timeit(
                lambda q=q: db.search(q, k=args.k, nprobe=args.nprobe), warm=1, reps=5
            )
            as_lat.append(ms)
            got = {r["id"] for r in out}
            recalls.append(len(got & gt[qi]) / args.k)
        exact_lat = []
        for q in qs[: min(10, len(qs))]:
            ms, _ = timeit(
                lambda q=q: db.search(q, k=args.k, nprobe=args.topics), warm=1, reps=3
            )
            exact_lat.append(ms)
        con = sqlite_setup(str(Path(td) / "vectors.sqlite"), x)
        sq_lat = []
        for q in qs[: min(args.sqlite_queries, len(qs))]:
            ms, _ = timeit(lambda q=q: sqlite_query(con, q, args.k), warm=0, reps=1)
            sq_lat.append(ms)
        con.close()
        result = {
            "system": {
                "platform": platform.platform(),
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "cpu_count": os.cpu_count(),
                "backend": backend_info().__dict__,
            },
            "dataset": {
                "kind": "clustered_rag_synthetic",
                "n": args.n,
                "dim": args.dim,
                "topics": args.topics,
                "queries": args.queries,
                "k": args.k,
            },
            "build": {"seconds": build_s},
            "asmdb": {
                **summarize(as_lat),
                "nprobe": args.nprobe,
                "mean_recall_at_k": float(statistics.mean(recalls)),
                "candidate_fraction_estimate": float(args.nprobe / args.topics),
            },
            "numpy_bruteforce": summarize(np_lat),
            "asmdb_exact_all_clusters": summarize(exact_lat),
            "sqlite_blob_udf_fullscan": {
                **summarize(sq_lat),
                "queries_measured": len(sq_lat),
            },
        }
        result["speedups"] = {
            "vs_numpy_mean": result["numpy_bruteforce"]["mean_ms"]
            / result["asmdb"]["mean_ms"],
            "vs_sqlite_mean": result["sqlite_blob_udf_fullscan"]["mean_ms"]
            / result["asmdb"]["mean_ms"],
        }
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        db.close()


if __name__ == "__main__":
    main()
