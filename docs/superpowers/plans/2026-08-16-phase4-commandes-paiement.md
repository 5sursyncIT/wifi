# Phase 4 — Commandes, paiement mock et activation garantie — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un citoyen achète une offre payante, paie par push mobile, et son droit d'accès est activé exactement une fois — même si le réseau est indisponible au moment de la confirmation.

**Architecture:** Le webhook validé committe en une seule transaction la commande payée, le paiement, le droit en attente et un message d'outbox. Un worker draine ensuite l'outbox et appelle le réseau avec ré-essais. Rien de faillible n'est appelé avant le commit ; rien de committé n'est perdu si l'appel échoue. Deux garanties d'unicité sont portées par la base (index unique partiel sur les webhooks traités, `OneToOne` entre commande et droit) plutôt que par du code sujet aux courses.

**Tech Stack:** Django 5 + DRF, drf-spectacular, PostgreSQL 16, Celery + Redis, pytest/pytest-django, uv, Astro 7 pour le portail, Playwright pour le bout en bout.

**Spec:** [`docs/superpowers/specs/2026-08-16-phase4-commandes-paiement-design.md`](../specs/2026-08-16-phase4-commandes-paiement-design.md)

## Global Constraints

- **Langue** (ADR-0003) : identifiants, code, commentaires techniques et messages de commit en **anglais** ; documentation (`docs/`) en **français** ; textes d'erreur destinés aux usagers en **français**.
- **Commits** : Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- **Montants** : entiers en XOF, jamais de décimaux (§1 règle 8).
- **Identifiants** : UUID publics, horodatages stockés en UTC (§9). Hériter de `apps.core.models.UUIDTimeStampedModel`.
- **Ruff** : `line-length = 100`, `target-version = "py313"`, règles `E, F, I, UP, B, DJ, S, C4, RUF`. La règle `S` est bandit : un faux secret dans un test demande `# noqa: S105` ou `# noqa: S106`.
- **Mypy** : `uv run mypy .` doit rester sans erreur.
- **Tests** : pytest, `DJANGO_SETTINGS_MODULE = config.settings.test`, `testpaths = ["apps"]`. L'accès base se demande par la fixture `db` (voir `conftest.py` racine) ou `@pytest.mark.django_db`.
- **Celery en test** : `CELERY_TASK_ALWAYS_EAGER = True`. **Attention** : les rappels `transaction.on_commit` ne se déclenchent PAS sous la fixture `db` ordinaire. Tout test qui dépend du chemin rapide doit utiliser la fixture pytest-django `django_capture_on_commit_callbacks(execute=True)`.
- **Contrat OpenAPI** : le job CI « Contrat OpenAPI à jour » échoue sur tout écart. Après toute modification d'endpoint, régénérer et committer :
  ```bash
  ENVIRONMENT=local uv run --directory services/core-api python manage.py spectacular \
    --format openapi --file ../../docs/api/openapi.yaml
  pnpm api-client:generate
  ```
- **Budget portail** (§12.1) : 150 Ko gzip, contrôlé et bloquant en CI. Marge actuelle : 146 Ko.
- **Répertoire de travail** : les commandes `uv` s'exécutent depuis `services/core-api`, les commandes `pnpm` depuis la racine du dépôt.

---

## Structure des fichiers

**Créés**

| Fichier | Responsabilité |
|---|---|
| `services/core-api/apps/core/outbox.py` | Registre de handlers, `enqueue()`, `drain()` |
| `services/core-api/apps/core/tasks.py` | Tâche Celery `drain_outbox` |
| `services/core-api/apps/core/tests/test_outbox.py` | Ré-essais, backoff, épuisement |
| `services/core-api/apps/billing/__init__.py` | |
| `services/core-api/apps/billing/apps.py` | `BillingConfig` |
| `services/core-api/apps/billing/models.py` | `Order`, `Payment`, `WebhookEvent` |
| `services/core-api/apps/billing/orders.py` | Création idempotente, transitions d'état |
| `services/core-api/apps/billing/webhooks.py` | Vérification, historique, traitement unique |
| `services/core-api/apps/billing/tasks.py` | Expiration, réconciliation |
| `services/core-api/apps/billing/serializers.py` | |
| `services/core-api/apps/billing/views.py` | Endpoints commandes + webhook |
| `services/core-api/apps/billing/urls.py` | |
| `services/core-api/apps/billing/admin.py` | |
| `services/core-api/apps/billing/providers/base.py` | Contrat `PaymentProvider` |
| `services/core-api/apps/billing/providers/mock.py` | `MockPaymentProvider` + fabrique de webhooks signés |
| `services/core-api/apps/billing/providers/__init__.py` | `get_payment_provider()` |
| `services/core-api/apps/billing/tests/conftest.py` | Fixtures `citizen`, `order` |
| `services/core-api/apps/billing/tests/test_*.py` | Voir tâches 2, 3, 4, 6, 7, 8 |
| `services/core-api/apps/access/activation.py` | Handler `entitlement.activate` |
| `services/core-api/apps/access/tests/test_activation.py` | Idempotence de l'activation |
| `apps/captive-portal/src/pages/achat.astro` | Parcours d'achat |
| `apps/captive-portal/e2e/purchase.spec.ts` | Bout en bout §16.2 |

**Modifiés**

| Fichier | Modification |
|---|---|
| `services/core-api/apps/core/models.py` | `+ OutboxMessage` |
| `services/core-api/apps/access/models.py` | `+ Entitlement.order` (OneToOne, nullable) |
| `services/core-api/config/settings/base.py` | `apps.billing` dans `INSTALLED_APPS`, réglages §11 de la spec, `CELERY_BEAT_SCHEDULE` |
| `services/core-api/config/settings/production.py` | Refus de la sentinelle de secret webhook |
| `services/core-api/config/urls.py` | `include("apps.billing.urls")` |
| `services/core-api/apps/core/management/commands/seed_demo_data.py` | Offre payante de démonstration |
| `.env.example` | Nouvelles variables |
| `docs/api/openapi.yaml`, `packages/api-client/src/schema.d.ts` | Régénérés |
| `packages/api-client/src/index.ts` | Appels commandes |
| `docs/phase0/03-backlog.md` | Phase 4 cochée |

---

## Task 1: Outbox transactionnelle

**Files:**
- Create: `services/core-api/apps/core/outbox.py`
- Create: `services/core-api/apps/core/tasks.py`
- Create: `services/core-api/apps/core/tests/test_outbox.py`
- Modify: `services/core-api/apps/core/models.py`
- Modify: `services/core-api/config/settings/base.py`
- Create: `services/core-api/apps/core/migrations/0002_outboxmessage.py` (généré)

**Interfaces:**
- Consumes: `apps.core.models.UUIDTimeStampedModel`
- Produces:
  - `apps.core.outbox.register(topic: str) -> Callable[[Handler], Handler]` — décorateur
  - `apps.core.outbox.enqueue(topic: str, payload: dict) -> OutboxMessage`
  - `apps.core.outbox.drain(limit: int = 20) -> int` — rend le nombre de messages traités
  - `apps.core.outbox.PermanentHandlerError`
  - `apps.core.models.OutboxMessage` avec `Status.PENDING|PROCESSING|DONE|FAILED`
  - `apps.core.tasks.drain_outbox` — tâche Celery

- [ ] **Step 1: Ajouter les réglages**

Dans `services/core-api/config/settings/base.py`, après le bloc `# --- Adapters` :

```python
# --- Outbox (cahier des charges §11.2) --------------------------------------

# A message that keeps failing must end up in front of an operator rather than
# retrying forever in silence.
OUTBOX_MAX_ATTEMPTS = env.int("OUTBOX_MAX_ATTEMPTS", default=10)
OUTBOX_BACKOFF_BASE_SECONDS = env.int("OUTBOX_BACKOFF_BASE_SECONDS", default=5)
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `services/core-api/apps/core/tests/test_outbox.py` :

```python
"""Transactional outbox: a failing outside world delays a message, never loses it (§11.2)."""

import pytest
from django.utils import timezone

from apps.core import outbox
from apps.core.models import OutboxMessage

CALLS: list[dict] = []


@pytest.fixture(autouse=True)
def registry():
    CALLS.clear()

    @outbox.register("test.ok")
    def _ok(payload):
        CALLS.append(payload)

    @outbox.register("test.flaky")
    def _flaky(payload):
        CALLS.append(payload)
        raise RuntimeError("le contrôleur est indisponible")

    @outbox.register("test.permanent")
    def _permanent(payload):
        CALLS.append(payload)
        raise outbox.PermanentHandlerError("profil inconnu")

    yield
    for topic in ("test.ok", "test.flaky", "test.permanent"):
        outbox._HANDLERS.pop(topic, None)


def test_enqueue_writes_a_pending_message(db):
    message = outbox.enqueue("test.ok", {"id": "abc"})

    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 0


def test_enqueue_refuses_an_unregistered_topic(db):
    with pytest.raises(ValueError, match="unknown outbox topic"):
        outbox.enqueue("test.nope", {})


def test_drain_runs_the_handler_and_marks_the_message_done(db):
    outbox.enqueue("test.ok", {"id": "abc"})

    assert outbox.drain() == 1
    assert CALLS == [{"id": "abc"}]
    assert OutboxMessage.objects.get().status == OutboxMessage.Status.DONE


def test_a_failure_reschedules_instead_of_losing_the_message(db):
    outbox.enqueue("test.flaky", {"id": "abc"})

    assert outbox.drain() == 0

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 1
    assert message.available_at > timezone.now()
    assert "indisponible" in message.last_error


def test_exhausting_the_attempts_surfaces_the_message_to_an_operator(db, settings):
    settings.OUTBOX_MAX_ATTEMPTS = 2
    outbox.enqueue("test.flaky", {"id": "abc"})

    for _ in range(2):
        OutboxMessage.objects.update(available_at=timezone.now())
        outbox.drain()

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.FAILED
    assert message.attempts == 2


def test_a_permanent_error_does_not_retry(db):
    outbox.enqueue("test.permanent", {"id": "abc"})

    outbox.drain()

    message = OutboxMessage.objects.get()
    assert message.status == OutboxMessage.Status.FAILED
    assert message.attempts == 1


def test_a_message_scheduled_for_later_is_not_picked_up(db):
    outbox.enqueue("test.ok", {"id": "abc"})
    OutboxMessage.objects.update(available_at=timezone.now() + timezone.timedelta(minutes=5))

    assert outbox.drain() == 0
    assert CALLS == []
```

- [ ] **Step 3: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/core/tests/test_outbox.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.core.outbox'`.

- [ ] **Step 4: Ajouter le modèle**

Dans `services/core-api/apps/core/models.py`, après `UUIDTimeStampedModel` :

```python
class OutboxMessage(UUIDTimeStampedModel):
    """Work that must happen outside the transaction that justified it (§11.2).

    Written in the same transaction as the state it follows from, so a crash between
    the two is impossible. The drain then talks to the outside world, where a failure
    only delays the message.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PROCESSING = "processing", "En cours"
        DONE = "done", "Traité"
        FAILED = "failed", "Échec définitif"

    topic = models.CharField(max_length=60)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["available_at"]
        indexes = [models.Index(fields=["status", "available_at"])]
        verbose_name = "message d'outbox"
        verbose_name_plural = "messages d'outbox"

    def __str__(self):
        return f"{self.topic} ({self.get_status_display()})"
```

Ajouter en tête du fichier : `from django.utils import timezone`.

- [ ] **Step 5: Écrire l'outbox**

Créer `services/core-api/apps/core/outbox.py` :

```python
"""Transactional outbox (cahier des charges §11.2).

The rule this exists to enforce: nothing fallible is called before the commit, and
nothing committed is lost when that call fails. A message is written in the same
transaction as the state that justifies it; the drain then calls the outside world.
"""

import logging
from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.models import OutboxMessage

logger = logging.getLogger(__name__)

Handler = Callable[[dict], None]
_HANDLERS: dict[str, Handler] = {}

MAX_BACKOFF_SECONDS = 3600


class PermanentHandlerError(Exception):
    """Retrying cannot help. The message goes to `failed`, in front of an operator."""


def register(topic: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        _HANDLERS[topic] = handler
        return handler

    return decorator


def enqueue(topic: str, payload: dict) -> OutboxMessage:
    # Refused early: a topic nobody handles would sit pending forever, and the caller
    # would believe the work was scheduled.
    if topic not in _HANDLERS:
        raise ValueError(f"Unknown outbox topic {topic!r}.")
    return OutboxMessage.objects.create(topic=topic, payload=payload)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(settings.OUTBOX_BACKOFF_BASE_SECONDS * 2 ** (attempts - 1),
                                 MAX_BACKOFF_SECONDS))


def _claim(limit: int) -> list[OutboxMessage]:
    """Take ownership of a batch in a short transaction, before any slow call.

    `skip_locked` lets several workers draw from the queue at once without blocking
    each other and without two of them taking the same row.
    """
    now = timezone.now()
    with transaction.atomic():
        claimed = list(
            OutboxMessage.objects.select_for_update(skip_locked=True)
            .filter(status=OutboxMessage.Status.PENDING, available_at__lte=now)
            .order_by("available_at")[:limit]
        )
        for message in claimed:
            message.status = OutboxMessage.Status.PROCESSING
            message.attempts += 1
            message.save(update_fields=["status", "attempts", "updated_at"])
    return claimed


def _reschedule(message: OutboxMessage, error: Exception) -> None:
    if message.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
        message.status = OutboxMessage.Status.FAILED
        logger.error("Outbox %s exhausted its retries: %s", message.topic, error)
    else:
        message.status = OutboxMessage.Status.PENDING
        message.available_at = timezone.now() + _backoff(message.attempts)
    message.last_error = str(error)[:300]
    message.save(update_fields=["status", "available_at", "last_error", "updated_at"])


def drain(limit: int = 20) -> int:
    """Run every due message. Returns how many succeeded."""
    succeeded = 0
    for message in _claim(limit):
        handler = _HANDLERS.get(message.topic)
        if handler is None:
            message.status = OutboxMessage.Status.FAILED
            message.last_error = f"No handler registered for {message.topic!r}."
            message.save(update_fields=["status", "last_error", "updated_at"])
            continue

        try:
            handler(message.payload)
        except PermanentHandlerError as error:
            message.status = OutboxMessage.Status.FAILED
            message.last_error = str(error)[:300]
            message.save(update_fields=["status", "last_error", "updated_at"])
            logger.error("Outbox %s failed permanently: %s", message.topic, error)
        except Exception as error:  # noqa: BLE001 - any failure must delay, never lose
            _reschedule(message, error)
        else:
            message.status = OutboxMessage.Status.DONE
            message.last_error = ""
            message.save(update_fields=["status", "last_error", "updated_at"])
            succeeded += 1
    return succeeded
```

- [ ] **Step 6: Écrire la tâche Celery**

Créer `services/core-api/apps/core/tasks.py` :

```python
"""Scheduled work owned by the core app."""

from celery import shared_task

from apps.core.outbox import drain


@shared_task(name="core.drain_outbox")
def drain_outbox() -> int:
    return drain()
```

- [ ] **Step 7: Générer la migration et lancer les tests**

```bash
cd services/core-api
uv run python manage.py makemigrations core
uv run pytest apps/core/tests/test_outbox.py -v
```
Attendu : 7 tests PASS.

Si `test_enqueue_refuses_an_unregistered_topic` échoue sur le message, aligner la casse : le test cherche `unknown outbox topic` sans tenir compte de la casse via `pytest.raises(match=...)`, qui est sensible à la casse — corriger le test en `match="Unknown outbox topic"`.

- [ ] **Step 8: Vérifier lint et types, puis committer**

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy .
cd ../.. && git add -A
git commit -m "feat: transactional outbox so a network outage delays work instead of losing it"
```

---

## Task 2: App billing, modèles et garanties d'unicité

**Files:**
- Create: `services/core-api/apps/billing/{__init__.py,apps.py,models.py,admin.py}`
- Create: `services/core-api/apps/billing/tests/{__init__.py,conftest.py,test_models.py}`
- Modify: `services/core-api/apps/access/models.py`
- Modify: `services/core-api/config/settings/base.py`
- Create: migrations `billing/0001_initial.py` et `access/000X_entitlement_order.py`

**Interfaces:**
- Consumes: `apps.catalog.models.PlanVersion`, `apps.citizens.models.Citizen`, `apps.network.models.Zone`, `apps.core.models.UUIDTimeStampedModel`
- Produces:
  - `apps.billing.models.Order` avec `Status.DRAFT|PENDING|REQUIRES_ACTION|PAID|FAILED|EXPIRED|CANCELLED|REFUNDED|PARTIALLY_REFUNDED`
  - `apps.billing.models.Payment` avec `Status.INITIATED|SUCCEEDED|REFUSED|EXPIRED`
  - `apps.billing.models.WebhookEvent` avec `Outcome.PROCESSED|DUPLICATE|BAD_SIGNATURE|AMOUNT_MISMATCH|UNKNOWN_ORDER|IGNORED`
  - `apps.access.models.Entitlement.order` — `OneToOneField(Order, null=True, related_name="entitlement")`
  - Fixtures `citizen` et `order` dans `apps/billing/tests/conftest.py`

- [ ] **Step 1: Créer l'app et l'enregistrer**

```bash
cd services/core-api && uv run python manage.py startapp billing apps/billing
```

Remplacer `services/core-api/apps/billing/apps.py` par :

```python
from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.billing"
    verbose_name = "Facturation — commandes, paiements, webhooks"
```

Supprimer `apps/billing/views.py` et `apps/billing/tests.py` créés par `startapp` (ils seront recréés proprement), puis créer `apps/billing/tests/__init__.py`.

Dans `config/settings/base.py`, ajouter `"apps.billing",` à la fin d'`INSTALLED_APPS`.

- [ ] **Step 2: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/conftest.py` :

```python
from django.utils import timezone

import pytest

from apps.billing.models import Order
from apps.citizens.models import Citizen


@pytest.fixture
def citizen(db):
    return Citizen.objects.create(
        phone_e164="+221771234567", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )


@pytest.fixture
def order(citizen, zone, plan_version):
    return Order.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-1",
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )
```

Créer `services/core-api/apps/billing/tests/test_models.py` :

```python
"""What the database itself guarantees about the financial chain (§8.5, §17 no 5)."""

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access.models import Entitlement
from apps.billing.models import Order, WebhookEvent


def test_an_order_number_is_assigned_and_unique(order, citizen, zone, plan_version):
    second = Order.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-2",
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    assert order.order_number
    assert order.order_number != second.order_number


def test_the_same_idempotency_key_cannot_create_two_orders(order, citizen, zone, plan_version):
    with pytest.raises(IntegrityError), transaction.atomic():
        Order.objects.create(
            citizen=citizen,
            plan_version=plan_version,
            zone=zone,
            amount_xof=plan_version.price_xof,
            currency="XOF",
            idempotency_key=order.idempotency_key,
            expires_at=timezone.now() + timezone.timedelta(minutes=30),
        )


def test_only_one_delivery_per_event_may_be_processed(order):
    WebhookEvent.objects.create(
        provider="mock",
        external_event_id="EVT-1",
        order=order,
        signature_valid=True,
        outcome=WebhookEvent.Outcome.PROCESSED,
    )

    # A duplicate delivery may be recorded — the history must be complete (§8.5) —
    # but never as a second processed one.
    WebhookEvent.objects.create(
        provider="mock",
        external_event_id="EVT-1",
        order=order,
        signature_valid=True,
        outcome=WebhookEvent.Outcome.DUPLICATE,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        WebhookEvent.objects.create(
            provider="mock",
            external_event_id="EVT-1",
            order=order,
            signature_valid=True,
            outcome=WebhookEvent.Outcome.PROCESSED,
        )


def test_an_order_can_carry_only_one_entitlement(order, plan_version, citizen, zone):
    Entitlement.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        order=order,
        source=Entitlement.Source.PURCHASE,
        starts_at=timezone.now(),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Entitlement.objects.create(
            citizen=citizen,
            plan_version=plan_version,
            zone=zone,
            order=order,
            source=Entitlement.Source.PURCHASE,
            starts_at=timezone.now(),
        )
```

- [ ] **Step 3: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_models.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.billing.models'` ou erreur d'import sur `Order`.

- [ ] **Step 4: Écrire les modèles**

Créer `services/core-api/apps/billing/models.py` :

```python
"""Orders, payments and webhook deliveries (cahier des charges §8.5, §9).

Amounts are integers in XOF and are frozen on the order at creation: a later change to
the offer must never alter a purchase already made (§8.3).
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import PlanVersion
from apps.citizens.models import Citizen
from apps.core.models import UUIDTimeStampedModel
from apps.network.models import Zone


class Order(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Brouillon"
        PENDING = "pending", "En attente de paiement"
        REQUIRES_ACTION = "requires_action", "Action requise"
        PAID = "paid", "Payée"
        FAILED = "failed", "Échouée"
        EXPIRED = "expired", "Expirée"
        CANCELLED = "cancelled", "Annulée"
        # Declared from the start, wired in phase 6: migrating a status field on
        # financial rows costs more than carrying two inert values.
        REFUNDED = "refunded", "Remboursée"
        PARTIALLY_REFUNDED = "partially_refunded", "Partiellement remboursée"

    order_number = models.CharField(max_length=24, unique=True, editable=False)
    citizen = models.ForeignKey(Citizen, on_delete=models.PROTECT, related_name="orders")
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.PROTECT, related_name="orders")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="orders")

    amount_xof = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    idempotency_key = models.CharField(max_length=100)
    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)

    # Set when a confirmation lands after the order expired (§8.5). The citizen paid,
    # so the right is granted, and the discrepancy is flagged for reconciliation.
    reactivated_after_expiry = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["citizen", "idempotency_key"], name="one_order_per_idempotency_key"
            )
        ]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["citizen", "-created_at"]),
        ]
        verbose_name = "commande"
        verbose_name_plural = "commandes"

    def __str__(self):
        return f"{self.order_number} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = _next_order_number()
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status in (self.Status.DRAFT, self.Status.PENDING, self.Status.REQUIRES_ACTION)


def _next_order_number() -> str:
    """`DW-YYYYMM-NNNNNN`, the sequential part coming from a PostgreSQL sequence.

    A COUNT would let two simultaneous purchases draw the same number.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('billing_order_number_seq')")
        value = cursor.fetchone()[0]
    return f"DW-{timezone.now():%Y%m}-{value:06d}"


class Payment(UUIDTimeStampedModel):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initié"
        SUCCEEDED = "succeeded", "Réussi"
        REFUSED = "refused", "Refusé"
        EXPIRED = "expired", "Expiré"

    class Mode(models.TextChoices):
        PUSH = "push", "Push mobile"
        REDIRECT = "redirect", "Redirection"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=40)
    mode = models.CharField(max_length=10, choices=Mode.choices)
    external_reference = models.CharField(max_length=120, db_index=True)
    amount_xof = models.PositiveIntegerField()
    fees_xof = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.INITIATED)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "paiement"
        verbose_name_plural = "paiements"

    def __str__(self):
        return f"{self.provider} {self.external_reference} ({self.get_status_display()})"


class WebhookEvent(UUIDTimeStampedModel):
    """One row per delivery — duplicates and rejections included (§8.5).

    The partial unique index is what makes a duplicate harmless: the history stays
    complete, but only one delivery per event may ever carry `processed`.
    """

    class Outcome(models.TextChoices):
        PROCESSED = "processed", "Traité"
        DUPLICATE = "duplicate", "Doublon"
        BAD_SIGNATURE = "bad_signature", "Signature invalide"
        AMOUNT_MISMATCH = "amount_mismatch", "Montant divergent"
        UNKNOWN_ORDER = "unknown_order", "Commande inconnue"
        IGNORED = "ignored", "Ignoré"

    provider = models.CharField(max_length=40)
    external_event_id = models.CharField(max_length=120)
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, null=True, blank=True, related_name="webhook_events"
    )
    signature_valid = models.BooleanField(default=False)
    outcome = models.CharField(max_length=20, choices=Outcome.choices)

    # Minimised projection, never the raw body: §9 forbids keeping a full copy that may
    # carry secrets when a reduced one is enough. The digest still lets an investigation
    # match a body against a recorded delivery.
    payload = models.JSONField(default=dict)
    body_sha256 = models.CharField(max_length=64)

    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"],
                condition=Q(outcome="processed"),
                name="one_processed_delivery_per_event",
            )
        ]
        indexes = [models.Index(fields=["provider", "external_event_id"])]
        verbose_name = "événement de webhook"
        verbose_name_plural = "événements de webhook"

    def __str__(self):
        return f"{self.provider} {self.external_event_id} ({self.get_outcome_display()})"
```

- [ ] **Step 5: Ajouter le lien commande → droit**

Dans `services/core-api/apps/access/models.py`, dans la classe `Entitlement`, après le champ `zone` :

```python
    # One entitlement per order, enforced by the database: "activation du forfait une
    # seule fois" (§8.5) must not depend on application logic getting concurrency right.
    order = models.OneToOneField(
        "billing.Order",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entitlement",
    )
```

La référence est une chaîne (`"billing.Order"`) pour éviter un import circulaire entre `access` et `billing`.

- [ ] **Step 6: Générer les migrations et ajouter la séquence**

```bash
cd services/core-api
uv run python manage.py makemigrations billing access
```

Éditer la migration `billing/0001_initial.py` : ajouter en fin de liste `operations` la création de la séquence utilisée par `_next_order_number` :

```python
        migrations.RunSQL(
            sql="CREATE SEQUENCE IF NOT EXISTS billing_order_number_seq START 1;",
            reverse_sql="DROP SEQUENCE IF EXISTS billing_order_number_seq;",
        ),
```

- [ ] **Step 7: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_models.py -v
```
Attendu : 4 tests PASS.

- [ ] **Step 8: Enregistrer dans l'administration, vérifier, committer**

Créer `services/core-api/apps/billing/admin.py` :

```python
from django.contrib import admin

from apps.billing.models import Order, Payment, WebhookEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "citizen", "amount_xof", "status", "created_at")
    list_filter = ("status", "reactivated_after_expiry")
    search_fields = ("order_number", "citizen__phone_e164")
    readonly_fields = ("order_number",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("external_reference", "order", "provider", "mode", "status")
    list_filter = ("provider", "mode", "status")
    search_fields = ("external_reference", "order__order_number")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("external_event_id", "provider", "outcome", "signature_valid", "created_at")
    list_filter = ("provider", "outcome", "signature_valid")
    search_fields = ("external_event_id", "order__order_number")
```

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: order, payment and webhook models with database-enforced uniqueness"
```

---

## Task 3: Contrat PaymentProvider et mock

**Files:**
- Create: `services/core-api/apps/billing/providers/{__init__.py,base.py,mock.py}`
- Create: `services/core-api/apps/billing/tests/test_payment_provider.py`
- Modify: `services/core-api/config/settings/base.py`
- Modify: `services/core-api/config/settings/production.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `apps.billing.models.Order`, `apps.billing.models.Payment`
- Produces:
  - `apps.billing.providers.get_payment_provider() -> PaymentProvider`
  - `apps.billing.providers.base.{PaymentProvider, PaymentIntent, PaymentStatus, WebhookPayload, RefundResult, Mode}`
  - `apps.billing.providers.base.{PaymentError, PaymentTimeout, PaymentTemporaryError, PaymentPermanentError, PaymentRefused}` — tous porteurs de `retryable: bool`
  - `apps.billing.providers.mock.MockPaymentProvider` avec `scenario`, `reset()`, `sign(body) -> str`, `build_webhook(order, *, status, event_id, amount_xof, currency, payee) -> tuple[bytes, dict[str, str]]`

- [ ] **Step 1: Ajouter les réglages**

Dans `config/settings/base.py`, après le bloc Outbox :

```python
# --- Billing (cahier des charges §8.5) --------------------------------------

ORDER_PENDING_TTL_SECONDS = env.int("ORDER_PENDING_TTL_SECONDS", default=1800)
PAYMENT_RECONCILE_AFTER_SECONDS = env.int("PAYMENT_RECONCILE_AFTER_SECONDS", default=300)

# Sentinel, not a credential: production.py refuses to start on it, exactly as for
# JWT_SIGNING_KEY.
INSECURE_WEBHOOK_SECRET_SENTINEL = "insecure-development-payment-webhook-secret"  # noqa: S105
PAYMENT_WEBHOOK_SECRET = env.str(
    "PAYMENT_WEBHOOK_SECRET", default=INSECURE_WEBHOOK_SECRET_SENTINEL
)
```

Dans `config/settings/production.py`, étendre l'import et ajouter la garde :

```python
from config.settings.base import (
    INSECURE_JWT_KEY_SENTINEL,
    INSECURE_SECRET_KEY_SENTINEL,
    INSECURE_WEBHOOK_SECRET_SENTINEL,
    JWT_SIGNING_KEY,
    PAYMENT_WEBHOOK_SECRET,
    SECRET_KEY,
    env,
)
```

```python
if PAYMENT_WEBHOOK_SECRET == INSECURE_WEBHOOK_SECRET_SENTINEL:
    raise ImproperlyConfigured("PAYMENT_WEBHOOK_SECRET must be set in production.")
```

Dans `.env.example`, ajouter :

```bash
# Paiement (§8.5). Générer avec : openssl rand -hex 32
PAYMENT_WEBHOOK_SECRET=insecure-development-payment-webhook-secret
ORDER_PENDING_TTL_SECONDS=1800
PAYMENT_RECONCILE_AFTER_SECONDS=300
OUTBOX_MAX_ATTEMPTS=10
OUTBOX_BACKOFF_BASE_SECONDS=5
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/test_payment_provider.py` :

```python
"""Payment adapter contract and its mock (§8.5, ADR-0004, §16.1)."""

import pytest

from apps.billing.providers import get_payment_provider
from apps.billing.providers.base import (
    Mode,
    PaymentTemporaryError,
)
from apps.billing.providers.mock import MockPaymentProvider


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


def test_the_factory_returns_the_configured_provider():
    assert get_payment_provider().name == "mock"


def test_an_unknown_provider_is_refused(settings):
    settings.PAYMENT_PROVIDER = "nope"

    with pytest.raises(RuntimeError, match="Unknown PAYMENT_PROVIDER"):
        get_payment_provider()


def test_push_is_the_nominal_journey(order):
    intent = get_payment_provider().create_payment(order)

    assert intent.mode == Mode.PUSH
    assert intent.external_reference
    assert intent.instructions
    assert intent.redirect_url == ""


def test_the_redirect_fallback_carries_a_url(order):
    MockPaymentProvider.scenario = "redirect_required"

    intent = get_payment_provider().create_payment(order)

    assert intent.mode == Mode.REDIRECT
    assert intent.redirect_url.startswith("https://")


def test_an_unavailable_provider_raises_a_retryable_error(order):
    MockPaymentProvider.scenario = "provider_unavailable"

    with pytest.raises(PaymentTemporaryError) as raised:
        get_payment_provider().create_payment(order)

    assert raised.value.retryable is True


def test_a_signed_webhook_verifies_and_a_tampered_one_does_not(order):
    provider = get_payment_provider()
    body, headers = MockPaymentProvider.build_webhook(order)

    assert provider.verify_webhook(headers, body) is True
    assert provider.verify_webhook(headers, body + b" ") is False
    assert provider.verify_webhook({"X-Signature": "nope"}, body) is False


def test_a_webhook_parses_into_the_shared_payload(order):
    body, _ = MockPaymentProvider.build_webhook(order)

    payload = get_payment_provider().parse_webhook(body)

    assert payload.external_reference == f"MOCK-{order.order_number}"
    assert payload.status == "succeeded"
    assert payload.amount_xof == order.amount_xof
    assert payload.currency == order.currency
    assert payload.payee == MockPaymentProvider.expected_payee


def test_refund_is_declared_but_not_simulated(order):
    # The contract carries refund() because §8.5 requires it, but simulating a refund
    # whose authorisation and audit rules do not exist yet would fake coverage on the
    # one irreversible gesture of the chain.
    with pytest.raises(NotImplementedError):
        get_payment_provider().refund(None, 500)
```

- [ ] **Step 3: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_payment_provider.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.billing.providers'`.

- [ ] **Step 4: Écrire le contrat**

Créer `services/core-api/apps/billing/providers/base.py` :

```python
"""Contract between the platform and whatever moves the money (cahier des charges §8.5).

Isolating this keeps the domain free of any provider's specifics and lets Wave, Orange
Money or a card aggregator appear later without touching business code. Both journeys of
ADR-0004 are modelled from the start: push is nominal, redirect is the fallback.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass


class PaymentError(Exception):
    """Base for every payment-side failure."""

    retryable = False


class PaymentTimeout(PaymentError):
    """The provider did not answer in time."""

    retryable = True


class PaymentTemporaryError(PaymentError):
    """A transient failure. The caller should retry with backoff."""

    retryable = True


class PaymentPermanentError(PaymentError):
    """A refusal retrying cannot fix."""

    retryable = False


class PaymentRefused(PaymentError):
    """The payer declined or the provider rejected the payment."""

    retryable = False


class Mode:
    PUSH = "push"
    REDIRECT = "redirect"


@dataclass(frozen=True)
class PaymentIntent:
    mode: str
    external_reference: str
    redirect_url: str = ""
    instructions: str = ""


@dataclass(frozen=True)
class PaymentStatus:
    external_reference: str
    status: str
    amount_xof: int = 0
    fees_xof: int = 0


@dataclass(frozen=True)
class WebhookPayload:
    external_event_id: str
    external_reference: str
    status: str
    amount_xof: int
    currency: str
    payee: str
    fees_xof: int = 0


@dataclass(frozen=True)
class RefundResult:
    external_reference: str
    amount_xof: int
    status: str


class PaymentProvider(ABC):
    """Operations the platform needs from the payment layer."""

    name: str
    # The merchant account this platform expects to be credited. Compared strictly on
    # every webhook (§8.5); it belongs to the adapter, not to the order.
    expected_payee: str

    @abstractmethod
    def create_payment(self, order) -> PaymentIntent:
        """Ask the provider to start a payment for an order."""

    @abstractmethod
    def get_payment_status(self, external_reference: str) -> PaymentStatus:
        """Server-to-server truth, used by reconciliation."""

    @abstractmethod
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool:
        """True when the signature proves the body came from the provider."""

    @abstractmethod
    def parse_webhook(self, body: bytes) -> WebhookPayload:
        """Normalise a provider body into the shared payload."""

    @abstractmethod
    def refund(self, payment, amount_xof: int) -> RefundResult:
        """Refund all or part of a payment."""

    @abstractmethod
    def healthcheck(self) -> bool:
        """True when the provider believes it is reachable."""
```

- [ ] **Step 5: Écrire le mock**

Créer `services/core-api/apps/billing/providers/mock.py` :

```python
"""In-memory payment provider covering the journeys of §16.1 and ADR-0004.

Every scenario is reachable by setting `MockPaymentProvider.scenario`, exactly as for
MockNetworkProvider. `build_webhook` produces a genuinely signed body so tests post it
to the real endpoint instead of calling the processing function directly — the signature
check is then exercised rather than bypassed.
"""

import hashlib
import hmac
import json

from django.conf import settings

from apps.billing.providers.base import (
    Mode,
    PaymentIntent,
    PaymentProvider,
    PaymentStatus,
    PaymentTemporaryError,
    RefundResult,
    WebhookPayload,
)

SCENARIOS = (
    "push_success",
    "push_refused",
    "push_timeout",
    "push_abandoned",
    "redirect_required",
    "provider_unavailable",
)

SIGNATURE_HEADER = "X-Signature"


class MockPaymentProvider(PaymentProvider):
    name = "mock"
    expected_payee = "dakar-wifi-mock"

    scenario: str = "push_success"
    statuses: dict[str, str] = {}

    @classmethod
    def reset(cls) -> None:
        cls.scenario = "push_success"
        cls.statuses = {}

    @staticmethod
    def reference_for(order) -> str:
        return f"MOCK-{order.order_number}"

    def create_payment(self, order) -> PaymentIntent:
        if type(self).scenario == "provider_unavailable":
            raise PaymentTemporaryError("Le prestataire est momentanément indisponible.")

        reference = self.reference_for(order)
        type(self).statuses[reference] = "pending"

        if type(self).scenario == "redirect_required":
            return PaymentIntent(
                mode=Mode.REDIRECT,
                external_reference=reference,
                redirect_url=f"https://paiement.exemple.test/{reference}",
            )
        return PaymentIntent(
            mode=Mode.PUSH,
            external_reference=reference,
            instructions="Validez le paiement sur votre téléphone.",
        )

    def get_payment_status(self, external_reference: str) -> PaymentStatus:
        return PaymentStatus(
            external_reference=external_reference,
            status=type(self).statuses.get(external_reference, "pending"),
        )

    def verify_webhook(self, headers, body: bytes) -> bool:
        return hmac.compare_digest(headers.get(SIGNATURE_HEADER, ""), self.sign(body))

    def parse_webhook(self, body: bytes) -> WebhookPayload:
        data = json.loads(body)
        return WebhookPayload(
            external_event_id=data["event_id"],
            external_reference=data["reference"],
            status=data["status"],
            amount_xof=int(data["amount"]),
            currency=data["currency"],
            payee=data["payee"],
            fees_xof=int(data.get("fees", 0)),
        )

    def refund(self, payment, amount_xof: int) -> RefundResult:
        raise NotImplementedError("Le remboursement arrive en phase 6 (§8.5, DW-P6-03).")

    def healthcheck(self) -> bool:
        return type(self).scenario != "provider_unavailable"

    # --- Test seam -----------------------------------------------------------------

    @staticmethod
    def sign(body: bytes) -> str:
        return hmac.new(
            settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()

    @classmethod
    def build_webhook(
        cls,
        order,
        *,
        status: str = "succeeded",
        event_id: str | None = None,
        amount_xof: int | None = None,
        currency: str | None = None,
        payee: str | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        """A body and headers the provider would send, signed for real."""
        body = json.dumps(
            {
                "event_id": event_id or f"EVT-{order.order_number}-{status}",
                "reference": cls.reference_for(order),
                "status": status,
                "amount": order.amount_xof if amount_xof is None else amount_xof,
                "currency": order.currency if currency is None else currency,
                "payee": cls.expected_payee if payee is None else payee,
                "fees": 0,
            },
            separators=(",", ":"),
        ).encode()
        return body, {SIGNATURE_HEADER: cls.sign(body)}
```

- [ ] **Step 6: Écrire la fabrique**

Créer `services/core-api/apps/billing/providers/__init__.py` :

```python
from django.conf import settings

from apps.billing.providers.base import PaymentProvider
from apps.billing.providers.mock import MockPaymentProvider

# Wave, Orange Money and the card aggregator arrive in phase 7, each validated in
# sandbox before any commitment (ADR-0004). Until then everything runs on the mock.
_PROVIDERS: dict[str, type[PaymentProvider]] = {"mock": MockPaymentProvider}


def get_payment_provider() -> PaymentProvider:
    name = settings.PAYMENT_PROVIDER
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown PAYMENT_PROVIDER {name!r}. Available: {', '.join(sorted(_PROVIDERS))}."
        ) from None


def is_known_provider(name: str) -> bool:
    """Whether a webhook path segment names a provider this platform speaks to."""
    return name in _PROVIDERS


__all__ = [
    "MockPaymentProvider",
    "PaymentProvider",
    "get_payment_provider",
    "is_known_provider",
]
```

- [ ] **Step 7: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_payment_provider.py -v
```
Attendu : 8 tests PASS.

- [ ] **Step 8: Vérifier et committer**

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: payment provider contract modelling push and redirect journeys"
```

---

## Task 4: Création de commande idempotente et transitions

**Files:**
- Create: `services/core-api/apps/billing/orders.py`
- Create: `services/core-api/apps/billing/tests/test_order_lifecycle.py`

**Interfaces:**
- Consumes: `apps.billing.models.{Order, Payment}`, `apps.billing.providers.get_payment_provider`
- Produces:
  - `apps.billing.orders.OrderRefused(reason: str, message: str)`
  - `apps.billing.orders.place_order(citizen, zone, plan_version, idempotency_key) -> tuple[Order, Payment]`
  - `apps.billing.orders.mark_paid(order, *, fees_xof: int = 0) -> Order`
  - `apps.billing.orders.mark_failed(order) -> Order`
  - `apps.billing.orders.expire(order) -> Order`
  - `apps.billing.orders.cancel(order) -> Order`
  - `apps.billing.orders.InvalidTransition`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/test_order_lifecycle.py` :

```python
"""Order creation, idempotency and state transitions (§8.5, §10.4)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order, Payment
from apps.billing.orders import (
    InvalidTransition,
    OrderRefused,
    cancel,
    expire,
    mark_failed,
    mark_paid,
    place_order,
)
from apps.billing.providers.mock import MockPaymentProvider
from apps.catalog.models import Plan, PlanVersion


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


def test_placing_an_order_initiates_a_push_payment(citizen, zone, plan_version):
    order, payment = place_order(citizen, zone, plan_version, "key-1")

    assert order.status == Order.Status.PENDING
    assert order.amount_xof == plan_version.price_xof
    assert order.expires_at > timezone.now()
    assert payment.mode == Payment.Mode.PUSH
    assert payment.status == Payment.Status.INITIATED


def test_the_redirect_fallback_puts_the_order_in_requires_action(citizen, zone, plan_version):
    MockPaymentProvider.scenario = "redirect_required"

    order, payment = place_order(citizen, zone, plan_version, "key-1")

    assert order.status == Order.Status.REQUIRES_ACTION
    assert payment.mode == Payment.Mode.REDIRECT


def test_replaying_an_idempotency_key_returns_the_same_order(citizen, zone, plan_version):
    first, _ = place_order(citizen, zone, plan_version, "key-1")
    second, _ = place_order(citizen, zone, plan_version, "key-1")

    assert first.pk == second.pk
    assert Order.objects.count() == 1


def test_an_unpublished_plan_cannot_be_bought(citizen, zone, plan, plan_version):
    plan.status = Plan.Status.DRAFT
    plan.save(update_fields=["status"])

    with pytest.raises(OrderRefused) as raised:
        place_order(citizen, zone, plan_version, "key-1")

    assert raised.value.reason == "offer_unavailable"


def test_a_provider_outage_leaves_no_half_created_order(citizen, zone, plan_version):
    MockPaymentProvider.scenario = "provider_unavailable"

    with pytest.raises(OrderRefused) as raised:
        place_order(citizen, zone, plan_version, "key-1")

    assert raised.value.reason == "provider_unavailable"
    # The draft is kept so the same idempotency key can be retried without colliding,
    # but it is never left as if payment had started.
    assert Order.objects.get().status == Order.Status.DRAFT


def test_a_later_price_change_does_not_alter_a_placed_order(citizen, zone, plan, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    PlanVersion.objects.create(
        plan=plan,
        version=2,
        price_xof=99_000,
        connection_seconds=3600,
        radius_profile_ref="dakar-1h",
        effective_at=timezone.now(),
    )
    order.refresh_from_db()

    assert order.amount_xof == plan_version.price_xof


def test_paying_an_order_stamps_it(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    mark_paid(order)

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.paid_at is not None


def test_an_expired_order_can_still_be_paid_and_is_flagged(citizen, zone, plan_version):
    # §8.5: the citizen paid, so the right is granted; the discrepancy goes to
    # reconciliation rather than being refused.
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    expire(order)

    mark_paid(order)

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.reactivated_after_expiry is True


def test_a_cancelled_order_cannot_be_paid(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    cancel(order)

    with pytest.raises(InvalidTransition):
        mark_paid(order)


def test_a_refused_payment_fails_the_order(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")

    mark_failed(order)

    order.refresh_from_db()
    assert order.status == Order.Status.FAILED
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_order_lifecycle.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.billing.orders'`.

- [ ] **Step 3: Écrire le module**

Créer `services/core-api/apps/billing/orders.py` :

```python
"""Order creation and state transitions (cahier des charges §8.5, §10.4).

Every transition lives here. No status is written anywhere else, so the set of legal
moves can be read in one place rather than reconstructed from call sites.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.billing.models import Order, Payment
from apps.billing.providers import get_payment_provider
from apps.billing.providers.base import PaymentError
from apps.catalog.models import Plan

logger = logging.getLogger(__name__)


class OrderRefused(Exception):
    """The order cannot be placed. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


class InvalidTransition(Exception):
    """The order is not in a state where this move is allowed."""


# What each status may become. Absent keys are terminal.
_ALLOWED: dict[str, set[str]] = {
    Order.Status.DRAFT: {Order.Status.PENDING, Order.Status.REQUIRES_ACTION,
                         Order.Status.CANCELLED},
    Order.Status.PENDING: {Order.Status.REQUIRES_ACTION, Order.Status.PAID,
                           Order.Status.FAILED, Order.Status.EXPIRED, Order.Status.CANCELLED},
    Order.Status.REQUIRES_ACTION: {Order.Status.PAID, Order.Status.FAILED,
                                   Order.Status.EXPIRED, Order.Status.CANCELLED},
    # An expired order may still be paid: the confirmation simply arrived late (§8.5).
    Order.Status.EXPIRED: {Order.Status.PAID},
}


def _move(order: Order, target: str, fields: list[str]) -> Order:
    if target not in _ALLOWED.get(order.status, set()):
        raise InvalidTransition(
            f"Order {order.order_number} cannot move from {order.status} to {target}."
        )
    order.status = target
    order.save(update_fields=[*fields, "status", "updated_at"])
    return order


def place_order(citizen, zone, plan_version, idempotency_key: str) -> tuple[Order, Payment]:
    """Create the order, then ask the provider to start a payment.

    The order is committed before the provider is called: a webhook can legitimately
    arrive before the browser comes back (§16.1), and it must find an order to match.
    """
    existing = Order.objects.filter(citizen=citizen, idempotency_key=idempotency_key).first()
    if existing is not None and existing.status != Order.Status.DRAFT:
        # Replaying the key must not charge twice (§10.4).
        payment = existing.payments.order_by("-created_at").first()
        return existing, payment

    if not citizen.is_usable:
        raise OrderRefused("account_unusable", "Ce compte ne peut pas être utilisé.")

    plan = plan_version.plan
    if plan.status != Plan.Status.PUBLISHED or plan.current_version_id != plan_version.pk:
        raise OrderRefused("offer_unavailable", "Cette offre n'est plus disponible.")

    if not plan.zones.filter(pk=zone.pk).exists():
        raise OrderRefused("offer_unavailable", "Cette offre n'est pas proposée ici.")

    order = existing or Order.objects.create(
        citizen=citizen,
        plan_version=plan_version,
        zone=zone,
        # Frozen here and never read from the plan again: a later price change must not
        # be retroactive (§8.3).
        amount_xof=plan_version.price_xof,
        currency=settings.DEFAULT_CURRENCY,
        idempotency_key=idempotency_key,
        expires_at=timezone.now() + timedelta(seconds=settings.ORDER_PENDING_TTL_SECONDS),
    )

    provider = get_payment_provider()
    try:
        intent = provider.create_payment(order)
    except PaymentError as error:
        logger.warning("Payment initiation failed for %s: %s", order.order_number, error)
        raise OrderRefused(
            "provider_unavailable", "Le paiement est momentanément indisponible."
        ) from error

    with transaction.atomic():
        payment = Payment.objects.create(
            order=order,
            provider=provider.name,
            mode=intent.mode,
            external_reference=intent.external_reference,
            amount_xof=order.amount_xof,
        )
        target = (
            Order.Status.REQUIRES_ACTION
            if intent.mode == Payment.Mode.REDIRECT
            else Order.Status.PENDING
        )
        _move(order, target, [])

    return order, payment


def mark_paid(order: Order, *, fees_xof: int = 0) -> Order:
    was_expired = order.status == Order.Status.EXPIRED
    order.paid_at = timezone.now()
    if was_expired:
        order.reactivated_after_expiry = True
        logger.warning(
            "Order %s confirmed after expiry: reactivated for reconciliation (§8.5).",
            order.order_number,
        )
    _move(order, Order.Status.PAID, ["paid_at", "reactivated_after_expiry"])
    order.payments.filter(status=Payment.Status.INITIATED).update(
        status=Payment.Status.SUCCEEDED, fees_xof=fees_xof
    )
    return order


def mark_failed(order: Order) -> Order:
    _move(order, Order.Status.FAILED, [])
    order.payments.filter(status=Payment.Status.INITIATED).update(status=Payment.Status.REFUSED)
    return order


def expire(order: Order) -> Order:
    order.expired_at = timezone.now()
    _move(order, Order.Status.EXPIRED, ["expired_at"])
    order.payments.filter(status=Payment.Status.INITIATED).update(status=Payment.Status.EXPIRED)
    return order


def cancel(order: Order) -> Order:
    order.cancelled_at = timezone.now()
    return _move(order, Order.Status.CANCELLED, ["cancelled_at"])
```

- [ ] **Step 4: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_order_lifecycle.py -v
```
Attendu : 10 tests PASS.

- [ ] **Step 5: Vérifier et committer**

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: idempotent order placement with a single place for state transitions"
```

---

## Task 5: Activation du droit par l'outbox

**Files:**
- Create: `services/core-api/apps/access/activation.py`
- Create: `services/core-api/apps/access/tests/test_activation.py`
- Modify: `services/core-api/apps/access/apps.py`

**Interfaces:**
- Consumes: `apps.core.outbox.register`, `apps.access.models.Entitlement`, `apps.access.providers.get_network_provider`
- Produces:
  - `apps.access.activation.TOPIC = "entitlement.activate"`
  - `apps.access.activation.activate_entitlement(payload: dict) -> None` — handler enregistré sur le sujet
  - `apps.access.activation.entitlement_for_order(order, *, starts_at) -> Entitlement`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `services/core-api/apps/access/tests/test_activation.py` :

```python
"""Activating a paid right through the outbox (§8.5, §11.2, §17 no 6)."""

import pytest
from django.utils import timezone

from apps.access.activation import TOPIC, activate_entitlement, entitlement_for_order
from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
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


def test_the_topic_is_the_one_the_outbox_registers():
    assert TOPIC == "entitlement.activate"


def test_creating_the_right_leaves_it_waiting_for_the_network(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    assert entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    assert entitlement.source == Entitlement.Source.PURCHASE
    assert entitlement.order_id == paid_order.pk


def test_creating_the_right_twice_returns_the_same_one(paid_order):
    first = entitlement_for_order(paid_order, starts_at=timezone.now())
    second = entitlement_for_order(paid_order, starts_at=timezone.now())

    assert first.pk == second.pk
    assert Entitlement.objects.count() == 1


def test_activation_applies_the_plan_and_marks_the_right_active(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())

    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    entitlement.refresh_from_db()
    assert entitlement.status == Entitlement.Status.ACTIVE
    assert entitlement.radius_username == str(paid_order.citizen_id)
    assert MockNetworkProvider.assignments[str(paid_order.citizen_id)] == (
        paid_order.plan_version.radius_profile_ref
    )


def test_activation_is_idempotent(paid_order):
    # §16.1: replaying an activation must not apply the plan a second time.
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    activate_entitlement({"entitlement_id": str(entitlement.pk)})
    calls_after_first = MockNetworkProvider.assignment_calls

    activate_entitlement({"entitlement_id": str(entitlement.pk)})

    assert MockNetworkProvider.assignment_calls == calls_after_first


def test_a_network_outage_raises_so_the_outbox_retries(paid_order):
    entitlement = entitlement_for_order(paid_order, starts_at=timezone.now())
    MockNetworkProvider.scenario = "temporary_error"

    with pytest.raises(Exception):  # noqa: B017 - the outbox catches any failure
        activate_entitlement({"entitlement_id": str(entitlement.pk)})

    entitlement.refresh_from_db()
    # Crucially still pending, not failed: the citizen paid, so this must be retried.
    assert entitlement.status == Entitlement.Status.PENDING_ACTIVATION
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/access/tests/test_activation.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.access.activation'`.

- [ ] **Step 3: Écrire le handler**

Créer `services/core-api/apps/access/activation.py` :

```python
"""Activating a right that was paid for (cahier des charges §8.5, §11.2).

Unlike the free allowance, this runs after the money is in: a failure here must never
refuse the citizen, only delay them. Every failure therefore propagates so the outbox
reschedules, and the right stays `pending_activation` rather than becoming a refusal.
"""

import logging
from datetime import timedelta

from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers import get_network_provider
from apps.access.providers.base import NetworkError
from apps.core.outbox import PermanentHandlerError, register

logger = logging.getLogger(__name__)

TOPIC = "entitlement.activate"


def entitlement_for_order(order, *, starts_at) -> Entitlement:
    """The right an order produces, created at most once.

    The OneToOne on `Entitlement.order` means a concurrent second call raises rather
    than granting twice; `get_or_create` turns that into the existing row.
    """
    version = order.plan_version
    duration = version.connection_seconds or version.validity_seconds
    entitlement, _ = Entitlement.objects.get_or_create(
        order=order,
        defaults={
            "citizen": order.citizen,
            "plan_version": version,
            "zone": order.zone,
            "source": Entitlement.Source.PURCHASE,
            "status": Entitlement.Status.PENDING_ACTIVATION,
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(seconds=duration) if duration else None,
        },
    )
    return entitlement


@register(TOPIC)
def activate_entitlement(payload: dict) -> None:
    entitlement = Entitlement.objects.select_related("plan_version", "citizen").filter(
        pk=payload["entitlement_id"]
    ).first()

    if entitlement is None:
        raise PermanentHandlerError(f"Unknown entitlement {payload['entitlement_id']!r}.")

    if entitlement.status == Entitlement.Status.ACTIVE:
        # Already applied. Replaying must not assign the plan a second time (§16.1).
        return

    provider = get_network_provider()
    subscriber_ref = str(entitlement.citizen_id)
    try:
        provider.ensure_user(subscriber_ref)
        provider.assign_plan(subscriber_ref, entitlement.plan_version.radius_profile_ref)
    except NetworkError as error:
        if error.retryable:
            # Left pending on purpose: the outbox will come back. Marking it failed
            # would turn a temporary outage into a lost purchase.
            logger.warning("Activation of %s deferred: %s", entitlement.pk, error)
            raise
        entitlement.status = Entitlement.Status.ACTIVATION_FAILED
        entitlement.activation_error = str(error)[:200]
        entitlement.save(update_fields=["status", "activation_error", "updated_at"])
        raise PermanentHandlerError(str(error)) from error

    entitlement.status = Entitlement.Status.ACTIVE
    entitlement.radius_username = subscriber_ref
    entitlement.radius_synced_at = timezone.now()
    entitlement.activation_error = ""
    entitlement.save(
        update_fields=[
            "status",
            "radius_username",
            "radius_synced_at",
            "activation_error",
            "updated_at",
        ]
    )
```

- [ ] **Step 4: Enregistrer le handler au démarrage**

Dans `services/core-api/apps/access/apps.py`, ajouter à la classe de configuration :

```python
    def ready(self):
        # Importing registers the outbox handler. Without it, enqueue() would refuse
        # the topic and a paid activation would never be scheduled.
        from apps.access import activation  # noqa: F401
```

- [ ] **Step 5: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/access/tests/test_activation.py -v
```
Attendu : 6 tests PASS.

- [ ] **Step 6: Vérifier et committer**

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: activate a paid entitlement through the outbox so an outage only delays it"
```

---

## Task 6: Réception et traitement des webhooks

**Files:**
- Create: `services/core-api/apps/billing/webhooks.py`
- Create: `services/core-api/apps/billing/views.py`
- Create: `services/core-api/apps/billing/serializers.py`
- Create: `services/core-api/apps/billing/urls.py`
- Create: `services/core-api/apps/billing/tests/test_webhooks.py`
- Modify: `services/core-api/config/urls.py`

**Interfaces:**
- Consumes: `apps.billing.orders.{mark_paid, mark_failed}`, `apps.access.activation.{TOPIC, entitlement_for_order}`, `apps.core.outbox.enqueue`, `apps.billing.providers.get_payment_provider`
- Produces:
  - `apps.billing.webhooks.WebhookResult(outcome: str, http_status: int)`
  - `apps.billing.webhooks.handle(provider_name: str, headers: Mapping[str, str], body: bytes) -> WebhookResult`
  - Endpoint `POST /api/v1/webhooks/payments/<provider>` nommé `payment-webhook`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/test_webhooks.py` :

```python
"""Webhook reception: signature, idempotence, history and late confirmations (§8.5, §16.1)."""

import pytest
from django.utils import timezone

from apps.access.models import Entitlement
from apps.access.providers.mock import MockNetworkProvider
from apps.billing.models import Order, WebhookEvent
from apps.billing.orders import expire, place_order
from apps.billing.providers.mock import MockPaymentProvider
from apps.core.models import OutboxMessage
from apps.core.outbox import drain

URL = "/api/v1/webhooks/payments/mock"


@pytest.fixture(autouse=True)
def reset_providers():
    MockPaymentProvider.reset()
    MockNetworkProvider.reset()
    yield
    MockPaymentProvider.reset()
    MockNetworkProvider.reset()


@pytest.fixture
def placed(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    return order


def post(client, body, headers):
    return client.post(
        URL, data=body, content_type="application/json", headers=headers
    )


def test_a_valid_webhook_pays_the_order_and_schedules_activation(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    assert OutboxMessage.objects.filter(topic="entitlement.activate").count() == 1


def test_the_scheduled_activation_makes_the_right_live(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed)
    post(client, body, headers)

    drain()

    placed.refresh_from_db()
    assert placed.entitlement.status == Entitlement.Status.ACTIVE


def test_a_webhook_arriving_before_the_browser_returns_is_honoured(client, placed):
    """§16.1 — nothing special is needed, and a test keeps it that way.

    The order is committed before the provider is ever called, so a confirmation that
    overtakes the browser still finds an order to match. The portal then simply polls
    an order that is already paid.
    """
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement is not None


def test_an_invalid_signature_is_recorded_and_changes_nothing(client, placed):
    body, _ = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, {"X-Signature": "forged"})

    assert response.status_code == 400
    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    event = WebhookEvent.objects.get()
    assert event.outcome == WebhookEvent.Outcome.BAD_SIGNATURE
    assert event.signature_valid is False


def test_a_duplicate_webhook_never_activates_twice(client, placed):
    # §17 criterion 5.
    body, headers = MockPaymentProvider.build_webhook(placed)
    post(client, body, headers)

    response = post(client, body, headers)

    assert response.status_code == 200
    assert Entitlement.objects.count() == 1
    assert OutboxMessage.objects.filter(topic="entitlement.activate").count() == 1
    outcomes = set(WebhookEvent.objects.values_list("outcome", flat=True))
    assert outcomes == {WebhookEvent.Outcome.PROCESSED, WebhookEvent.Outcome.DUPLICATE}


def test_a_divergent_amount_is_refused(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, amount_xof=1)

    response = post(client, body, headers)

    assert response.status_code == 400
    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
    assert WebhookEvent.objects.get().outcome == WebhookEvent.Outcome.AMOUNT_MISMATCH


def test_a_divergent_payee_is_refused(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, payee="quelquun-dautre")

    response = post(client, body, headers)

    assert response.status_code == 400
    assert WebhookEvent.objects.get().outcome == WebhookEvent.Outcome.AMOUNT_MISMATCH


def test_an_unknown_order_is_recorded_without_a_link(client, citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    body, headers = MockPaymentProvider.build_webhook(order)
    order.delete()

    response = post(client, body, headers)

    assert response.status_code == 404
    event = WebhookEvent.objects.get()
    assert event.outcome == WebhookEvent.Outcome.UNKNOWN_ORDER
    assert event.order_id is None


def test_a_refusal_fails_the_order(client, placed):
    body, headers = MockPaymentProvider.build_webhook(placed, status="refused")

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.FAILED
    assert not Entitlement.objects.exists()


def test_a_confirmation_after_expiry_reactivates_the_order(client, placed):
    # §8.5 and §16.1: the citizen paid, so the right is granted and the discrepancy
    # is flagged rather than the payment being dropped.
    expire(placed)
    body, headers = MockPaymentProvider.build_webhook(placed)

    response = post(client, body, headers)

    assert response.status_code == 200
    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.reactivated_after_expiry is True
    assert placed.entitlement is not None


def test_a_payment_confirmed_while_the_network_is_down_recovers(client, placed):
    """§17 criterion 6 — the reason the whole outbox exists."""
    MockNetworkProvider.scenario = "temporary_error"
    body, headers = MockPaymentProvider.build_webhook(placed)

    post(client, body, headers)
    drain()

    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID
    assert placed.entitlement.status == Entitlement.Status.PENDING_ACTIVATION
    message = OutboxMessage.objects.get(topic="entitlement.activate")
    assert message.status == OutboxMessage.Status.PENDING
    assert message.attempts == 1

    MockNetworkProvider.scenario = "success"
    OutboxMessage.objects.update(available_at=timezone.now())
    drain()

    placed.refresh_from_db()
    assert placed.entitlement.status == Entitlement.Status.ACTIVE
    assert OutboxMessage.objects.get().status == OutboxMessage.Status.DONE
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_webhooks.py -v
```
Attendu : erreur 404 sur l'URL, ou `ModuleNotFoundError` sur `apps.billing.webhooks`.

- [ ] **Step 3: Écrire le traitement**

Créer `services/core-api/apps/billing/webhooks.py` :

```python
"""Webhook reception (cahier des charges §8.5, §10.2, §16.1).

Trust rests entirely on the signature: this endpoint has no authentication, because the
provider has no session. Every delivery is recorded — duplicates and rejections included
— and exactly one may ever be marked processed, which the database enforces.
"""

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access.activation import TOPIC, entitlement_for_order
from apps.billing.models import Order, WebhookEvent
from apps.billing.orders import InvalidTransition, mark_failed, mark_paid
from apps.billing.providers import get_payment_provider, is_known_provider
from apps.core.outbox import enqueue

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookResult:
    outcome: str
    http_status: int


def _record(provider_name, event_id, body, *, outcome, order=None,
            signature_valid=False, payload=None) -> WebhookEvent:
    return WebhookEvent.objects.create(
        provider=provider_name,
        external_event_id=event_id,
        order=order,
        signature_valid=signature_valid,
        outcome=outcome,
        payload=payload or {},
        body_sha256=hashlib.sha256(body).hexdigest(),
        processed_at=timezone.now() if outcome == WebhookEvent.Outcome.PROCESSED else None,
    )


def handle(provider_name: str, headers: Mapping[str, str], body: bytes) -> WebhookResult:
    if not is_known_provider(provider_name):
        return WebhookResult(WebhookEvent.Outcome.IGNORED, 404)

    provider = get_payment_provider()

    if not provider.verify_webhook(headers, body):
        # 400 and not 500: a signature that is wrong will never become right, so
        # asking the provider to retry would be pointless noise.
        _record(provider_name, "", body, outcome=WebhookEvent.Outcome.BAD_SIGNATURE)
        logger.warning("Rejected a %s webhook with an invalid signature.", provider_name)
        return WebhookResult(WebhookEvent.Outcome.BAD_SIGNATURE, 400)

    event = provider.parse_webhook(body)
    # Only what an investigation needs. The raw body is never kept: it may carry
    # secrets, and §9 forbids a full copy when a reduced one suffices.
    minimised = {
        "event_id": event.external_event_id,
        "reference": event.external_reference,
        "status": event.status,
        "amount": event.amount_xof,
        "currency": event.currency,
    }

    order = Order.objects.filter(payments__external_reference=event.external_reference).first()
    if order is None:
        _record(provider_name, event.external_event_id, body,
                outcome=WebhookEvent.Outcome.UNKNOWN_ORDER,
                signature_valid=True, payload=minimised)
        return WebhookResult(WebhookEvent.Outcome.UNKNOWN_ORDER, 404)

    # Strict comparison, never tolerant (§8.5).
    if (
        event.amount_xof != order.amount_xof
        or event.currency != order.currency
        or event.payee != provider.expected_payee
    ):
        _record(provider_name, event.external_event_id, body,
                outcome=WebhookEvent.Outcome.AMOUNT_MISMATCH, order=order,
                signature_valid=True, payload=minimised)
        logger.error("Webhook for %s diverges from the order.", order.order_number)
        return WebhookResult(WebhookEvent.Outcome.AMOUNT_MISMATCH, 400)

    if event.status != "succeeded":
        try:
            mark_failed(order)
        except InvalidTransition:
            pass
        _record(provider_name, event.external_event_id, body,
                outcome=WebhookEvent.Outcome.PROCESSED, order=order,
                signature_valid=True, payload=minimised)
        return WebhookResult(WebhookEvent.Outcome.PROCESSED, 200)

    try:
        with transaction.atomic():
            # Everything that must survive commits together; the network call happens
            # afterwards, driven by the outbox row written here.
            _record(provider_name, event.external_event_id, body,
                    outcome=WebhookEvent.Outcome.PROCESSED, order=order,
                    signature_valid=True, payload=minimised)
            mark_paid(order, fees_xof=event.fees_xof)
            entitlement = entitlement_for_order(order, starts_at=timezone.now())
            enqueue(TOPIC, {"entitlement_id": str(entitlement.pk)})
    except IntegrityError:
        # The partial unique index refused a second processed delivery: this is a
        # duplicate. Recorded for the history, not replayed.
        _record(provider_name, event.external_event_id, body,
                outcome=WebhookEvent.Outcome.DUPLICATE, order=order,
                signature_valid=True, payload=minimised)
        return WebhookResult(WebhookEvent.Outcome.DUPLICATE, 200)

    return WebhookResult(WebhookEvent.Outcome.PROCESSED, 200)
```

- [ ] **Step 4: Écrire l'endpoint**

Créer `services/core-api/apps/billing/views.py` :

```python
"""Payment webhook endpoint (cahier des charges §10.2)."""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.billing.webhooks import handle


@extend_schema(
    request=None,
    responses={200: None, 400: None, 404: None},
    auth=[],
    summary="Webhook de paiement",
    tags=["webhooks"],
)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def payment_webhook(request: Request, provider: str) -> Response:
    # Read the raw body before anything touches request.data: the signature covers the
    # exact bytes the provider sent, and a parsed-then-reserialised copy is not them.
    body = request.body
    result = handle(provider, request.headers, body)
    return Response({"outcome": result.outcome}, status=result.http_status)
```

Créer `services/core-api/apps/billing/urls.py` :

```python
from django.urls import path

from apps.billing import views

urlpatterns = [
    path(
        "webhooks/payments/<str:provider>",
        views.payment_webhook,
        name="payment-webhook",
    ),
]
```

Dans `config/urls.py`, ajouter après la ligne `apps.access.urls` :

```python
    path("api/v1/", include("apps.billing.urls")),
```

- [ ] **Step 5: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_webhooks.py -v
```
Attendu : 11 tests PASS.

Si `test_a_duplicate_webhook_never_activates_twice` échoue avec une `TransactionManagementError`, c'est que l'`IntegrityError` est capturée à l'intérieur du bloc atomique : vérifier que le `try` entoure bien le `with transaction.atomic()` et non l'inverse.

- [ ] **Step 6: Régénérer le contrat, vérifier, committer**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
ENVIRONMENT=local uv run --directory services/core-api python manage.py spectacular \
  --format openapi --file ../../docs/api/openapi.yaml
pnpm api-client:generate
cd services/core-api && uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd .. && cd .. && git add -A
git commit -m "feat: signed payment webhooks with complete history and single processing"
```

---

## Task 7: Tâches planifiées

**Files:**
- Create: `services/core-api/apps/billing/tasks.py`
- Create: `services/core-api/apps/billing/tests/test_tasks.py`
- Modify: `services/core-api/config/settings/base.py`
- Modify: `services/core-api/apps/billing/webhooks.py`

**Interfaces:**
- Consumes: `apps.billing.orders.expire`, `apps.billing.providers.get_payment_provider`, `apps.core.tasks.drain_outbox`
- Produces:
  - `apps.billing.tasks.expire_pending_orders() -> int`
  - `apps.billing.tasks.reconcile_pending_payments() -> int`
  - `CELERY_BEAT_SCHEDULE` dans les réglages

- [ ] **Step 1: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/test_tasks.py` :

```python
"""Scheduled work behind the purchase chain (§8.5)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order
from apps.billing.orders import place_order
from apps.billing.providers.mock import MockPaymentProvider
from apps.billing.tasks import expire_pending_orders, reconcile_pending_payments


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


@pytest.fixture
def placed(citizen, zone, plan_version):
    order, _ = place_order(citizen, zone, plan_version, "key-1")
    return order


def test_an_order_past_its_deadline_expires(placed):
    Order.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))

    assert expire_pending_orders() == 1

    placed.refresh_from_db()
    assert placed.status == Order.Status.EXPIRED


def test_an_order_still_within_its_deadline_is_left_alone(placed):
    assert expire_pending_orders() == 0

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING


def test_a_paid_order_is_never_expired(placed):
    Order.objects.update(
        status=Order.Status.PAID, expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )

    assert expire_pending_orders() == 0


def test_reconciliation_pays_an_order_the_provider_reports_as_settled(placed, settings):
    settings.PAYMENT_RECONCILE_AFTER_SECONDS = 0
    MockPaymentProvider.statuses[MockPaymentProvider.reference_for(placed)] = "succeeded"

    assert reconcile_pending_payments() == 1

    placed.refresh_from_db()
    assert placed.status == Order.Status.PAID


def test_reconciliation_leaves_a_still_pending_payment_alone(placed, settings):
    settings.PAYMENT_RECONCILE_AFTER_SECONDS = 0

    assert reconcile_pending_payments() == 0

    placed.refresh_from_db()
    assert placed.status == Order.Status.PENDING
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_tasks.py -v
```
Attendu : `ModuleNotFoundError: No module named 'apps.billing.tasks'`.

- [ ] **Step 3: Écrire les tâches**

Créer `services/core-api/apps/billing/tasks.py` :

```python
"""Scheduled work owned by billing (cahier des charges §8.5)."""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.access.activation import TOPIC, entitlement_for_order
from apps.billing.models import Order
from apps.billing.orders import InvalidTransition, expire, mark_paid
from apps.billing.providers import get_payment_provider
from apps.core.outbox import enqueue

logger = logging.getLogger(__name__)


@shared_task(name="billing.expire_pending_orders")
def expire_pending_orders() -> int:
    """Close orders nobody paid within the configured window."""
    due = Order.objects.filter(
        status__in=[Order.Status.PENDING, Order.Status.REQUIRES_ACTION],
        expires_at__lte=timezone.now(),
    )
    count = 0
    for order in due:
        try:
            expire(order)
        except InvalidTransition:
            continue
        count += 1
    return count


@shared_task(name="billing.reconcile_pending_payments")
def reconcile_pending_payments() -> int:
    """Ask the provider about orders that stayed pending (§8.5).

    A webhook can be lost. Polling is the safety net that keeps a paid citizen from
    waiting on a message that never arrives.
    """
    threshold = timezone.now() - timedelta(seconds=settings.PAYMENT_RECONCILE_AFTER_SECONDS)
    stale = Order.objects.filter(
        status__in=[Order.Status.PENDING, Order.Status.REQUIRES_ACTION],
        created_at__lte=threshold,
    ).prefetch_related("payments")

    provider = get_payment_provider()
    settled = 0
    for order in stale:
        payment = order.payments.order_by("-created_at").first()
        if payment is None:
            continue
        status = provider.get_payment_status(payment.external_reference)
        if status.status != "succeeded":
            continue
        # Same rule as the webhook path: state and outbox row commit together, and the
        # network call happens afterwards. Reconciliation must not be the one place
        # where a payment can be recorded without its activation being scheduled.
        with transaction.atomic():
            mark_paid(order, fees_xof=status.fees_xof)
            entitlement = entitlement_for_order(order, starts_at=timezone.now())
            enqueue(TOPIC, {"entitlement_id": str(entitlement.pk)})
        logger.warning("Order %s settled by reconciliation, not by webhook.", order.order_number)
        settled += 1
    return settled
```

- [ ] **Step 4: Ajouter le battement Celery**

Dans `config/settings/base.py`, après les réglages Celery existants :

```python
CELERY_BEAT_SCHEDULE = {
    # The drain also runs on commit for latency; this beat is the recovery path for
    # when a worker died between the commit and the call (§11.2).
    "drain-outbox": {"task": "core.drain_outbox", "schedule": 30.0},
    "expire-pending-orders": {"task": "billing.expire_pending_orders", "schedule": 60.0},
    "reconcile-pending-payments": {
        "task": "billing.reconcile_pending_payments",
        "schedule": 300.0,
    },
}
```

- [ ] **Step 5: Brancher le chemin rapide après le webhook**

Dans `services/core-api/apps/billing/webhooks.py`, ajouter l'import :

```python
from apps.core.tasks import drain_outbox
```

et, juste avant le `return WebhookResult(WebhookEvent.Outcome.PROCESSED, 200)` final :

```python
    # Fast path: drain as soon as the transaction is durable. The beat remains the
    # safety net if this worker dies before the task is picked up.
    transaction.on_commit(drain_outbox.delay)
```

- [ ] **Step 6: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/ -v
```
Attendu : tous PASS.

Note : les tests de la tâche 6 appellent `drain()` explicitement et ne dépendent donc pas de `on_commit`, qui ne se déclenche pas sous la fixture `db`. C'est délibéré — un test qui reposerait sur `on_commit` sans `django_capture_on_commit_callbacks` passerait pour de mauvaises raisons.

- [ ] **Step 7: Vérifier et committer**

```bash
cd services/core-api
uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: expire, reconcile and drain on a schedule so a lost webhook is not a lost sale"
```

---

## Task 8: API des commandes

**Files:**
- Modify: `services/core-api/apps/billing/serializers.py`
- Modify: `services/core-api/apps/billing/views.py`
- Modify: `services/core-api/apps/billing/urls.py`
- Create: `services/core-api/apps/billing/tests/test_order_api.py`
- Modify: `services/core-api/apps/citizens/tests/test_schema.py`
- Modify: `docs/api/openapi.yaml`, `packages/api-client/src/schema.d.ts`, `packages/api-client/src/index.ts`

**Interfaces:**
- Consumes: `apps.citizens.authentication.{CitizenTokenAuthentication, citizen_of}`, `apps.portal.services.resolve_portal_context`, `apps.portal.views._error`
- Produces:
  - `POST /api/v1/orders` — nom `order-create`
  - `GET /api/v1/orders/<uuid:order_id>` — nom `order-detail`
  - `GET /api/v1/orders/<uuid:order_id>/receipt` — nom `order-receipt`
  - Client TS : `createOrder`, `getOrder`, `getReceipt`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `services/core-api/apps/billing/tests/test_order_api.py` :

```python
"""Order endpoints for the portal (§10.1, §10.4)."""

import pytest
from django.utils import timezone

from apps.billing.models import Order
from apps.billing.providers.mock import MockPaymentProvider
from apps.citizens.models import Citizen
from apps.citizens.tokens import issue_tokens

CREATE_URL = "/api/v1/orders"


@pytest.fixture(autouse=True)
def reset_provider():
    MockPaymentProvider.reset()
    yield
    MockPaymentProvider.reset()


@pytest.fixture
def auth(citizen):
    tokens = issue_tokens(citizen)
    return {"Authorization": f"Bearer {tokens.access}"}


def test_an_anonymous_caller_cannot_place_an_order(client, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
    )

    assert response.status_code == 401


def test_placing_an_order_returns_the_push_instructions(client, auth, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == Order.Status.PENDING
    assert body["mode"] == "push"
    assert body["instructions"]


def test_the_idempotency_key_is_required(client, auth, hotspot, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers=auth,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_required"


def test_replaying_the_key_does_not_place_a_second_order(client, auth, hotspot, plan_version):
    payload = {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)}
    headers = {**auth, "Idempotency-Key": "key-1"}

    first = client.post(CREATE_URL, payload, content_type="application/json", headers=headers)
    second = client.post(CREATE_URL, payload, content_type="application/json", headers=headers)

    assert first.json()["id"] == second.json()["id"]
    assert Order.objects.count() == 1


def test_an_unknown_hotspot_exposes_nothing(client, auth, plan_version):
    response = client.post(
        CREATE_URL,
        {"nas_id": "inconnue", "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    )

    assert response.status_code == 404


def test_a_citizen_reads_their_own_order(client, auth, hotspot, plan_version):
    created = client.post(
        CREATE_URL,
        {"nas_id": hotspot.nas_identifier, "plan_version_id": str(plan_version.pk)},
        content_type="application/json",
        headers={**auth, "Idempotency-Key": "key-1"},
    ).json()

    response = client.get(f"{CREATE_URL}/{created['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json()["order_number"]


def test_a_citizen_cannot_read_someone_elses_order(client, auth, zone, plan_version):
    # A second citizen, because the `order` fixture belongs to the authenticated one.
    other = Citizen.objects.create(
        phone_e164="+221770000000", status=Citizen.Status.ACTIVE, verified_at=timezone.now()
    )
    theirs = Order.objects.create(
        citizen=other,
        plan_version=plan_version,
        zone=zone,
        amount_xof=plan_version.price_xof,
        currency="XOF",
        idempotency_key="key-other",
        expires_at=timezone.now() + timezone.timedelta(minutes=30),
    )

    response = client.get(f"{CREATE_URL}/{theirs.pk}", headers=auth)

    # Not 403: confirming the id exists would already leak something.
    assert response.status_code == 404
```

- [ ] **Step 2: Lancer le test et vérifier qu'il échoue**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_order_api.py -v
```
Attendu : 404 sur `/api/v1/orders`.

- [ ] **Step 3: Écrire les sérialiseurs**

Créer `services/core-api/apps/billing/serializers.py` :

```python
from rest_framework import serializers

from apps.billing.models import Order


class OrderRequestSerializer(serializers.Serializer):
    nas_id = serializers.CharField(max_length=120)
    plan_version_id = serializers.UUIDField()


class OrderSerializer(serializers.ModelSerializer):
    mode = serializers.CharField(read_only=True, default="")
    instructions = serializers.CharField(read_only=True, default="")
    redirect_url = serializers.CharField(read_only=True, default="")
    entitlement_status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "amount_xof",
            "currency",
            "status",
            "expires_at",
            "paid_at",
            "mode",
            "instructions",
            "redirect_url",
            "entitlement_status",
        ]

    def get_entitlement_status(self, order) -> str:
        entitlement = getattr(order, "entitlement", None)
        return entitlement.status if entitlement is not None else ""


class ReceiptSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan_version.plan.name", read_only=True)

    class Meta:
        model = Order
        fields = ["order_number", "plan_name", "amount_xof", "currency", "paid_at"]
```

- [ ] **Step 4: Écrire les vues**

Ajouter à `services/core-api/apps/billing/views.py` (en conservant `payment_webhook`) :

```python
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.billing.models import Order
from apps.billing.orders import OrderRefused, place_order
from apps.billing.serializers import OrderRequestSerializer, OrderSerializer, ReceiptSerializer
from apps.catalog.models import PlanVersion
from apps.citizens.authentication import CitizenTokenAuthentication, citizen_of
from apps.portal.serializers import ErrorSerializer
from apps.portal.services import UnknownHotspot, resolve_portal_context
from apps.portal.views import _error


@extend_schema(
    request=OrderRequestSerializer,
    responses={201: OrderSerializer, 400: ErrorSerializer, 404: ErrorSerializer},
    summary="Commander une offre payante",
    tags=["commandes"],
)
@api_view(["POST"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def create_order(request: Request) -> Response:
    idempotency_key = request.headers.get("Idempotency-Key", "").strip()
    if not idempotency_key:
        return _error(
            request,
            "idempotency_key_required",
            "L'en-tête Idempotency-Key est obligatoire.",
            status.HTTP_400_BAD_REQUEST,
        )

    payload = OrderRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    # The zone comes from the hotspot, never from the caller (§8.2).
    try:
        context = resolve_portal_context(nas_identifier=payload.validated_data["nas_id"])
    except UnknownHotspot:
        return _error(
            request, "unknown_hotspot", "Ce point d'accès n'est pas reconnu.",
            status.HTTP_404_NOT_FOUND,
        )

    version = PlanVersion.objects.filter(pk=payload.validated_data["plan_version_id"]).first()
    if version is None:
        return _error(
            request, "unknown_offer", "Cette offre n'existe pas.", status.HTTP_404_NOT_FOUND
        )

    try:
        order, payment = place_order(
            citizen_of(request), context.zone, version, idempotency_key
        )
    except OrderRefused as error:
        return _error(request, error.reason, error.message, status.HTTP_400_BAD_REQUEST)

    data = OrderSerializer(order).data
    data["mode"] = payment.mode
    data["instructions"] = (
        "Validez le paiement sur votre téléphone." if payment.mode == "push" else ""
    )
    return Response(data, status=status.HTTP_201_CREATED)


@extend_schema(
    responses={200: OrderSerializer, 404: ErrorSerializer},
    summary="Statut d'une commande",
    tags=["commandes"],
)
@api_view(["GET"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def order_detail(request: Request, order_id) -> Response:
    # Filtered on the authenticated citizen, never on the id alone.
    order = Order.objects.filter(pk=order_id, citizen=citizen_of(request)).first()
    if order is None:
        return _error(
            request, "unknown_order", "Cette commande n'existe pas.", status.HTTP_404_NOT_FOUND
        )
    return Response(OrderSerializer(order).data)


@extend_schema(
    responses={200: ReceiptSerializer, 404: ErrorSerializer},
    summary="Reçu d'une commande payée",
    tags=["commandes"],
)
@api_view(["GET"])
@authentication_classes([CitizenTokenAuthentication])
@permission_classes([IsAuthenticated])
def order_receipt(request: Request, order_id) -> Response:
    order = Order.objects.filter(
        pk=order_id, citizen=citizen_of(request), status=Order.Status.PAID
    ).select_related("plan_version__plan").first()
    if order is None:
        return _error(
            request, "unknown_order", "Aucun reçu pour cette commande.",
            status.HTTP_404_NOT_FOUND,
        )
    return Response(ReceiptSerializer(order).data)
```

Compléter `services/core-api/apps/billing/urls.py` :

```python
urlpatterns = [
    path("orders", views.create_order, name="order-create"),
    path("orders/<uuid:order_id>", views.order_detail, name="order-detail"),
    path("orders/<uuid:order_id>/receipt", views.order_receipt, name="order-receipt"),
    path(
        "webhooks/payments/<str:provider>",
        views.payment_webhook,
        name="payment-webhook",
    ),
]
```

- [ ] **Step 5: Étendre les tests de contrat**

Dans `services/core-api/apps/citizens/tests/test_schema.py`, ajouter aux listes :

```python
PROTECTED = [
    ("/api/v1/auth/logout", "post"),
    ("/api/v1/me", "get"),
    ("/api/v1/me/entitlements", "get"),
    ("/api/v1/portal/free-access", "post"),
    ("/api/v1/orders", "post"),
    ("/api/v1/orders/{order_id}", "get"),
    ("/api/v1/orders/{order_id}/receipt", "get"),
]
```

et à `PUBLIC` :

```python
    ("/api/v1/webhooks/payments/{provider}", "post"),
```

- [ ] **Step 6: Lancer les tests**

```bash
cd services/core-api && uv run pytest apps/billing/tests/test_order_api.py apps/citizens/tests/test_schema.py -v
```
Attendu : tous PASS.

- [ ] **Step 7: Étendre le client TypeScript**

`request` n'accepte pas d'en-têtes aujourd'hui ([index.ts:44-48](../../../packages/api-client/src/index.ts#L44-L48)). Trois modifications dans `packages/api-client/src/index.ts`.

**a.** Étendre `RequestOptions` :

```typescript
  interface RequestOptions {
    query?: Record<string, string>;
    body?: unknown;
    method?: string;
    /** Per-call headers. Only the order endpoints need one, for Idempotency-Key. */
    headers?: Record<string, string>;
  }
```

**b.** Les fusionner dans la construction des en-têtes, après la ligne du jeton :

```typescript
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    Object.assign(headers, options.headers ?? {});
```

**c.** Ajouter les types exportés à côté des autres, puis les trois méthodes avant `myEntitlements` :

```typescript
export type Order = Json<paths["/api/v1/orders"]["post"]["responses"]["201"]>;
export type Receipt = Json<paths["/api/v1/orders/{order_id}/receipt"]["get"]["responses"]["200"]>;
```

```typescript
    /**
     * Place an order. The key makes a retry safe: replaying it returns the same
     * order rather than charging twice (§10.4).
     */
    createOrder: (nasId: string, planVersionId: string, idempotencyKey: string) =>
      request<Order>("/api/v1/orders", {
        body: { nas_id: nasId, plan_version_id: planVersionId },
        headers: { "Idempotency-Key": idempotencyKey },
      }),

    /** Status of an order, for the push wait screen. */
    getOrder: (orderId: string) => request<Order>(`/api/v1/orders/${orderId}`),

    getReceipt: (orderId: string) => request<Receipt>(`/api/v1/orders/${orderId}/receipt`),
```

- [ ] **Step 8: Régénérer le contrat, vérifier, committer**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
ENVIRONMENT=local uv run --directory services/core-api python manage.py spectacular \
  --format openapi --file ../../docs/api/openapi.yaml
pnpm api-client:generate
pnpm typecheck
cd services/core-api && uv run ruff check . && uv run ruff format . && uv run mypy . && uv run pytest
cd ../.. && git add -A
git commit -m "feat: order endpoints with a mandatory idempotency key"
```

---

## Task 9: Parcours d'achat du portail

**Files:**
- Create: `apps/captive-portal/src/pages/achat.astro`
- Modify: `apps/captive-portal/src/pages/index.astro`
- Modify: `apps/captive-portal/src/lib/portal.ts`
- Modify: `services/core-api/apps/core/management/commands/seed_demo_data.py`

**Interfaces:**
- Consumes: client TS `createOrder`, `getOrder`, `getReceipt`
- Produces: écran d'attente sondant `getOrder` jusqu'à un état terminal

- [ ] **Step 1: Ajouter une offre payante aux données de démonstration**

Lire `services/core-api/apps/core/management/commands/seed_demo_data.py`, puis ajouter une offre payante publiée sur la zone de démonstration, sur le modèle de l'offre gratuite déjà présente : `type=Plan.Type.PAID`, `price_xof=500`, `connection_seconds=3600`, `radius_profile_ref="dakar-1h"`, et `plan.zones.add(zone)`.

Vérifier :

```bash
cd /home/youssoupha/projets/Wifi_Dakar && make seed
```
Attendu : le compte d'offres publiées augmente de un.

- [ ] **Step 2: Écrire l'écran d'achat**

Créer `apps/captive-portal/src/pages/achat.astro` en suivant strictement la forme de `src/pages/index.astro` — même `Base.astro`, mêmes classes Tailwind, script en ligne sans dépendance de framework (ADR-0005). Lire `index.astro` d'abord pour reprendre son balisage et ses libellés.

Le balisage doit exposer ces points d'ancrage, sur lesquels le test bout en bout s'appuie :

```html
<section id="attente" hidden>
  <h1>Validez sur votre téléphone</h1>
  <p id="instructions"></p>
  <p id="compte-a-rebours" role="timer"></p>
</section>

<section id="redirection" hidden>
  <h1>Terminez le paiement</h1>
  <p>Ouvrez ce lien dans votre navigateur complet pour terminer le paiement.</p>
  <a id="lien-paiement" href="#" rel="noopener">Ouvrir la page de paiement</a>
</section>

<section id="succes" hidden>
  <h1>Votre accès est activé</h1>
  <p id="recu"></p>
</section>

<section id="echec" hidden>
  <h1>Le paiement n'a pas abouti</h1>
  <p id="raison-echec" role="alert"></p>
</section>
```

Le script, littéralement :

```typescript
const params = new URLSearchParams(location.search);
const nasId = params.get("nas_id") ?? "";
const planVersionId = params.get("offre") ?? "";

const TERMINAL = new Set(["paid", "failed", "expired", "cancelled"]);
const POLL_MS = 3000;

const show = (id: string) => {
  for (const section of document.querySelectorAll<HTMLElement>("section[id]")) {
    section.hidden = section.id !== id;
  }
};

/**
 * Kept for the whole tab: a refresh must not place a second order. The API returns
 * the same order for the same key, so reloading resumes rather than charges again.
 */
const idempotencyKey = (() => {
  const stored = sessionStorage.getItem(`order-key:${planVersionId}`);
  if (stored) return stored;
  const fresh = crypto.randomUUID();
  sessionStorage.setItem(`order-key:${planVersionId}`, fresh);
  return fresh;
})();

let countdown: number | undefined;

function startCountdown(expiresAt: string) {
  const deadline = new Date(expiresAt).getTime();
  const node = document.getElementById("compte-a-rebours")!;
  const tick = () => {
    const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
    const minutes = String(Math.floor(left / 60)).padStart(2, "0");
    node.textContent = `Temps restant : ${minutes}:${String(left % 60).padStart(2, "0")}`;
    if (left === 0) window.clearInterval(countdown);
  };
  tick();
  countdown = window.setInterval(tick, 1000);
}

function fail(message: string) {
  window.clearInterval(countdown);
  document.getElementById("raison-echec")!.textContent = message;
  show("echec");
}

async function succeed(orderId: string) {
  window.clearInterval(countdown);
  const receipt = await client.getReceipt(orderId);
  document.getElementById("recu")!.textContent =
    `Commande ${receipt.order_number} — ${receipt.amount_xof} ${receipt.currency}`;
  show("succes");
}

async function poll(orderId: string, deadline: number) {
  // Bounded on purpose: the screen stops on a terminal status and at the deadline.
  // A portal that polls forever keeps a captive mini-browser awake for nothing.
  if (Date.now() > deadline) return fail("Le délai de paiement est écoulé.");

  const order = await client.getOrder(orderId);

  if (order.status === "paid") {
    // Paid is not yet usable: the right is activated by the outbox, just after.
    if (order.entitlement_status === "active") return succeed(orderId);
  } else if (TERMINAL.has(order.status)) {
    return fail("Le paiement a été refusé ou la commande a expiré.");
  }

  window.setTimeout(() => void poll(orderId, deadline), POLL_MS);
}

async function start() {
  try {
    const order = await client.createOrder(nasId, planVersionId, idempotencyKey);
    const deadline = new Date(order.expires_at).getTime();

    if (order.mode === "redirect") {
      const link = document.getElementById("lien-paiement") as HTMLAnchorElement;
      link.href = order.redirect_url;
      show("redirection");
    } else {
      document.getElementById("instructions")!.textContent = order.instructions;
      show("attente");
      startCountdown(order.expires_at);
    }

    void poll(order.id, deadline);
  } catch {
    fail("La commande n'a pas pu être créée. Réessayez dans un instant.");
  }
}

void start();
```

`client` est l'instance déjà construite par `src/lib/portal.ts` ; reprendre la même importation que dans `index.astro`, et y ajouter le jeton d'accès du citoyen via `setAccessToken` comme le fait déjà le parcours gratuit.

- [ ] **Step 3: Vérifier le budget**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
pnpm --filter @dakar-wifi/captive-portal build
node scripts/check-bundle-budget.mjs apps/captive-portal 150
```
Attendu : sous le budget. La marge de départ est de 146 Ko ; si elle est entamée de plus de quelques kilo-octets, c'est qu'une dépendance a été introduite — la retirer plutôt que relever le budget.

- [ ] **Step 4: Vérifier types et lint, puis committer**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
pnpm lint && pnpm typecheck && pnpm test
git add -A
git commit -m "feat: portal purchase journey with push wait, bounded polling and receipt"
```

---

## Task 10: Bout en bout et clôture de la phase

**Files:**
- Create: `apps/captive-portal/e2e/purchase.spec.ts`
- Modify: `docs/phase0/03-backlog.md`
- Modify: `README.md`
- Modify: `Makefile`

**Interfaces:**
- Consumes: tout ce qui précède

- [ ] **Step 1: Écrire le test bout en bout**

Le test doit déclencher un webhook signé. Reconstruire la signature HMAC en TypeScript dupliquerait le secret dans le portail ; exposer plutôt un déclencheur de développement, gardé deux fois comme l'est déjà `sms_outbox`.

Ajouter à `services/core-api/apps/billing/views.py` :

```python
from django.http import Http404

from apps.billing.providers.mock import MockPaymentProvider


class EmitWebhookSerializer(serializers.Serializer):
    order_number = serializers.CharField()
    status = serializers.ChoiceField(choices=["succeeded", "refused"], default="succeeded")


@extend_schema(exclude=True)
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def emit_demo_webhook(request: Request) -> Response:
    """Development helper: make the mock provider send the webhook it would send.

    Guarded by environment *and* by the configured provider, exactly as the SMS
    outbox is: a route that can mark an order paid must never exist in production.
    """
    if settings.ENVIRONMENT not in ("local", "test") or settings.PAYMENT_PROVIDER != "mock":
        raise Http404

    payload = EmitWebhookSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    order = Order.objects.filter(order_number=payload.validated_data["order_number"]).first()
    if order is None:
        raise Http404

    body, headers = MockPaymentProvider.build_webhook(
        order, status=payload.validated_data["status"]
    )
    result = handle("mock", headers, body)
    return Response({"outcome": result.outcome}, status=result.http_status)
```

Ajouter les imports manquants en tête du fichier (`from django.conf import settings`, `from rest_framework import serializers`) et la route dans `apps/billing/urls.py` :

```python
    path("dev/payments/emit", views.emit_demo_webhook, name="dev-emit-webhook"),
```

Créer `apps/captive-portal/e2e/purchase.spec.ts` :

```typescript
/**
 * End-to-end purchase journey (cahier des charges §16.2, §17 critères 4 à 6).
 *
 * Runs against the real API and the real portal build. The webhook is triggered
 * through the development helper so it is genuinely signed and genuinely verified,
 * rather than the processing function being called directly.
 *
 * Requires `make up && make seed` beforehand.
 */
import { expect, test } from "@playwright/test";

const API = process.env.PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const NAS_ID = "demo-nas-001";

function uniquePhone(): string {
  const suffix = String(Date.now()).slice(-7);
  return `+2217${suffix}`;
}

async function readCode(request: import("@playwright/test").APIRequestContext, phone: string) {
  const response = await request.get(`${API}/api/v1/dev/sms-outbox`);
  expect(response.ok()).toBeTruthy();
  const { messages } = await response.json();
  const mine = [...messages].reverse().find((message) => message.to === phone);
  expect(mine, `no SMS sent to ${phone}`).toBeTruthy();
  return /\b(\d{6})\b/.exec(mine.body)![1];
}

async function signIn(page: import("@playwright/test").Page, request: import("@playwright/test").APIRequestContext, phone: string) {
  await page.goto(`/?nas_id=${NAS_ID}`);
  await page.getByRole("button", { name: "Se connecter gratuitement" }).click();
  await page.getByLabel("Numéro au format international").fill(phone);
  await page.getByLabel(/J’accepte les conditions/).check();
  await page.getByRole("button", { name: "Recevoir un code" }).click();
  await page.getByLabel("Code à six chiffres").fill(await readCode(request, phone));
  await page.getByRole("button", { name: "Valider" }).click();
  await expect(page.getByRole("heading", { name: "Vous êtes connecté" })).toBeVisible();
}

test("un citoyen achète une offre et son accès s'active", async ({ page, request }) => {
  await signIn(page, request, uniquePhone());

  // L'écran d'attente du push, sans redirection : c'est le parcours nominal d'ADR-0004.
  await page.getByRole("button", { name: /1 heure/ }).click();
  await expect(page.getByRole("heading", { name: "Validez sur votre téléphone" })).toBeVisible();
  await expect(page.getByRole("timer")).toContainText("Temps restant");

  // Le prestataire confirme.
  const orderNumber = await page.locator("#attente").getAttribute("data-order-number");
  const emitted = await request.post(`${API}/api/v1/dev/payments/emit`, {
    data: { order_number: orderNumber, status: "succeeded" },
  });
  expect(emitted.ok()).toBeTruthy();

  // Le sondage découvre le paiement, puis l'activation par l'outbox.
  await expect(page.getByRole("heading", { name: "Votre accès est activé" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.locator("#recu")).toContainText(orderNumber!);
});

test("un paiement refusé n'ouvre pas l'accès", async ({ page, request }) => {
  await signIn(page, request, uniquePhone());

  await page.getByRole("button", { name: /1 heure/ }).click();
  const orderNumber = await page.locator("#attente").getAttribute("data-order-number");
  await request.post(`${API}/api/v1/dev/payments/emit`, {
    data: { order_number: orderNumber, status: "refused" },
  });

  await expect(page.getByRole("alert")).toContainText("refusé");
  await expect(page.getByRole("heading", { name: "Votre accès est activé" })).toBeHidden();
});
```

Le test lit le numéro de commande dans un attribut : ajouter dans `achat.astro`, après la création de la commande,

```typescript
    document.getElementById("attente")!.dataset.orderNumber = order.order_number;
```

- [ ] **Step 2: Lancer le parcours**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
make up && make seed && make e2e
```
Attendu : 5 tests verts — les 3 du parcours gratuit, plus les 2 de l'achat. `make e2e` couvre déjà tous les fichiers de `e2e/`, aucune cible supplémentaire n'est nécessaire.

- [ ] **Step 3: Mettre à jour la documentation**

Dans `docs/phase0/03-backlog.md`, marquer les six items DW-P4-01 à DW-P4-06 comme livrés, en suivant la convention déjà utilisée pour les phases 1 à 3.

Dans `README.md`, ajouter le parcours d'achat à la liste de ce qui fonctionne et documenter `PAYMENT_WEBHOOK_SECRET` à côté de `JWT_SIGNING_KEY`.

- [ ] **Step 4: Vérification complète**

```bash
cd /home/youssoupha/projets/Wifi_Dakar
make check
cd services/core-api && uv run pytest
cd ../.. && pnpm lint && pnpm typecheck && pnpm test && pnpm build
node scripts/check-bundle-budget.mjs apps/captive-portal 150
git diff --exit-code docs/api/openapi.yaml packages/api-client/src/schema.d.ts
```
Attendu : tout vert, aucun écart sur le contrat.

- [ ] **Step 5: Committer et pousser**

```bash
git add -A
git commit -m "feat: phase 4 — orders, mock payment and guaranteed activation"
git push origin main
```

- [ ] **Step 6: Lire le résultat réel de la CI**

```bash
gh run watch "$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')"
gh run view "$(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')" \
  --json conclusion,jobs --jq '"RUN: \(.conclusion)", (.jobs[] | "\(.conclusion)\t\(.name)")'
```
Attendu : 7 jobs verts. **Ne pas déclarer la phase terminée sur un vert local** — la Phase 3 a été annoncée close alors que quatre jobs n'avaient jamais exécuté une seule vérification.

---

## Notes de mise en œuvre

**Ce qui est délibérément absent**

- Aucun remboursement simulé : `refund()` lève `NotImplementedError`. Simuler le seul geste irréversible de la chaîne, sans les règles d'habilitation et d'audit du §13.4, donnerait une fausse impression de couverture.
- Aucune migration du chemin gratuit vers l'outbox. L'asymétrie est un choix documenté dans la spécification, pas un reste à nettoyer.
- Aucun `ReconciliationRun` : la tâche de réconciliation existe, ses états et exports appartiennent à la phase 6.

**Le test qui juge l'architecture**

`test_a_payment_confirmed_while_the_network_is_down_recovers` (tâche 6) est le critère 6 du §17. S'il passe alors que les autres échouent, la conception tient. S'il échoue alors que les autres passent, la conception ne sert à rien.

**Ordre des tâches**

Les tâches 1 à 3 sont indépendantes entre elles et peuvent être menées en parallèle. Les tâches 4 à 8 sont séquentielles : chacune consomme les interfaces de la précédente. Les tâches 9 et 10 supposent l'API complète.
