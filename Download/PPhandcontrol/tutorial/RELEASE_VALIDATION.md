# Version 1.1.1 validation

- 82 automated tests pass for thumbs, pointing swipes, settings migration,
  duplicate prevention, camera lifecycle, and Windows navigation commands.
- New SDK integration tests construct the actual MediaPipe options and run
  the complete camera worker with the bundled model on a synthetic video
  frame. Only the hardware capture is replaced in this test.
- A local camera-0 startup check produced a 640 x 480 frame, completed model
  inference, and released the camera. It saved no images and sent no keys.
- The source runtime smoke test passes using the exact camera configuration
  and initializes Tk. Windows release CI requires the same frozen-EXE smoke
  test before publication; camera_configuration must be passed in self-test.json.
- The earlier 1.1.0 smoke test used separate settings and missed a misspelled
  classifier argument in the camera worker. Version 1.1.1 fixes that argument
  and shares the configuration between the worker and smoke test.
- Previous actual-model sample checks classified Google's thumbs-up sample,
  its mirror, and its rotated thumbs-down variant. Synthetic 3D landmarks
  cover pointing into the camera, both hands and unintended movement rejection.

Live thumb/pointing accuracy and full viewer rehearsal on the user's hardware
are not measured by these checks. Use VALIDATION.md before presenting.
The local unsigned EXE may be blocked by Application Control; an existing
approved Python environment can run the updated source.
