# ASMDB 1.0.0 release status

Validated on 2026-10-03: Windows 10, Intel Core i7-3930K, Python 3.13.12,
NumPy 2.4.3, NASM and Visual Studio linker. Native x64 DLLs and OpenCL dispatch
DLL are packaged with the OpenCL kernel in a Windows x64 wheel.

CPU scalar and AVX1 scoring passed numerical tails, empty score matrices, retrieval,
input rejection, unsafe ISA rejection, UTF-8 metadata, storage corruption and
resource lifetime checks. Pascal P104-100 passed direct GPU scoring and database
retrieval. A separate wheel installation passed the same release suite.

The GPU driver exposes duplicate entries for one PCI device. Enumeration removes
that duplicate. OpenCL reports P104-100, capability 6.1, bus 1; Windows display
names differ. Maxwell hardware execution is unverified. AVX2/AVX-512 were assembled
but not executed on the i7-3930K. Linux and 32-bit execution are unverified here.

Release benchmark results are in benchmarks/release-1.0.0. At 50,000 x 128,
nprobe=4, recall@10 is 0.978. Read the current raw JSON for latency measurements.
GPU scoring is functional but slower than CPU on the measured single-query workloads.

The supported deployment is an embedded immutable vector store. See
[deployment boundaries](docs/LIMITATIONS.md) for lifecycle, durability and
operational constraints. This release does not establish broad production
certification or compatibility with every advertised GPU generation.

Older benchmark logs, binaries and PROJECT_SHA256SUMS.txt describe the original
0.1 archive. Release checksums are recorded separately in dist/SHA256SUMS.txt.
