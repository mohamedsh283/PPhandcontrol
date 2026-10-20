# Manual validation record

Automated synthetic tests and blank-frame model inference do not measure real
webcam accuracy. Complete this rehearsal on the hardware and viewers you will
use. Empty boxes mean **not verified**, not passed.

Date: __________  Windows version: __________  Camera: __________

CPU: __________  Lighting/distance: __________  Sensitivity: __________

PowerPoint version: __________  Acrobat/Reader version: __________

SumatraPDF version: __________  Release/checksum: __________

- [ ] Extracted portable ZIP runs without installed Python and without an internet connection.
- [ ] Starts paused; saves camera, sensitivity, reverse flag, and profile; restarts paused.
- [ ] Preview is mirrored and landmarks follow one open hand.
- [ ] Left advances and right goes back; Reverse directions swaps this.
- [ ] P/Q work while app-focused; bare P/Q in other apps are not intercepted.
- [ ] Ctrl+Alt+P and Ctrl+Alt+Q work with the viewer focused and app minimized.
- [ ] Navigation is suppressed while PPhandcontrol itself is focused.
- [ ] PowerPoint animation steps and slide changes match manual arrow-key behavior.
- [ ] Acrobat/Reader changes exactly one PDF page per command with its profile.
- [ ] SumatraPDF changes exactly one PDF page in single-page/presentation mode.
- [ ] App stays minimized; viewer keeps keyboard focus after navigation.
- [ ] Stationary, closed, vertical-moving, and multiple hands do not navigate.
- [ ] Leaving/re-entering the camera view does not trigger a stale swipe.
- [ ] Pause/resume and settings changes clear prior motion.
- [ ] Cooldown and stable-hand rearming prevent duplicate commands.
- [ ] Camera disconnect pauses navigation and shows a useful error; reconnect/retry recovers.
- [ ] Unavailable global shortcut is explained; other controls remain usable.
- [ ] Quit releases the camera so another program can immediately use it.

## Deliberate swipe accuracy

Use normal indoor lighting and the full hand in view. Hold still to arm before
each swipe, close the palm while repositioning, and leave at least the cooldown
between trials. Count one correct command as a success; count wrong, missed,
and duplicated commands separately.

| Direction in standard preview | Trials | Correct single commands | Missed | Wrong | Duplicates |
| --- | --- | --- | --- | --- | --- |
| Left / Next | 20 | ___ | ___ | ___ | ___ |
| Right / Previous | 20 | ___ | ___ | ___ | ___ |

Target: **at least 18 of 20 correct in each direction, with zero duplicates**.

Notes, failed cases, applications unavailable for testing, and corrective work:

___________________________________________________________________________

___________________________________________________________________________
