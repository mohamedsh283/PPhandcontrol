"""Export a checksum-verified release ZIP as the browsable GitHub app folder."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=ROOT / "dist" / "PPhandcontrol-windows-x64.zip")
    args = parser.parse_args()
    archive = args.archive.resolve()
    expected = None
    for line in archive.with_name("SHA256SUMS.txt").read_text(encoding="ascii").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == archive.name:
            expected = fields[0].lower()
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if not expected or actual != expected:
        raise ValueError("Release archive checksum does not match SHA256SUMS.txt")
    destination = ROOT / "Download"
    app = destination / "PPhandcontrol"
    if app.exists():
        raise FileExistsError("Download/PPhandcontrol already exists. Review and remove the old distribution before replacing it.")
    destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = (destination / member.filename).resolve()
            if not path.is_relative_to(app.resolve()):
                raise ValueError(f"Unexpected archive member: {member.filename}")
            if member.file_size >= 100 * 1024 * 1024:
                raise ValueError(f"File exceeds GitHub's individual-file limit: {member.filename}")
        bundle.extractall(destination)
    shutil.copy2(ROOT / "LICENSE", app / "License.txt")
    shutil.copy2(ROOT / "tutorial" / "How to use.txt", app / "How to use.txt")
    shutil.copytree(ROOT / "tutorial", app / "tutorial", dirs_exist_ok=True)
    (app / "README.md").write_text(
        "# PPhandcontrol — ready-to-run Windows folder\n\n"
        "Created by **Mohamed Sherif**. Windows 10/11 x64.\n\n"
        "> [!IMPORTANT]\n"
        "> **Keep this entire folder together, including `_internal`.** "
        "Read **How to use.txt**, then start **PPhandcontrol.exe**. "
        "The app is free and unsigned, so Windows may show a first-run security warning.\n\n"
        "This is the extracted application, with all its required runtime files.\n\n"
        "- **PPhandcontrol.exe** — double-click to start the Windows app.\n"
        "- [How to use.txt](How%20to%20use.txt) — setup, gestures, and P/Q controls.\n"
        "- [License.txt](License.txt) — free use; no sale or false authorship.\n"
        "- **_internal/** — required runtime; keep it beside the EXE.\n"
        "- **licenses/** and the credits/notices — retain these when sharing.\n"
        "- [tutorial/](tutorial/) — illustrated offline guide and validation notes.\n\n"
        "### [⬇ Download PPhandcontrol for Windows]"
        "(https://github.com/mohamedsh283/PPhandcontrol/releases/latest/download/PPhandcontrol-windows-x64.zip)\n\n"
        "One click downloads this complete app folder as a ZIP. Choose **Extract All**, "
        "open the **PPhandcontrol** folder, and run **PPhandcontrol.exe**. "
        "No Python installation is needed. Keep the whole folder together; the EXE alone is insufficient.\n",
        encoding="utf-8",
    )
    print(f"Exported {app} from verified release {actual}")


if __name__ == "__main__":
    main()
