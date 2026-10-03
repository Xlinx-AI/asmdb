# ASMDB benchmark result

Dataset: **50,000 x 128 float32**, 64 synthetic semantic topics, 50 queries, top-10.

Native backend selected: **x64_avx1_sse3**. Native loaded: `True`.

| Engine | Mean latency | p95 | Approx. QPS | Recall@10 |
|---|---:|---:|---:|---:|
| ASMDB nprobe=4 | 0.7005 ms | 0.7510 ms | 1427.5 | 0.978 |
| NumPy brute-force | 1.7078 ms | 1.8844 ms | 585.6 | 1.000 |
| SQLite BLOB+UDF full scan | 315.5392 ms | 318.1084 ms | 3.2 | 1.000 |

Mean latency speedup: **2.44x vs NumPy full scan**, **450.4x vs SQLite full scan**.

ASMDB's speed comes primarily from coarse semantic routing + cluster-contiguous layout (estimated scan fraction 6.250%), then SIMD exact scoring inside selected postings. This is an ANN trade-off, so speedup must be read together with recall.

Exact all-cluster ASMDB mean latency: 9.1141 ms. This is included to separate the indexing win from raw SIMD-kernel speed.
