from setuptools import Distribution, setup
from setuptools.command.bdist_wheel import bdist_wheel


class NativeWheel(bdist_wheel):
    def get_tag(self):
        _, _, platform = super().get_tag()
        return "py3", "none", platform


class NativeDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(distclass=NativeDistribution, cmdclass={"bdist_wheel": NativeWheel})
