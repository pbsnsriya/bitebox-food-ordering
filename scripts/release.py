"""Cut a release: one command, so every release is made the same way.

    python scripts/release.py 0.2.0            move the Unreleased notes of CHANGELOG.md under 0.2.0, set the version in package.json, commit and tag
    python scripts/release.py 0.2.0 --dry-run  show what would change and touch nothing
    python scripts/release.py --notes 0.2.0    print the changelog section of a version (the release workflow uses this for the GitHub Release text)

It does not push. Afterwards:  git push && git push origin v0.2.0   (one tag at a time; the tag starts the release workflow).
The version lives in package.json (and package-lock.json); the git tag is the same number with a v in front.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def repo_url() -> str:
    url = git("remote", "get-url", "origin")
    url = re.sub(r"^git@github\.com:", "https://github.com/", url)
    return re.sub(r"\.git$", "", url)


def key(version: str) -> tuple:
    """Sort key following the precedence rules of semver.org: a pre-release is older than its release, numeric identifiers compare as numbers."""
    m = SEMVER.match(version)
    assert m, version
    pre = m.group(4)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), pre is None, [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in (pre or "").split(".")])


def latest_tag() -> str | None:
    tags = [t[1:] for t in git("tag", "--list", "v*").split() if SEMVER.match(t[1:])]
    return max(tags, key=key) if tags else None


def section(changelog: str, version: str) -> str:
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: )", changelog, re.S | re.M)
    if not m:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    return m.group(1).strip() + "\n"


def relink(changelog: str) -> str:
    """Rebuild the comparison links at the bottom from the version headings."""
    repo = repo_url()
    body = re.split(r"^\[Unreleased\]: ", changelog, flags=re.M)[0].rstrip("\n")
    versions = re.findall(r"^## \[(\d[^\]]*)\]", body, re.M)
    links = [f"[Unreleased]: {repo}/compare/v{versions[0]}...HEAD"] if versions else []
    for i, v in enumerate(versions):
        links.append(f"[{v}]: {repo}/compare/v{versions[i + 1]}...v{v}" if i + 1 < len(versions) else f"[{v}]: {repo}/releases/tag/v{v}")
    return body + "\n\n" + "\n".join(links) + "\n"


def set_version(path: Path, version: str, occurrences: int) -> None:
    """Change the first `occurrences` "version" values in a package file, leaving every other byte alone."""
    text = path.read_text(encoding="utf-8")
    count = 0

    def sub(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f'{m.group(1)}"{version}"' if count <= occurrences else m.group(0)

    path.write_text(re.sub(r'("version":\s*)"[^"]*"', sub, text, count=occurrences), encoding="utf-8", newline="")


def main(argv: list[str]) -> int:
    changelog_path = ROOT / "CHANGELOG.md"
    if len(argv) == 3 and argv[1] == "--notes":
        print(section(changelog_path.read_text(encoding="utf-8"), argv[2].removeprefix("v")), end="")
        return 0
    if len(argv) < 2 or not SEMVER.match(argv[1]):
        print(__doc__)
        return 2
    version, dry = argv[1], "--dry-run" in argv
    current = latest_tag()
    if current and key(version) <= key(current):
        raise SystemExit(f"{version} is not newer than the latest version {current}")
    if not dry and git("status", "--porcelain"):
        raise SystemExit("the working tree is not clean; commit or stash first")
    if not dry and git("branch", "--show-current") not in ("main", "master"):
        raise SystemExit("release from the main branch")
    if git("tag", "--list", f"v{version}"):
        raise SystemExit(f"the tag v{version} exists already; a released version is never changed, release a new one")

    text = changelog_path.read_text(encoding="utf-8")
    m = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.S | re.M)
    if not m or not re.search(r"^- ", m.group(1), re.M):
        raise SystemExit("CHANGELOG.md has nothing under [Unreleased]; write what changed for people first")
    new = text.replace(m.group(0), f"## [Unreleased]\n\n## [{version}] - {datetime.date.today().isoformat()}\n{m.group(1).rstrip()}\n\n", 1)
    new = relink(new)
    print(f"{current or '(no tag yet)'} -> {version}\n--- notes ---\n{section(new, version)}")
    if dry:
        return 0

    changelog_path.write_text(new, encoding="utf-8", newline="\n")
    files = ["CHANGELOG.md"]
    if (ROOT / "package.json").exists():
        set_version(ROOT / "package.json", version, 1)
        files.append("package.json")
        if (ROOT / "package-lock.json").exists():
            set_version(ROOT / "package-lock.json", version, 2)          # the top of the lock file names the package twice
            files.append("package-lock.json")
    git("add", *files)
    git("commit", "-m", f"chore(release): v{version}")
    git("tag", "-a", f"v{version}", "-m", f"{ROOT.name} {version}")
    print(f"committed and tagged v{version}. Push with:  git push && git push origin v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
