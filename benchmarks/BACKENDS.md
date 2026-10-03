# Native scorer microbenchmark

Input: 4096 x 128 float32 matrix, 100 timed iterations. Error is against NumPy dot.

| backend | median | mean | p95 | max abs error |
|---|---:|---:|---:|---:|
| x64 | 0.3642 ms | 0.3645 ms | 0.4579 ms | 1.53e-05 |
| x64_avx1_sse3 | 0.0482 ms | 0.0498 ms | 0.0690 ms | 3.81e-06 |
| x64_avx2_sse4 | 0.0412 ms | 0.0425 ms | 0.0604 ms | 4.77e-06 |
| x64_avx512_sse41 | 0.0424 ms | 0.0440 ms | 0.0606 ms | 5.72e-06 |
