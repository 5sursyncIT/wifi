# Phase 0 — Registre des risques

Probabilité et impact : Faible / Moyen / Élevé. Revue à chaque fin de phase.
Reprend le §23 du cahier des charges, avec suivi opérationnel.

| ID | Risque | Prob. | Impact | Mesure de réduction | Suivi |
|---|---|---|---|---|---|
| R01 | Hypothèses OpenWISP invalidées (quotas, CoA, accounting) | M | **É** | Spike Phase 0 sur API réelles avant l'adaptateur | Ouvert — spike planifié |
| R02 | Matériel non compatible OpenWrt | M | É | Validation modèle par modèle en laboratoire avant achat | Ouvert — dépend question §22.2 |
| R03 | Paiement confirmé mais accès non activé | M | É | Outbox, retries, réconciliation, interface de reprise | Couvert par conception (P4) |
| R04 | Webhooks dupliqués ou hors ordre | É | M | Idempotence, contraintes d'unicité, historique complet | Couvert par conception (P4) |
| R05 | Parcours de paiement impossible en mini-navigateur | É | É | Push serveur nominal (ADR-0004), repli redirection | Couvert par conception |
| R06 | Randomisation MAC casse la reconnaissance d'appareil | É | M | MAC = indice, compte/jeton = autorité (§8.1) | Couvert par conception |
| R07 | Paiement bloqué par le walled garden | M | É | `WalledGardenEntry` par zone, test par prestataire | Couvert par conception (P4/P7) |
| R08 | Fraude OTP / vouchers | M | M | Rate limiting distribué, codes non prédictibles, `OtpRequest` | Couvert par conception (P3) |
| R09 | Coût SMS/OTP non maîtrisé | M | M | Budget alloué (§22.16), suivi `SmsMessage`, seuil d'alerte | Ouvert — budget inconnu |
| R10 | Rétention légale vs minimisation non arbitrée | M | É | Arbitrage juridique documenté avant production (§13.3) | Ouvert — bloquant production |
| R11 | Saturation bande passante des sites | M | M | QoS, quotas, supervision, dimensionnement par site | Ouvert — phase 8 |
| R12 | Perte de connectivité centrale | M | M | VPN supervisé ; période de grâce = point d'étude (ADR à venir) | Ouvert — étude avant P5 |
| R13 | Collecte excessive de données | F | É | Minimisation, pseudonymisation, validation CDP | Couvert par conception |
| R14 | Coût d'exploitation sous-estimé | M | M | Pilote mesuré, indicateurs de coût, extension progressive | Ouvert — phase 8 |
| R15 | Mise à jour OpenWISP difficile | F | M | Pas de fork, adaptateur versionné, staging | Couvert par ADR-0001 |
| R16 | Écart financier non détecté | M | É | Réconciliation quotidienne, journal d'audit | Couvert par conception (P6) |
| R17 | Mini-navigateurs captifs hétérogènes (iOS/Android/constructeurs) | É | M | PWA légère, budget perf CI, tests sur appareils réels | Ouvert — parc de test à constituer |
| R18 | Poids JavaScript du portail au-dessus de la cible §12.1 | **É** | É | Plancher Next.js mesuré à 169 Ko gzip contre 150 Ko visés ; garde-fou CI à 175 Ko ; décision de stack à prendre avant la Phase 2 | **Ouvert — [ADR-0005](../adr/0005-budget-portail-captif.md)** |
