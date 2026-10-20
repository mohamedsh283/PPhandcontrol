# Version 1.0.0 validation record

Date: 20 October 2026. Platform: Windows x64, Python 3.12.

Completed locally:

- 69 automated tests passed: synthetic swipe sequences, settings persistence,
  stale-frame handling, camera failures/cleanup, keyboard profiles and shortcuts.
- Source runtime smoke test passed: Tk/Pillow, OpenCV, model checksum and
  offline MediaPipe inference on a blank image.
- 12 native Windows integration checks passed against a temporary receiver:
  all six profile commands, own-process focus suppression, both global shortcuts,
  thread shutdown and shortcut re-registration after cleanup.
- The real Tk UI passed paused-start, pause-on-settings-change and profile
  persistence checks, and its layout was inspected using a synthetic image.
- Camera index 0 delivered a 640 x 480 RGB frame through the tracking worker;
  inference completed and the camera was released. No camera image was saved.

The local unsigned EXE could not be launched because Windows Application
Control returned error 4551. The release workflow therefore requires the
separate GitHub Windows runner to pass the frozen-app smoke test before it
publishes a ZIP. The distributed `self-test.json` records that actual result.

Not established by these checks:

- Real-hand recognition accuracy, including the 18/20 target in each direction.
- Acrobat/Reader, SumatraPDF and Google Slides end-to-end behavior.
- Full live-presentation rehearsal with gestures while minimized.

Use `VALIDATION.md` to record those checks on the presentation computer.
