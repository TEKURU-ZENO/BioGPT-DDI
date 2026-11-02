import pytest

from api.ddi.normalize import resolve


@pytest.mark.parametrize("raw,expected", [
    ("Warfarin", ["warfarin"]),
    ("  WARFARIN ", ["warfarin"]),
    ("Coumadin", ["warfarin"]),
    ("Metoprolol tartrate 50 mg", ["metoprolol"]),
    ("Losartan potassium", ["losartan"]),
    ("Atorvastatin calcium tablets", ["atorvastatin"]),
    ("Sertraline HCl", ["sertraline"]),
    ("St. John's Wort", ["st john's wort"]),
    ("Percocet", ["oxycodone", "acetaminophen"]),
    ("sulfamethoxazole/trimethoprim", ["sulfamethoxazole", "trimethoprim"]),
    ("Paracetamol", ["acetaminophen"]),
    ("Potassium", ["potassium chloride"]),
])
def test_resolves(raw, expected):
    r = resolve(raw)
    assert r.recognized and r.ingredients == expected


@pytest.mark.parametrize("raw", ["", "   ", "a", "in", "water", "hydroxyzinee hydralazine"])
def test_does_not_guess(raw):
    assert not resolve(raw).recognized


def test_substring_does_not_match():
    # v1 matched "in" inside "warfarin"
    assert not resolve("arin").recognized
