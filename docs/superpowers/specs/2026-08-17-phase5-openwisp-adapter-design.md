# Phase 5 — Adaptateur OpenWISP et instance Docker jetable

- Date : 2026-08-17
- Statut : conception validée, implémentation à venir
- Sources : cahier des charges v1.2 §4.3, §6.2, §8.7, §8.8, §11, §16.1, §17, §18
- Décisions antérieures : [ADR-0001](../../adr/0001-openwisp-systeme-externe.md)
  (OpenWISP externe), [ADR-0006](../../adr/0006-integration-openwisp.md)
  (extension plutôt que fork),
  [spec Phase 4](2026-08-16-phase4-commandes-paiement-design.md) (outbox at-least-once)
- Backlog couvert : DW-P5-00, DW-P5-02, DW-P5-03 (lite), lecture d'usage de DW-P5-04
- Spike : [06-spike-openwisp](../../phase0/06-spike-openwisp.md) (OpenWISP 25.10.4 /
  openwisp-radius 1.2.2)
- Hors de cette itération : DW-P5-01 (Ansible staging Ville), DW-P5-05 matériel
  (CoA sur borne réelle), entrepôt accounting local

---

## 1. Le problème que cette phase résout

Les Phases 3 et 4 activent déjà un droit — gratuit en synchrone, payant via l'outbox —
derrière le contrat `NetworkProvider`. Seul `MockNetworkProvider` le tient. Sur le
terrain, c'est OpenWISP qui possède les usagers RADIUS, les groupes-forfaits et le CoA
qui doit appliquer un forfait **pendant une session déjà ouverte** (§4.3).

Le spike a montré que l'API officielle crée un usager et lit la consommation, mais
n'affecte pas un groupe RADIUS précis et ne force pas une déconnexion. L'extension
maquette dans `infra/openwisp-extension/` comble ces deux trous. Elle n'est pas encore
un adaptateur de production : droits trop larges (`IsAdminUser`), pas de tests, pas
d'instance reproductible dans le monorepo.

Cette phase branche le métier sur OpenWISP **sans toucher au drain d'outbox, aux
commandes, ni au portail**. Le mock reste le défaut local et CI.

### 1.1 La règle structurante

Tout appel réseau passe par `NetworkProvider`. Aucune vue, aucune tâche métier, aucun
handler d'outbox n'importe un client OpenWISP. La bascule est un réglage :

```
NETWORK_PROVIDER=mock      # make up, pytest, e2e — inchangé
NETWORK_PROVIDER=openwisp  # overlay Compose, labo
```

L'outbox Phase 4 est at-least-once : un worker peut mourir après `assign_plan()`
réussi et avant le passage de l'`Entitlement` à `ACTIVE`. Le replay doit alors être un
**no-op réseau** (même groupe → pas de CoA) puis un commit métier. C'est DW-P5-02.

### 1.2 Ce qui ne change pas

- Activation gratuite synchrone et activation payante par outbox.
- Asymétrie gratuit / payant de la Phase 4.
- Montants entiers en XOF.
- Aucune écriture dans les tables OpenWISP depuis core-api (ADR-0001).
- Aucun fork du cœur OpenWISP (ADR-0006).

---

## 2. Périmètre

### 2.1 Livré dans cette itération

| Item | Contenu |
|---|---|
| DW-P5-00 | Extension durcie : droits bornés aux organisations de l'appelant, tests anti-régression du CoA in-place, version OpenWISP épinglée. |
| DW-P5-02 | `OpenWispClient` derrière `NetworkProvider` : retries courts, circuit breaker, mapping d'erreurs, no-op même groupe. |
| DW-P5-03 lite | `ensure_user` (création + rattachement d'org) ; groupes RADIUS pré-provisionnés dont les noms = `PlanVersion.radius_profile_ref` ; réconciliation beat des entitlements `ACTIVE` dérivés. |
| Lecture d'usage | `read_usage` via l'API officielle `account/usage/`. |
| Overlay Compose | Projet Docker séparé, hors de `make up`, cibles `make openwisp-up` / `make openwisp-down` / `make test-openwisp`. |

### 2.2 Explicitement hors périmètre

| Sujet | Renvoyé à | Raison |
|---|---|---|
| Ansible staging Ville, `freeradius_allowed_hosts` de prod | DW-P5-01 | Pas d'accès à l'infra Ville dans cette itération. |
| CoA / Disconnect sur borne réelle | DW-P5-05 | Pas de hotspot de laboratoire. Un NAS fictif suffit à démontrer l'API. |
| Entrepôt accounting local, webhook `radius-accounting` | itération suivante de DW-P5-04 | OpenWISP déduplique déjà sur `unique_id` (spike H4). Copier les sessions dans core-api sans besoin métier crée un double comptage potentiel. |
| UI back-office des divergences | plus tard | La réconciliation beat répare ; l'écran d'exploitation n'existe pas encore. |
| Identifiants RADIUS présentés au portail captif | passerelle réelle | `ensure_user` crée un mot de passe aléatoire non persisté dans core-api. Sans borne, le citoyen ne s'authentifie pas en RADIUS. |
| Contribution des endpoints à openwisp-radius | ADR-0006 option C | Parallèle, pas un livrable. |
| Circuit breaker Redis partagé entre workers | plus tard | Un état de module par processus suffit : l'outbox espace déjà les essais. |
| `make up` embarque OpenWISP | jamais dans cette phase | Images lourdes, Postgres/Redis en collision de ports. |

---

## 3. Architecture

```
Portail / OTP / webhook paiement
        │
        ▼
  core-api (inchangé)
        │
        ▼
  NetworkProvider.get_network_provider()
     ├── mock
     └── openwisp  →  OpenWispClient (HTTP, httpx)
                         │
                         ├── API officielles
                         │     POST/PATCH /api/v1/users/user/
                         │     GET /api/v1/radius/organization/<slug>/account/usage/
                         │     GET santé / version
                         └── Extension Dakar
                               POST /api/v1/dakar/radius/assign-group/
                               POST /api/v1/dakar/radius/disconnect/
```

`OpenWispClient` vit dans `apps/access/providers/openwisp.py`. Il implémente
`NetworkProvider` et n'est enregistré que sous la clé `"openwisp"`.

`get_network_provider()` continue de construire une instance à chaque appel (le mock
range son état au niveau classe). Le circuit breaker, le cache de jeton et le compteur
d'échecs de `OpenWispClient` sont **également au niveau classe**, sinon chaque drain
repartirait circuit fermé.

Identifiants :

| Côté métier | Côté OpenWISP |
|---|---|
| `subscriber_ref` = `str(citizen.id)` (UUID canonique, avec tirets) | `username` RADIUS |
| `PlanVersion.radius_profile_ref` | nom de `RadiusGroup` **déjà créé** par le seed overlay |
| `OPENWISP_ORGANIZATION_ID` | UUID d'organisation auquel `ensure_user` rattache l'usager |

Les plans ne créent pas de groupes à la volée.

---

## 4. Contrat `OpenWispClient`

Le contrat `NetworkProvider` ne change pas. Mapping :

| Méthode | Transport |
|---|---|
| `healthcheck` | GET court sur l'API (échec → `False`, jamais d'exception) |
| `ensure_user` | GET par username ; si absent, `POST /api/v1/users/user/` puis `PATCH` d'organisation. Mot de passe aléatoire à la création seulement, non stocké dans core-api. Idempotent. |
| `assign_plan` | `POST /api/v1/dakar/radius/assign-group/` `{username, group_name}`. Si la réponse 200 porte déjà `group_name` égal au demandé → `AssignmentResult(applied=False, profile_ref=..., detail="already assigned")`. Sinon `applied=True`. |
| `disconnect` | `POST /api/v1/dakar/radius/disconnect/`. Une `DisconnectResult` par session du JSON. Un HTTP 2xx avec des sessions `refused_or_unreachable` n'est **pas** une exception : c'est le cas normal d'une borne injoignable. |
| `read_usage` | `GET /api/v1/radius/organization/<slug>/account/usage/` ; `seconds_used` / `bytes_used` pris sur `Max-Daily-Session` et `Max-Daily-Session-Traffic` quand présents, sinon 0. |

`activate_entitlement` ne consulte pas `applied`. Un no-op (`applied=False`) laisse
quand même passer l'entitlement à `ACTIVE` : l'état réseau est déjà le bon.

### 4.1 Mapping HTTP → exceptions

| Situation | Exception | `retryable` |
|---|---|---|
| 2xx | succès | — |
| timeout httpx, 429, 5xx | `NetworkTimeout` ou `NetworkTemporaryError` | oui |
| circuit ouvert | `NetworkTemporaryError` | oui |
| 400 (groupe inconnu, payload) | `NetworkPermanentError` | non |
| 401, 403 | `NetworkPermanentError` | non |
| 404 usager sur `assign_plan` / `disconnect` après `ensure_user` | `NetworkPermanentError` | non |
| 404 usager pendant `ensure_user` | création, pas une erreur | — |

`QuotaExhausted` et `SessionAlreadyActive` ne sont **pas** produits par cet adaptateur.
OpenWISP ne les expose pas sur `assign-group`. Le mock continue de les simuler pour les
tests métier des Phases 3 et 4.

### 4.2 Retries courts (dans la requête)

- Timeout d'appel : 10 s.
- Au plus **2 retries** (3 tentatives au total) uniquement sur timeout, 429 et 5xx.
- Backoff 200 ms puis 400 ms.
- Aucun retry sur les autres 4xx.
- 401 sur un jeton déjà présent : pas de retry, `NetworkPermanentError` (mauvaise
  config). Le jeton vient de `OPENWISP_API_TOKEN`, il n'est pas obtenu par login à
  chaque appel.

Ces retries ne remplacent pas l'outbox. Ils absorbent un hic d'une seconde. L'outbox
absorbe une indisponibilité de minutes.

### 4.3 Circuit breaker (état de classe, in-process)

| Paramètre | Valeur |
|---|---|
| Seuil d'ouverture | 5 échecs **retryables** consécutifs |
| Durée ouvert | 30 s |
| Demi-ouvert | un appel-sonde ; succès → fermé et compteur à 0 ; échec retryable → rouvert |

Un 4xx permanent **ne compte pas** dans le seuil : un groupe mal nommé ne doit pas
isoler tout OpenWISP.

Circuit ouvert → `NetworkTemporaryError` immédiat, sans HTTP. L'outbox recule. Les
workers Celery ont chacun leur compteur ; c'est accepté.

`healthcheck` n'ouvre pas le circuit (sondage passif). Un succès de n'importe quelle
méthode métier le referme et remet le compteur à 0.

### 4.4 Journaux

URL, verbe, statut, durée, `subscriber_ref`. Jamais le Bearer, jamais le mot de passe
RADIUS généré, jamais le corps brut d'erreur s'il peut contenir un jeton.

---

## 5. Extension durcie

Toujours dans `infra/openwisp-extension/`. Surface inchangée :

- `POST /api/v1/dakar/radius/assign-group/`
- `POST /api/v1/dakar/radius/disconnect/`

Authentification : `BearerAuthentication` + session, comme l'API amont.

**Permission.** `IsAdminUser` est retiré. L'appelant doit être authentifié **et**
partager au moins une organisation avec l'usager cible (`user.organizations_dict`).
Hors périmètre → **403**. Usager inconnu → **404**. Groupe absent des orgs de
l'usager → **400** (`GroupNotFound`), inchangé.

Le compte de service du labo n'est membre que de l'organisation seed « Ville de
Dakar ». Un second org dans les tests d'extension prouve le 403.

**In-place.** `assign_group` dans `services.py` ne change pas d'algorithme :

1. Chercher le groupe dans les orgs de l'usager.
2. Prendre le `RadiusUserGroup` prioritaire existant, ou en créer un s'il n'y en a pas.
3. Si `group_id` est déjà le bon → retourner sans `save` (pas de CoA).
4. Sinon assigner, `full_clean`, `save` — **jamais** delete puis recreate.
5. Supprimer les memberships supplémentaires après coup.

Un test d'extension construit un usager déjà membre, appelle `assign_group` vers un
autre groupe, et vérifie que le `pk` du `RadiusUserGroup` est **le même**. Un second
test vérifie qu'un assign vers le groupe courant ne déclenche pas `save` (mock du
modèle ou comparaison `updated` inchangé, selon ce qui est fiable dans OpenWISP).

La justification de déconnexion (§8.8) et l'audit restent côté plateforme métier.
L'extension ne les porte pas.

---

## 6. Overlay Compose

Projet Docker **séparé**, nom `dakar-wifi-openwisp`, fichier
`infra/compose/openwisp.yml`. Il n'est pas inclus par `make up`.

- Images `openwisp/*:25.10.4` (openwisp-radius 1.2.2), tag écrit en dur dans le
  compose et rappelé dans le README de l'extension.
- Volume : `infra/openwisp-extension/` monté sur le chemin de personnalisation
  officiel (`custom_django_settings.py`, `custom_urls.py`, `dakar_radius_ext/`).
- Postgres et Redis **propres** à ce projet. Ports publiés hors 8000 / 5432 / 6379
  (API/nginx sur un port documenté, par exemple 8002).
- Cibles Makefile : `openwisp-up`, `openwisp-down`, `test-openwisp`.

Seed exécuté une fois après le premier up (script documenté, idempotent) :

- organisation « Ville de Dakar » + `coa_enabled` ;
- groupes dont les noms égalent les `radius_profile_ref` du seed métier
  (`dakar-demo-gratuit`, `dakar-1h`, `dakar-demo-1h`, `dakar-demo-jour`,
  `dakar-demo-semaine`) ;
- compte de service + jeton recopié vers `OPENWISP_API_TOKEN` local (fichier
  d'exemple, jamais un secret réel) ;
- `OPENWISP_ORGANIZATION_ID` correspondant ;
- un `Nas` fictif pour que l'extension puisse tenter un CoA/Disconnect (l'ACK
  matériel n'est pas exigé).

`.env.example` : `NETWORK_PROVIDER=mock` inchangé. Les trois variables
`OPENWISP_*` existent déjà ; on documente leurs valeurs de labo overlay, toujours
fictives.

---

## 7. Réconciliation

Nouvelle tâche Celery `access.reconcile_active_entitlements`, cadence 1 h dans
`CELERY_BEAT_SCHEDULE`.

- Si `NETWORK_PROVIDER != openwisp` → no-op immédiat.
- Pour chaque `Entitlement` `ACTIVE` non expiré : `ensure_user` puis `assign_plan`
  avec `plan_version.radius_profile_ref`.
- Erreur retryable → log + passage à l'entitlement suivant (le beat suivant
  reprend). Pas de nouvelle ligne d'outbox : l'affectation est déjà idempotente.
- Erreur permanente → log d'exploitant, le droit reste `ACTIVE` (un groupe manquant
  est une config cassée, pas une révocation silencieuse).

Pas d'écran back-office dans cette phase.

---

## 8. Tests

### 8.1 CI / `make test-api` — sans OpenWISP

Dépendance de dev : `httpx` (runtime de l'adaptateur) + `respx` (mocks HTTP).

Fichier principal : `apps/access/tests/test_openwisp_client.py`.

| Cas | Attendu |
|---|---|
| 200 assign-group avec un nouveau groupe | `applied=True` |
| 200 assign-group déjà sur ce groupe | `applied=False` (le POST part, l'extension no-op), pas d'exception |
| 500 puis 200 | retry, succès |
| 5 timeouts d'affilée | circuit ouvert, 6e appel sans HTTP, `NetworkTemporaryError` |
| 400 groupe inconnu | `NetworkPermanentError`, circuit toujours fermé |
| 401 | `NetworkPermanentError` |
| `disconnect` 200 avec session `refused_or_unreachable` | liste de résultats, pas d'exception |
| `get_network_provider` avec `NETWORK_PROVIDER=openwisp` | instance `OpenWispClient` |
| défaut | toujours le mock ; les tests existants restent verts |

Les e2e Playwright restent sur le mock. Pas de workflow GitHub Actions pour l'overlay.

### 8.2 Tests d'extension (dans l'image OpenWISP)

- in-place : même `pk` après changement de groupe ;
- no-op même groupe ;
- 403 cross-org ;
- 404 usager inconnu ;
- 400 groupe inconnu ;
- Bearer refusé sans jeton.

### 8.3 `make test-openwisp` (local, hors CI)

Overlay allumé. HTTP réel : `ensure_user`, deux `assign_plan` (second `applied=False`),
`read_usage`, `disconnect`. Échec si l'image n'est pas 25.10.4 (contrôle du tag
compose).

### 8.4 Le test qui compte le plus

Replay at-least-once sur HTTP mocké :

1. `assign_plan` → 200, `applied=True`.
2. On ne marque pas l'entitlement `ACTIVE` (crash simulé).
3. Second `assign_plan` vers le même `radius_profile_ref` → `applied=False`.
4. Le handler d'activation, rejoué, passe l'entitlement à `ACTIVE`.
5. Les deux POST partent ; seul le premier change le groupe. Le second est un no-op
   documenté par `applied=False`.

C'est la fenêtre déjà notée en Phase 4 : l'adaptateur la ferme, l'outbox ne change pas.

---

## 9. Réglages

| Réglage | Défaut | Rôle |
|---|---|---|
| `NETWORK_PROVIDER` | `mock` | Inchangé. |
| `OPENWISP_BASE_URL` | `https://openwisp.example.invalid` | Inchangé. Overlay local : URL du nginx publié. |
| `OPENWISP_API_TOKEN` | sentinelle | Bearer unique API officielle + extension. |
| `OPENWISP_ORGANIZATION_ID` | sentinelle | Org de rattachement de `ensure_user`. |
| `OPENWISP_ORGANIZATION_SLUG` | `ville-de-dakar` | Slug pour `account/usage/`. Nouveau, fictif. |
| `OPENWISP_HTTP_TIMEOUT_SECONDS` | 10 | Timeout d'un appel. |
| `OPENWISP_RETRY_MAX` | 2 | Retries courts, pas l'outbox. |
| `OPENWISP_CIRCUIT_FAILURES` | 5 | Seuil d'ouverture. |
| `OPENWISP_CIRCUIT_OPEN_SECONDS` | 30 | Durée ouvert. |

`production.py` refuse de démarrer si `NETWORK_PROVIDER=openwisp` et que l'URL ou le
jeton sont encore les sentinelles, sur le même modèle que `JWT_SIGNING_KEY`.

---

## 10. Frontières de code

```
services/core-api/apps/access/providers/
├── base.py          inchangé (contrat)
├── mock.py          inchangé
├── openwisp.py      OpenWispClient, retries, circuit, mapping HTTP
└── __init__.py      registre + "openwisp"

services/core-api/apps/access/tasks.py     reconcile_active_entitlements
services/core-api/config/settings/base.py  réglages OPENWISP_* + beat
services/core-api/pyproject.toml           httpx ; respx en dev

infra/openwisp-extension/dakar_radius_ext/
├── api.py           permission d'org à la place de IsAdminUser
├── permissions.py   nouveau
├── services.py      inchangé (in-place déjà correct)
└── tests/           tests Django de l'extension

infra/compose/openwisp.yml
Makefile             openwisp-up, openwisp-down, test-openwisp
```

Aucune migration métier. L'extension n'ajoute aucun modèle.

---

## 11. Risques

| Risque | Traitement |
|---|---|
| Delete+recreate de `RadiusUserGroup` : 200 sans CoA | Test d'extension sur la stabilité du `pk` ; code déjà in-place. |
| Retries client × retries outbox = martèlement | 2 retries courts seulement ; circuit après 5 échecs ; outbox exponentielle. |
| `get_network_provider()` réinstancie le client | Circuit et cache au niveau classe. |
| UUID citoyen refusé comme username | Le spike créait des usagers par API ; un test overlay `ensure_user` avec un UUID le fige. Si refus, le correctif est un préfixe `dw-` sans changer le contrat (`subscriber_ref` reste l'UUID métier, le client traduit). Ce préfixe n'est **pas** introduit tant que l'UUID n'est pas rejeté. |
| Overlay trop lourd pour la CI | Jamais dans le workflow par défaut. |
| Mot de passe RADIUS jeté | Accepté tant qu'il n'y a pas de borne ; à revoir quand le portail soumettra des identifiants. |

---

## 12. Critères de fin de phase

- `NETWORK_PROVIDER=mock` par défaut ; `make test-api` vert sans conteneur OpenWISP.
- `NETWORK_PROVIDER=openwisp` résout `OpenWispClient`.
- Replay du même groupe = no-op puis entitlement `ACTIVE`.
- Extension : 403 cross-org, assign in-place, version d'image 25.10.4.
- `make openwisp-up` documenté ; `make test-openwisp` exercable en local.
- Ansible, borne réelle, accounting local : non livrés, et nommés comme tels.
