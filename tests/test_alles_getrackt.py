"""Elke bronmap moet ook echt in git staan.

Op 2026-08-14 kostte dit een rode CI. Een **globale** gitignore-regel (een kale `config`
in `~/.gitignore_global`) sluit elke map met die naam uit, ook een Python-package.
`src/iso_audit/config/` werd daardoor stil niet gecommit: `git add -A` sloeg hem over,
`git commit` slaagde, en de lokale testsuite was groen omdat die tegen de working tree
draait. In CI viel de import om.

Dit soort fout is onzichtbaar bij de enige controle die je normaal doet — de tests. Deze
test is de gate: hij vergelijkt de working tree met wat git daadwerkelijk kent.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

WORTELS = ("src", "tests")


def _repo_root() -> Path | None:
    try:
        uit = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if uit.returncode != 0:
        return None
    return Path(uit.stdout.strip())


def _getrackt(root: Path) -> set[Path]:
    uit = subprocess.run(
        ["git", "ls-files", "-z", *WORTELS],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=root,
        check=True,
    )
    return {Path(p) for p in uit.stdout.split("\0") if p}


def test_elk_python_bestand_staat_in_git() -> None:
    """Een bestand dat git niet kent, bestaat niet voor CI, voor een reviewer of voor
    een auditor — ook al draait het lokaal prima."""
    root = _repo_root()
    if root is None:
        pytest.skip("Geen git-repo; deze gate hoort bij een checkout.")

    getrackt = _getrackt(root)
    ontbreekt: list[str] = []
    for wortel in WORTELS:
        for pad in (root / wortel).rglob("*.py"):
            if "__pycache__" in pad.parts or ".venv" in pad.parts:
                continue
            relatief = pad.relative_to(root)
            if relatief not in getrackt:
                ontbreekt.append(str(relatief))

    assert not ontbreekt, (
        "deze bestanden staan niet in git — controleer `git check-ignore -v <pad>`, "
        f"ook tegen ~/.gitignore_global: {sorted(ontbreekt)}"
    )


def test_geen_bytecode_in_git() -> None:
    """De negatie-regels in `.gitignore` mogen geen `__pycache__` meetrekken."""
    root = _repo_root()
    if root is None:
        pytest.skip("Geen git-repo; deze gate hoort bij een checkout.")

    fout = [str(p) for p in _getrackt(root) if p.suffix == ".pyc" or "__pycache__" in p.parts]
    assert not fout, f"bytecode in git: {sorted(fout)}"
