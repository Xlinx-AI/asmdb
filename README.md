# ASMDB 1.0.0

Embedded cosine vector search with cluster-contiguous storage, NASM CPU scoring,
and an optional OpenCL GPU scorer. Databases are immutable after publication.

## Build and install

Windows x64 requires Python 3.10+, NumPy, NASM and the Visual Studio x64 linker.
Linux x64 requires NASM and a C linker.

```
python tools/build_native.py
python -m pip install .
python -m pip install ".[gpu]"
```

The builder assembles scalar, AVX1, AVX2 and AVX-512 DLLs/shared libraries.
Runtime dispatch filters CPU features before loading a scorer, including forced
`ASMDB_BACKEND` selections. An i7-3930K uses scalar or AVX1.

## Search

```python
import numpy as np
from asmdb import ASMDB

vectors = np.random.default_rng(1).normal(size=(10000, 128)).astype(np.float32)
with ASMDB.build("my.asmb", vectors, n_clusters=64) as db:
    rows = db.search(vectors[42], k=10, nprobe=4)

with ASMDB("my.asmb", backend="opencl", device=0) as db:
    rows = db.search(vectors[42], k=10, nprobe=4)
```

`build` accepts an absent or empty destination and refuses to overwrite a database.
IDs must be unique. Inputs must be finite, nonempty matrices. Metadata uses UTF-8.
Close databases before moving/deleting their files, especially on Windows.

## GPU backend

`native/opencl.asm` implements x86-64 OpenCL kernel dispatch in NASM.
`asmdb/kernels/scores.cl` performs GPU dot products with a 64-thread reduction.
The driver compiles this OpenCL C 1.2 kernel for the selected GPU. NASM does not
assemble NVIDIA GPU instructions. Maxwell/Pascal and newer devices need a working
OpenCL implementation; device enumeration is available through `asmdb.gpu.devices()`.

GPU selection is explicit. Candidate scans gather and upload selected postings.
For direct `GPUScorer.score` calls, a contiguous read-only matrix is cached until
its identity or shape changes. Its underlying storage must remain immutable while
cached. Mutable matrices are uploaded on every call. Transfers and result reads
are included in GPU timings. A scorer serializes calls and supports `close()`.

## Query programs

```asm
MOV K, 10
MOV P, 4
QLOAD Q0, $query
QNORM Q0
COARSE C0, Q0, P
SCAN S0, C0, Q0
TOPK R0, S0, K
RET R0
```

Pass source as `db.search(query, program=source)`. See `docs/DSL.md` for opcodes.
The CLI provides `asmdb backend`, `asmdb info DB` and
`asmdb search DB QUERY.npy --backend opencl --device 0`.

## Validation and benchmarks

```
python -m unittest discover -s tests -v
python benchmarks/bench_release.py
python benchmarks/bench_rag.py --n 50000 --nprobe 4 --out benchmarks/release-1.0.0/rag.json
```

Set `ASMDB_TEST_GPU=1` to include installed GPU checks. Current Windows results
are in `benchmarks/release-1.0.0/`; older Linux captures remain in `benchmarks/`.
Synthetic retrieval timings must be read together with recall. Read
`STATUS.md` and `docs/LIMITATIONS.md` before deploying.
