"""De review draait op een zwaarder model dan de classificatie."""

from __future__ import annotations

import pytest

from iso_audit import modellen


def test_de_review_staat_standaard_op_sonnet(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwaarder dan de classificatie, en dat is de hele reden dat de review bestaat.

    De classificatie draait over honderden documenten op het goedkoopste model. De review
    draait over tientallen clausules en bereidt een oordeel voor dat een auditor overneemt; daar
    wegen de tokens niet op tegen een verkeerd voorbereid oordeel.
    """
    monkeypatch.delenv(modellen.REVIEW_ENV_VAR, raising=False)
    assert modellen.review_model() == modellen.SONNET_5
    assert modellen.review_model() != modellen.STANDAARD


def test_de_omgeving_kan_hem_overrulen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(modellen.REVIEW_ENV_VAR, modellen.OPUS_5)
    assert modellen.review_model() == modellen.OPUS_5


def test_het_reviewmodel_is_kiesbaar_en_heeft_dus_een_prijsregel() -> None:
    """Zonder prijsregel loopt de duurste stap zonder kostenrapportage."""
    assert modellen.REVIEW_STANDAARD in modellen.KIESBAAR
