"""Refill the auto-updated blocks in README.md from the GitHub API.

Run by .github/workflows/build.yml on a schedule. Uses only the standard
library so the workflow needs no install step.

Each block is delimited by markers, e.g.

    <!-- releases starts -->
    ...generated...
    <!-- releases ends -->

Everything outside the markers is hand-written and never touched.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = "Byun11"
# The profile repo is this file; listing it as activity is noise.
SKIP_REPOS = {"Byun11"}
# Team repositories that live under another account but should still count.
EXTRA_REPOS = ["ansua79/kisti-mcp"]
README = Path(__file__).parent / "README.md"
TOKEN = os.environ.get("GITHUB_TOKEN")


def api(path):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "byun11-readme-builder",
            **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # A repo with no releases 404s; that is expected, not a failure.
        if e.code == 404:
            return None
        raise


def ago(iso):
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    days = (datetime.now(timezone.utc) - when).days
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 30:
        return f"{days} days ago"
    months = days // 30
    return "1 month ago" if months == 1 else f"{months} months ago"


def public_repos():
    repos = [
        r
        for r in api(f"/users/{USER}/repos?per_page=100&sort=pushed")
        if not r["fork"] and r["name"] not in SKIP_REPOS
    ]
    for full in EXTRA_REPOS:
        r = api(f"/repos/{full}")
        if r:
            repos.append(r)
    return repos


def releases_block(repos):
    rows = []
    for repo in repos:
        rel = api(f"/repos/{repo['full_name']}/releases/latest")
        if not rel:
            continue
        rows.append(
            (
                rel["published_at"],
                f"- [{repo['name']} {rel['tag_name']}]({rel['html_url']}) — {ago(rel['published_at'])}",
            )
        )
    rows.sort(reverse=True)
    return "\n".join(line for _, line in rows[:5]) or "_No releases yet._"


def activity_block(repos):
    rows = []
    for repo in sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:4]:
        desc = (repo["description"] or "").strip()
        if len(desc) > 70:
            desc = desc[:67].rstrip() + "…"
        suffix = f" — {desc}" if desc else ""
        rows.append(f"- [{repo['name']}]({repo['html_url']}){suffix} · {ago(repo['pushed_at'])}")
    return "\n".join(rows) or "_Nothing recent._"


def replace(text, name, body):
    pattern = re.compile(
        rf"(<!-- {name} starts -->)(.*?)(<!-- {name} ends -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise SystemExit(f"marker pair '{name}' not found in README.md")
    return pattern.sub(rf"\1\n{body}\n\3", text)


def main():
    repos = public_repos()
    text = README.read_text(encoding="utf-8")
    text = replace(text, "releases", releases_block(repos))
    text = replace(text, "activity", activity_block(repos))
    README.write_text(text, encoding="utf-8")
    print("README updated")


if __name__ == "__main__":
    main()
