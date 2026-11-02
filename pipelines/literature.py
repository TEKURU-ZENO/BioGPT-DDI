"""Literature mining for emerging drug-drug interactions (Phase 4).

PubMed abstracts -> sentences -> drug mentions (lexicon dictionary NER) ->
relation scoring -> novelty filter -> pharmacist review queue (JSONL).

Relation scorers
* ``pattern`` (default): transparent cue-phrase scorer with negation handling.
  It is a recall-oriented triage baseline, not a classifier to trust blindly.
* ``hf:<model-id>``: any Hugging Face text-classification model fine-tuned for
  sentence-level DDI relation extraction (e.g. a BioGPT/BioBERT model trained
  on the DDI-2013 corpus). Inputs use the ``<e1>``/``<e2>`` entity-marker
  format common to DDI-2013 models. Labels other than "negative"/"false"/
  "DDI-false" count as positive. This is the role BioGPT is suited to:
  relation extraction from literature, not open-ended clinical writing.

Every candidate goes to human review; nothing from this pipeline changes the
knowledge base automatically.

Usage::

    python -m pipelines.literature --days 30 --out review_queue.jsonl [--scorer hf:<model>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import httpx

os.environ.setdefault("DDI_ENABLE_RXNAV", "false")

from api.ddi.engine import analyze_pair  # noqa: E402
from api.ddi.lexicon import DRUGS, SYNONYMS  # noqa: E402

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_QUERY = ('("drug interactions"[MeSH Terms] OR "drug-drug interaction"[Title/Abstract] OR '
                 '"coadministration"[Title/Abstract] OR "concomitant use"[Title/Abstract]) AND humans[MeSH Terms]')

# ----------------------------------------------------------------------------- dictionary NER

_AMBIGUOUS = {"alcohol", "iron", "calcium", "magnesium", "potassium", "the pill", "antacid", "wine", "beer",
              "liquor", "grapefruit", "asa", "gtn", "dxm", "soma"}


def _build_terms() -> List[Tuple[re.Pattern, str]]:
    terms: Dict[str, str] = {name: name for name in DRUGS}
    for alias, target in SYNONYMS.items():
        if isinstance(target, str) and alias not in _AMBIGUOUS and len(alias) > 3:
            terms[alias] = target
    for amb in ("alcohol", "ethanol"):
        terms[amb] = "alcohol"
    ordered = sorted(terms.items(), key=lambda kv: -len(kv[0]))
    return [(re.compile(rf"(?<![\w-]){re.escape(t)}(?![\w-])", re.I), ing) for t, ing in ordered]


_TERMS = _build_terms()


def find_drugs(sentence: str) -> List[Tuple[str, int, int]]:
    """Return (ingredient, start, end) mentions; longest match wins on overlap."""
    taken: List[Tuple[int, int]] = []
    out = []
    for pat, ing in _TERMS:
        for m in pat.finditer(sentence):
            if any(m.start() < e and m.end() > s for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            out.append((ing, m.start(), m.end()))
    return sorted(out, key=lambda x: x[1])


def sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text) if s.strip()]


# ----------------------------------------------------------------------------- relation scoring

_POSITIVE = [
    (r"\b(increase[sd]?|elevat\w+|rais\w+|doubl\w+|(\d+(\.\d+)?)-fold)\b.{0,60}\b(auc|exposure|plasma (level|concentration)s?|"
     r"serum (level|concentration)s?|cmax|inr)\b", 0.5, "exposure increase"),
    (r"\b(decrease[sd]?|reduc\w+|lower\w*)\b.{0,60}\b(auc|exposure|plasma (level|concentration)s?|efficacy|"
     r"antiplatelet effect)\b", 0.45, "exposure/efficacy decrease"),
    (r"\b(inhibit\w*|induc\w*)\b.{0,40}\b(cyp\w*|p-?glycoprotein|metabolism|clearance)\b", 0.35, "PK mechanism"),
    (r"\b(serotonin syndrome|qt prolongation|torsades?|rhabdomyolysis|bleeding|hemorrhage|haemorrhage|"
     r"hypotension|hyperkal\w+|hypoglyc\w+|respiratory depression|toxicity)\b", 0.35, "adverse outcome"),
    (r"\b(interact\w*|coadministration|co-administration|concomitant\w*|combined use|combination)\b", 0.2,
     "interaction language"),
    (r"\b(contraindicated|should be avoided|avoid)\b", 0.3, "management language"),
]
_NEGATIVE = re.compile(
    r"\b(no (clinically )?(significant|relevant|meaningful)? ?(pharmacokinetic )?(interaction|effect|change|"
    r"difference)|did not (significantly )?(alter|affect|change|increase|decrease)|was not (significantly )?"
    r"(altered|affected|changed)|not associated with|no evidence of)\b", re.I)


def pattern_scorer(sentence: str, a: str, b: str) -> Tuple[float, List[str]]:
    s = sentence.lower()
    score, cues = 0.0, []
    for pat, w, label in _POSITIVE:
        if re.search(pat, s):
            score += w
            cues.append(label)
    if _NEGATIVE.search(sentence):
        score -= 0.6
        cues.append("negated")
    return max(0.0, min(1.0, score)), cues


def hf_scorer(model_id: str) -> Callable[[str, str, str], Tuple[float, List[str]]]:
    from transformers import pipeline  # optional dependency

    clf = pipeline("text-classification", model=model_id, top_k=None)
    negative = {"negative", "false", "ddi-false", "0", "no", "label_0"}

    def score(sentence: str, a: str, b: str) -> Tuple[float, List[str]]:
        marked = re.sub(rf"\b{re.escape(a)}\b", f"<e1>{a}</e1>", sentence, count=1, flags=re.I)
        marked = re.sub(rf"\b{re.escape(b)}\b", f"<e2>{b}</e2>", marked, count=1, flags=re.I)
        preds = clf(marked)[0]
        pos = sum(p["score"] for p in preds if p["label"].lower() not in negative)
        top = max(preds, key=lambda p: p["score"])["label"]
        return float(pos), [f"model:{top}"]

    return score


# ----------------------------------------------------------------------------- PubMed

@dataclass
class Abstract:
    pmid: str
    title: str
    text: str
    year: Optional[str] = None


def parse_pubmed_xml(xml: str) -> List[Abstract]:
    root = ET.fromstring(xml)
    out = []
    for art in root.iter("PubmedArticle"):
        pmid = art.findtext(".//MedlineCitation/PMID") or ""
        title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
        parts = ["".join(n.itertext()) for n in art.findall(".//Abstract/AbstractText")]
        year = art.findtext(".//PubDate/Year")
        if pmid and parts:
            out.append(Abstract(pmid, title.strip(), " ".join(p.strip() for p in parts), year))
    return out


def fetch_pubmed(query: str, days: int, retmax: int, api_key: Optional[str] = None) -> List[Abstract]:
    params = {"db": "pubmed", "term": query, "retmax": retmax, "retmode": "json", "datetype": "edat",
              "mindate": (date.today() - timedelta(days=days)).strftime("%Y/%m/%d"),
              "maxdate": date.today().strftime("%Y/%m/%d")}
    if api_key:
        params["api_key"] = api_key
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{EUTILS}/esearch.fcgi", params=params)
        r.raise_for_status()
        ids = r.json()["esearchresult"].get("idlist", [])
        if not ids:
            return []
        p = {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", **({"api_key": api_key} if api_key else {})}
        r = client.get(f"{EUTILS}/efetch.fcgi", params=p)
        r.raise_for_status()
        return parse_pubmed_xml(r.text)


# ----------------------------------------------------------------------------- pipeline

@dataclass
class Candidate:
    drug1: str
    drug2: str
    pmid: str
    url: str
    sentence: str
    score: float
    cues: List[str]
    scorer: str
    known_status: str          # interaction_found | no_known_interaction | ...
    known_severity: str
    novel: bool


def mine(abstracts: Iterable[Abstract], scorer=pattern_scorer, scorer_name: str = "pattern",
         threshold: float = 0.5) -> List[Candidate]:
    out: List[Candidate] = []
    known_cache: Dict[Tuple[str, str], dict] = {}
    for ab in abstracts:
        for sent in sentences(f"{ab.title}. {ab.text}"):
            mentions = find_drugs(sent)
            ings = list(dict.fromkeys(m[0] for m in mentions))
            for i in range(len(ings)):
                for j in range(i + 1, len(ings)):
                    a, b = sorted((ings[i], ings[j]))
                    score, cues = scorer(sent, a, b)
                    if score < threshold:
                        continue
                    if (a, b) not in known_cache:
                        known_cache[(a, b)] = analyze_pair(a, b)
                    k = known_cache[(a, b)]
                    documented = k["status"] == "interaction_found" and any(
                        f["basis"] != "external-db" for f in k["findings"])
                    out.append(Candidate(a.title(), b.title(), ab.pmid,
                                         f"https://pubmed.ncbi.nlm.nih.gov/{ab.pmid}/", sent, round(score, 3), cues,
                                         scorer_name, k["status"], k["severity"], not documented))
    return out


def aggregate(cands: List[Candidate]) -> List[dict]:
    """One row per pair, novel pairs first, ranked by support."""
    by_pair: Dict[Tuple[str, str], dict] = {}
    for c in cands:
        row = by_pair.setdefault((c.drug1, c.drug2), {
            "drug1": c.drug1, "drug2": c.drug2, "novel": c.novel, "known_severity": c.known_severity,
            "pmids": [], "max_score": 0.0, "examples": []})
        if c.pmid not in row["pmids"]:
            row["pmids"].append(c.pmid)
        row["max_score"] = max(row["max_score"], c.score)
        if len(row["examples"]) < 3:
            row["examples"].append({"pmid": c.pmid, "sentence": c.sentence, "cues": c.cues})
    return sorted(by_pair.values(), key=lambda r: (not r["novel"], -len(r["pmids"]), -r["max_score"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", default=DEFAULT_QUERY)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--retmax", type=int, default=500)
    ap.add_argument("--xml", help="parse a saved PubMed efetch XML file instead of querying")
    ap.add_argument("--scorer", default="pattern", help="'pattern' or 'hf:<model-id>'")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="review_queue.jsonl")
    args = ap.parse_args(argv)

    if args.xml:
        with open(args.xml, encoding="utf-8") as fh:
            abstracts = parse_pubmed_xml(fh.read())
    else:
        abstracts = fetch_pubmed(args.query, args.days, args.retmax, os.getenv("NCBI_API_KEY"))
    scorer = pattern_scorer if args.scorer == "pattern" else hf_scorer(args.scorer.split(":", 1)[1])
    rows = aggregate(mine(abstracts, scorer, args.scorer, args.threshold))
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    novel = sum(r["novel"] for r in rows)
    print(f"{len(abstracts)} abstracts -> {len(rows)} candidate pairs ({novel} not in the knowledge base) "
          f"-> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
