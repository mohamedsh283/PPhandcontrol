# Live rehearsal checklist — version 1.1.1

Record Windows/camera/viewer versions, lighting, distance and sensitivity here.
Empty boxes mean not checked. Automated tests do not measure live accuracy.

- [ ] New EXE reports v1.1.1 and defaults to Thumbs on a fresh settings file.
- [ ] Camera, mode, sensitivity and profile persist; every launch starts paused.
- [ ] Thumbs up sends Next; thumbs down sends Previous after a short hold.
- [ ] Holding a thumb for five seconds sends exactly one command.
- [ ] Relaxing/lowering the thumb allows the same direction again.
- [ ] Brief recognition flicker or hand loss does not duplicate a held thumb.
- [ ] Point & swipe: index toward the camera, left Next, right Previous.
- [ ] Relaxing/retracting the index finger allows another pointing swipe.
- [ ] Open palms, ordinary hand movement, and multiple hands do not navigate.
- [ ] Mode/settings changes pause input and clear unfinished gestures.
- [ ] Minimized operation and global Ctrl+Alt+P/Q work while presenting.
- [ ] PowerPoint animations and PDF page changes match the selected profile.
- [ ] Camera failure pauses input, retry recovers, and quitting releases camera.

For each of thumbs up, thumbs down, pointing left and pointing right, record
20 deliberate trials: correct / missed / wrong / duplicate commands. Aim for
18 correct single commands out of 20, with zero duplicates. This is a rehearsal
target, not a measured accuracy claim. Rehearse on the actual presentation setup.
