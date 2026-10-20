# PPhandcontrol

Control your PowerPoint presentations and PDFs with hand gestures, using only your webcam.

> [!IMPORTANT]
> **Setup takes about 2 minutes after downloading. Follow the Windows steps below in order and keep the entire app folder together.** This app is free and unsigned, so Windows may show a first-run warning. If device policy blocks the EXE, contact your administrator or use the source setup below.

**Windows 10/11 x64 · Version 1.1.1 · Created by Mohamed Sherif.**

![Thumbs up: Next; thumbs down: Previous. Optional pointing swipes: left Next, right Previous.](tutorial/gestures.svg)

## Download and run

### [⬇ Download PPhandcontrol for Windows](https://github.com/mohamedsh283/PPhandcontrol/releases/latest/download/PPhandcontrol-windows-x64.zip)

**One click downloads the complete app folder as a ZIP:** **PPhandcontrol.exe**,
**License.txt**, **How to use.txt**, and all runtime files. Download the new ZIP
when upgrading; close the old app and extract into a fresh folder.

1. Click **Download PPhandcontrol for Windows** above.
2. Right-click the ZIP → **Extract All** → open **PPhandcontrol**.
3. Run **PPhandcontrol.exe**. No Python installation is needed. Keep `_internal` beside the EXE.
4. Leave **Gesture mode** on **Thumbs** (default) and choose your presentation viewer.
5. Open your slideshow or PDF, click the slide/page, and press **Ctrl+Alt+P** to resume. The app always starts paused.
6. Show **thumbs up for Next**, or **thumbs down for Previous**. Relax your thumb briefly before repeating.

The [extracted app folder](Download/PPhandcontrol) is also in this repository.
Read its **How to use.txt**, or open [the illustrated offline guide](tutorial/index.html).

**Version 1.1.1 fixes the gesture recognizer startup error in 1.1.0.**
Close the old app and extract the new download into a fresh folder.

## Two gesture modes

| Mode | Next | Previous | Repeat |
| --- | --- | --- | --- |
| **Thumbs — default** | Hold 👍 thumbs up briefly | Hold 👎 thumbs down briefly | Lower/relax the thumb for about 0.25 seconds, then show it again |
| **Point & swipe — optional** | Extend your index finger toward the camera and swipe **left** in the mirrored preview | Point and swipe **right** | Relax/retract your index finger before the next swipe |

**Thumbs** uses a trained offline gesture classifier. You do not need to move
your hand across the screen or hold it in one exact position. At Medium
sensitivity the pose is confirmed for about **0.35 seconds**. A held thumb
sends **one command**, even if you keep it up. You may switch directly to a
stable opposite thumb after the cooldown.

For **Point & swipe**, fold the other fingers and move the pointing hand
horizontally. Keep the whole hand visible; a slight angle helps if pointing
directly into the lens hides your finger. An open palm does not activate this mode.
Left/right follow the mirrored preview. Close or relax your finger while returning
your hand to its starting position to prevent a return motion from navigating.

Select the mode in the app; changing mode or settings pauses gestures and clears
incomplete input. The app remembers your choice. Existing v1.0 settings upgrade
to Thumbs by default; the old reversed-swipe setting is ignored.

## Controls and settings

| Control | Action |
| --- | --- |
| **P** in PPhandcontrol | Pause/resume |
| **Q** in PPhandcontrol | Quit and release the camera |
| **Ctrl+Alt+P** anywhere | Pause/resume without taking focus |
| **Ctrl+Alt+Q** anywhere | Quit |
| **Gesture mode** | Thumbs or Point & swipe |
| **Sensitivity** | High: shorter hold/smaller swipe; Low: longer hold/larger swipe |

There is a **0.8-second cooldown**, plus one command per held gesture. The app
continues working when minimized. Navigation is suppressed while PPhandcontrol
has focus: click your viewer to test. If a global shortcut cannot register,
the app explains the conflict and you can use its buttons or focused P/Q.

Camera, mode, sensitivity, and viewer profile are saved at
`%LOCALAPPDATA%\PPhandcontrol\settings.json`. Activation is never restored.

## Viewer profiles

| Profile | Next / previous | Setup |
| --- | --- | --- |
| PowerPoint / Google Slides | Right / Left arrow | Start slideshow and focus the slide |
| Adobe Acrobat / Reader | Ctrl+PageDown / Ctrl+PageUp | Focus the PDF document area |
| SumatraPDF | PageDown / PageUp | Use single-page or presentation mode |

PowerPoint advances normal animation steps before the next slide. Keys go to
the focused application. Browser PDF viewers are outside guaranteed compatibility.
Avoid running the viewer as administrator; Windows can block incoming keys.

## Privacy and troubleshooting

The camera is processed locally. No images are recorded or uploaded; the model
is bundled and there are no runtime downloads or app telemetry. Quit releases
the camera. If tracking is uncertain, use even lighting, one hand, and keep the
whole hand in view. Check the recognized-gesture status in the preview.

If the camera fails, close video-call/camera apps, check Windows camera
permissions, choose another camera index, or click Retry camera. Navigation
pauses on camera errors. See the [text guide](tutorial/How%20to%20use.txt).

## Run from source and build

Use 64-bit CPython 3.12 with Tcl/Tk on Windows:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pphandcontrol --self-test --report build/source-self-test.json
.venv\Scripts\python.exe -m pphandcontrol
```

Keep `models/gesture_recognizer.task` and its checksum with the source.
Build with `.venv\Scripts\python.exe scripts/build.py`. This runs checks,
packages the offline EXE, smoke-tests it, and writes the ZIP and checksum to
`dist/`. See [packaging](packaging/README.md) for exporting the GitHub folder.
Windows CI builds each main-branch push; version tags publish the verified ZIP.

## Verification

Automated tests cover both gesture modes, mode migration, held-pose duplicate
prevention, brief detection loss, sensitivity, camera errors, and Windows keys.
The actual trained model was also checked on Google's thumbs-up sample, its
mirror, and its rotated thumbs-down variant. These checks do not establish
live-camera accuracy on your hardware. See [release validation](tutorial/RELEASE_VALIDATION.md)
and the [rehearsal checklist](tutorial/VALIDATION.md). Practice before presenting.

## License and credits

Created by **Mohamed Sherif**. Free use, modification, and free redistribution
under the custom [license](LICENSE). **Do not sell original or modified copies
or claim the original work as your own.** Keep the license and credits, and
mark modifications. This is source-available software with a sale restriction.

Inspired by [Mahmoud Wael's hand-control project](https://github.com/mahmoudwaelali/hand-control),
with fresh application source. See [credits](CREDITS.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).
