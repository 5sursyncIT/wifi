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
| 8 | Rôles empêchent les accès non autorisés | Autorisations horizontales/verticales | DW-P2-06 + transverse | — |
| 9 | Admin configure zones, offres, vouchers, sponsors | E2E back-office | DW-P2-06, DW-P6-01..02 | — |
| 10 | Carte et santé des hotspots | E2E agent réseau (hors ligne → incident) | DW-P2-07, DW-P5-01 | — |
| 11 | Rapprochement et exports financiers | E2E financier (paiement → écart → export) | DW-P6-03 | — |
| 12 | Journaux d'audit sur opérations sensibles | Transverse (chaque phase) | AuditLog, toutes phases | — |
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
| Limite de sessions simultanées | §8.7 | §16.1 | DW-P5-03 |
