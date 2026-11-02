"""Fetch FDA label "Drug Interactions" sections from openFDA.

For every ingredient in the lexicon, query the openFDA drug label endpoint and
store the label's Drug Interactions text with its SPL set id and a DailyMed
link, in ``api/ddi/data/label_evidence.json``. The engine then cites the label
and quotes the passage that names the interacting drug.

Usage::

    python -m scripts.fetch_label_evidence [--out PATH] [--api-key KEY] [--only warfarin,fluconazole]

openFDA allows 240 requests/minute (1,000/day) without a key; pass
``--api-key`` (or set ``OPENFDA_API_KEY``) for higher limits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Optional

import httpx

from api.ddi.evidence import DEFAULT_DATA_DIR
from api.ddi.lexicon import DRUGS

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}"

# Ingredients whose openFDA generic name differs from the lexicon key.
GENERIC_QUERY = {
    "alcohol": None, "grapefruit juice": None, "st john's wort": None, "omega-3 fatty acids": None,
    "ethinyl estradiol": "ethinyl estradiol", "potassium chloride": "potassium chloride",
    "valproate": "divalproex sodium", "insulin": "insulin glargine", "phytonadione": "phytonadione",
}


def parse_label(result: dict) -> Optional[dict]:
    set_id = result.get("set_id")
    sections = result.get("drug_interactions") or result.get("drug_interactions_table") or []
    if not set_id or not sections:
        return None
    openfda = result.get("openfda") or {}
    title = ", ".join((openfda.get("brand_name") or [])[:2]) or ", ".join((openfda.get("generic_name") or [])[:1])
    return {
        "set_id": set_id,
        "title": f"{title} - FDA label, Drug Interactions" if title else "FDA label, Drug Interactions",
        "url": DAILYMED_URL.format(set_id=set_id),
        "effective_time": result.get("effective_time"),
        "drug_interactions": " ".join(s if isinstance(s, str) else json.dumps(s) for s in sections),
    }


def fetch_one(client: httpx.Client, generic: str, api_key: Optional[str]) -> Optional[dict]:
    params = {"search": f'openfda.generic_name.exact:"{generic.upper()}"', "limit": 1}
    if api_key:
        params["api_key"] = api_key
    r = client.get(OPENFDA_URL, params=params)
    if r.status_code == 404:  # openFDA returns 404 for "no matches"
        params["search"] = f'openfda.generic_name:"{generic}"'
        r = client.get(OPENFDA_URL, params=params)
        if r.status_code == 404:
            return None
    r.raise_for_status()
    results = r.json().get("results") or []
    return parse_label(results[0]) if results else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_DATA_DIR / "label_evidence.json")
    ap.add_argument("--api-key", default=os.getenv("OPENFDA_API_KEY"))
    ap.add_argument("--only", help="comma-separated ingredient subset")
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args(argv)

    names = [n.strip() for n in args.only.split(",")] if args.only else sorted(DRUGS)
    labels, missing = {}, []
    with httpx.Client(timeout=20.0) as client:
        for name in names:
            generic = GENERIC_QUERY.get(name, name)
            if generic is None:
                continue
            try:
                lab = fetch_one(client, generic, args.api_key)
            except httpx.HTTPError as exc:
                print(f"  ! {name}: {exc}", file=sys.stderr)
                lab = None
            if lab:
                labels[name] = lab
            else:
                missing.append(name)
            time.sleep(args.sleep)

    payload = {"source": "openFDA drug label API", "retrieved": date.today().isoformat(), "labels": labels}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    print(f"wrote {len(labels)} labels to {args.out}; no label found for {len(missing)}: {missing}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
