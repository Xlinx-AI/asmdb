# nprobe trade-off

All rows use the same deterministic 50,000 x 128 clustered RAG-like corpus and 100 queries. Each ASMDB/NumPy query latency is the median of repeated calls.

| nprobe | ASMDB mean | p95 | recall@10 | speedup vs flat NumPy | speedup vs SQLite | selected backend |
|---:|---:|---:|---:|---:|---:|---|
| 2 | 0.1306 ms | 0.1484 ms | 0.954 | 4.57x | 554.0x | x64_avx2_sse4 |
| 4 | 0.1793 ms | 0.2132 ms | 0.966 | 3.36x | 414.2x | x64_avx2_sse4 |
| 8 | 0.2964 ms | 0.3852 ms | 0.970 | 1.82x | 265.6x | x64_avx512_sse41 |
