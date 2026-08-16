# Phase 0 — Spike OpenWISP

- Objectif : vérifier **sur les API réelles** les hypothèses structurantes de l'architecture
  avant d'écrire l'adaptateur (`OpenWispClient`).
- Statut : **exécuté le 2026-08-16**. Instance jetable détruite après le spike.
- Décisions induites : [ADR-0006](../adr/0006-integration-openwisp.md).

## Conditions de l'essai

| Élément | Valeur |
|---|---|
| Déploiement | `docker-openwisp`, images `openwisp/*:25.10.4` |
| `openwisp-radius` | 1.2.2 |
| Modules activés | RADIUS (topologie, firmware et monitoring désactivés : hors périmètre du spike) |
| Accès | API REST via nginx, jeton obtenu par `POST /api/v1/users/token/` |

Le spike a porté sur les API REST et sur le code des paquets installés. Aucun matériel
Wi-Fi réel n'était disponible : tout ce qui dépend du comportement d'une borne
(CoA effectif, isolation client, débit) reste à valider en laboratoire (Phase 5).

## Résultats

| # | Hypothèse | Résultat |
|---|---|---|
| H1 | Création/modification d'un utilisateur RADIUS par API | **Partielle** |
| H2 | Des profils RADIUS portent les limites d'un plan | **Partielle** |
| H3 | Consommation des quotas lisible par API | **Vérifiée** |
| H4 | Accounting exposé avec identifiants dédupliquables | **Vérifiée** |
| H5 | Déconnexion/CoA déclenchable | **Partielle** |
| H6 | Multi-tenant conforme au modèle Ville → sites | **Partielle** |
| H7 | Compte de service à droits limités | **Vérifiée** |

### H1 — Utilisateurs · partielle

- `POST /api/v1/users/user/` crée l'utilisateur ; `PATCH` le rattache à une organisation.
- Le rattachement à une organisation affecte **automatiquement** le groupe RADIUS par
  défaut de celle-ci (vérifié : `spike_user → dakar-spike-users`).
- **Manque** : aucun endpoint REST pour affecter un **groupe RADIUS précis**, ni pour
  poser des attributs `RadiusCheck`/`RadiusReply` par utilisateur. `RadiusBatch` ne
  comporte pas non plus de champ de groupe. C'est l'écart le plus lourd (voir ADR-0006).

### H2 — Profils · partielle

- La création d'une organisation génère deux groupes : `<org>-users` (défaut) et
  `<org>-power-users`. Le groupe par défaut porte :
  `Max-Daily-Session := 10800` (3 h/jour) et `Max-Daily-Session-Traffic := 3000000000` (3 Go/jour).
- Compteurs disponibles (module `sqlcounter` de FreeRADIUS) : `Max-Daily-Session`,
  `Max-Monthly-Session`, `Max-All-Session`, `Max-Daily-Session-Traffic`, `Expire-After`.
- **Écarts par rapport au §8.3 / §8.4 du cahier des charges** :
  - le quota de trafic est **cumulé** montant + descendant, alors que le §8.3 demande
    un quota montant *et* descendant distincts ;
  - il existe un compteur quotidien et un mensuel, **pas d'hebdomadaire** (§8.4) ;
  - débit maximal et nombre de sessions simultanées ne sont pas configurés par défaut ;
    ils s'ajoutent en attributs (`WISPr-Bandwidth-Max-*`, `Simultaneous-Use`) mais leur
    effet dépend du matériel — à valider en laboratoire.
- **Manque** : aucun endpoint REST pour créer ou modifier un groupe et ses attributs.

### H3 — Consommation · vérifiée

`GET /api/v1/radius/organization/<slug>/account/usage/` renvoie, par compteur, la limite
et le consommé. Réponse obtenue après 600 s et 50 Mo de trafic simulés :

```json
{"checks": [
  {"attribute": "Max-Daily-Session",         "value": "10800",      "result": 600,      "type": "seconds"},
  {"attribute": "Max-Daily-Session-Traffic", "value": "3000000000", "result": 50000000, "type": "bytes"}
]}
```

C'est exactement ce qu'il faut pour l'affichage « quota et temps restant » du §12.1.

### H4 — Accounting · vérifiée

- `POST /api/v1/freeradius/accounting/` accepte `Start`, `Interim-Update` et `Stop`.
- La clé de déduplication est **`unique_id`** (`Acct-Unique-Session-Id`), transmise par
  FreeRADIUS en plus de `session_id`.
- **Test de double comptage** : 5 requêtes (Start, Interim, puis rejeu à l'identique du
  Start et de l'Interim, puis une seconde session) → **2 lignes en base**, totaux exacts
  (10 000 000 entrants / 40 000 000 sortants / 600 s). Aucun doublon, aucun sur-comptage.
  Les rejeux répondent `200` au lieu de `201` : l'idempotence est explicite.
- `GET /api/v1/radius/sessions/` liste les sessions avec début, durée, octets, NAS,
  `called_station_id`, `calling_station_id`, groupe et organisation.
- L'API freeradius est **restreinte par IP source** (`freeradius_allowed_hosts`) :
  une requête depuis une adresse non autorisée est rejetée en 403. À configurer au
  déploiement pour n'autoriser que nos services.

### H5 — CoA et déconnexion · partielle

- Implémenté dans `openwisp_radius/coa.py` via **pyrad** (Python pur, aucun binaire
  `radclient` requis). `RadClient` sait envoyer un **CoA-Request** et un **Disconnect-Request**.
- Déclenchement : **uniquement sur changement de groupe RADIUS d'un usager**, via une
  tâche Celery. Si les compteurs du nouveau groupe indiquent un quota déjà atteint,
  un `Disconnect` est envoyé à la place du CoA.
- Prérequis : `coa_enabled` sur l'organisation, et un enregistrement `Nas` dont le champ
  `name` est un réseau IP contenant l'adresse de la session, porteur du secret partagé.
- **Manque** : aucun moyen de forcer la déconnexion d'un usager à la demande — ni endpoint
  REST, ni déclencheur public. Le §8.8 exige pourtant qu'« un agent autorisé force une
  déconnexion avec justification ».
- **Comblé et vérifié** : l'extension décidée en [ADR-0006](../adr/0006-integration-openwisp.md)
  expose les deux opérations. Un faux NAS (pyrad) a **reçu réellement** le CoA-Request et
  le Disconnect-Request, avec les limites du plan dans la charge utile
  (`Session-Timeout=10800`, `CoovaChilli-Max-Total-Octets=3000000000`).
- Le comportement d'une **borne réelle** (écoute du port 3799, prise en compte de
  l'attribut `CoovaChilli-Max-Total-Octets`) reste à valider en Phase 5.

### H6 — Multi-tenant · partielle

- `GET`/`POST /api/v1/users/organization/` fonctionnent ; une organisation créée par API
  reçoit bien ses groupes RADIUS.
- **Manque** : `OrganizationRadiusSettings` n'est **pas** créé pour autant. L'organisation
  se retrouve sans jeton RADIUS, sans `coa_enabled` et sans liste d'IP autorisées. Il a
  fallu le créer hors API. Aucun endpoint REST ne le couvre.

### H7 — Compte de service · vérifiée

- `POST /api/v1/users/token/` renvoie un jeton, utilisable en `Authorization: Bearer`.
- Le cloisonnement est effectif : le jeton d'un compte non privilégié reçoit **403** sur
  `/users/organization/`, `/users/user/`, `/radius/sessions/` et `/controller/device/`.
- Réserve : les droits fins d'un compte de service dédié (lecture seule, périmètre d'une
  organisation) n'ont pas été éprouvés en détail — à faire en Phase 5.

## Ce que le spike n'a pas couvert

- Comportement d'une borne réelle : CoA effectif, débit, sessions simultanées, isolation.
- Modules OpenWISP Monitoring et Controller (désactivés ici), donc les métriques du §8.10.
- Montée en charge et volumétrie d'accounting.
- Droits fins d'un compte de service restreint.
