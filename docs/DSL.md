# ASMQ pseudo-assembly

ASMQ programs specify the retrieval plan.

- `MOV R, value` вЂ” load scalar/register. `$name` reads a host binding.
- `QLOAD Q, $query` вЂ” load float32 query.
- `QNORM Q` вЂ” L2-normalize query.
- `COARSE C, Q, probes` вЂ” select coarse centroid postings.
- `SCAN S, C, Q` вЂ” native exact dot scan of selected postings.
- `TOPK R, S, k` вЂ” select and sort top-k.
- `FILTER ...` вЂ” metadata post-filter.
- `RET R` вЂ” return a register.

Because the program is explicit, later backends can add opcodes for lexical fusion, rerankers, filters, score transforms, quantized scans or graph traversal without changing the Python API.
