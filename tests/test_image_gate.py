"""De PreSync-gate houdt de oude pod overeind terwijl het image nog gebouwd wordt.

Op 2026-08-26 synct Argo de nieuwe `newTag` zodra de commit op main stond, terwijl het image pas
daarna werd gebouwd — die build duurde elf minuten (wachttijd op een GitHub-runner; de testjob
zelf deed 1m43). De Deployment gebruikt `Recreate`, verplicht bij een RWO-volume, dus de oude pod
was al weg. Negen minuten `ImagePullBackOff` met een portaal dat eruit lag.

De gate is een Job die niets doet behalve bestaan, met precies het image dat straks uitgerold
wordt. Niet pullbaar betekent: hook onvoltooid, sync wacht, oude pod draait door.

Wat hier bewaakt wordt zijn de vier eigenschappen waarop dat berust. Gaat er één stuk, dan is de
gate geen gate meer maar een Job die stil slaagt — en dat merk je pas als het portaal er weer uit
ligt.
"""

from __future__ import annotations

import subprocess

import pytest

yaml = pytest.importorskip("yaml")


def _manifesten() -> list[dict]:
    uit = subprocess.run(
        ["kubectl", "kustomize", "deploy/"], capture_output=True, text=True, check=False
    )
    if uit.returncode != 0:
        pytest.skip(f"kubectl kustomize niet beschikbaar: {uit.stderr.strip()[:120]}")
    return [d for d in yaml.safe_load_all(uit.stdout) if d]


@pytest.fixture(scope="module")
def gate() -> dict:
    for doc in _manifesten():
        if doc.get("kind") == "Job" and doc["metadata"]["name"] == "iso-audit-image-gate":
            return doc
    pytest.fail("de PreSync-gate staat niet in de gerenderde manifesten")


def test_de_gate_draait_als_presync_hook(gate: dict) -> None:
    """Na de sync is de oude pod al vervangen; dan beschermt hij niets meer."""
    assert gate["metadata"]["annotations"]["argocd.argoproj.io/hook"] == "PreSync"


def test_de_gate_gebruikt_precies_het_uitgerolde_image(gate: dict) -> None:
    """Een afwijkende tag zou een image controleren dat straks niet gepullt wordt."""
    deployment = next(d for d in _manifesten() if d.get("kind") == "Deployment")
    app = next(
        c for c in deployment["spec"]["template"]["spec"]["containers"] if c["name"] == "app"
    )
    gate_image = gate["spec"]["template"]["spec"]["containers"][0]["image"]
    assert gate_image == app["image"], f"gate={gate_image} app={app['image']}"


def test_de_gate_faalt_zichtbaar_in_plaats_van_eindeloos_te_wachten(gate: dict) -> None:
    """Zonder deadline blijft een sync hangen op een image dat nooit komt."""
    deadline = gate["spec"]["activeDeadlineSeconds"]
    assert 600 <= deadline <= 3600, deadline


def test_de_vorige_gate_blijft_staan_tot_de_volgende_sync(gate: dict) -> None:
    """`HookSucceeded` zou hem meteen opruimen; dan is achteraf niet te zien of een uitrol
    op het image heeft staan wachten."""
    beleid = gate["metadata"]["annotations"]["argocd.argoproj.io/hook-delete-policy"]
    assert beleid == "BeforeHookCreation"


def test_de_gate_doet_niets_anders_dan_bestaan(gate: dict) -> None:
    """Elke echte opdracht erin maakt van een controle een tweede plek waar iets kan breken."""
    containers = gate["spec"]["template"]["spec"]["containers"]
    assert len(containers) == 1
    assert containers[0]["command"] == ["/bin/true"]
