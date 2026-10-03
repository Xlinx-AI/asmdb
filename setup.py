import subprocess
import sys
from pathlib import Path

from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.command.build_py import build_py


class NativeBuild(build_py):
    def run(self):
        root = Path(__file__).resolve().parent
        subprocess.run(
            [sys.executable, str(root / "tools/build_native.py")], check=True
        )
        super().run()

    def find_data_files(self, package, src_dir):
        files = super().find_data_files(package, src_dir)
        suffix = (
            ".dll"
            if sys.platform == "win32"
            else ".dylib"
            if sys.platform == "darwin"
            else ".so"
        )
        return [
            file
            for file in files
            if Path(file).suffix not in {".dll", ".so", ".dylib"}
            or Path(file).suffix == suffix
        ]


class NativeWheel(bdist_wheel):
    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(
    distclass=NativeDistribution,
    cmdclass={"bdist_wheel": NativeWheel, "build_py": NativeBuild},
)
