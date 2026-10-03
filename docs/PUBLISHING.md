# Publishing packages

The workflow builds five platform wheels and one source archive. Wheels use the
py3-none ABI tag because ctypes calls a plain native interface. Python 3.13 runs
the CI suite; that does not establish validation of every supported Python version.

Linux x86-64 and ARM64 wheels target glibc 2.28 or newer. macOS Intel wheels target
10.15 or newer; Apple Silicon wheels target 11.0 or newer. Windows wheels target
x64. ARM64 code uses NEON assembly; x64 code uses NASM.

On pushes to main, pull requests and manual runs, CI builds packages and tests
their installed CPU backends. GPU tests are disabled because hosted runners do
not provide the required GPU/runtime combination. A published GitHub release
starts the same checks and publishes only after every build job succeeds.

Create the GitHub environment `pypi`. In PyPI, configure a GitHub Trusted Publisher
with owner `kirill670`, the exact repository name, workflow filename `publish.yml`
and environment `pypi`. For a new project, use a pending publisher. The PyPI project
name must match the project name in pyproject.toml and must be available to you.
No long-lived API token is needed.

Commit the workflow and source before creating a release. Its tag must be the
package version, optionally prefixed with v; for example v1.0.0. PyPI versions
cannot be replaced: after publishing 1.0.0, change asmdb.__version__ before the
next release. Publishing retries do not skip existing files automatically.

Source installations compile the platform backend during wheel creation and need
the corresponding assembler and linker. Installing a published platform wheel
does not require build tools. OpenCL use additionally requires the gpu extra
and a functioning device runtime.
