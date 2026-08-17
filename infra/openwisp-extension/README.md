# Extension RADIUS Dakar WiFi pour OpenWISP

Cette application comble les deux manques de l'API REST d'openwisp-radius identifiés
par le [spike](../../docs/phase0/06-spike-openwisp.md) et tranchés en
[ADR-0006](../../docs/adr/0006-integration-openwisp.md) :

| Endpoint | Manque comblé | Exigence |
|---|---|---|
| `POST /api/v1/dakar/radius/assign-group/` | Affecter un groupe RADIUS précis à un usager | §4.3, §8.7 — activation du forfait après paiement |
| `POST /api/v1/dakar/radius/disconnect/` | Forcer la déconnexion d'un usager | §8.8 — déconnexion par un agent autorisé |

## Ce que cette extension n'est pas

Ce n'est **pas un fork d'OpenWISP** (règle 2 du cahier des charges). C'est une
application Django distincte, chargée par le mécanisme de personnalisation officiel de
`docker-openwisp`. Elle :

- ne modifie aucun fichier du cœur d'OpenWISP ;
- n'écrit dans aucune table RADIUS directement — elle passe par les modèles et les
  fonctions d'openwisp-radius (`RadiusUserGroup`, `coa_manager`, `RadClient`) ;
- vit dans son propre espace d'URL (`/api/v1/dakar/`), pour ne jamais entrer en
  collision avec les routes amont lors d'une montée de version.

La surface est volontairement minimale : deux endpoints. Tout le reste continue de
passer par les API officielles d'OpenWISP.

## Comment ça se branche

OpenWISP importe `configuration/custom_django_settings.py` **à la toute fin** de son
propre module de settings. À cet instant `INSTALLED_APPS` et `ROOT_URLCONF` ont leurs
valeurs définitives : on peut donc les étendre au lieu de les remplacer.

```text
custom_django_settings.py   ajoute l'application et remplace ROOT_URLCONF
custom_urls.py              URLs d'OpenWISP + notre espace /api/v1/dakar/
dakar_radius_ext/           l'application elle-même
├── api.py                  vues DRF
├── services.py             opérations métier (groupe, déconnexion)
└── urls.py
```

## Déploiement

L'extension est validée avec OpenWISP `25.10.4`. Depuis la racine du projet, le
laboratoire jetable copie automatiquement son contenu dans le répertoire de
personnalisation officiel de `docker-openwisp` :

```bash
make openwisp-up
make test-openwisp
```

Le répertoire est monté en lecture seule dans les conteneurs `dashboard`, `api`,
`celery`, `celery_monitoring` et `celerybeat`. Aucune migration : l'extension
n'ajoute aucun modèle.

Prérequis côté OpenWISP pour que la déconnexion et le CoA fonctionnent réellement :

- `coa_enabled` activé sur l'organisation ;
- un enregistrement `Nas` dont le champ `name` est un réseau IP contenant l'adresse
  `nas_ip_address` des sessions, porteur du secret partagé ;
- la borne doit écouter les paquets CoA/Disconnect (port 3799).

## Utilisation

```bash
# Activer un forfait : déplace l'usager vers le groupe RADIUS du plan.
# Un CoA part automatiquement vers le NAS de chaque session ouverte.
curl -X POST https://<api>/api/v1/dakar/radius/assign-group/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"username": "usager", "group_name": "dakar-spike-power-users"}'

# Déconnexion forcée : un Disconnect-Request par session ouverte.
curl -X POST https://<api>/api/v1/dakar/radius/disconnect/ \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"username": "usager"}'
```

`disconnect` renvoie un état **par session** plutôt qu'une erreur globale : une borne
injoignable pendant que les autres répondent est un cas normal, pas un échec.

## Sécurité et exploitation

Les deux vues exigent que l'appelant soit authentifié et membre d'une organisation
commune avec l'usager ciblé. Une tentative d'action entre organisations renvoie `403`.

Les opérations sensibles doivent rester journalisées en audit côté plateforme métier
(§13.4), où la justification exigée au §8.8 est disponible. À chaque montée de version
d'OpenWISP, mettre à jour l'épinglage puis rejouer `make test-openwisp`.
