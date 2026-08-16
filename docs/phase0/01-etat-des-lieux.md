# Phase 0 — État des lieux

- Date : 2026-08-16
- Référence : `CAHIER_DES_CHARGES_DAKAR_WIFI.md` v1.1

## 1. Inventaire du dépôt

| Élément | État |
|---|---|
| Cahier des charges v1.1 | présent, à la racine |
| Code applicatif | **aucun** — projet vierge |
| Dépôt git | initialisé le 2026-08-16, branche `main` |
| Infrastructure existante | aucune (pas de serveur, pas d'instance OpenWISP connue) |
| Matériel réseau | aucun inventaire fourni (question 2 du §22) |

## 2. Environnement de développement local

| Outil | Version constatée | Statut |
|---|---|---|
| Node.js | 25.9.0 | OK |
| npm | 11.12.1 | OK |
| pnpm | absent | **à installer** (ADR-0002) |
| Python | 3.14.4 | OK (≥ 3.12 requis) |
| uv | à vérifier | **à installer si absent** (ADR-0002) |
| Docker | 29.1.3 | OK |
| Docker Compose | 2.40.3 | OK |
| GNU Make | 4.4.1 | OK |

## 3. Écarts par rapport au cahier des charges

Le projet démarre de zéro : **tout le périmètre du §3.2 est à construire.** Les écarts
notables ne sont donc pas dans le code mais dans les prérequis :

1. **Aucune instance OpenWISP** disponible, même de test → le spike Phase 0
   ([06-spike-openwisp](06-spike-openwisp.md)) doit la créer en Docker jetable.
2. **Aucun accès sandbox** paiement ou SMS → conforme au plan (mocks d'abord),
   mais les questions 7, 8 et 19 du §22 restent ouvertes.
3. **Aucune donnée terrain** (sites, matériel, opérateurs) → n'empêche ni la Phase 1
   ni les mocks ; bloque les phases 5 et 8.
4. **Identité visuelle absente** → placeholder neutre, conformément au §2.2.

## 4. Architecture

Le diagramme d'architecture logique du §4.1 du cahier des charges reste la référence ;
aucune mise à jour nécessaire à ce stade. Il sera complété d'un diagramme de déploiement
lors de la Phase 5 (OpenWISP staging).

## 5. Conclusion

Rien ne bloque la Phase 1. Les décisions immédiates sont consignées dans
[02-decisions-manquantes](02-decisions-manquantes.md) et les ADR 0001 à 0004.
