# Deployment boundaries

ASMDB 1.0.0 is an embedded, immutable vector store. It has no network server,
authentication, online updates, compaction, replication or transaction API.
Publication uses a temporary sibling directory and rename after flushing files.
Power-loss durability of directory metadata depends on the filesystem; no recovery
journal is implemented. Existing databases are never overwritten by `build`.

Open validates dimensions, format, file lengths, centroids and posting boundaries.
There are no per-file cryptographic checksums for stored databases. Deploy trusted
artifacts and use filesystem access controls. Concurrent searches are supported
while a database stays open; closing a database during search is unsupported.

Clustering is approximate. Increasing nprobe improves recall and increases work;
using all clusters gives exact cosine scoring apart from floating-point rounding.
FILTER runs after TOPK and may return fewer than k rows. Equal scores have no
specified ordering. The full build holds normalized and reordered vectors in RAM.

The CPU kernels assume valid pointers supplied by the Python wrapper. Direct
foreign calls must supply matching lengths and writable output storage. AVX2 and
AVX-512 binaries are assembled on this host but cannot execute on its i7-3930K.
32-bit x86 is legacy source and is outside the validated 1.0 Windows x64 release.
Linux ABI changes have not been run on Linux in this release session.

OpenCL currently exposes one distinct NVIDIA P104-100, capability 6.1, PCI bus 1.
Duplicate platform entries are deduplicated by PCI identity. Windows display names
are Quadro K620 and GTX 1070; they are not proof of OpenCL device availability.
Pascal execution is tested. Maxwell and later architectures require additional
hardware validation. GPU performance includes validation, synchronization, uploads
where required and output transfers. It is not guaranteed to outperform CPU.

The bundled wheel is platform-specific. Build on the target OS before packaging.
Benchmarks use synthetic clustered vectors; application embeddings and external
vector databases have not been benchmarked by the 1.0 release checks.
