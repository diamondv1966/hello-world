#!/usr/bin/env python3
"""Install the D-Skill playbook kit into a user-level .claude directory.

  python install.py                 # installs into ~/.claude (C:\\Users\\<you>\\.claude on Windows)
  python install.py --target DIR    # installs into another .claude directory
  python install.py --dry-run       # show what would change

What it does:
  * copies .claude/skills/00-fable-d-skill-playbook/ (an existing copy is backed up first)
  * /takeover and /evolve: if you already have these commands, your file is kept and only
    the D-SKILL-PREFLIGHT block is inserted/refreshed (a .bak copy is made); otherwise the
    kit's version is installed
  * runs audit_skills_security.py on the target and reports the result

Standard library only. Nothing is sent over the network.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

SKILL = "00-fable-d-skill-playbook"
BLOCK_RE = re.compile(r"<!-- D-SKILL-PREFLIGHT:BEGIN -->.*?<!-- D-SKILL-PREFLIGHT:END -->\n?", re.S)
KIT = Path(__file__).resolve().parent / ".claude"


def merge_command(src: Path, dst: Path, dry: bool) -> str:
    new = src.read_text(encoding="utf-8")
    if not dst.exists():
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(new, encoding="utf-8", newline="\n")
        return "installed"
    old = dst.read_text(encoding="utf-8-sig")
    if old == new:
        return "already up to date"
    block = BLOCK_RE.search(new).group(0)
    if BLOCK_RE.search(old):
        merged = BLOCK_RE.sub(lambda _: block, old, count=1)
    else:
        m = re.match(r"---\r?\n.*?\r?\n---\r?\n", old, re.S)  # keep frontmatter first
        head, body = (m.group(0), old[m.end():]) if m else ("", old)
        merged = f"{head}\n{block}\n{body.lstrip()}"
    if merged == old:
        return "already up to date"
    if not dry:
        shutil.copy2(dst, dst.with_suffix(dst.suffix + ".bak"))
        dst.write_text(merged, encoding="utf-8", newline="\n")
    return "preflight block merged into your existing file (backup: .bak)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Install the D-Skill playbook kit")
    ap.add_argument("--target", type=Path, default=Path.home() / ".claude")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    target, dry = args.target.expanduser(), args.dry_run
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    src_skill, dst_skill = KIT / "skills" / SKILL, target / "skills" / SKILL
    if not (src_skill / "SKILL.md").is_file():
        print(f"ERROR: kit is incomplete, {src_skill / 'SKILL.md'} not found")
        return 2
    print(f"Target: {target}{'  (dry run)' if dry else ''}")

    if dst_skill.exists():
        backup = target / "backups" / f"{SKILL}-{time.strftime('%Y%m%d-%H%M%S')}"
        print(f"  skill: replacing existing copy, backup -> {backup}")
        if not dry:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst_skill), str(backup))
    if not dry:
        shutil.copytree(src_skill, dst_skill, ignore=shutil.ignore_patterns("__pycache__"))
    print(f"  skill: {dst_skill / 'SKILL.md'}")

    for name in ("takeover.md", "evolve.md"):
        status = merge_command(KIT / "commands" / name, target / "commands" / name, dry)
        print(f"  /{name[:-3]}: {status}")

    if dry:
        return 0
    if not (dst_skill / "SKILL.md").is_file():
        print("ERROR: SKILL.md is not at the expected path after install")
        return 1
    print("\nRunning security audit on the target...\n")
    audit = dst_skill / "scripts" / "audit_skills_security.py"
    rc = subprocess.call([sys.executable, str(audit), "--root", str(target)])
    if rc:
        print("\nInstalled, but the audit found problems above (they may be in your other skills).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
