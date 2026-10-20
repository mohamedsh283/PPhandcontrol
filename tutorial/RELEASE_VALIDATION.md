# Version 1.1.0 validation

- 80 automated tests pass for thumbs, pointing swipes, mode/settings migration,
  duplicate prevention, camera lifecycle, and Windows navigation commands.
- The actual offline model correctly classified Google's thumbs-up sample,
  its horizontal mirror, and its rotated thumbs-down variant. Holding each
  classification produced exactly one correct navigation command.
- Synthetic 3D landmarks test both hands and an index finger directed into
  the camera, along with rejection of open palms and vertical movement.
- The source runtime smoke test loads the Gesture Recognizer and initializes
  Tk without opening a camera. Windows release CI requires the same frozen-EXE
  smoke test before publication; see self-test.json in the download.

Live thumb/pointing accuracy and full viewer rehearsal on the user's hardware
are not measured by these checks. Use VALIDATION.md before presenting.
The local unsigned EXE may be blocked by Application Control; an existing
approved Python environment can run the updated source.
