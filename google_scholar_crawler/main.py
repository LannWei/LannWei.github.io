"""Fetch the Google Scholar citation count for the homepage badge.

Google Scholar often blocks requests from GitHub Actions runners, and the
`scholarly` library then retries forever (it swallows ordinary exceptions,
so in-process timeouts do not stop it). Each attempt therefore runs in its
own subprocess with a hard time limit:

  1. one plain request to the public profile page;
  2. the `scholarly` library as a fallback.

If both are blocked the script exits cleanly without publishing, so the
badge keeps showing the last good value.

Writes results/gs_data.json and results/gs_data_shieldsio.json, and sets the
step output `ok=true|false` for the workflow.
"""
import json
import logging
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

scholar_id = os.environ.get("GOOGLE_SCHOLAR_ID", "").strip()
if not scholar_id:
    raise SystemExit("Set GOOGLE_SCHOLAR_ID before running the crawler.")


def from_profile_page():
    """One plain request to the public profile page; parse the stats table."""
    url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    stats = re.findall(r'class="gsc_rsb_std">(\d+)<', html)
    name = re.search(r'id="gsc_prf_in">([^<]+)<', html)
    if len(stats) < 6:
        raise RuntimeError("stats table not found (probably a captcha page)")
    return {
        "name": name.group(1) if name else None,
        "citedby": int(stats[0]),
        "hindex": int(stats[2]),
        "i10index": int(stats[4]),
        "source": "profile-page",
    }


def from_scholarly():
    from scholarly import scholarly
    scholarly.set_timeout(15)
    scholarly.set_retries(1)
    author = scholarly.search_author_id(scholar_id)
    scholarly.fill(author, sections=["basics", "indices"])
    return {
        "name": author.get("name"),
        "citedby": author.get("citedby", 0),
        "hindex": author.get("hindex"),
        "i10index": author.get("i10index"),
        "source": "scholarly",
    }


FETCHERS = {"profile_page": from_profile_page, "scholarly": from_scholarly}

# Child mode: run one fetcher and print its result as JSON on the last line.
if len(sys.argv) == 3 and sys.argv[1] == "--attempt":
    print(json.dumps(FETCHERS[sys.argv[2]]()))
    sys.exit(0)


def run_attempt(name: str, limit: int) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, os.path.abspath(__file__), "--attempt", name],
            capture_output=True, text=True, timeout=limit,
        )
    except subprocess.TimeoutExpired:  # the child is killed by subprocess.run
        raise RuntimeError(f"gave up after {limit}s")
    if proc.returncode != 0:
        lines = (proc.stderr or proc.stdout or "no output").strip().splitlines()
        raise RuntimeError(lines[-1] if lines else f"exit code {proc.returncode}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def set_output(ok: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"ok={'true' if ok else 'false'}\n")


summary = None
for name, limit in (("profile_page", 45), ("scholarly", 100)):
    logging.info("Trying %s (limit %ss)", name, limit)
    try:
        summary = run_attempt(name, limit)
        break
    except Exception as e:  # blocked, captcha, network error, time limit...
        logging.warning("%s failed: %s", name, e)

if summary is None:
    logging.warning("Google Scholar blocked every attempt; keeping the previous badge value.")
    set_output(False)
    sys.exit(0)

summary["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
print(json.dumps(summary, indent=2))

os.makedirs("results", exist_ok=True)
with open("results/gs_data.json", "w") as f:
    json.dump(summary, f, ensure_ascii=False)
with open("results/gs_data_shieldsio.json", "w") as f:
    json.dump({"schemaVersion": 1, "label": "citations", "message": f"{summary['citedby']}"}, f)
set_output(True)
