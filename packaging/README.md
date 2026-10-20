# Windows portable build

Build on Windows x64 using 64-bit CPython 3.12 with Tcl/Tk available. CI uses
Python 3.12.10, the final 3.12 release with an official Windows binary installer.
Use a clean virtual environment and install `requirements-dev.txt`. Run
`python scripts/build.py` from any working directory.

The script verifies the committed model SHA-256, runs `pip check`, the unit
suite, and the source smoke test, then creates a PyInstaller **onedir/windowed**
bundle. It smoke-tests the executable with `--self-test --report <path>` before
creating the ZIP and `SHA256SUMS.txt`. The test initializes Tk and the bundled
Gesture Recognizer and performs blank-frame inference without opening the camera.
No network access is needed after installing build dependencies.

The model is copied into `_internal/models` by PyInstaller. MediaPipe package
data and native libraries are explicitly collected. Keep `_internal` with the
EXE. External tutorial files, attribution, custom license, full model license,
Python/Tcl/Tk and installed dependency license files are included. The generated
`build-report.json` records dependencies and verification limits; `self-test.json`
records the actual packaged smoke-test output.

`build/` and `dist/` contain disposable generated files and are ignored by Git.
Do not commit virtual environments or EXEs. Publish the ZIP and checksum as
GitHub Release assets. The binary is unsigned; codesigning can be added later
when the author has a signing certificate.

The repository also contains the complete extracted application in
`Download/PPhandcontrol`, linked from the main README's **Download and run**
section. Export a validated release there with
`python scripts/export_download.py path/to/PPhandcontrol-windows-x64.zip`;
keep its `SHA256SUMS.txt` beside the ZIP. The exporter verifies the checksum,
preserves the runtime bytes, and adds `License.txt` and `How to use.txt` at the
top of the app folder. The committed distribution's `.pyd` files must remain
tracked; the Git ignore exceptions and attributes preserve them.

All Python dependency versions are pinned. ZIP filenames are sorted and entry
timestamps use `SOURCE_DATE_EPOCH` (default 2026-01-01 UTC). PyInstaller artifacts
can still differ with the Windows image, Python patch version, dependency
wheels, or toolchain. The build recipe is reproducible; binary identity is not
guaranteed across different environments.

The committed Tcl/Tk notices were obtained from the upstream `core-8-6-branch`
license files at [Tcl](https://github.com/tcltk/tcl/blob/core-8-6-branch/license.terms)
and [Tk](https://github.com/tcltk/tk/blob/core-8-6-branch/license.terms).

## CI and releases

Main-branch pushes and pull requests run the Windows build and upload the ZIP,
checksum, and smoke-test report as Actions artifacts. Pushing a version tag
such as `v1.1.1` runs the same validation and publishes a GitHub Release with
the ZIP and checksum using the workflow's scoped `GITHUB_TOKEN`.

Before tagging a later release, update the package version and release notes.
For this initial release, real-camera accuracy and manual viewer checks are
explicitly unverified unless a completed manual validation record is supplied.
