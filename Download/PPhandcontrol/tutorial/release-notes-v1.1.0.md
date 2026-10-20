# PPhandcontrol 1.1.0 — thumbs first, pointing optional

- **Thumbs** is the default: thumbs up Next, thumbs down Previous.
- **Point & swipe** is selectable: index finger toward the camera, left Next,
  right Previous. The old open-palm gesture is removed.
- A trained offline recognizer confirms thumb poses after a brief hold;
  holding a pose sends one command. Relax it before repeating.
- Mode selection, updated live instructions, new illustrations and text guide.
- Legacy settings migrate to Thumbs without retaining reversed swipe directions.

Download PPhandcontrol-windows-x64.zip, close the old app, extract to a fresh
folder, and run PPhandcontrol.exe. No Python installation is required. The
license, text guide and runtime files are included. The README's one-click
download link points to this release automatically.

80 automated tests and actual-model sample checks pass. Windows CI validates
the packaged model/Tk runtime before publication. Real-camera gesture accuracy
and full presentation rehearsal are not measured; see the included validation
record and practice on your setup. Credited to Mohamed Sherif under the same
free-use, no-sale and attribution license. The Windows EXE is unsigned.
