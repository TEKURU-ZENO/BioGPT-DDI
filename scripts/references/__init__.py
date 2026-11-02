"""Builders for independent validation references (not authored by this project).

Each builder writes a CSV with the common columns::

    drug1, drug2, severity, source, source_id, note

where drug1/drug2 are this project's ingredient names. Only pairs whose drugs
both resolve to single lexicon ingredients are kept: the engine cannot be
scored on drugs it does not know, and the share of reference drugs it does
not know is reported separately as lexicon coverage.
"""
