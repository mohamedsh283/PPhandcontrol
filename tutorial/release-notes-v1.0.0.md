PPhandcontrol 1.0.0 introduces local webcam swipe navigation for Windows 10/11 x64.

- Open-palm swipe left: next slide/animation step/page. Swipe right: previous.
- Mirrored preview, tracking feedback, sensitivity, reverse directions, and saved settings.
- PowerPoint/Google Slides, Adobe Acrobat/Reader, and SumatraPDF keyboard profiles.
- Starts paused; P/Q in the app and Ctrl+Alt+P / Ctrl+Alt+Q globally.
- Offline bundled hand model, illustrated tutorial, attribution, and dependency notices.

Download **PPhandcontrol-windows-x64.zip**, extract the whole folder, and run
**PPhandcontrol.exe**. No Python installation is required. Compare the ZIP's
SHA-256 with **SHA256SUMS.txt**. This is an unsigned Windows EXE, not an Android APK.

Validation: release packaging runs the synthetic unit suite and a frozen-app
smoke test for Tk and offline blank-frame model inference. See the included
`self-test.json` for the packaged smoke-test result. Real-camera accuracy,
PowerPoint animations, Acrobat/Reader and SumatraPDF navigation, minimized
interaction, and shortcut-conflict behavior require the manual checklist in
`tutorial/VALIDATION.md`; they are not established by the automated build.
The 18/20 swipe target is an acceptance target, not a measured release claim.
Additional completed native Windows, camera and UI checks are recorded in
`tutorial/RELEASE_VALIDATION.md`. The local unsigned executable was blocked by
Windows Application Control; release publication requires the Windows CI
packaged smoke test to pass.

Created for and credited to **Mohamed Sherif**. Free use and free redistribution
under the included custom license; no sale of original or modified copies and
no false authorship claims. Inspired by Mahmoud Wael's hand-control project.
