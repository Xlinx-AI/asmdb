# Architecture

## Retrieval pipeline

1. Input embeddings are L2-normalized at build time.
2. Lightweight spherical k-means creates coarse semantic centroids.
3. Vectors are physically reordered by centroid assignment, producing contiguous postings.
4. At query time `COARSE` scores only centroids.
5. `SCAN` invokes one native SIMD kernel per selected contiguous posting.
6. `TOPK` performs the final exact rerank across those candidates.

The design target is RAG latency, where a corpus commonly contains semantic locality and top-k retrieval does not require evaluating every row.

## Why this can win

A full vector-table scan is O(ND). ASMDB query work is approximately O(CD + nprobe * N/C * D), where C is the number of coarse clusters. The assembly kernels optimize the second term, but the larger gain comes from avoiding most rows and keeping selected rows contiguous for prefetch/cache behavior.

## Why it can lose

Uniform/random embeddings destroy coarse locality. Too-small `nprobe` harms recall. Too-large `nprobe` approaches a full scan, where tuned BLAS/FAISS implementations may beat ASMDB. Tiny databases are dominated by Python/ctypes overhead.

## Native ABI

Linux x86_64 kernels expose:

`void asmdb_scores(const float *matrix, const float *query, size_t rows, size_t dim, float *out);`

Each variant is a separate shared object so no unsupported ISA is executed before CPU dispatch.
