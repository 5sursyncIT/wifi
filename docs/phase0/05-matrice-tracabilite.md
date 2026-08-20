# Phase 0 — Matrice de traçabilité exigences / tests

Trace chaque critère d'acceptation du §17 vers les tests du §16 et les items de backlog.
Colonne « Preuve » complétée au fil des phases (chemin du test automatisé ou procès-verbal).

| # §17 | Critère (résumé) | Tests §16 | Backlog | Preuve |
|---|---|---|---|---|
| 1 | Inscription OTP + conditions versionnées | OTP réussi/expiré, abus OTP | DW-P3-01..04, DW-P3-07 | — |
| 2 | Zone résolue côté serveur, pas de confiance navigateur | Redirection ouverte, contexte falsifié | DW-P2-03, DW-P2-04 | — |
| 3 | Offre gratuite avec quota RADIUS réel | Attribution gratuite / quota consommé | DW-P3-05, DW-P5-03 | — |
| 4 | Cycle complet commande avec prestataire mock | Achat réussi/échoué/annulé/expiré ; push succès/refus/timeout | DW-P4-01..06 | — |
| 5 | Webhook dupliqué n'active jamais deux droits | Webhook dupliqué, hors ordre, post-expiration | DW-P4-03, DW-P4-04 | — |
| 6 | Indisponibilité OpenWISP → reprise sans perte | Paiement confirmé / OpenWISP down / reprise | DW-P4-04, DW-P5-02 | — |
| 7 | Sessions RADIUS sans double comptage | Import accounting en double | DW-P5-04 | — |
| 8 | Rôles empêchent les accès non autorisés | Autorisations horizontales/verticales | DW-P2-06 + transverse | `apps/core/tests/test_seed_demo_data.py`, `apps/promotions/tests/test_admin_scope.py` |
| 9 | Admin configure zones, offres, vouchers, sponsors | E2E back-office | DW-P2-06, DW-P6-01..02 | admin Django + `apps/promotions/tests/` |
| 10 | Carte et santé des hotspots | E2E agent réseau (hors ligne → incident) | DW-P2-07, DW-P2-08 | `apps/incidents/tests/test_incidents.py` ; OpenWISP live reporté (DW-P5-01) |
| 11 | Rapprochement et exports financiers | E2E financier (paiement → écart → export) | DW-P6-03 | `apps/billing/tests/test_reconciliation.py`, `test_exports.py`, `test_refunds.py` |
| 12 | Journaux d'audit sur opérations sensibles | Transverse (chaque phase) | AuditLog, toutes phases | `apps/core/tests/test_audit.py`, `apps/billing/tests/test_exports.py`, `apps/citizens/tests/test_account.py`, `apps/access/tests/test_sessions.py`, `apps/support/tests/test_tickets.py`, `apps/incidents/tests/test_incidents.py` |
| 13 | Portail OK en mini-navigateur + Android entrée de gamme | Budget perf CI + test appareil réel | DW-P1-04, DW-P4-05 | — |
| 14 | Tests critiques passent en CI | CI complète §15.3 | DW-P1-07 | — |
| 15 | Installation reproductible local + staging | README, docs install | DW-P1-08, DW-P5-01 | — |
| 16 | Sauvegarde + restauration démontrées | Restauration testée (§15.2) | Phase 8 | — |
| 17 | Aucun secret réel dans le dépôt | Détection de secrets en CI | DW-P1-07 | — |

Exigences transverses non couvertes par un critère §17 mais tracées :

| Exigence | Source | Tests | Backlog |
|---|---|---|---|
| Rotation MAC sans double comptage d'appareil | §8.1 | §16.1 | DW-P3-01 |
| Walled garden : paiement accessible non authentifié | §13.2 | §16.1 | DW-P4-02, P7 |
| Changement de tarif sans effet rétroactif | §8.3 | §16.1 | DW-P2-02 |
| Voucher valide, expiré, révoqué, déjà consommé | §8.6 | §16.1 | DW-P6-01 |
| Vue partenaire limitée à sa campagne | §8.11 | §16.2 | DW-P6-02 |
| Export et suppression de compte | §8.1 | §16.1 | DW-P3-08 |
| Contenus wolof et pictogrammes | §1 règle 16 | `apps/captive-portal/src/lib/i18n.test.ts` | DW-P2-09 |
