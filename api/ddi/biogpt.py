"""Optional BioGPT literature-style context (experimental).

Disabled by default. When enabled (``BIOGPT_ENABLED=true`` plus
``HF_API_TOKEN``), BioGPT is prompted with the *already determined* mechanism
so it continues from grounded text instead of free-associating. The output is
returned separately as ``literature_context``, explicitly labelled as
unverified, and never influences severity or the main reports.

BioGPT is a PubMed-style language model, not an instruction-following
assistant. Its documented strength is biomedical relation extraction, which is
the intended future role in this project (literature mining for emerging DDIs).
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

DEFAULT_URL = "https://router.huggingface.co/hf-inference/models/microsoft/BioGPT-Large"


def enabled() -> bool:
    return os.getenv("BIOGPT_ENABLED", "false").lower() in {"1", "true", "yes"} and bool(os.getenv("HF_API_TOKEN"))


async def literature_context(result: dict) -> Optional[str]:
    if not enabled() or result.get("status") != "interaction_found":
        return None
    top = result["findings"][0]
    a, b = top["drugs"]
    prompt = f"{a} and {b} interact. {top['mechanism']} As a result,"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(
                os.getenv("BIOGPT_API_URL", DEFAULT_URL),
                headers={"Authorization": f"Bearer {os.environ['HF_API_TOKEN']}"},
                json={"inputs": prompt, "parameters": {"max_new_tokens": 80, "do_sample": False,
                                                       "return_full_text": False}},
            )
            r.raise_for_status()
            data = r.json()
            text = data[0].get("generated_text", "") if isinstance(data, list) and data else ""
            text = text.replace(prompt, "").strip()
            return f"As a result, {text}" if text else None
    except Exception:
        return None
