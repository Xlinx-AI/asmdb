# Storage and dispatch

Vectors are normalized once and grouped by coarse centroid. Each CPU posting scan
reads a contiguous matrix and contiguous IDs. Coarse routing reduces the number of
scored rows; nprobe controls the recall/latency trade-off.

Separate native libraries isolate ISA variants. NumPy runtime feature detection
provides the OS-aware feature gate. A short calibration chooses between supported
variants. Explicit unsupported selections raise an error before kernel execution.

The NASM ABI include maps Win64 argument registers into the scorer register layout
and preserves nonvolatile registers. Linux uses SysV argument registers directly.
The OpenCL NASM bridge supplies the launch dimensions and calls the runtime function
pointer. Allocation, device lifetime and error handling remain in the Python wrapper.

ASMQ compiles retrieval operations into a validated instruction list. Every search
uses its own register dictionary. The database stays read-only after publication.
