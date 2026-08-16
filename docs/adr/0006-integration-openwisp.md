# ADR-0006 — Frontière d'intégration OpenWISP après le spike

- Statut : **Acceptée** — option B retenue le 2026-08-16, et **vérifiée par une maquette
  fonctionnelle** ([`infra/openwisp-extension/`](../../infra/openwisp-extension/))
- Date : 2026-08-16
- Source : [spike OpenWISP](../phase0/06-spike-openwisp.md), cahier des charges §11, §4.3
- Complète : [ADR-0001](0001-openwisp-systeme-externe.md)

## Contexte

L'[ADR-0001](0001-openwisp-systeme-externe.md) pose qu'OpenWISP est un système externe
piloté par ses API officielles, sans fork ni écriture directe en base. Le spike a mesuré
ce que ces API couvrent réellement en version 25.10.4 / openwisp-radius 1.2.2.

**Ce que l'API REST couvre**, et qui suffit au fonctionnement courant :

| Besoin | Endpoint |
|---|---|
| Créer un usager, le rattacher à une organisation | `POST`/`PATCH /api/v1/users/user/` |
| Lire la consommation et les quotas restants | `GET /api/v1/radius/organization/<slug>/account/usage/` |
| Ingérer l'accounting, sans double comptage | `POST /api/v1/freeradius/accounting/` |
| Lister les sessions | `GET /api/v1/radius/sessions/` |
| Créer des lots d'usagers (vouchers) | `POST /api/v1/radius/batch/` |
| Gérer les organisations | `/api/v1/users/organization/` |

**Ce que l'API REST ne couvre pas**, et qui relève de la configuration :

1. **Affecter un groupe RADIUS précis à un usager.** Aucun endpoint. Un usager hérite du
   groupe par défaut de son organisation, et rien d'autre n'est possible par API.
2. Créer ou modifier un groupe RADIUS et ses attributs (`RadiusGroupCheck`/`Reply`).
3. Poser des attributs `RadiusCheck`/`RadiusReply` par usager.
4. Créer `OrganizationRadiusSettings` (jeton RADIUS, `coa_enabled`, IP autorisées).
5. Déclarer un `Nas` (borne/passerelle) et son secret partagé.
6. Forcer la déconnexion d'un usager à la demande.

Le point 1 est bloquant : **toute l'activation de forfait après paiement en dépend**
(§4.3 « L'accès doit pouvoir être activé immédiatement après un paiement réussi »,
§8.7 entitlements). Le point 6 empêche de tenir le §8.8. Les points 2 à 5 relèvent du
provisionnement et peuvent rester des opérations d'exploitation.

## Options

**A. Provisionnement manuel + activation impossible par API.** Les groupes, NAS et
réglages sont créés par un exploitant dans l'admin OpenWISP ; nos plans les référencent
par nom (`PlanVersion.radius_profile_ref`, déjà prévu au §9). Ne résout pas le point 1 :
un usager ne peut pas changer de forfait. **Insuffisant pour le MVP.**

**B. Application d'extension OpenWISP.** OpenWISP documente un mécanisme d'extension
(applications Django distinctes réutilisant ses modèles). Nous ajoutons une petite
application exposant les endpoints manquants (affectation de groupe, déconnexion), sans
toucher au cœur. Le déploiement OpenWISP en contient alors une brique de plus, à
maintenir à chaque montée de version. Conforme à la règle 2 du cahier des charges
(« adaptateurs et services séparés »), mais c'est une modification du déploiement
et elle doit être validée explicitement.

**C. Contribution amont.** Proposer les endpoints manquants au projet openwisp-radius.
Le plus propre à long terme, mais le calendrier ne dépend pas de nous ; à mener en
parallèle de B, pas à sa place.

**D. Écriture directe en base OpenWISP.** Explicitement interdite par l'ADR-0001 et le
§4.3 du cahier des charges. Écartée.

## Décision

**Option B, complétée par C.** Une application d'extension expose les deux endpoints
manquants ; tout le reste continue de passer par les API officielles.

La faisabilité n'a pas été supposée : elle a été **démontrée** sur l'instance jetable du
spike, avec un faux NAS en pyrad pour recevoir réellement les paquets RADIUS.

### Preuves

| Étape vérifiée | Résultat |
|---|---|
| Chargement de l'extension sans toucher au cœur | `INSTALLED_APPS` et `ROOT_URLCONF` étendus depuis `custom_django_settings.py`, importé en fin de `settings.py` |
| `POST /api/v1/dakar/radius/assign-group/` | HTTP 200 ; `RadiusUserGroup` vérifié en base : une seule affectation, le bon groupe |
| CoA sur session ouverte | Tâche Celery `perform_change_of_authorization` exécutée, **CoA-Request reçu par le NAS**, CoAACK renvoyé |
| Attributs réellement transmis | `Session-Timeout=10800`, `CoovaChilli-Max-Total-Octets=3000000000` — les limites du plan atteignent la borne |
| `POST /api/v1/dakar/radius/disconnect/` | HTTP 200 ; **Disconnect-Request reçu par le NAS** avec `User-Name`, DisconnectACK renvoyé |
| Authentification | Même `BearerAuthentication` que l'API OpenWISP : un seul jeton de service pour les deux |

### Piège découvert pendant la vérification

La première version de la maquette **supprimait puis recréait** l'affectation de groupe.
L'endpoint répondait 200, la base était correcte — et **aucun CoA ne partait**.

En cause : openwisp-radius déclenche le CoA depuis un récepteur `pre_save` qui compare le
groupe stocké au groupe entrant, et abandonne si l'objet n'existe pas encore en base. Une
ligne neuve n'a pas de contrepartie stockée : le récepteur sort, et le changement
n'atteint jamais la borne.

L'affectation doit donc être **modifiée en place**. Un test qui se serait arrêté au code
HTTP 200 aurait laissé passer ce défaut jusqu'en production, où il se serait manifesté
par des forfaits payés qui ne s'appliquent qu'à la session suivante.

### Portée

Cette décision conditionne la Phase 5. Elle n'empêche pas les Phases 2 à 4, qui
s'appuient sur `MockNetworkProvider`.

## Conséquences

- L'interface `NetworkProvider` doit exposer `assign_plan(user, plan_ref)` et
  `disconnect(session)` dès la Phase 3, même si seul le mock les implémente : c'est le
  contrat que l'implémentation OpenWISP devra tenir.
- `PlanVersion.radius_profile_ref` (§9) désigne un **nom de groupe RADIUS** pré-provisionné.
  Les plans ne créent pas de groupes à la volée.
- Le déploiement doit configurer `freeradius_allowed_hosts` pour n'autoriser que nos
  services à pousser de l'accounting, et `coa_enabled` par organisation.
- L'extension est une **maquette**, pas du code de production. Avant la Phase 5 :
  restreindre les droits aux organisations de l'appelant, ajouter des tests automatisés,
  épingler la version d'OpenWISP validée. Liste complète dans son
  [README](../../infra/openwisp-extension/README.md).
- Le quota de trafic est poussé par l'attribut **`CoovaChilli-Max-Total-Octets`**, propre
  à un fournisseur : les passerelles retenues doivent le comprendre, sans quoi le quota de
  volume ne s'applique pas côté équipement. À vérifier modèle par modèle (§6.1).
- Écarts fonctionnels à arbitrer avec la Ville, indépendants de cette décision :
  quota de trafic cumulé au lieu de montant/descendant séparés, absence de compteur
  hebdomadaire, débit et sessions simultanées dépendants du matériel (§8.3, §8.4).
- openwisp-radius fournit déjà une inscription par téléphone et OTP
  (`account/phone/token/`, `account/phone/verify/`). La Phase 3 doit décider si elle
  s'appuie dessus ou conserve son propre parcours OTP — le cahier des charges impose des
  règles d'abus et de consentement (§8.1) qui plaident pour garder la maîtrise côté
  plateforme, l'OTP OpenWISP servant alors uniquement de vérification RADIUS.
