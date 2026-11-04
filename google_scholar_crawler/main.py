"""Fetch citation counts from Google Scholar for the homepage badge.

Writes results/gs_data.json (summary) and results/gs_data_shieldsio.json
(the shields.io endpoint format used by the "citations" badge).
"""
import json
import logging
import os
from datetime import datetime, timezone

from scholarly import scholarly

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

scholar_id = os.environ.get("GOOGLE_SCHOLAR_ID", "").strip()
if not scholar_id:
    raise SystemExit("Set GOOGLE_SCHOLAR_ID before running the crawler.")

scholarly.set_timeout(20)
scholarly.set_retries(3)

logging.info("Fetching Google Scholar profile %s", scholar_id)
author = scholarly.search_author_id(scholar_id)
scholarly.fill(author, sections=["basics", "indices", "counts"])

summary = {
    "name": author.get("name"),
    "citedby": author.get("citedby", 0),
    "hindex": author.get("hindex"),
    "i10index": author.get("i10index"),
    "cites_per_year": author.get("cites_per_year", {}),
    "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
print(json.dumps(summary, indent=2))

os.makedirs("results", exist_ok=True)
with open("results/gs_data.json", "w") as f:
    json.dump(summary, f, ensure_ascii=False)

with open("results/gs_data_shieldsio.json", "w") as f:
    json.dump({"schemaVersion": 1, "label": "citations", "message": f"{summary['citedby']}"}, f)
