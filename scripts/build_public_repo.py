#!/usr/bin/env python
"""Build the clean public repository from the development tree.

The development repository keeps internal notes, client names and the real-data acceptance captures in
its history, so the public repository is a fresh history: one release commit from the current tree
minus an explicit exclusion list, plus one follow-up commit that pins the marketplace metadata to the
release commit. Nothing from the private history is copied.

Run from the development repository root:  python scripts/build_public_repo.py D:/spilot-public
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

EXCLUDE = (
    # internal working notes: private history, client context, production hosts
    "docs/HANDOFF-ROCK.md",
    "docs/ICP-ALETRA-DRAFT.md",
    "docs/MULTI-MAILBOX-AUDIT.md",
    "docs/GSHEET-WORKFLOW-AUDIT.md",
    "docs/PHASE1-AUDIT.md",
    "docs/PHASE2-AUDIT.md",
    "docs/PHASE3-AUDIT.md",
    "docs/PHASE4-AUDIT.md",
    "docs/PHASE35-AUDIT.md",
    "docs/PHASE36-AUDIT.md",
    "docs/ROCKSCRAPER-AUDIT.md",
    "docs/LIVE-MAILBOX-TEST-PLAN.md",
    "docs/phase3-demo-transcript.md",
    "docs/screenshots/acceptance-20261108",
    "scripts/acceptance_v11.py",
)
GITIGNORE = "__pycache__/\n*.py[cod]\n.pytest_cache/\n.venv/\n*.db\n*.db-journal\n*.db-wal\n*.db-shm\n"
AUTHOR = ("ROCK", "ranggaoscar@users.noreply.github.com")
RELEASE_MESSAGE = """SalesPilot v1.1.0 — the AI sales desk for Hermes

Collect leads from evidence, draft outreach, send only after a human approves, and track replies and
who to follow up today. Sends nothing on its own: every email waits for a host approval prompt, and a
refusal, bounce or do-not-contact stops a draft that was written before it.

Ships the Hermes tools, the desktop workspace, SMTP/IMAP adapters that keep credentials in Hermes
secrets, the plugin lifecycle tests and the marketplace metadata.
"""
PIN_MESSAGE = "chore(catalog): pin sha and cover image to the v1.1.0 commit"


def run(*args: str, cwd: Path) -> str:
    result = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"{' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def main() -> int:
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "D:/spilot-public")
    dev = Path(__file__).resolve().parent.parent
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # 1. Export the tracked tree only, so nothing untracked or ignored leaks in.
    subprocess.run(f'git archive HEAD | tar -x -C "{dest}"', shell=True, cwd=str(dev), check=True)

    # 2. Drop internal material.
    for rel in EXCLUDE:
        target = dest / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()

    (dest / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

    # 3. Fresh history: one release commit.
    run("git", "init", "-q", "-b", "main", cwd=dest)
    run("git", "add", "-A", cwd=dest)
    run("git", "-c", f"user.name={AUTHOR[0]}", "-c", f"user.email={AUTHOR[1]}",
        "commit", "-q", "-m", RELEASE_MESSAGE, cwd=dest)
    release = run("git", "rev-parse", "HEAD", cwd=dest)

    # 4. Pin the catalog to the release commit and record it as its own commit.
    for path in (dest / "catalog" / "hermes-salespilot.yaml", dev / "catalog" / "hermes-salespilot.yaml"):
        text = path.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines(keepends=True):
            if line.startswith("sha:"):
                line = f"sha: {release}\n"
            elif line.startswith("image:"):
                line = ("image: https://raw.githubusercontent.com/ranggaoscar/hermes-salespilot/"
                        f"{release}/assets/catalog-cover.png\n")
            lines.append(line)
        path.write_text("".join(lines), encoding="utf-8")
    run("git", "add", "-A", cwd=dest)
    run("git", "-c", f"user.name={AUTHOR[0]}", "-c", f"user.email={AUTHOR[1]}",
        "commit", "-q", "-m", PIN_MESSAGE, cwd=dest)

    head = run("git", "rev-parse", "HEAD", cwd=dest)
    print(f"release commit: {release}")
    print(f"public HEAD:    {head}")
    print(f"files:          {len(run('git', 'ls-files', cwd=dest).splitlines())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
