from api.ddi.lexicon import DRUGS, SYNONYMS
from api.ddi.rules import CURATED

ALL_TAGS = set().union(*(d.tags for d in DRUGS.values()))
SEVERITIES = {"Contraindicated", "Major", "Moderate", "Minor"}


def test_synonyms_point_to_known_ingredients():
    for alias, target in SYNONYMS.items():
        targets = target if isinstance(target, list) else [target]
        for t in targets:
            assert t in DRUGS, f"synonym {alias!r} -> unknown ingredient {t!r}"


def test_synonyms_do_not_shadow_ingredients():
    assert not set(SYNONYMS) & set(DRUGS)


def test_curated_selectors_resolve():
    for rule in CURATED:
        for sel in rule.a + rule.b:
            if sel.startswith("@"):
                assert sel[1:] in ALL_TAGS, f"unknown tag {sel} in rule {rule.title!r}"
            else:
                assert sel in DRUGS, f"unknown ingredient {sel!r} in rule {rule.title!r}"


def test_curated_rules_are_complete():
    for rule in CURATED:
        assert rule.severity in SEVERITIES
        assert rule.mechanism and rule.effect and rule.management and rule.patient
        assert rule.evidence, f"rule {rule.title!r} has no source"


def test_cyp_annotations_use_valid_vocabulary():
    for d in DRUGS.values():
        assert set(d.sub.values()) <= {"sensitive", "moderate"}, d.name
        assert set(d.inh.values()) <= {"strong", "moderate", "weak"}, d.name
        assert set(d.ind.values()) <= {"strong", "moderate"}, d.name
