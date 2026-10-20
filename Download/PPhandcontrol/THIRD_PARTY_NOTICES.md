# Third-party notices

The custom PPhandcontrol license covers only original project material.
Third-party components retain their own terms and attribution. The portable
ZIP includes a `licenses/` folder copied from the installed distributions,
including dependency license and NOTICE files, together with Python and Tcl/Tk
notices. Keep that folder with redistributed executables.

| Component | Source and terms |
| --- | --- |
| MediaPipe 0.10.32 | [Google MediaPipe](https://github.com/google-ai-edge/mediapipe), Apache License 2.0; bundled package LICENSE and NOTICE |
| Hand Landmarker model, float16 version 1 | [Official model documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/index#models); model and its source/license details are recorded in `models/README.md` |
| OpenCV contrib Python 4.11.0.86 | [OpenCV Python](https://github.com/opencv/opencv-python), Apache License 2.0; its wheel includes additional third-party and multimedia notices |
| Pillow | [Pillow](https://github.com/python-pillow/Pillow), HPND/PIL and bundled codec notices |
| NumPy | [NumPy](https://numpy.org), BSD-style terms and bundled numerical-library notices |
| Matplotlib and dependencies | [Matplotlib](https://matplotlib.org), Matplotlib license and dependency notices; installed to satisfy MediaPipe, not used to display the application |
| Python | [Python Software Foundation](https://docs.python.org/3/license.html), PSF License Agreement and included notices |
| Tcl/Tk | [Tcl/Tk](https://www.tcl.tk/software/tcltk/license.html), Tcl/Tk license terms |
| PyInstaller bootloader | [PyInstaller](https://pyinstaller.org/en/stable/license.html), GPL with a special exception allowing bundled applications to use their own license |

The build also includes the installed license files of absl-py, flatbuffers,
sounddevice/PortAudio, cffi, pycparser, contourpy, cycler, fonttools, kiwisolver,
packaging, pyparsing, python-dateutil, six, and packaging dependencies where
distributed. These files, rather than this short index, contain the applicable
license text. `licenses/DEPENDENCIES.txt` records the versions in each build.

No third-party author endorses PPhandcontrol. PowerPoint, Windows, Adobe
Acrobat, and Google Slides are trademarks of their respective owners.
