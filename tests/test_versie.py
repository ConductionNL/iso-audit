"""De versie staat op één plek en de uitrol wijst naar diezelfde versie.

Op 2026-08-16 stond `pyproject.toml` op `0.2.0a8` en `__version__` op `0.1.0a0`. Bij een
uitrol is dat de string waaraan je ziet welke build draait — en een portaal dat de
verkeerde versie meldt is precies hoe een stille stilstand onzichtbaar blijft.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import iso_audit


def _pyproject_versie() -> str:
    data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def test_versie_komt_uit_pyproject() -> None:
    assert iso_audit.__version__ == _pyproject_versie()


def test_image_tag_volgt_de_versie() -> None:
    """Argo synct op de tag in kustomization; wijkt die af, dan rolt een andere build uit
    dan je denkt — of er verandert niets en dat lijkt op een mislukte sync."""
    tekst = Path("deploy/kustomization.yaml").read_text(encoding="utf-8")
    m = re.search(r'newTag:\s*"([^"]+)"', tekst)
    assert m, "geen newTag in kustomization.yaml"
    assert m.group(1) == _pyproject_versie()
