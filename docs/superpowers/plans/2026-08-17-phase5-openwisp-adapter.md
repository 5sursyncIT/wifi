# Phase 5 — Adaptateur OpenWISP et Compose jetable — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brancher le métier sur OpenWISP via `NetworkProvider` sans toucher à l'outbox, avec no-op sur réaffectation du même groupe, extension durcie, et une instance Docker jetable hors de `make up`.

**Architecture:** `OpenWispClient` (HTTP `httpx`) implémente `NetworkProvider`. Les API officielles couvrent `ensure_user` et `read_usage` ; l'extension Dakar couvre `assign_plan` et `disconnect`. Retries courts et circuit breaker in-process dans le client ; l'outbox Phase 4 reste le retry long. `NETWORK_PROVIDER=mock` reste le défaut. Overlay Compose séparé, images `openwisp/*:25.10.4`.

**Tech Stack:** Django 5.2, httpx, respx, pytest-django, Celery beat, Docker Compose, extension Django `dakar_radius_ext`.

**Spec:** [`docs/superpowers/specs/2026-08-17-phase5-openwisp-adapter-design.md`](../specs/2026-08-17-phase5-openwisp-adapter-design.md)

## Global Constraints

- **Langue** (ADR-0003) : code, identifiants, commentaires techniques et commits en **anglais** ; `docs/` en **français** ; messages usager en **français**.
- **Commits** : Conventional Commits. Un commit par tâche, après les tests verts de cette tâche.
- **TDD** : aucun code de production avant un test qui a échoué pour la bonne raison.
- **Pas de fork, pas d'écriture SQL dans OpenWISP** (ADR-0001, ADR-0006).
- **Montants** : hors sujet ici ; ne pas y toucher.
- **Ruff / mypy** : `uv run ruff check .` et `uv run mypy .` depuis `services/core-api` restent verts.
- **Tests** : `DJANGO_SETTINGS_MODULE=config.settings.test`, `testpaths=["apps"]`. Commande :
  ```bash
  docker compose -f infra/compose/docker-compose.yml up -d --wait db redis
  uv run --directory services/core-api pytest
  ```
- **Défaut** : `NETWORK_PROVIDER=mock`. Les tests et e2e existants ne doivent pas casser.
- **Répertoire** : `uv` depuis `services/core-api` ; `make` depuis la racine.
- **Ne pas** lancer `make openwisp-up` dans la CI ni dans `make test` / `make check`.

---

## Structure des fichiers

**Créés**

| Fichier | Responsabilité |
|---|---|
| `services/core-api/apps/access/providers/openwisp.py` | `OpenWispClient` : HTTP, mapping d'erreurs, retries, circuit |
| `services/core-api/apps/access/tests/test_openwisp_client.py` | Mocks HTTP (respx) |
| `services/core-api/apps/access/tests/test_openwisp_activation.py` | Replay crash window via le handler d'outbox |
| `services/core-api/apps/access/tasks.py` | `reconcile_active_entitlements` |
| `services/core-api/apps/access/tests/test_reconcile.py` | No-op mock + ré-assign OpenWISP |
| `infra/openwisp-extension/dakar_radius_ext/org_scope.py` | Comparaison d'organisations, sans import OpenWISP |
| `infra/openwisp-extension/dakar_radius_ext/permissions.py` | Permission DRF |
| `infra/openwisp-extension/dakar_radius_ext/tests/test_org_scope.py` | Tests purs du scope |
| `infra/openwisp-extension/dakar_radius_ext/tests/test_assign_in_place.py` | Tests Django (image OpenWISP) |
| `infra/openwisp/.env.example` | Ports et domaines du labo overlay |
| `infra/openwisp/seed.py` | Org, groupes, compte de service, NAS fictif |
| `infra/openwisp/README.md` | `make openwisp-up` |

**Modifiés**

| Fichier | Modification |
|---|---|
| `services/core-api/apps/access/providers/__init__.py` | Enregistrer `"openwisp"` |
| `services/core-api/config/settings/base.py` | Réglages `OPENWISP_*` + beat de réconciliation |
| `services/core-api/config/settings/production.py` | Refus des sentinelles si provider `openwisp` |
| `services/core-api/pyproject.toml` | `httpx` ; `respx` en dev |
| `infra/openwisp-extension/dakar_radius_ext/api.py` | Permission d'org |
| `infra/openwisp-extension/README.md` | Droits, version épinglée, tests |
| `Makefile` | `openwisp-up`, `openwisp-down`, `test-openwisp` |
| `.env.example` | `OPENWISP_ORGANIZATION_SLUG` |
| `.gitignore` | `infra/docker-openwisp/`, `celerybeat-schedule*` |
| `docs/phase0/03-backlog.md` | Items livrés vs reportés |

---

## Task 1: Client HTTP et `assign_plan`

**Files:**
- Create: `services/core-api/apps/access/providers/openwisp.py`
- Create: `services/core-api/apps/access/tests/test_openwisp_client.py`
- Modify: `services/core-api/apps/access/providers/__init__.py`
- Modify: `services/core-api/config/settings/base.py`
- Modify: `services/core-api/pyproject.toml`

**Interfaces:**
- Consumes: `NetworkProvider`, `AssignmentResult`, `NetworkTimeout`, `NetworkTemporaryError`, `NetworkPermanentError` depuis `apps.access.providers.base`
- Produces:
  - `OpenWispClient` avec `name = "openwisp"`
  - `OpenWispClient.reset() -> None` — remet circuit et compteurs (classe)
  - `OpenWispClient.assign_plan(subscriber_ref: str, profile_ref: str) -> AssignmentResult`
  - `get_network_provider()` accepte `NETWORK_PROVIDER=openwisp`
  - Réglages : `OPENWISP_BASE_URL`, `OPENWISP_API_TOKEN`, `OPENWISP_ORGANIZATION_ID`, `OPENWISP_ORGANIZATION_SLUG`, `OPENWISP_HTTP_TIMEOUT_SECONDS`, `OPENWISP_RETRY_MAX`, `OPENWISP_CIRCUIT_FAILURES`, `OPENWISP_CIRCUIT_OPEN_SECONDS`

- [ ] **Step 1: Dépendances et réglages**

Depuis `services/core-api` :

```bash
uv add httpx
uv add --group dev respx
```

Dans `config/settings/base.py`, **juste après** `NETWORK_PROVIDER = ...` :

```python
OPENWISP_BASE_URL = env.str("OPENWISP_BASE_URL", default="https://openwisp.example.invalid")
OPENWISP_API_TOKEN = env.str("OPENWISP_API_TOKEN", default="change-me")
OPENWISP_ORGANIZATION_ID = env.str("OPENWISP_ORGANIZATION_ID", default="change-me")
OPENWISP_ORGANIZATION_SLUG = env.str("OPENWISP_ORGANIZATION_SLUG", default="ville-de-dakar")
OPENWISP_HTTP_TIMEOUT_SECONDS = env.int("OPENWISP_HTTP_TIMEOUT_SECONDS", default=10)
OPENWISP_RETRY_MAX = env.int("OPENWISP_RETRY_MAX", default=2)
OPENWISP_CIRCUIT_FAILURES = env.int("OPENWISP_CIRCUIT_FAILURES", default=5)
OPENWISP_CIRCUIT_OPEN_SECONDS = env.int("OPENWISP_CIRCUIT_OPEN_SECONDS", default=30)
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `services/core-api/apps/access/tests/test_openwisp_client.py` :

```python
"""HTTP adapter for OpenWISP (cahier des charges §11, DW-P5-02)."""

import httpx
import pytest
import respx
from django.test import override_settings

from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkPermanentError, NetworkTemporaryError
from apps.access.providers.openwisp import OpenWispClient

BASE = "http://openwisp.test"
ASSIGN = f"{BASE}/api/v1/dakar/radius/assign-group/"

OPENWISP = dict(
    NETWORK_PROVIDER="openwisp",
    OPENWISP_BASE_URL=BASE,
    OPENWISP_API_TOKEN="test-token",
    OPENWISP_ORGANIZATION_ID="org-1",
    OPENWISP_ORGANIZATION_SLUG="ville-de-dakar",
    OPENWISP_HTTP_TIMEOUT_SECONDS=10,
    OPENWISP_RETRY_MAX=2,
    OPENWISP_CIRCUIT_FAILURES=5,
    OPENWISP_CIRCUIT_OPEN_SECONDS=30,
)


@pytest.fixture(autouse=True)
def _reset():
    OpenWispClient.reset()
    yield
    OpenWispClient.reset()


@override_settings(**OPENWISP)
def test_the_factory_returns_the_openwisp_client():
    assert isinstance(get_network_provider(), OpenWispClient)


@override_settings(**OPENWISP)
@respx.mock
def test_assign_plan_posts_the_group_and_reports_applied():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={"username": "citizen-1", "group_name": "dakar-1h", "organization": "org-1"},
        )
    )

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is True
    assert result.profile_ref == "dakar-1h"
    assert respx.calls.last.request.headers["Authorization"] == "Bearer test-token"


@override_settings(**OPENWISP)
@respx.mock
def test_assigning_the_same_group_is_a_noop():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={"username": "citizen-1", "group_name": "dakar-1h", "organization": "org-1"},
        )
    )

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is False
    assert result.profile_ref == "dakar-1h"
    assert "already" in result.detail.lower()


@override_settings(**OPENWISP)
@respx.mock
def test_unknown_group_is_a_permanent_error():
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(400, json={"detail": "No RADIUS group."})
    )

    with pytest.raises(NetworkPermanentError):
        OpenWispClient().assign_plan("citizen-1", "missing-group")


@override_settings(**OPENWISP)
@respx.mock
def test_server_error_is_retryable():
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))

    with pytest.raises(NetworkTemporaryError) as raised:
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert raised.value.retryable is True
```

Le troisième test (`already assigned`) et le premier succès se marchent sur les pieds : **la même 200 avec `group_name` égal au demandé**. Corriger le test de succès : la première affectation doit renvoyer un **autre** groupe dans la réponse que celui demandé ? Non — la spec dit : si `group_name` de la réponse **égale** le `profile_ref` demandé → `applied=False`.

Donc le cas `applied=True` est : la réponse porte le groupe demandé **et** un signal de changement. L'extension actuelle ne renvoie pas `changed`. Décision du plan (conforme à la spec §4) : comparer n'est pas suffisant pour `applied=True` vs `False` si l'extension renvoie toujours le groupe courant.

**Décision d'implémentation :** l'extension gagne un champ booléen `changed` dans la JSON de `assign-group` :

- `changed: true` → `applied=True`
- `changed: false` → `applied=False` (`detail="already assigned"`)

C'est le seul moyen honnête sans GET préalable. Modifier `infra/openwisp-extension/dakar_radius_ext/api.py` **dans cette tâche** pour exposer `changed` (True si `save` a eu lieu). `services.py` doit indiquer si un `save` a eu lieu : faire renvoyer `(user_group, changed)` depuis `assign_group`, ou comparer le `group_id` avant/après dans la vue.

Mettre à jour les tests ci-dessus :

```python
# applied=True
json={"username": "citizen-1", "group_name": "dakar-1h", "organization": "org-1", "changed": True}

# applied=False
json={"username": "citizen-1", "group_name": "dakar-1h", "organization": "org-1", "changed": False}
```

Si `changed` est absent (vieille extension), traiter comme `applied=True` si 200 — mieux : exiger `changed`. Exiger le champ : absence → `applied=True` seulement si on ne veut pas casser ; **exiger `changed`** : s'il manque, `applied=True` (activation métier OK, CoA peut avoir eu lieu).

- [ ] **Step 3: Lancer le test, constater l'échec**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: apps.access.providers.openwisp` ou `KeyError: 'openwisp'`.

- [ ] **Step 4: Implémentation minimale**

`assign_group` dans `services.py` : avant le `save`, `changed = not (user_group.pk and user_group.group_id == group.id)` ; après le no-op `return user_group, False` ; après `save` `return user_group, True`. Adapter l'unique appelant `api.py` :

```python
user_group, changed = assign_group(user, data["group_name"])
return Response({
    "username": user.username,
    "group_name": user_group.group.name,
    "organization": str(user_group.group.organization_id),
    "changed": changed,
})
```

`openwisp.py` :

```python
"""OpenWISP HTTP adapter behind NetworkProvider (ADR-0001, ADR-0006, §11)."""

from urllib.parse import urljoin

import httpx
from django.conf import settings

from apps.access.providers.base import (
    AssignmentResult,
    NetworkPermanentError,
    NetworkProvider,
    NetworkTemporaryError,
    NetworkTimeout,
)


class OpenWispClient(NetworkProvider):
    name = "openwisp"
    _failures = 0
    _opened_at: float | None = None

    @classmethod
    def reset(cls) -> None:
        cls._failures = 0
        cls._opened_at = None

    def _url(self, path: str) -> str:
        return urljoin(settings.OPENWISP_BASE_URL.rstrip("/") + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                self._url(path),
                headers={"Authorization": f"Bearer {settings.OPENWISP_API_TOKEN}"},
                timeout=settings.OPENWISP_HTTP_TIMEOUT_SECONDS,
                **kwargs,
            )
        except httpx.TimeoutException as error:
            raise NetworkTimeout(str(error)) from error
        except httpx.TransportError as error:
            raise NetworkTemporaryError(str(error)) from error

        if response.status_code >= 500 or response.status_code == 429:
            raise NetworkTemporaryError(
                f"OpenWISP returned HTTP {response.status_code}."
            )
        if response.status_code >= 400:
            raise NetworkPermanentError(
                f"OpenWISP returned HTTP {response.status_code}."
            )
        return response

    def assign_plan(self, subscriber_ref: str, profile_ref: str) -> AssignmentResult:
        response = self._request(
            "POST",
            "/api/v1/dakar/radius/assign-group/",
            json={"username": subscriber_ref, "group_name": profile_ref},
        )
        payload = response.json()
        changed = payload.get("changed", True)
        return AssignmentResult(
            applied=bool(changed),
            profile_ref=profile_ref,
            detail="" if changed else "already assigned",
        )

    def healthcheck(self) -> bool:
        raise NotImplementedError

    def ensure_user(self, subscriber_ref: str) -> str:
        raise NotImplementedError

    def disconnect(self, subscriber_ref: str):
        raise NotImplementedError

    def read_usage(self, subscriber_ref: str):
        raise NotImplementedError
```

Dans `__init__.py` :

```python
from apps.access.providers.openwisp import OpenWispClient

_PROVIDERS: dict[str, type[NetworkProvider]] = {
    "mock": MockNetworkProvider,
    "openwisp": OpenWispClient,
}
```

Les méthodes abstraites doivent exister dès maintenant (stubs `NotImplementedError`) pour que la classe soit instanciable. `healthcheck` du contrat ne peut pas rester abstraite.

- [ ] **Step 5: Tests verts**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_client.py -v
uv run --directory services/core-api pytest apps/access/tests/test_mock_network_provider.py -v
```

Expected: PASS. Le mock reste le défaut.

- [ ] **Step 6: Commit**

```bash
git add services/core-api/pyproject.toml services/core-api/uv.lock \
  services/core-api/apps/access/providers/openwisp.py \
  services/core-api/apps/access/providers/__init__.py \
  services/core-api/apps/access/tests/test_openwisp_client.py \
  services/core-api/config/settings/base.py \
  infra/openwisp-extension/dakar_radius_ext/api.py \
  infra/openwisp-extension/dakar_radius_ext/services.py
git commit -m "$(cat <<'EOF'
feat: add OpenWISP HTTP adapter for plan assignment

EOF
)"
```

---

## Task 2: Retries courts et circuit breaker

**Files:**
- Modify: `services/core-api/apps/access/providers/openwisp.py`
- Modify: `services/core-api/apps/access/tests/test_openwisp_client.py`

**Interfaces:**
- Consumes: `OpenWispClient._request`, `OPENWISP_RETRY_MAX`, `OPENWISP_CIRCUIT_FAILURES`, `OPENWISP_CIRCUIT_OPEN_SECONDS`
- Produces: `_request` retry 429/5xx/timeout jusqu'à `RETRY_MAX` fois de plus ; circuit classe ; 4xx permanents n'incrémentent pas le circuit

- [ ] **Step 1: Tests qui échouent**

Ajouter à `test_openwisp_client.py` :

```python
from apps.access.providers.base import NetworkTimeout


@override_settings(**OPENWISP)
@respx.mock
def test_a_transient_failure_is_retried_until_success(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    route = respx.post(ASSIGN)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(503),
        httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        ),
    ]

    result = OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert result.applied is True
    assert route.call_count == 3


@override_settings(**OPENWISP)
@respx.mock
def test_retries_stop_at_the_configured_cap(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))

    with pytest.raises(NetworkTemporaryError):
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 3  # 1 + OPENWISP_RETRY_MAX


@override_settings(**OPENWISP)
@respx.mock
def test_four_hundreds_are_not_retried():
    respx.post(ASSIGN).mock(return_value=httpx.Response(400, json={"detail": "no"}))

    with pytest.raises(NetworkPermanentError):
        OpenWispClient().assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 1


@override_settings(**OPENWISP)
@respx.mock
def test_the_circuit_opens_after_consecutive_retryable_failures(monkeypatch):
    monkeypatch.setattr("apps.access.providers.openwisp.time.sleep", lambda _s: None)
    respx.post(ASSIGN).mock(return_value=httpx.Response(503))
    client = OpenWispClient()

    for _ in range(5):
        with pytest.raises(NetworkTemporaryError):
            client.assign_plan("citizen-1", "dakar-1h")

    calls_before = respx.calls.call_count
    with pytest.raises(NetworkTemporaryError):
        client.assign_plan("citizen-1", "dakar-1h")
    assert respx.calls.call_count == calls_before  # no HTTP


@override_settings(**OPENWISP)
@respx.mock
def test_a_permanent_error_does_not_open_the_circuit():
    respx.post(ASSIGN).mock(return_value=httpx.Response(400, json={"detail": "no"}))
    client = OpenWispClient()

    for _ in range(6):
        with pytest.raises(NetworkPermanentError):
            client.assign_plan("citizen-1", "dakar-1h")

    assert respx.calls.call_count == 6
```

Le test circuit : chaque `assign_plan` fait 3 tentatives HTTP (1+2 retries) avant d'incrémenter **une** défaillance circuit. Cinq défaillances = 15 HTTP, puis le 6e `assign_plan` sans HTTP.

Documenter dans le test : `_record_failure()` une fois par **appel métier** épuisé, pas par tentative HTTP. Sinon le circuit s'ouvre trop tôt (2 assign suffiraient).

- [ ] **Step 2: Constater l'échec**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_client.py::test_a_transient_failure_is_retried_until_success -v
```

Expected: FAIL — un seul appel, `NetworkTemporaryError` immédiat.

- [ ] **Step 3: Implémenter retries + circuit**

Dans `openwisp.py`, importer `time`.

État classe déjà là. Ajouter :

```python
def _raise_if_open(self) -> None:
    if self._opened_at is None:
        return
    elapsed = time.monotonic() - self._opened_at
    if elapsed < settings.OPENWISP_CIRCUIT_OPEN_SECONDS:
        raise NetworkTemporaryError("OpenWISP circuit is open.")
    # Half-open: allow one probe. Leave _opened_at set until success clears it.

def _record_success(self) -> None:
    type(self)._failures = 0
    type(self)._opened_at = None

def _record_failure(self) -> None:
    type(self)._failures += 1
    if type(self)._failures >= settings.OPENWISP_CIRCUIT_FAILURES:
        type(self)._opened_at = time.monotonic()
```

Envelopper `_request` :

1. `_raise_if_open()`
2. boucle `for attempt in range(1 + settings.OPENWISP_RETRY_MAX)`
3. timeout/5xx/429 : si attempt restant, `time.sleep(0.2 * 2 ** (attempt - 1))` et continue ; sinon `_record_failure()` et raise
4. 4xx permanent : raise **sans** `_record_failure`
5. 2xx : `_record_success()` ; return

Un timeout `httpx` compte comme retryable.

- [ ] **Step 4: Tests verts**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_client.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/core-api/apps/access/providers/openwisp.py \
  services/core-api/apps/access/tests/test_openwisp_client.py
git commit -m "$(cat <<'EOF'
feat: retry transient OpenWISP errors behind a circuit breaker

EOF
)"
```

---

## Task 3: `ensure_user`, `disconnect`, `read_usage`, `healthcheck`

**Files:**
- Modify: `services/core-api/apps/access/providers/openwisp.py`
- Modify: `services/core-api/apps/access/tests/test_openwisp_client.py`

**Interfaces:**
- Consumes: `_request`
- Produces:
  - `ensure_user(subscriber_ref: str) -> str`
  - `disconnect(subscriber_ref: str) -> list[DisconnectResult]`
  - `read_usage(subscriber_ref: str) -> Usage`
  - `healthcheck() -> bool`

`ensure_user` :

1. `GET /api/v1/users/user/?username={subscriber_ref}`
2. Si `results` non vide → retourner `subscriber_ref` (déjà créé).
3. Sinon `POST /api/v1/users/user/` avec `username`, `password=secrets.token_urlsafe(32)`, `email=f"{subscriber_ref}@radius.dakar-wifi.invalid"`.
4. `PATCH /api/v1/users/user/{id}/` JSON `{"organization": settings.OPENWISP_ORGANIZATION_ID}` (forme du spike). Si 400, tenter `{"organizations": [settings.OPENWISP_ORGANIZATION_ID]}` uniquement si le premier PATCH échoue — **non** : un seul contrat. Utiliser le body que le spike a validé : **PATCH d'organisation** comme dans `docs/phase0/06-spike-openwisp.md` (« `PATCH` le rattache à une organisation »). Implémenter `{"organization": OPENWISP_ORGANIZATION_ID}`. Si les tests overlay le réfutent, corriger avec un test overlay, pas les deux formes à l'avance.

`disconnect` : POST `/api/v1/dakar/radius/disconnect/` `{username}`. Mapper `sessions[]` : `session` → `session_id`, `status == "acknowledged"` → `acknowledged=True`, sinon False, `detail=status`. HTTP 2xx même avec des refus NAS : **pas d'exception**.

`read_usage` : GET `/api/v1/radius/organization/{slug}/account/usage/?username={subscriber_ref}` — si 404 query, GET sans query et ignorer. Spec : `GET /api/v1/radius/organization/<slug>/account/usage/`. Le spike n'a pas montré le query username. **Décision :** GET `{path}?username={subscriber_ref}`. Parser `checks[]` : attribut `Max-Daily-Session` → `seconds_used=int(result)`, `Max-Daily-Session-Traffic` → `bytes_used=int(result)`. Absent → 0.

`healthcheck` : GET `/api/v1/users/user/?limit=1`. 2xx → True. Toute exception réseau ou 4xx/5xx → False. **N'ouvre pas le circuit** : appeler httpx directement, pas `_request`.

- [ ] **Step 1: Tests qui échouent**

```python
from apps.access.providers.base import DisconnectResult, Usage

USERS = f"{BASE}/api/v1/users/user/"
DISCONNECT = f"{BASE}/api/v1/dakar/radius/disconnect/"
USAGE = f"{BASE}/api/v1/radius/organization/ville-de-dakar/account/usage/"


@override_settings(**OPENWISP)
@respx.mock
def test_ensure_user_creates_when_missing():
    respx.get(USERS).mock(return_value=httpx.Response(200, json={"results": []}))
    created = respx.post(USERS).mock(
        return_value=httpx.Response(201, json={"id": "u1", "username": "citizen-1"})
    )
    respx.patch(f"{USERS}u1/").mock(return_value=httpx.Response(200, json={"id": "u1"}))

    assert OpenWispClient().ensure_user("citizen-1") == "citizen-1"
    assert created.called


@override_settings(**OPENWISP)
@respx.mock
def test_ensure_user_is_idempotent_when_present():
    respx.get(USERS).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": "u1", "username": "citizen-1"}]}
        )
    )
    post = respx.post(USERS)

    assert OpenWispClient().ensure_user("citizen-1") == "citizen-1"
    assert not post.called


@override_settings(**OPENWISP)
@respx.mock
def test_disconnect_returns_per_session_results_without_raising():
    respx.post(DISCONNECT).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "citizen-1",
                "sessions": [
                    {"session": "abc", "nas": "10.0.0.1", "status": "acknowledged"},
                    {
                        "session": "def",
                        "nas": "10.0.0.2",
                        "status": "refused_or_unreachable",
                    },
                ],
            },
        )
    )

    results = OpenWispClient().disconnect("citizen-1")

    assert results == [
        DisconnectResult(session_id="abc", acknowledged=True, detail="acknowledged"),
        DisconnectResult(
            session_id="def", acknowledged=False, detail="refused_or_unreachable"
        ),
    ]


@override_settings(**OPENWISP)
@respx.mock
def test_read_usage_maps_daily_counters():
    respx.get(USAGE).mock(
        return_value=httpx.Response(
            200,
            json={
                "checks": [
                    {
                        "attribute": "Max-Daily-Session",
                        "value": "10800",
                        "result": 600,
                        "type": "seconds",
                    },
                    {
                        "attribute": "Max-Daily-Session-Traffic",
                        "value": "3000000000",
                        "result": 50000000,
                        "type": "bytes",
                    },
                ]
            },
        )
    )

    usage = OpenWispClient().read_usage("citizen-1")

    assert usage.seconds_used == 600
    assert usage.bytes_used == 50_000_000


@override_settings(**OPENWISP)
@respx.mock
def test_healthcheck_is_true_on_http_ok():
    respx.get(f"{USERS}").mock(return_value=httpx.Response(200, json={"results": []}))

    assert OpenWispClient().healthcheck() is True


@override_settings(**OPENWISP)
@respx.mock
def test_healthcheck_is_false_on_failure_and_does_not_open_the_circuit():
    respx.get(USERS).mock(return_value=httpx.Response(503))
    assert OpenWispClient().healthcheck() is False
    respx.post(ASSIGN).mock(
        return_value=httpx.Response(
            200,
            json={
                "username": "x",
                "group_name": "dakar-1h",
                "organization": "org-1",
                "changed": True,
            },
        )
    )
    OpenWispClient().assign_plan("x", "dakar-1h")  # must still hit HTTP
```

- [ ] **Step 2: Constater l'échec** puis implémenter les quatre méthodes (plus `secrets`).

`healthcheck` : `try/except (NetworkError, httpx.HTTPError)` autour d'un `httpx.request` brut, return False. Ne pas appeler `_record_failure`.

- [ ] **Step 3: Tests verts + commit**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_client.py -v
```

```bash
git add services/core-api/apps/access/providers/openwisp.py \
  services/core-api/apps/access/tests/test_openwisp_client.py
git commit -m "$(cat <<'EOF'
feat: cover remaining OpenWISP NetworkProvider operations

EOF
)"
```

---

## Task 4: Replay d'activation après crash

**Files:**
- Create: `services/core-api/apps/access/tests/test_openwisp_activation.py`

**Interfaces:**
- Consumes: `activate_entitlement`, `entitlement_for_order`, `OpenWispClient`, fixture `order`
- Produces: preuve DW-P5-02 — second `assign_plan` `changed: false` puis entitlement `ACTIVE`

- [ ] **Step 1: Test qui échoue s'il n'y a pas de mocks `ensure_user`**

Le handler appelle `ensure_user` puis `assign_plan`. Le test mocke les deux.

```python
"""Crash window: assign succeeded, entitlement not yet ACTIVE, replay is a no-op."""

import httpx
import pytest
import respx
from django.test import override_settings
from django.utils import timezone

from apps.access.activation import activate_entitlement, entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.openwisp import OpenWispClient
from apps.access.tests.test_openwisp_client import ASSIGN, OPENWISP, USERS
from apps.billing.models import Order


@pytest.fixture
def paid_order(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


@override_settings(**OPENWISP)
@respx.mock
def test_replaying_activation_after_a_crash_does_not_reassign(paid_order):
    OpenWispClient.reset()
    username = str(paid_order.citizen_id)
    group = paid_order.plan_version.radius_profile_ref
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    respx.get(USERS).mock(
        return_value=httpx.Response(
            200, json={"results": [{"id": "u1", "username": username}]}
        )
    )
    assign = respx.post(ASSIGN)
    assign.side_effect = [
        httpx.Response(
            200,
            json={
                "username": username,
                "group_name": group,
                "organization": "org-1",
                "changed": True,
            },
        ),
        httpx.Response(
            200,
            json={
                "username": username,
                "group_name": group,
                "organization": "org-1",
                "changed": False,
            },
        ),
    ]

    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.ACTIVE

    entitlement.status = Entitlement.Status.PENDING_ACTIVATION
    entitlement.save(update_fields=["status", "updated_at"])

    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    entitlement.refresh_from_db()

    assert entitlement.status == Entitlement.Status.ACTIVE
    assert assign.call_count == 2
```

**Attention :** le handler actuel, si le statut est déjà `ACTIVE`, **ne rappelle pas** `assign_plan`. Le crash window suppose qu'on n'a **pas** encore committé `ACTIVE`. Le test remet donc le statut à `PENDING_ACTIVATION` après le premier succès — c'est exactement la fenêtre (processus tué après l'HTTP, avant le `save`).

Si le premier `activate_entitlement` marque déjà ACTIVE, le second sans reset ne posterait pas. Le reset de statut est le crash simulé.

- [ ] **Step 2: Lancer**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_openwisp_activation.py -v
```

Expected: PASS dès que Task 3 est là (le handler existant + client suffisent). Si FAIL, corriger le client (username, URLs), pas le handler métier.

Si le test passe du premier coup : c'est le comportement déjà garanti par Tasks 1–3. Le commit reste `test:` — il fige la propriété.

- [ ] **Step 3: Commit**

```bash
git add services/core-api/apps/access/tests/test_openwisp_activation.py
git commit -m "$(cat <<'EOF'
test: replay OpenWISP assignment after an activation crash

EOF
)"
```

---

## Task 5: Réconciliation des entitlements actifs

**Files:**
- Create: `services/core-api/apps/access/tasks.py`
- Create: `services/core-api/apps/access/tests/test_reconcile.py`
- Modify: `services/core-api/config/settings/base.py`

**Interfaces:**
- Consumes: `get_network_provider()`, `Entitlement`, `NetworkError`
- Produces: `reconcile_active_entitlements() -> int` (nombre d'assign réussis) ; tâche Celery `access.reconcile_active_entitlements` ; beat 3600 s

- [ ] **Step 1: Test qui échoue**

```python
import pytest
from django.test import override_settings
from django.utils import timezone

from apps.access.activation import entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.access.tasks import reconcile_active_entitlements
from apps.billing.models import Order


@pytest.fixture(autouse=True)
def reset_provider():
    MockNetworkProvider.reset()
    yield
    MockNetworkProvider.reset()


@pytest.fixture
def paid_order(order):
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


def test_reconcile_is_a_noop_on_the_mock_provider(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    assert reconcile_active_entitlements() == 0
    assert MockNetworkProvider.assignment_calls == 0


@override_settings(NETWORK_PROVIDER="openwisp")
def test_reconcile_reassigns_active_entitlements(paid_order, monkeypatch):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.save(update_fields=["status", "updated_at"])

    calls: list[tuple[str, str]] = []

    class Fake:
        def ensure_user(self, subscriber_ref: str) -> str:
            return subscriber_ref

        def assign_plan(self, subscriber_ref: str, profile_ref: str):
            calls.append((subscriber_ref, profile_ref))

    monkeypatch.setattr("apps.access.tasks.get_network_provider", lambda: Fake())

    assert reconcile_active_entitlements() == 1
    assert calls == [(str(paid_order.citizen_id), paid_order.plan_version.radius_profile_ref)]
```

Filtrer : `status=ACTIVE` et (`ends_at` null ou `ends_at__gt=now`). Un entitlement `PENDING_ACTIVATION` n'est pas repris ici (l'outbox s'en charge).

- [ ] **Step 2: Échec import** puis implémenter

```python
"""Periodic repair of ACTIVE entitlements that drifted on the network."""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError

logger = logging.getLogger(__name__)


def reconcile_active_entitlements() -> int:
    if settings.NETWORK_PROVIDER != "openwisp":
        return 0
    provider = get_network_provider()
    now = timezone.now()
    rows = Entitlement.objects.filter(status=Entitlement.Status.ACTIVE).filter(
        models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)
    )
    repaired = 0
    for entitlement in rows.select_related("plan_version"):
        subscriber_ref = str(entitlement.citizen_id)
        try:
            provider.ensure_user(subscriber_ref)
            provider.assign_plan(subscriber_ref, entitlement.plan_version.radius_profile_ref)
        except NetworkError as error:
            logger.warning("Reconcile skipped %s: %s", entitlement.pk, error)
            continue
        repaired += 1
    return repaired


@shared_task(name="access.reconcile_active_entitlements")
def reconcile_active_entitlements_task() -> int:
    return reconcile_active_entitlements()
```

Importer `django.db.models` pour `Q`. Beat dans `CELERY_BEAT_SCHEDULE` :

```python
"reconcile-active-entitlements": {
    "task": "access.reconcile_active_entitlements",
    "schedule": 3600.0,
},
```

- [ ] **Step 3: Tests verts + commit**

```bash
uv run --directory services/core-api pytest apps/access/tests/test_reconcile.py -v
```

```bash
git add services/core-api/apps/access/tasks.py \
  services/core-api/apps/access/tests/test_reconcile.py \
  services/core-api/config/settings/base.py
git commit -m "$(cat <<'EOF'
feat: reconcile drifted active entitlements against OpenWISP

EOF
)"
```

---

## Task 6: Droits d'organisation de l'extension

**Files:**
- Create: `infra/openwisp-extension/dakar_radius_ext/org_scope.py`
- Create: `infra/openwisp-extension/dakar_radius_ext/permissions.py`
- Create: `infra/openwisp-extension/dakar_radius_ext/tests/test_org_scope.py`
- Create: `infra/openwisp-extension/dakar_radius_ext/tests/__init__.py`
- Modify: `infra/openwisp-extension/dakar_radius_ext/api.py`

**Interfaces:**
- Consumes: `request.user.organizations_dict`, `target.organizations_dict` (clés = ids d'org)
- Produces: `shares_organization(actor_org_ids: set[str], target_org_ids: set[str]) -> bool` ; `SameOrganizationPermission` ; plus de `IsAdminUser`

- [ ] **Step 1: Test pur (pas Django)**

`infra/openwisp-extension/dakar_radius_ext/tests/test_org_scope.py` :

```python
from dakar_radius_ext.org_scope import shares_organization


def test_sharing_one_organization_is_enough():
    assert shares_organization({"a", "b"}, {"b", "c"}) is True


def test_disjoint_organizations_are_denied():
    assert shares_organization({"a"}, {"b"}) is False


def test_empty_sets_are_denied():
    assert shares_organization(set(), {"a"}) is False
    assert shares_organization({"a"}, set()) is False
```

Lancer depuis `infra/openwisp-extension` :

```bash
python -c "import sys; sys.path.insert(0, '.'); import pytest; raise SystemExit(pytest.main(['dakar_radius_ext/tests/test_org_scope.py', '-v']))"
```

Ou : `PYTHONPATH=infra/openwisp-extension python -m pytest infra/openwisp-extension/dakar_radius_ext/tests/test_org_scope.py -v` depuis la racine (pytest du venv core-api convient : pas de Django requis).

Expected RED : import error.

- [ ] **Step 2: `org_scope.py`**

```python
def shares_organization(actor_org_ids: set[str], target_org_ids: set[str]) -> bool:
    return bool(actor_org_ids & target_org_ids)
```

- [ ] **Step 3: Permission DRF et branchement**

`permissions.py` :

```python
from rest_framework.permissions import BasePermission

from .org_scope import shares_organization


class SameOrganizationPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        actor = set(map(str, request.user.organizations_dict.keys()))
        target = set(map(str, obj.organizations_dict.keys()))
        return shares_organization(actor, target)
```

Dans `api.py` : remplacer `IsAdminUser` par `SameOrganizationPermission`. Dans `post`, après `get_user` :

- 404 si `user is None` (inchangé)
- si pas `has_object_permission(request, self, user)` → `Response({"detail": "Forbidden."}, status=403)`

`APIView.has_object_permission` n'est pas appelé tout seul sur un POST sans objet d'URL. **Appeler explicitement** la permission dans `post` :

```python
permission = SameOrganizationPermission()
if not permission.has_object_permission(request, self, user):
    return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
```

Garder `authentication_classes` inchangées. `permission_classes = [SameOrganizationPermission]` pour le 401/403 d'auth.

- [ ] **Step 4: Tests org_scope verts + commit**

```bash
PYTHONPATH=infra/openwisp-extension uv run --directory services/core-api pytest ../../infra/openwisp-extension/dakar_radius_ext/tests/test_org_scope.py -v
```

`testpaths = ["apps"]` va **ignorer** ce fichier si on lance pytest sans chemin. **Toujours passer le chemin du fichier.**

```bash
git add infra/openwisp-extension/dakar_radius_ext/org_scope.py \
  infra/openwisp-extension/dakar_radius_ext/permissions.py \
  infra/openwisp-extension/dakar_radius_ext/api.py \
  infra/openwisp-extension/dakar_radius_ext/tests/
git commit -m "$(cat <<'EOF'
fix: scope OpenWISP extension actions to the caller's organizations

EOF
)"
```

---

## Task 7: Overlay Compose et `make test-openwisp`

**Files:**
- Create: `infra/openwisp/.env.example`
- Create: `infra/openwisp/seed.py`
- Create: `infra/openwisp/README.md`
- Create: `infra/openwisp-extension/dakar_radius_ext/tests/test_assign_in_place.py`
- Modify: `Makefile`
- Modify: `.gitignore`
- Modify: `infra/openwisp-extension/README.md`

**Interfaces:**
- Produces: clone gitignore `infra/docker-openwisp` tag `25.10.4` ; cibles `openwisp-up`, `openwisp-down`, `test-openwisp`

Cette tâche a des fichiers de config : TDD allégé (exception « configuration files »). Les tests in-place **sont** écrits avant d'être exécutés dans le conteneur.

- [ ] **Step 1: `.gitignore`**

```
infra/docker-openwisp/
services/core-api/celerybeat-schedule
services/core-api/celerybeat-schedule-shm
services/core-api/celerybeat-schedule-wal
```

- [ ] **Step 2: `infra/openwisp/.env.example`**

S'aligner sur [Settings 25.10](https://openwisp.io/docs/25.10/docker/user/settings.html). Minimum :

```
OPENWISP_RADIUS=True
NGINX_PORT=8002
DASHBOARD_DOMAIN=localhost
API_DOMAIN=localhost
VPN_DOMAIN=localhost
SSL_CERT_MODE=False
```

Compléter avec les variables **obligatoires** du `.env` amont (mots de passe fictifs `dakar-openwisp-lab`, jamais un secret réel). Copier depuis le `.env.sample` du tag 25.10.4 au moment du clone, puis écraser `NGINX_PORT=8002`.

- [ ] **Step 3: Makefile**

```makefile
OPENWISP_DIR := infra/docker-openwisp
OPENWISP_TAG := 25.10.4
OPENWISP_COMPOSE := docker compose -f $(OPENWISP_DIR)/docker-compose.yml --env-file infra/openwisp/.env

openwisp-up: ## Instance OpenWISP jetable (hors make up)
	@if [ ! -d "$(OPENWISP_DIR)/.git" ]; then \
	  git clone --depth 1 --branch $(OPENWISP_TAG) https://github.com/openwisp/docker-openwisp.git $(OPENWISP_DIR); \
	fi
	@test -f infra/openwisp/.env || cp infra/openwisp/.env.example infra/openwisp/.env
	@mkdir -p $(OPENWISP_DIR)/customization/configuration/django
	@cp infra/openwisp-extension/custom_django_settings.py \
	    infra/openwisp-extension/custom_urls.py \
	    $(OPENWISP_DIR)/customization/configuration/django/
	@cp -R infra/openwisp-extension/dakar_radius_ext \
	    $(OPENWISP_DIR)/customization/configuration/django/
	@cp infra/openwisp/seed.py $(OPENWISP_DIR)/customization/configuration/django/
	$(OPENWISP_COMPOSE) up -d
	@echo "OpenWISP lab: http://localhost:8002"

openwisp-down: ## Arrête l'instance OpenWISP jetable
	@if [ -d "$(OPENWISP_DIR)" ]; then $(OPENWISP_COMPOSE) down; fi

test-openwisp: openwisp-up ## Tests d'extension + smoke HTTP (pas CI)
	$(OPENWISP_COMPOSE) exec -T api python manage.py test openwisp.configuration.dakar_radius_ext
```

Si le module Django dans l'image s'appelle autrement, ajuster après le premier `up` (le README du spike : `openwisp.configuration.dakar_radius_ext`). Vérifier le tag d'image : `docker compose images` contient `:25.10.4`.

- [ ] **Step 4: `seed.py`**

Script Django exécutable via `python manage.py shell < seed.py` ou `exec api python /opt/openwisp/openwisp/configuration/seed.py` si le chemin le permet. Créer de façon idempotente :

- Organization name `Ville de Dakar`, slug `ville-de-dakar`, `coa_enabled=True` (via `OrganizationRadiusSettings`, créé s'il manque — le spike H6)
- Groupes : `dakar-demo-gratuit`, `dakar-1h`, `dakar-demo-1h`, `dakar-demo-jour`, `dakar-demo-semaine`
- User service `dakar-service` staff, membre de cette org uniquement, token imprimé
- `Nas` name `0.0.0.0/0` secret `lab-nas-secret` (fictif)

Documenter dans `infra/openwisp/README.md` : recopier le token vers `.env` racine `OPENWISP_API_TOKEN`, l'UUID d'org vers `OPENWISP_ORGANIZATION_ID`, URL `http://localhost:8002`, **laisser** `NETWORK_PROVIDER=mock` sauf essai manuel.

- [ ] **Step 5: Test in-place dans l'extension**

Créer `infra/openwisp-extension/dakar_radius_ext/tests/test_assign_in_place.py` :

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from openwisp_radius.utils import load_model
from openwisp_users.models import Organization, OrganizationUser
from rest_framework.test import APIClient

from dakar_radius_ext.services import assign_group

RadiusGroup = load_model("RadiusGroup")
RadiusUserGroup = load_model("RadiusUserGroup")
User = get_user_model()


class AssignGroupInPlaceTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Ville", slug="ville-test")
        self.other_org = Organization.objects.create(name="Autre", slug="autre-test")
        self.group_a = RadiusGroup.objects.create(
            organization=self.org, name="plan-a"
        )
        self.group_b = RadiusGroup.objects.create(
            organization=self.org, name="plan-b"
        )
        self.user = User.objects.create_user(username="citizen-1", password="x")
        OrganizationUser.objects.create(user=self.user, organization=self.org)
        self.foreign = User.objects.create_user(username="foreign-1", password="x")
        OrganizationUser.objects.create(user=self.foreign, organization=self.other_org)
        self.actor = User.objects.create_user(username="dakar-service", password="x")
        OrganizationUser.objects.create(
            user=self.actor, organization=self.org, is_admin=True
        )

    def test_changing_group_keeps_the_same_membership_row(self):
        first, changed = assign_group(self.user, "plan-a")
        self.assertTrue(changed)
        second, changed = assign_group(self.user, "plan-b")
        self.assertTrue(changed)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.group_id, self.group_b.pk)
        self.assertEqual(RadiusUserGroup.objects.filter(user=self.user).count(), 1)

    def test_same_group_is_a_noop(self):
        first, _ = assign_group(self.user, "plan-a")
        second, changed = assign_group(self.user, "plan-a")
        self.assertFalse(changed)
        self.assertEqual(first.pk, second.pk)

    def test_assign_group_api_forbids_a_foreign_organization(self):
        client = APIClient()
        client.force_authenticate(user=self.actor)
        response = client.post(
            "/api/v1/dakar/radius/assign-group/",
            {"username": "foreign-1", "group_name": "plan-a"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
```

Ces tests ne tournent que dans l'image (`make test-openwisp`). Si `RadiusGroup` exige d'autres champs au runtime, les ajouter sans changer l'assertion sur la stabilité du `pk`.

- [ ] **Step 6: README extension** — retirer « PROOF OF CONCEPT / IsAdminUser » ; noter 25.10.4 ; pointer `make test-openwisp`.

- [ ] **Step 7: Commit** (même si `make test-openwisp` n'a pas été lancé dans cet environnement : le README dit de le lancer). Si Docker est disponible, lancer `make test-openwisp` avant le commit.

```bash
git add Makefile .gitignore infra/openwisp infra/openwisp-extension
git commit -m "$(cat <<'EOF'
feat: add a disposable OpenWISP lab overlay pinned to 25.10.4

EOF
)"
```

---

## Task 8: Sentinelles production, env, backlog

**Files:**
- Create: `services/core-api/config/openwisp_guard.py`
- Create: `services/core-api/apps/core/tests/test_openwisp_guard.py`
- Modify: `services/core-api/config/settings/production.py`
- Modify: `.env.example`
- Modify: `docs/phase0/03-backlog.md`

**Interfaces:**
- Produces: `assert_openwisp_ready(network_provider: str, base_url: str, token: str) -> None` ; `ImproperlyConfigured` si provider `openwisp` et URL sentinelle ou jeton `change-me` / vide

- [ ] **Step 1: Test qui échoue**

Créer `services/core-api/apps/core/tests/test_openwisp_guard.py` :

```python
import pytest
from django.core.exceptions import ImproperlyConfigured

from config.openwisp_guard import assert_openwisp_ready


def test_mock_provider_skips_the_guard():
    assert_openwisp_ready("mock", "https://openwisp.example.invalid", "change-me")


def test_openwisp_with_sentinels_is_rejected():
    with pytest.raises(ImproperlyConfigured):
        assert_openwisp_ready("openwisp", "https://openwisp.example.invalid", "change-me")


def test_openwisp_with_real_values_passes():
    assert_openwisp_ready("openwisp", "https://radius.ville.dakar.sn", "not-a-sentinel")
```

```bash
uv run --directory services/core-api pytest apps/core/tests/test_openwisp_guard.py -v
```

Expected: FAIL — `ModuleNotFoundError: config.openwisp_guard`.

- [ ] **Step 2: Implémenter la garde et l'appeler en production**

Créer `services/core-api/config/openwisp_guard.py` :

```python
from django.core.exceptions import ImproperlyConfigured

INSECURE_OPENWISP_URL_MARK = "example.invalid"
INSECURE_OPENWISP_TOKENS = frozenset({"", "change-me"})


def assert_openwisp_ready(network_provider: str, base_url: str, token: str) -> None:
    if network_provider != "openwisp":
        return
    if INSECURE_OPENWISP_URL_MARK in base_url or token in INSECURE_OPENWISP_TOKENS:
        raise ImproperlyConfigured(
            "OPENWISP_BASE_URL and OPENWISP_API_TOKEN must be set in production."
        )
```

Dans `production.py`, après les autres gardes :

```python
from config.openwisp_guard import assert_openwisp_ready
from config.settings.base import NETWORK_PROVIDER, OPENWISP_API_TOKEN, OPENWISP_BASE_URL

assert_openwisp_ready(NETWORK_PROVIDER, OPENWISP_BASE_URL, OPENWISP_API_TOKEN)
```

`.env.example` : ajouter `OPENWISP_ORGANIZATION_SLUG=ville-de-dakar` sous les variables OpenWISP existantes. Ne pas changer `NETWORK_PROVIDER=mock`.

Backlog : cocher DW-P5-00, DW-P5-02, DW-P5-03 lite. DW-P5-01, DW-P5-04 (entrepôt), DW-P5-05 **restent ouverts** avec une note « reporté, hors itération adapter-docker ».

- [ ] **Step 3: Tests verts puis toute la suite**

```bash
uv run --directory services/core-api pytest apps/core/tests/test_openwisp_guard.py -v
uv run --directory services/core-api ruff check .
uv run --directory services/core-api mypy apps/access
uv run --directory services/core-api pytest -q
```

Expected: toute la suite existante verte.

- [ ] **Commit**

```bash
git add services/core-api/config/openwisp_guard.py \
  services/core-api/config/settings/production.py \
  services/core-api/apps/core/tests/test_openwisp_guard.py \
  .env.example docs/phase0/03-backlog.md
git commit -m "$(cat <<'EOF'
chore: refuse OpenWISP sentinels in production and close phase 5 backlog notes

EOF
)"
```

---

## Couverture spec → tâches

| Spec | Tâche |
|---|---|
| §1–3 architecture, mock défaut | 1 |
| §4 `assign_plan` + `changed` | 1 |
| §4.2–4.3 retries, circuit, 4xx hors circuit | 2 |
| §4 `ensure_user`, `disconnect`, `read_usage`, `healthcheck` | 3 |
| §1.1 / §8.4 crash window | 4 |
| §7 réconciliation | 5 |
| §5 droits d'org | 6 |
| §6 overlay, pin 25.10.4, seed, Makefile | 7 |
| §9 sentinelles, §12 critères de fin, backlog | 8 |
| Hors scope Ansible / borne / accounting local | aucune (volontaire) |

## Décisions verrouillées dans ce plan (jugement demandé)

1. L'extension expose `changed` pour distinguer no-op et CoA, plutôt qu'un GET du groupe courant.
2. Une défaillance circuit = un appel métier épuisé, pas une tentative HTTP.
3. Overlay = clone gitignoré de `docker-openwisp` @ `25.10.4`, pas un compose réécrit.
4. Garde production extraite dans `assert_openwisp_ready` pour rester testable.
