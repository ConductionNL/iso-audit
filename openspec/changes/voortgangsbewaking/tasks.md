# Taken — voortgangsbewaking

## 0. Volgorde

- [ ] 0.1 Deze change hangt aan `managementmemo-1a4`: zonder de actie-velden (`wat`, `wie`,
      `waar`, `uiterlijk`) is er niets te bewaken. Niet starten voordat die er zijn

## 1. Datamodel

- [ ] 1.1 Actie-status: open, in uitvoering, aangetoond, vervallen
- [ ] 1.2 Statuswisseling append-only met identiteit, tijdstip en reden — zelfde vorm als de
      triage-trail
- [ ] 1.3 Bewijsverwijzing bij een actie: Jira-issue, document-id uit het landschap, of
      bevinding-id uit een latere run
- [ ] 1.4 Weigering: `aangetoond` zonder verwijzing kan niet
- [ ] 1.5 Test: elk van de drie soorten verwijzing wordt geaccepteerd, geen enkele lege

## 2. Overzichtsscherm

- [ ] 2.1 Alle openstaande acties over audits en runs heen, niet per run
- [ ] 2.2 Sortering op termijn, verlopen bovenaan
- [ ] 2.3 Herkomst per actie: uit welke audit en welke bevinding
- [ ] 2.4 Onvolledige acties (zonder eigenaar of termijn) blijven zichtbaar als openstaand
- [ ] 2.5 Test: een actie uit een eerdere audit staat in het overzicht

## 3. Planning ernaast

- [ ] 3.1 Per actie tonen wanneer de clausule volgens de auditplanning weer aan de beurt is
- [ ] 3.2 Planning niet gekoppeld: kolom weg plus de reden, geen lege kolom die als
      "niet gepland" leest
- [ ] 3.3 Test met en zonder gekoppelde Planning-bron

## 4. Bewakende agent (optioneel, als laatste)

- [ ] 4.1 Per openstaande actie zoeken naar bewijs dat sinds het ontstaan is bijgekomen
- [ ] 4.2 Voorstel met bronverwijzing; geen statuswijziging
- [ ] 4.3 Test: de agent heeft geen schrijfpad naar de actiestatus
- [ ] 4.4 Trail: elke agent-aanroep met model, kosten en peildatum

## 5. Documentatie

- [ ] 5.1 `docs/reference/voortgangsbewaking.md`: waarom een actie hier leeft en de uitvoering
      elders, en waarom `aangetoond` bewijs vereist (9001 §10.2, doeltreffendheid)
- [ ] 5.2 CHANGELOG met de motivatie
