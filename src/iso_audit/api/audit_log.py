"""Toegangs-audit-log voor het portaal (capability portal-auth, sec-bevinding 4).

Eén regel JSONL per gebeurtenis naar stdout, waar Kubernetes hem oppikt. Bewust
gescheiden van de **inhoudelijke** audit-trail (`triage_log.jsonl`): die legt vast
*wat* er inhoudelijk besloten is, dit legt vast *wie* wanneer wat aanraakte. Beide
zijn nodig en het zijn verschillende vragen.

## Waarom hier geen credential kan lekken

De functie accepteert alleen scalars via `**velden` en heeft geen toegang tot het
request-object, de headers of de cookies. Er is dus geen pad waarlangs een token in
een logregel komt — niet omdat we eraan denken te redigeren, maar omdat de
gegevens er nooit binnenkomen. Dat is de reden voor deze vorm: een redactie-lijst
die iemand moet onderhouden is een redactie-lijst die verouderd raakt.

Volgt het patroon van openwoo's assistent-audit-log (JSONL naar stdout, retentie
via de cluster-logging), zodat er één vorm in de organisatie is.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("iso_audit.audit")
"""Eigen logger-naam zodat de cluster-logging hierop kan filteren zonder de
applicatie-logs mee te slepen."""

_TOEGESTANE_TYPES = (str, int, float, bool, type(None))


def log_event(soort: str, identiteit: str, **velden: object) -> None:
    """Schrijf één audit-regel.

    ``soort`` is een korte, stabiele sleutel (``auth_geweigerd``, ``mutatie``,
    ``run_gestart``). ``identiteit`` is de geverifieerde actor. ``velden`` zijn
    extra scalars; niet-scalars worden naar ``repr`` afgekapt zodat een per ongeluk
    doorgegeven object geen volledige structuur uitstort in het log.
    """
    regel: dict[str, object] = {
        "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "soort": soort,
        "identiteit": identiteit,
    }
    for naam, waarde in velden.items():
        regel[naam] = waarde if isinstance(waarde, _TOEGESTANE_TYPES) else repr(waarde)[:200]
    logger.info(json.dumps(regel, ensure_ascii=False, sort_keys=True))
