#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
VARIANTS = ["x64", "x64_avx1_sse3", "x64_avx2_sse4", "x64_avx512_sse41", "opencl"]


def find_linker():
    if os.name != "nt":
        return shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    vswhere = (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    if vswhere.exists():
        installation = subprocess.check_output(
            [
                str(vswhere),
                "-latest",
                "-products",
                "*",
                "-property",
                "installationPath",
            ],
            text=True,
        ).strip()
        choices = sorted(
            Path(installation).glob("VC/Tools/MSVC/*/bin/Hostx64/x64/link.exe")
        )
        if choices:
            return str(choices[-1])
    return shutil.which("link")


def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def build_nasm():
    nasm = shutil.which("nasm")
    cc = find_linker()
    if not nasm or not cc:
        return False
    BUILD.mkdir(exist_ok=True)
    system = platform.system()
    output_format = {"Windows": "win64", "Linux": "elf64", "Darwin": "macho64"}[system]
    for v in VARIANTS:
        obj = BUILD / f"{v}.o"
        run(
            [
                nasm,
                "-I",
                str(ROOT / "native") + "/",
                "-f",
                output_format,
                "-O2",
                str(ROOT / "native" / f"{v}.asm"),
                "-o",
                str(obj),
            ]
        )
        if os.name == "nt":
            library = BUILD / f"libasmdb_{v}.dll"
            symbol = "asmdb_cl_enqueue" if v == "opencl" else "asmdb_scores"
            run(
                [
                    cc,
                    "/DLL",
                    "/NOENTRY",
                    "/MACHINE:X64",
                    "/DYNAMICBASE",
                    "/NXCOMPAT",
                    f"/EXPORT:{symbol}",
                    f"/OUT:{library}",
                    str(obj),
                ]
            )
        elif system == "Darwin":
            library = BUILD / f"libasmdb_{v}.dylib"
            run(
                [
                    cc,
                    "-dynamiclib",
                    "-arch",
                    "x86_64",
                    "-Wl,-install_name,@rpath/" + library.name,
                    "-o",
                    str(library),
                    str(obj),
                ]
            )
        else:
            library = BUILD / f"libasmdb_{v}.so"
            run([cc, "-shared", "-Wl,-z,noexecstack", "-o", str(library), str(obj)])
        destination = ROOT / "asmdb" / "_native"
        destination.mkdir(exist_ok=True)
        shutil.copy2(library, destination / library.name)
    (BUILD / "CURRENT_BUILD.txt").write_text(
        f"NASM: {nasm}\nPlatform: {platform.platform()}\n"
    )
    if system == "Linux" and os.environ.get("ASMDB_BUILD_X86") == "1":
        obj = BUILD / "x86.o"
        run(
            [
                nasm,
                "-f",
                "elf32",
                "-O2",
                str(ROOT / "native" / "x86.asm"),
                "-o",
                str(obj),
            ]
        )
        run([cc, "-m32", "-shared", "-o", str(BUILD / "libasmdb_x86.so"), str(obj)])
    return True


def build_bootstrap():
    cc = find_linker()
    if not cc:
        raise SystemExit("No C compiler available for bootstrap assembler path")
    BUILD.mkdir(exist_ok=True)
    flags = {
        "x64": [],
        "x64_avx1_sse3": ["-mavx", "-msse3"],
        "x64_avx2_sse4": ["-mavx2", "-msse4.1"],
        "x64_avx512_sse41": ["-mavx512f", "-msse4.1"],
    }
    for v in VARIANTS[:-1]:
        run(
            [
                cc,
                "-shared",
                "-fPIC",
                *flags[v],
                str(ROOT / "native" / "bootstrap" / f"{v}.S"),
                "-o",
                str(BUILD / f"libasmdb_{v}.so"),
            ]
        )
    (BUILD / "BOOTSTRAP_BUILD.txt").write_text(
        "Official NASM executable was unavailable. Native kernels were assembled from GAS Intel-syntax mirrors of the canonical NASM sources.\n"
    )


def build_arm64():
    cc = find_linker()
    if not cc:
        raise SystemExit("ARM64 assembly requires Clang or GCC")
    BUILD.mkdir(exist_ok=True)
    destination = ROOT / "asmdb/_native"
    destination.mkdir(exist_ok=True)
    macos = platform.system() == "Darwin"
    for name, source in [("arm64_neon", "arm64.S"), ("opencl", "opencl_arm64.S")]:
        extension = ".dylib" if macos else ".so"
        library = BUILD / f"libasmdb_{name}{extension}"
        flags = (
            [
                "-dynamiclib",
                "-arch",
                "arm64",
                "-Wl,-install_name,@rpath/" + library.name,
            ]
            if macos
            else ["-shared", "-fPIC", "-Wl,-z,noexecstack"]
        )
        run([cc, *flags, "-o", str(library), str(ROOT / "native" / source)])
        shutil.copy2(library, destination / library.name)
    (BUILD / "CURRENT_BUILD.txt").write_text(
        f"assembler={cc}\nplatform={platform.platform()}\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-if-needed", action="store_true")
    args = parser.parse_args()
    system = platform.system()
    machine = platform.machine().lower()
    if system not in {"Windows", "Linux", "Darwin"}:
        raise SystemExit(f"Unsupported operating system: {system}")
    if machine in {"arm64", "aarch64"} and system in {"Linux", "Darwin"}:
        build_arm64()
    elif machine in {"amd64", "x86_64"}:
        if not build_nasm():
            if args.bootstrap_if_needed and system == "Linux":
                build_bootstrap()
            else:
                raise SystemExit("Native builds require NASM and a platform linker")
    else:
        raise SystemExit(f"Unsupported native architecture: {machine}")


if __name__ == "__main__":
    main()
