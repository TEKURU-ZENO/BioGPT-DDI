"""Drug-name normalisation.

Resolution order (first hit wins):

1. exact ingredient name in the local lexicon
2. brand / synonym / combination product
3. the same after stripping doses ("20 mg") and salt or formulation words
   ("hydrochloride", "ER", "tablet")
4. optional RxNorm lookup via the NLM RxNav API (exact/normalised string match
   only, never approximate matching) to map unfamiliar brand names to
   ingredients

Typos are never auto-corrected: a near-miss such as "hydroxyzine" vs
"hydralazine" is clinically dangerous. Close matches are returned as
suggestions only.
"""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional

from .lexicon import DRUGS, SALT_WORDS, SYNONYMS

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
_DOSE_RE = re.compile(r"\b\d+(\.\d+)?\s*(mg|mcg|µg|ug|g|ml|iu|units?|%)?\b", re.I)
_ALLOWED_RE = re.compile(r"[^a-z0-9'\-\.\s/+]")


@dataclass
class ResolvedDrug:
    input: str
    recognized: bool
    ingredients: List[str] = field(default_factory=list)
    display_name: str = ""
    matched_via: str = "none"  # exact | synonym | salt-stripped | rxnorm | none
    in_knowledge_base: bool = False
    suggestions: List[str] = field(default_factory=list)
    unknown_ingredients: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "input": self.input,
            "recognized": self.recognized,
            "display_name": self.display_name,
            "ingredients": self.ingredients,
            "matched_via": self.matched_via,
            "in_knowledge_base": self.in_knowledge_base,
            "unknown_ingredients": self.unknown_ingredients,
            "suggestions": self.suggestions,
        }


def _clean(text: str) -> str:
    text = re.sub(r"\[[^\]]*\]", " ", text)  # RxNorm branded names: "... Oral Tablet [Coumadin]"
    text = text.lower().strip()
    text = text.replace("’", "'").replace("‘", "'")
    text = _ALLOWED_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _lookup(key: str) -> Optional[List[str]]:
    if key in DRUGS:
        return [key]
    hit = SYNONYMS.get(key)
    if hit is None:
        return None
    return list(hit) if isinstance(hit, list) else [hit]


def _strip(key: str) -> str:
    key = _DOSE_RE.sub(" ", key)
    words = [w for w in re.split(r"[\s/]+", key) if w and w not in SALT_WORDS]
    return " ".join(words).strip()


def _split_combo(key: str) -> Optional[List[str]]:
    """Handle free-text combinations such as 'sulfamethoxazole/trimethoprim'."""
    parts = [p.strip() for p in re.split(r"\s*(?:/|\+|\band\b|\bwith\b)\s*", key) if p.strip()]
    if len(parts) < 2:
        return None
    out: List[str] = []
    for p in parts:
        hit = _lookup(p) or _lookup(_strip(p))
        if not hit:
            return None
        out.extend(hit)
    return out


def _rxnav_enabled() -> bool:
    return os.getenv("DDI_ENABLE_RXNAV", "true").lower() in {"1", "true", "yes"}


@lru_cache(maxsize=2048)
def _rxnav_ingredients(name: str) -> tuple:
    """Map a name to RxNorm ingredient names using exact/normalised matching."""
    try:
        import httpx

        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{RXNAV_BASE}/rxcui.json", params={"name": name, "search": 2})
            r.raise_for_status()
            ids = (r.json().get("idGroup") or {}).get("rxnormId") or []
            if not ids:
                return ()
            r = client.get(f"{RXNAV_BASE}/rxcui/{ids[0]}/related.json", params={"tty": "IN+MIN"})
            r.raise_for_status()
            names: List[str] = []
            for group in (r.json().get("relatedGroup") or {}).get("conceptGroup") or []:
                for concept in group.get("conceptProperties") or []:
                    if group.get("tty") == "IN":
                        names.append(concept["name"].lower())
            return tuple(dict.fromkeys(names))
    except Exception:  # network, timeout, schema change: degrade gracefully
        return ()


def resolve(raw: str) -> ResolvedDrug:
    key = _clean(raw)
    result = ResolvedDrug(input=raw, recognized=False)
    if not key:
        return result

    hits, via = _lookup(key), None
    if hits:
        via = "exact" if key in DRUGS else "synonym"
    else:
        stripped = _strip(key)
        if stripped and stripped != key:
            hits = _lookup(stripped)
            via = "salt-stripped" if hits else None
        if not hits:
            hits = _split_combo(key)
            via = "combination" if hits else None

    if not hits and _rxnav_enabled() and len(key) >= 3:
        rx = list(_rxnav_ingredients(key))
        if rx:
            hits, via = [], "rxnorm"
            for ing in rx:
                local = _lookup(ing) or _lookup(_strip(ing))
                if local:
                    hits.extend(local)
                else:
                    result.unknown_ingredients.append(ing)
            if not hits and result.unknown_ingredients:
                # Recognised by RxNorm, but we hold no interaction profile for it.
                result.recognized = True
                result.matched_via = via
                result.display_name = " + ".join(result.unknown_ingredients)
                return result

    if hits:
        result.recognized = True
        result.ingredients = list(dict.fromkeys(hits))
        result.matched_via = via or "exact"
        result.in_knowledge_base = not result.unknown_ingredients
        result.display_name = " + ".join(i.title() for i in result.ingredients)
        return result

    vocab = list(DRUGS) + list(SYNONYMS)
    result.suggestions = difflib.get_close_matches(key, vocab, n=3, cutoff=0.75)
    return result
