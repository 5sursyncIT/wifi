# Phase 0 — Décisions manquantes

Trois catégories : tranchées (ADR), à trancher pour la Phase 1, à trancher plus tard.

## 1. Tranchées

| Décision | Référence |
|---|---|
| OpenWISP externe, adaptateur, pas de fork | ADR-0001 |
| Stack et outillage monorepo (pnpm, uv, drf-spectacular) | ADR-0002 |
| Code EN / docs FR, Conventional Commits | ADR-0003 |
| Paiement push nominal, redirection en repli | ADR-0004 |

## 2. À trancher pendant la Phase 1 (proposition par défaut indiquée)

| # | Décision | Proposition par défaut |
|---|---|---|
| D1 | Versions épinglées Node/Python pour CI et Docker | Node 24 LTS, Python 3.13 (les versions locales 25.9/3.14 sont plus récentes que les images stables) |
| D2 | Bibliothèque UI accessible (§5.2) | Radix UI + Tailwind (léger, accessible, compatible budget perf §12.1) |
| D3 | Auth admin Phase 1 | Django + django-otp (MFA TOTP) ; OIDC si la Ville a un IdP (question §22) |
| D4 | Jetons citoyens | JWT courts + refresh rotation, bibliothèque SimpleJWT |
| D5 | Générateur client TS depuis OpenAPI | openapi-typescript + fetch wrapper maison (léger) |
| D6 | CI | GitHub Actions — **confirmé** (dépôt : github.com/5sursyncIT/wifi) |
| D7 | Cartographie | MapLibre GL ou Leaflet + OSM ; **Leaflet proposé** (plus léger, suffisant) |
| D8 | Bibliothèque i18n portail | next-intl |

## 3. À trancher plus tard (bloquantes pour la production, pas pour le développement)

Voir §22 du cahier des charges (questions 1 à 19). Synthèse des plus structurantes :

- matériel réseau et architecture OpenWrt / UniFi / hybride (bloque Phase 5) ;
- contrats paiement et capacité push des prestataires (bloque Phase 7) ;
- fournisseur SMS/OTP et budget (bloque Phase 7) ;
- arbitrage juridique rétention/minimisation + formalités CDP (bloque la production) ;
- hébergement et souveraineté des données (bloque le déploiement staging/production).
