# PPhandcontrol 1.1.1 — camera startup fix

Fixes the gesture recognizer startup error in 1.1.0:
`unexpected keyword argument canned_gestures_classifier_options`.
The installed MediaPipe SDK requires `canned_gesture_classifier_options`.

The camera and packaged smoke test now share the same recognizer settings.
New integration tests initialize the real bundled model through the camera
worker and process a video frame using the pinned SDK, without a webcam.

Thumbs up Next / thumbs down Previous remain the default. Point & swipe
remains optional: left Next, right Previous.

Close the old app, download PPhandcontrol-windows-x64.zip, extract into a
fresh folder, and launch PPhandcontrol.exe. The license and How to use.txt
are included. The README one-click download points to this release.

Live gesture accuracy and presentation rehearsal still need checking on your
setup; see tutorial/VALIDATION.md. Created by Mohamed Sherif.
