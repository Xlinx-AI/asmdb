# Benchmark methodology

The included `bench_rag.py` generates normalized float32 vectors around latent semantic topic centers. Queries are generated near the same topic centers. This approximates the locality that a topical RAG corpus often has; it is not claimed to represent every embedding distribution.

For every query, NumPy brute-force over the full matrix supplies both a latency baseline and exact top-k ground truth. ASMDB reports recall@k against that ground truth. SQLite stores the same float32 vectors as BLOB rows and computes a full-scan dot product through a SQLite UDF; only a small number of SQLite queries are timed because Python/UDF row overhead is large, but the full dataset is used.

Warm-up calls are used for ASMDB/NumPy. Results are wall-clock query latency and are not hardware-independent. Build time is reported separately. `asmdb_exact_all_clusters` is also measured on a subset to show that the primary RAG win is candidate pruning plus layout, full-scan throughput.
