#!/usr/bin/env python3
"""Audit Claude Code skills and slash commands for path, spec and security problems.

Checks (per Agent Skills specification, agentskills.io):
  * every skill is at <root>/skills/<name>/SKILL.md (exact filename, exact depth)
  * YAML frontmatter exists; `name` matches the folder name 100% and the spec's
    naming rules; `description` is 1..1024 characters
  * SKILL.md length (FAIL above --max-lines, default 500)
  * no dynamic-context syntax (shell commands executed before the skill loads)
  * no commands that read tokens/credentials and send them over the network

Scans ~/.claude and ./.claude by default. Standard library only; read-only.
Exit code: 0 = no FAIL findings, 1 = at least one FAIL, 2 = usage error.

Usage:
  python audit_skills_security.py [--root DIR ...] [--json] [--strict]
                                  [--allow-local-dynamic] [--max-lines N] [--ignore NAME]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# `!` immediately followed by a backtick-quoted command, or a ```! fenced block.
DYN_INLINE_RE = re.compile(r"!`([^`\n]+)`")
DYN_FENCE_RE = re.compile(r"^\s*```!\s*$")
NETWORK_RE = re.compile(
    r"\b(curl|wget|invoke-webrequest|invoke-restmethod|iwr|irm|ncat|netcat|nc|scp|sftp|ftp|"
    r"telnet|nslookup|dig)\b|https?://|\bfetch\(|requests\.(get|post|put)|urllib",
    re.IGNORECASE,
)
SECRET_RE = re.compile(
    r"GITHUB_TOKEN|GH_TOKEN|GITHUB_PAT|ANTHROPIC_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|"
    r"AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|SUPABASE_SERVICE_ROLE|SERVICE_ROLE_KEY|"
    r"VERCEL_TOKEN|NPM_TOKEN|\.credentials\.json|\.ssh[/\\]|id_rsa|id_ed25519|\.netrc|"
    r"\.npmrc|\.git-credentials|gh\s+auth\s+token|git\s+credential|\bprintenv\b|"
    r"\benv\s*\||\bset\s*\||Get-ChildItem\s+env:|\$env:\w*(TOKEN|KEY|SECRET)|"
    r"(^|[\s\"'/\\])\.env(\.\w+)?\b|security\s+find-generic-password",
    re.IGNORECASE,
)
SKIP_DIRS = {"plugins", "cache", "projects", "backups", "node_modules", ".git",
             "sessions", "shell-snapshots", "session-env", "state"}
TEXT_SUFFIXES = {".md", ".markdown", ".txt", ".yaml", ".yml"}


class Report:
    def __init__(self) -> None:
        self.findings: list[dict] = []
        self.skills = 0
        self.commands = 0

    def add(self, level: str, code: str, path: Path, msg: str, line: int | None = None) -> None:
        self.findings.append({"level": level, "code": code, "path": str(path),
                              "line": line, "message": msg})

    def count(self, level: str) -> int:
        return sum(1 for f in self.findings if f["level"] == level)


def read_text(path: Path, rep: Report) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        rep.add("FAIL", "ENCODING", path, "file is not valid UTF-8")
    except OSError as exc:
        rep.add("FAIL", "UNREADABLE", path, f"cannot read file: {exc}")
    return None


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Minimal YAML reader: top-level `key: value`, quoted and block scalars."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None
    data: dict[str, str] = {}
    key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", raw)
        if m and not raw[0].isspace():
            key, val = m.group(1), m.group(2).strip()
            if val in ("|", ">", "|-", ">-", "|+", ">+"):
                val = ""
            elif len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            data[key] = val
        elif key and raw[0].isspace():
            data[key] = (data[key] + " " + raw.strip()).strip()
    return data


def scan_content(path: Path, text: str, rep: Report, allow_local_dynamic: bool) -> None:
    """Flag dynamic-context syntax and token-exfiltration patterns."""
    in_dyn_fence = False
    for no, line in enumerate(text.splitlines(), 1):
        dyn_cmds = [m.group(1) for m in DYN_INLINE_RE.finditer(line)]
        if DYN_FENCE_RE.match(line):
            in_dyn_fence = True
            rep.add("WARN" if allow_local_dynamic else "FAIL", "DYNAMIC_CONTEXT", path,
                    "dynamic-context fenced block (commands run before the skill loads)", no)
            continue
        if in_dyn_fence:
            if line.strip().startswith("```"):
                in_dyn_fence = False
                continue
            dyn_cmds.append(line)
        for cmd in dyn_cmds:
            risky = NETWORK_RE.search(cmd) or SECRET_RE.search(cmd)
            if risky:
                rep.add("FAIL", "DYNAMIC_CONTEXT_EXFIL", path,
                        f"dynamic-context command touches network/secrets: {cmd.strip()[:120]}", no)
            elif not in_dyn_fence:
                rep.add("WARN" if allow_local_dynamic else "FAIL", "DYNAMIC_CONTEXT", path,
                        f"dynamic-context command: {cmd.strip()[:120]}", no)
        if NETWORK_RE.search(line) and SECRET_RE.search(line):
            if not any(f["path"] == str(path) and f["line"] == no
                       and f["code"] == "DYNAMIC_CONTEXT_EXFIL" for f in rep.findings):
                rep.add("FAIL", "TOKEN_EXFIL", path,
                        f"credential reference and network call on one line: {line.strip()[:120]}", no)
        elif re.search(r"gh\s+auth\s+token|\.credentials\.json|\.git-credentials|id_rsa|id_ed25519",
                       line, re.IGNORECASE):
            rep.add("WARN", "SECRET_READ", path,
                    f"reads a credential store: {line.strip()[:120]}", no)


def audit_skill_dir(skill_dir: Path, rep: Report, args: argparse.Namespace) -> None:
    entries = {p.name: p for p in skill_dir.iterdir()}
    skill_md = entries.get("SKILL.md")
    if skill_md is None:
        wrong = [n for n in entries if n.lower() in ("skill.md", "skills.md", "skill.markdown")]
        nested = [p for p in skill_dir.rglob("SKILL.md")]
        if wrong:
            rep.add("FAIL", "WRONG_FILENAME", entries[wrong[0]],
                    "file must be named exactly SKILL.md (case-sensitive)")
        elif nested:
            for p in nested:
                rep.add("FAIL", "WRONG_DEPTH", p,
                        f"SKILL.md is nested too deep; expected {skill_dir.parent / p.parent.name / 'SKILL.md'}")
        else:
            rep.add("WARN", "NO_SKILL_MD", skill_dir, "folder under skills/ has no SKILL.md")
        return
    if not skill_md.is_file():
        rep.add("FAIL", "WRONG_FILENAME", skill_md, "SKILL.md is not a regular file")
        return

    rep.skills += 1
    text = read_text(skill_md, rep)
    if text is None:
        return
    folder = skill_dir.name
    fm = parse_frontmatter(text)
    if fm is None:
        rep.add("FAIL", "NO_FRONTMATTER", skill_md, "missing YAML frontmatter delimited by '---' lines", 1)
    else:
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if not name:
            rep.add("FAIL", "NAME_MISSING", skill_md, "frontmatter has no `name`")
        else:
            if name != folder:
                rep.add("FAIL", "NAME_MISMATCH", skill_md,
                        f"name '{name}' does not match folder '{folder}' (violates the spec; the skill may not be found)")
            if len(name) > 64 or not NAME_RE.match(name):
                rep.add("FAIL", "NAME_INVALID", skill_md,
                        f"name '{name}' must be 1-64 chars of a-z, 0-9 and single hyphens, "
                        "not starting or ending with a hyphen")
        if not desc:
            rep.add("FAIL", "DESC_MISSING", skill_md, "frontmatter has no `description`")
        elif len(desc) > 1024:
            rep.add("FAIL", "DESC_TOO_LONG", skill_md, f"description is {len(desc)} chars (max 1024)")
        elif len(desc) < 40:
            rep.add("WARN", "DESC_VAGUE", skill_md,
                    "description is very short; say what the skill does and when to use it")

    n_lines = text.count("\n") + 1
    if n_lines > args.max_lines:
        rep.add("FAIL", "TOO_LONG", skill_md, f"SKILL.md has {n_lines} lines (limit {args.max_lines})")

    for p in sorted(skill_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT_SUFFIXES:
            body = text if p == skill_md else read_text(p, rep)
            if body is not None:
                scan_content(p, body, rep, args.allow_local_dynamic)


def audit_claude_dir(claude_dir: Path, rep: Report, args: argparse.Namespace) -> None:
    skills_root = claude_dir / "skills"
    if skills_root.is_dir():
        for child in sorted(skills_root.iterdir()):
            if child.is_dir() and child.name in args.ignore:
                continue
            if child.is_dir():
                audit_skill_dir(child, rep, args)
            elif child.name.lower() == "skill.md":
                rep.add("FAIL", "WRONG_DEPTH", child,
                        "SKILL.md sits directly in skills/; it must be in skills/<name>/SKILL.md")

    for sub in ("commands", "agents"):
        d = claude_dir / sub
        if d.is_dir():
            for p in sorted(d.rglob("*.md")):
                rep.commands += 1
                body = read_text(p, rep)
                if body is not None:
                    scan_content(p, body, rep, args.allow_local_dynamic)

    # Skills saved in the wrong place are invisible to the model.
    for dirpath, dirnames, filenames in os.walk(claude_dir):
        here = Path(dirpath)
        if here == claude_dir:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and d != "skills"]
        else:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower() == "skill.md":
                rep.add("FAIL", "MISPLACED", here / fn,
                        f"skill file outside {skills_root}; move it to {skills_root / here.name / 'SKILL.md'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", action="append", type=Path, metavar="DIR",
                    help="a .claude directory to scan (repeatable). Default: ~/.claude and ./.claude")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--strict", action="store_true", help="treat WARN as FAIL")
    ap.add_argument("--allow-local-dynamic", action="store_true",
                    help="downgrade dynamic-context commands with no network/secret access to WARN")
    ap.add_argument("--ignore", action="append", default=["synced"], metavar="NAME",
                    help="folder under skills/ to skip (repeatable). Default: synced "
                         "(app-managed skill sync folder)")
    ap.add_argument("--max-lines", type=int, default=500, help="SKILL.md line limit (default 500)")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    roots = args.root or [Path.home() / ".claude", Path.cwd() / ".claude"]
    rep = Report()
    seen: set[Path] = set()
    scanned: list[str] = []
    for root in roots:
        root = root.expanduser()
        try:
            key = root.resolve()
        except OSError:
            key = root
        if key in seen:
            continue
        seen.add(key)
        if not root.is_dir():
            if args.root:
                rep.add("FAIL", "ROOT_MISSING", root, "directory does not exist")
            continue
        scanned.append(str(root))
        audit_claude_dir(root, rep, args)

    if args.strict:
        for f in rep.findings:
            if f["level"] == "WARN":
                f["level"] = "FAIL"
    fails, warns = rep.count("FAIL"), rep.count("WARN")

    if args.json:
        print(json.dumps({"scanned": scanned, "skills": rep.skills, "commands": rep.commands,
                          "fail": fails, "warn": warns, "findings": rep.findings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"Scanned: {', '.join(scanned) or '(nothing found)'}")
        for f in sorted(rep.findings, key=lambda x: (x["level"], x["path"], x["line"] or 0)):
            loc = f["path"] + (f":{f['line']}" if f["line"] else "")
            print(f"[{f['level']}] {f['code']}: {loc}\n       {f['message']}")
        print(f"\n{rep.skills} skill(s), {rep.commands} command/agent file(s): "
              f"{fails} FAIL, {warns} WARN -> {'FAILED' if fails else 'PASSED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
