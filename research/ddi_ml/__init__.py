"""Learned DDI layer (Phase 3): research code, not deployed with the API.

Pipeline: load pairs -> leakage-aware split -> featurise -> train ->
split-conformal calibration -> evaluate -> export artifact.

The API can load an exported artifact (``DDI_MODEL_PATH``) and attach a
clearly labelled "predicted - not documented" signal to pairs for which the
curated and mechanism layers found nothing. It never assigns or lowers a
severity.
"""
