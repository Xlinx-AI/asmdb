from __future__ import annotations

import ctypes
import ctypes.util
import os
import threading
from pathlib import Path

import numpy as np


def devices():
    import pyopencl as cl

    result = []
    seen = set()
    for platform in cl.get_platforms():
        for device in platform.get_devices(device_type=cl.device_type.GPU):
            try:
                identity = (device.vendor, device.pci_bus_id_nv, device.pci_slot_id_nv)
            except (AttributeError, cl.LogicError):
                identity = (platform.int_ptr, device.int_ptr)
            if identity not in seen:
                seen.add(identity)
                result.append(device)
    return result


class GPUScorer:
    def __init__(self, device=0):
        import pyopencl as cl

        available = devices()
        if not 0 <= device < len(available):
            raise ValueError(f"GPU index {device} is unavailable")
        self.device = available[device]
        self._lock = threading.Lock()
        self._closed = False
        self.context = cl.Context([self.device])
        self.queue = cl.CommandQueue(self.context)
        source = (Path(__file__).parent / "kernels/scores.cl").read_text(
            encoding="utf-8"
        )
        self.program = cl.Program(self.context, source).build(options=["-cl-std=CL1.2"])
        self.kernel = cl.Kernel(self.program, "scores")
        from .native import _lib_paths

        library = next((p for p in _lib_paths("opencl") if p.is_file()), None)
        if library is None:
            raise RuntimeError(
                "Native OpenCL dispatch library is missing; run tools/build_native.py"
            )
        self._bridge = ctypes.CDLL(str(library))
        self._enqueue = self._bridge.asmdb_cl_enqueue
        self._enqueue.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
        ]
        self._enqueue.restype = ctypes.c_int
        runtime = (
            "OpenCL.dll" if os.name == "nt" else ctypes.util.find_library("OpenCL")
        )
        if not runtime:
            raise RuntimeError("OpenCL runtime is missing")
        self._runtime = ctypes.CDLL(runtime)
        self._function = ctypes.cast(
            self._runtime.clEnqueueNDRangeKernel, ctypes.c_void_p
        )
        self._matrix = None
        self._host_matrix = None
        self._query = None
        self._output = None
        self._shape = None

    def score(self, matrix, query):
        import pyopencl as cl

        from .native import _validate_arrays

        with self._lock:
            if self._closed:
                raise RuntimeError("GPU scorer is closed")
            matrix, query = _validate_arrays(
                matrix, query, check_matrix=matrix is not self._host_matrix
            )
            rows, dim = matrix.shape
            if not rows or not dim:
                return np.zeros(rows, dtype=np.float32)
            flags = cl.mem_flags
            if self._shape != matrix.shape:
                self._matrix = cl.Buffer(self.context, flags.READ_ONLY, matrix.nbytes)
                self._query = cl.Buffer(self.context, flags.READ_ONLY, query.nbytes)
                self._output = cl.Buffer(self.context, flags.WRITE_ONLY, rows * 4)
                self._shape = matrix.shape
                self._host_matrix = None
            cacheable = not matrix.flags.writeable
            if self._host_matrix is not matrix or not cacheable:
                cl.enqueue_copy(self.queue, self._matrix, matrix, is_blocking=True)
                self._host_matrix = matrix if cacheable else None
            cl.enqueue_copy(self.queue, self._query, query, is_blocking=True)
            self.kernel.set_args(
                self._matrix, self._query, self._output, np.uint64(rows), np.uint64(dim)
            )
            size = ctypes.c_size_t(rows * 64)
            status = self._enqueue(
                self.queue.int_ptr,
                self.kernel.int_ptr,
                ctypes.byref(size),
                self._function,
            )
            if status:
                raise RuntimeError(f"OpenCL native enqueue failed: {status}")
            output = np.empty(rows, dtype=np.float32)
            cl.enqueue_copy(self.queue, output, self._output, is_blocking=True)
            return output

    def close(self):
        with self._lock:
            if not self._closed:
                self.queue.finish()
                self._host_matrix = self._matrix = self._query = self._output = None
                self.kernel = self.program = self.queue = self.context = None
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
