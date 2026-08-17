# Laboratoire OpenWISP jetable

Cet overlay lance `docker-openwisp` au tag `25.10.4`, hors de `make up`, de
`make test` et de la CI. Le clone local `infra/docker-openwisp/` et le fichier
`infra/openwisp/.env` sont ignorés par Git.

## Démarrage et arrêt

```bash
make openwisp-up
make openwisp-down
```

Au premier démarrage, `make openwisp-up` clone la version épinglée, crée
`infra/openwisp/.env` depuis le modèle et copie l'extension Django ainsi que
`seed.py` dans la personnalisation OpenWISP. Le laboratoire est ensuite accessible
sur <http://localhost:8002>.

Vérifier que toutes les images OpenWISP sont bien épinglées :

```bash
docker compose -f infra/docker-openwisp/docker-compose.yml \
  --env-file infra/openwisp/.env images
```

Les références des images OpenWISP doivent contenir `:25.10.4`.

## Initialisation

Après le premier démarrage, créer ou actualiser les données de laboratoire :

```bash
docker compose -f infra/docker-openwisp/docker-compose.yml \
  --env-file infra/openwisp/.env exec -T api \
  python manage.py shell < infra/openwisp/seed.py
```

Le script est idempotent. Il crée l'organisation `Ville de Dakar`, les groupes
RADIUS correspondant aux `radius_profile_ref` de démonstration, l'utilisateur de
service `dakar-service` et le NAS fictif `0.0.0.0/0` avec le secret fictif
`lab-nas-secret`.

Recopier les deux lignes imprimées par le script dans le fichier `.env` à la racine :

```dotenv
OPENWISP_BASE_URL=http://localhost:8002
OPENWISP_API_TOKEN=<token imprimé>
OPENWISP_ORGANIZATION_ID=<UUID imprimé>
```

Laisser `NETWORK_PROVIDER=mock` dans le `.env` racine. Ne passer à
`NETWORK_PROVIDER=openwisp` que pour un essai manuel explicite.

## Tests de l'extension

```bash
make test-openwisp
```

Cette cible démarre le laboratoire puis exécute uniquement les tests Django de
l'extension. Elle n'est appelée ni par `make test`, ni par `make check`.
