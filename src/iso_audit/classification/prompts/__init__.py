"""Versiegestuurde classificatie-prompts.

Een package zodat `importlib.resources.files()` erbij kan en de `.md`-bestanden meekomen in de
wheel — zoals `iso_audit.data.clause_maps` dat voor de YAML-maps doet. Zonder dit werkt het
lokaal (er staat een bestand) en niet in het image.
"""
