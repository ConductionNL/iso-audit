# Tasks: credential-opslag

- [x] 1.1 `config/secret_store.py`: lezen en patchen via de kube-API
- [x] 1.2 Expliciete HTTPS-verbinding in plaats van `urlopen`, zodat een string het schema
      niet kan bepalen
- [x] 1.3 Foutmeldingen zonder responsbody
- [x] 1.4 `BronConfig` kiest de backend; publieke methodes ongewijzigd
- [x] 1.5 PVC-terugval met waarschuwing
- [x] 2.1 `deploy/rbac-config.yaml`: Role + RoleBinding, één naam, `get`+`patch`
- [x] 2.2 Projected token, alleen in de app-container, 1 uur
- [x] 2.3 `automountServiceAccountToken` blijft `false`
- [x] 2.4 `deploy/README.md`: waarom de app nu een token heeft, met verificatiecommando's
- [x] 3.1 Tests: terugval, merge-patch op één sleutel, geen responsbody in de fout
- [ ] 4.1 In het cluster verifiëren met `kubectl auth can-i` (drie regels uit de README)
