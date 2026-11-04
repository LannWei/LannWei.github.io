"""Fetch the Google Scholar citation count for the homepage badge.

Google Scholar often blocks requests from GitHub Actions runners, so this
script tries a single lightweight page fetch first, falls back to the
`scholarly` library, and if both are blocked it exits cleanly without
publishing (the badge keeps showing the last good value).

Writes results/gs_data.json and results/gs_data_shieldsio.json, and sets the
step output `ok=true|false` for the workflow.
"""
import json
import logging
import os
import re
import signal
import sys
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

scholar_id = os.environ.get("GOOGLE_SCHOLAR_ID", "").strip()
if not scholar_id:
    raise SystemExit("Set GOOGLE_SCHOLAR_ID before running the crawler.")


def set_output(ok: bool) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"ok={'true' if ok else 'false'}\n")


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


class AttemptTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise AttemptTimeout("gave up after the time limit")


# scholarly keeps retrying forever when Scholar shows a captcha, so every
# attempt gets a hard wall-clock limit (seconds).
ATTEMPTS = ((from_profile_page, 45), (from_scholarly, 100))

summary = None
signal.signal(signal.SIGALRM, _on_alarm)
for fetch, limit in ATTEMPTS:
    logging.info("Trying %s (limit %ss)", fetch.__name__, limit)
    signal.alarm(limit)
    try:
        summary = fetch()
        break
    except BaseException as e:  # blocked, captcha, network error, time limit...
        if isinstance(e, KeyboardInterrupt):
            raise
        logging.warning("%s failed: %s", fetch.__name__, e)
    finally:
        signal.alarm(0)

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
