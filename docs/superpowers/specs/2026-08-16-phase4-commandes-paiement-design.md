# Phase 4 — Commandes, paiement mock et activation garantie

- Date : 2026-08-16
- Statut : conception validée, implémentation à venir
- Sources : cahier des charges v1.1 §8.5, §9, §10.2, §10.4, §11.2, §13.4, §16.1, §17
- Décisions antérieures : [ADR-0004](../../adr/0004-paiement-push-nominal.md) (paiement par push),
  [ADR-0006](../../adr/0006-integration-openwisp.md) (frontière OpenWISP),
  [ADR-0007](../../adr/0007-comptes-citoyens-et-otp.md) (comptes citoyens)
- Backlog couvert : DW-P4-01 à DW-P4-06
- Critères d'acceptation visés : §17 nos 4, 5 et 6

---

## 1. Le problème que cette phase résout

Jusqu'ici la plateforme ne manipule que des droits gratuits. Un échec d'activation y est
acceptable : le citoyen ne perd rien, on lui dit de réessayer.

À partir du moment où de l'argent est encaissé, cette forme devient une faute. Le §8.5
l'énonce sans détour : « Reprise automatique si le paiement est confirmé mais que RADIUS
est temporairement indisponible ». Un refus après encaissement, c'est un client qui a payé
et n'a rien reçu — et aucune quantité de journalisation ne répare cela après coup.

Toute la conception de cette phase découle de cette seule contrainte.

### 1.1 La règle structurante

Le chemin gratuit actuel ([`free_access.py`](../../../services/core-api/apps/access/free_access.py))
crée le droit, committe, puis appelle le réseau. Si l'appel échoue, il marque
`activation_failed` et refuse. C'est correct pour du gratuit.

Le chemin payant inverse la responsabilité :

```
Webhook validé
      │
      ├──────── UNE seule transaction ────────┐
      │  Order          → paid                │
      │  Payment        → succeeded           │
      │  Entitlement    → pending_activation  │
      │  OutboxMessage  → entitlement.activate│
      │  WebhookEvent   → processed           │
      └───────────────── commit ──────────────┘
                          │
                          ▼
              Worker draine l'outbox
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        activation OK           échec réseau
     Entitlement → active    ré-essai avec backoff
                             (jamais de perte)
```

**Rien de faillible n'est appelé avant le commit. Rien de committé n'est perdu si
l'appel échoue.** L'`OutboxMessage` est ce qui transforme une indisponibilité réseau en
retard plutôt qu'en perte.

C'est le miroir des deux défauts corrigés en Phase 3, où `@transaction.atomic` suivi d'une
exception annulait la garde qu'on venait d'écrire. Là je committais trop tard ; ici je
m'interdis d'appeler l'extérieur avant d'avoir committé.

### 1.2 Asymétrie assumée entre gratuit et payant

Le chemin gratuit **ne migre pas** vers l'outbox. Il garde son activation synchrone qui
peut refuser.

Les unifier ferait attendre une attribution gratuite pour une garantie dont elle n'a pas
besoin : personne n'a payé, l'échec immédiat est la bonne réponse, et un écran d'attente
sur une offre gratuite dégraderait le parcours le plus fréquent du portail. L'asymétrie
est le choix, pas un reste à nettoyer.

---

## 2. Périmètre

### 2.1 Livré en Phase 4

| Item | Contenu |
|---|---|
| DW-P4-01 | `Order`, ses états, l'expiration des `pending`, l'`Idempotency-Key` |
| DW-P4-02 | Contrat `PaymentProvider` (push et redirection) + `MockPaymentProvider` |
| DW-P4-03 | Webhooks signés : signature, montant, devise, idempotence, historique, post-expiration |
| DW-P4-04 | `Entitlement` payant, outbox transactionnelle, activation idempotente |
| DW-P4-05 | Portail : écran d'attente push, sondage de statut, repli redirection, reçu |
| DW-P4-06 | E2E achat complet sur le mock |

### 2.2 Explicitement hors périmètre

| Sujet | Renvoyé à | Raison |
|---|---|---|
| Remboursements effectifs | Phase 6 (DW-P6-03) | Exigent habilitation et audit (§8.5, §13.4) qui n'existent pas encore. `refund()` figure au contrat comme l'impose le §8.5 ; le mock lève `NotImplementedError`. |
| Rapprochement financier complet et exports | Phase 6 (DW-P6-03) | Phase 4 pose la tâche de réconciliation des `pending`, pas les états ni les exports. |
| Comptage d'appareils (§8.4 `max_devices`) | Phase 5 | La MAC du client n'est pas transmise sans passerelle réelle. Inchangé depuis la Phase 3. |
| Export et suppression de compte (§8.1) | Après Phase 4 | La suppression d'un compte porteur de commandes est une anonymisation avec conservation des pièces financières. L'écrire avant le modèle de commande garantirait de la réécrire. |
| Activation RADIUS réelle | Phase 5 | Le `MockNetworkProvider` couvre déjà les sept modes d'échec du §11.3. |

---

## 3. Frontières de code

### 3.1 Nouvel app `apps/billing`

`Order`, `Payment` et `WebhookEvent` vivent dans un seul app. Ils changent ensemble et
n'ont pas de sens séparément : une commande sans paiement n'est pas une commande, un
webhook sans commande à rapprocher n'est pas exploitable.

```
apps/billing/
├── models.py          Order, Payment, WebhookEvent
├── orders.py          création, idempotence, transitions d'état
├── webhooks.py        réception, vérification, traitement idempotent
├── tasks.py           expiration, réconciliation
├── serializers.py
├── views.py
├── urls.py
├── admin.py
└── providers/
    ├── base.py        PaymentProvider (ABC) + dataclasses + exceptions
    ├── mock.py        MockPaymentProvider
    └── __init__.py    get_payment_provider() depuis settings.PAYMENT_PROVIDER
```

`providers/` reprend exactement la forme de [`apps/access/providers/`](../../../services/core-api/apps/access/providers/) :
classe abstraite, dataclasses gelées, hiérarchie d'exceptions avec attribut `retryable`,
fabrique lisant les réglages. Le réglage `PAYMENT_PROVIDER` existe déjà dans
[`base.py`](../../../services/core-api/config/settings/base.py).

### 3.2 L'outbox va dans `apps/core`, pas dans `billing`

`OutboxMessage` est un mécanisme générique, pas un objet financier. Le §11.2 le désigne
comme le support de la synchronisation réseau, dont la Phase 5 aura besoin pour OpenWISP
et la Phase 6 pour les vouchers.

Il reste toutefois **minimal** : un seul sujet est enregistré en Phase 4
(`entitlement.activate`). Le registre de handlers est un dictionnaire, pas un système de
plugins.

```
apps/core/
├── models.py     + OutboxMessage
├── outbox.py       enqueue(), registre des handlers, drain()
└── tasks.py        drain_outbox (Celery)
```

### 3.3 Ce que `apps/access` reçoit

`Entitlement` gagne un lien optionnel vers la commande qui l'a produit, et le handler
d'activation :

```
apps/access/
├── models.py       + Entitlement.order (OneToOne, nullable)
└── activation.py     handler entitlement.activate, idempotent
```

Le lien est un `OneToOneField` et non un `ForeignKey` : « activation du forfait une seule
fois » (§8.5) devient alors une contrainte de base de données et non une convention de
code. Deux webhooks concurrents pour la même commande ne peuvent pas créer deux droits,
même si la logique applicative se trompe.

---

## 4. Modèle de données

Reprend les entités du §9 sans renommage. Identifiants UUID, montants entiers en XOF
(règle 8 du §1), horodatages UTC.

### 4.1 `Order`

| Champ | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `order_number` | CharField unique | Numéro interne lisible (§8.5). Format `DW-AAAAMM-NNNNNN`, la partie séquentielle venant d'une séquence PostgreSQL et non d'un `COUNT` : deux commandes simultanées ne doivent pas pouvoir tirer le même numéro. |
| `citizen` | FK PROTECT | |
| `plan_version` | FK PROTECT | Jamais `Plan` : un changement de tarif ne doit pas être rétroactif (§8.3, test §16.1). |
| `zone` | FK PROTECT | Zone d'achat, portée du droit produit. |
| `amount_xof` | PositiveInteger | Copié de `plan_version.price_xof` à la création, jamais relu ensuite. |
| `currency` | CharField(3) | Comparé strictement au webhook (§8.5). |
| `status` | CharField | Voir 4.2. |
| `idempotency_key` | CharField | Unique par citoyen (§10.4). |
| `expires_at` | DateTime | `created_at` + TTL configurable. |
| `paid_at`, `cancelled_at`, `expired_at` | DateTime null | |
| `reactivated_after_expiry` | Boolean | Marque le cas du §8.5 pour le rapprochement. |

Contraintes : `UniqueConstraint(citizen, idempotency_key)`, index sur
`(status, expires_at)` pour la tâche d'expiration, index sur `(citizen, -created_at)`.

### 4.2 États et transitions

Les neuf états du §8.5 sont **tous déclarés**, sept sont câblés. `refunded` et
`partially_refunded` restent sans transition jusqu'à la Phase 6 mais figurent dans
l'énumération dès maintenant : migrer un champ d'état sur des données financières
existantes coûte plus cher que de déclarer deux valeurs inertes.

```
draft ──create_payment──> pending ──────webhook succès─────> paid
  │                          │                                 │
  │                          ├──repli redirection──> requires_action
  │                          │                          │      │
  │                          │                          └──────┤
  │                          ├──webhook refus─────────> failed │
  │                          ├──TTL dépassé───────────> expired│
  │                          │                             │   │
  │                          │        webhook succès tardif│   │
  │                          │        (§8.5, réactivation) └───┤
  └──annulation citoyen─────────────────────────────> cancelled│
                                                               │
                                          Phase 6 ─────────────┴──> refunded
                                                                    partially_refunded
```

Les transitions sont concentrées dans `orders.py` : aucun `save()` d'état ailleurs. Toute
transition invalide lève, elle n'est pas silencieusement ignorée.

### 4.3 `Payment`

| Champ | Notes |
|---|---|
| `order` | FK CASCADE |
| `provider` | Nom de l'adaptateur |
| `mode` | `push` ou `redirect` (ADR-0004) |
| `external_reference` | Référence prestataire, indexée |
| `amount_xof`, `fees_xof` | Entiers |
| `status` | `initiated`, `succeeded`, `refused`, `expired` |

Plusieurs tentatives sont possibles sur une même commande : le repli redirection après un
push non abouti crée un second `Payment`, pas une seconde `Order`.

### 4.4 `WebhookEvent` — historique complet *et* traitement unique

Le §8.5 demande deux choses qui semblent s'opposer : conserver **tous** les webhooks, y
compris doublons et échecs de validation, mais n'activer le droit qu'une fois.

La résolution est une ligne par livraison, plus un index unique partiel sur le traitement :

| Champ | Notes |
|---|---|
| `provider` | |
| `external_event_id` | Identifiant d'événement du prestataire |
| `order` | FK null (un webhook peut ne rapprocher aucune commande) |
| `signature_valid` | Booléen, faux également conservé |
| `outcome` | `processed`, `duplicate`, `bad_signature`, `amount_mismatch`, `unknown_order`, `ignored` |
| `payload` | JSON **minimisé** — voir 4.5 |
| `body_sha256` | Empreinte du corps brut |
| `received_at`, `processed_at` | |

```python
UniqueConstraint(
    fields=["provider", "external_event_id"],
    condition=Q(outcome="processed"),
    name="one_processed_delivery_per_event",
)
```

Un seul enregistrement peut porter `outcome=processed` pour un identifiant d'événement
donné. L'historique reste complet, l'unicité du traitement est garantie par la base et non
par une vérification applicative sujette aux courses. C'est ce qui satisfait le critère 5
du §17 — « un webhook dupliqué n'active jamais deux droits » — indépendamment du code.

### 4.5 Ce qui est conservé d'un webhook

Le §9 exige l'historique complet mais interdit de stocker une copie intégrale d'un webhook
porteur de secrets si une version minimisée suffit, et impose un chiffrement applicatif
sinon.

Décision : stocker une **projection minimisée** — identifiant d'événement, statut, montant,
devise, référence externe, horodatage prestataire — accompagnée du `sha256` du corps brut.
Une enquête peut confirmer qu'un corps donné correspond à un événement enregistré sans que
la plateforme conserve ni en-tête de signature, ni jeton, ni donnée porteuse de secret. Le
chiffrement applicatif devient inutile, donc n'est pas introduit.

### 4.6 `OutboxMessage`

| Champ | Notes |
|---|---|
| `topic` | `entitlement.activate` en Phase 4 |
| `payload` | JSON, identifiants uniquement |
| `status` | `pending`, `processing`, `done`, `failed` |
| `attempts` | |
| `available_at` | Prochaine tentative ; backoff exponentiel |
| `last_error` | Tronqué |

Index sur `(status, available_at)`. Le drain sélectionne avec `select_for_update(skip_locked=True)`
pour que plusieurs workers puissent tirer sans se bloquer ni traiter deux fois la même ligne.

---

## 5. Contrat `PaymentProvider`

Signature imposée par le §8.5 :

```python
class PaymentProvider(ABC):
    name: str

    def create_payment(self, order) -> PaymentIntent: ...
    def get_payment_status(self, external_reference: str) -> PaymentStatus: ...
    def verify_webhook(self, headers: Mapping[str, str], body: bytes) -> bool: ...
    def parse_webhook(self, body: bytes) -> WebhookPayload: ...
    def refund(self, payment, amount_xof: int) -> RefundResult: ...
    def healthcheck(self) -> bool: ...
```

`PaymentIntent` porte le mode retenu par le prestataire :

```python
@dataclass(frozen=True)
class PaymentIntent:
    mode: str                  # "push" | "redirect"
    external_reference: str
    redirect_url: str = ""     # renseigné en mode redirect uniquement
    instructions: str = ""     # message d'attente en mode push
```

Hiérarchie d'exceptions calquée sur `NetworkError` : `PaymentError` avec attribut
`retryable`, spécialisée en `PaymentTimeout`, `PaymentTemporaryError`,
`PaymentPermanentError`, `PaymentRefused`.

### 5.1 Scénarios du `MockPaymentProvider`

Pilotés par un attribut de classe `scenario`, exactement comme le
[`MockNetworkProvider`](../../../services/core-api/apps/access/providers/mock.py), avec
`reset()` entre les tests.

| Scénario | Couvre |
|---|---|
| `push_success` | §16.1 push succès |
| `push_refused` | §16.1 push refus |
| `push_timeout` | §16.1 push timeout — aucun webhook, la commande expire |
| `push_abandoned` | §16.1 fermeture du mini-navigateur pendant l'attente |
| `redirect_required` | Parcours de repli d'ADR-0004 |
| `provider_unavailable` | `create_payment` lève une erreur re-essayable |

Le mock expose en outre une méthode de test construisant un corps de webhook **signé**
pour une commande et une issue données. Les tests le postent réellement sur l'endpoint :
la vérification de signature est ainsi exercée pour de vrai, et non contournée par un
appel direct à la fonction de traitement. Les cas signature invalide, doublon, montant
divergent et arrivée après expiration se construisent depuis ce même point.

---

## 6. Traitement d'un webhook

`POST /api/v1/webhooks/payments/{provider}` — sans authentification, la confiance repose
entièrement sur la signature (règle 10 du cahier des charges).

1. Prestataire inconnu → `404`, rien enregistré.
2. `verify_webhook` échoue → `WebhookEvent(outcome=bad_signature)`, `400`. Un `400` plutôt
   qu'un `500` : une signature invalide ne deviendra jamais valide, faire ré-essayer le
   prestataire n'a pas de sens.
3. `parse_webhook` → commande introuvable → `outcome=unknown_order`, `404`.
4. Montant, devise ou bénéficiaire divergents → `outcome=amount_mismatch`, `400`. La
   comparaison est stricte, jamais tolérante (§8.5). Le montant et la devise attendus sont
   ceux figés sur la commande à sa création ; le bénéficiaire attendu est une propriété de
   l'adaptateur (`PaymentProvider.expected_payee`), puisqu'il désigne le compte marchand de
   la plateforme chez ce prestataire et non une donnée de la commande.
5. Un enregistrement `processed` existe déjà pour cet identifiant d'événement →
   `outcome=duplicate`, `200`. Le prestataire ne doit pas ré-essayer : le traitement a eu
   lieu.
6. Sinon, **une transaction** applique le bloc du §1.1 puis committe.
7. `transaction.on_commit` publie la tâche de drain — chemin rapide. Le battement Celery
   reste le filet de sécurité si le worker est tombé.

### 6.1 Webhook reçu avant le retour navigateur

Cas nommé du §16.1. Il ne demande aucun traitement particulier : la commande est créée
*avant* l'initiation du paiement, donc elle existe déjà lorsque le webhook arrive. Le
sondage du portail découvre simplement une commande déjà `paid`. Un test le fixe pour que
la propriété reste vraie.

### 6.2 Webhook reçu après expiration

Cas nommé du §8.5 et du §16.1. La commande `expired` repasse à `paid`, le droit est créé
et activé une seule fois, `reactivated_after_expiry` est positionné, un enregistrement
d'audit est écrit et la commande est marquée pour le rapprochement de la Phase 6.

Le client a payé : lui refuser son accès parce qu'une minuterie interne a expiré serait la
mauvaise réponse.

---

## 7. Tâches planifiées

Premier `beat_schedule` du projet — il n'en existe aucun aujourd'hui.

| Tâche | Cadence | Rôle |
|---|---|---|
| `core.drain_outbox` | 30 s + `on_commit` | Draine l'outbox. Le battement est le filet de reprise ; `on_commit` donne la latence. |
| `billing.expire_pending_orders` | 1 min | `pending`/`requires_action` échues → `expired` (§8.5). |
| `billing.reconcile_pending_payments` | 5 min | Interroge `get_payment_status` pour les commandes restées `pending` au-delà d'un seuil (§8.5). |

Le drain applique un backoff exponentiel borné. Au-delà du nombre maximal de tentatives,
le message passe `failed` et devient visible dans l'administration : une activation
définitivement bloquée doit atterrir devant un exploitant, pas disparaître.

---

## 8. API

| Endpoint | Auth | Notes |
|---|---|---|
| `POST /api/v1/orders` | citoyen | En-tête `Idempotency-Key` obligatoire. Crée la commande et initie le paiement. |
| `GET /api/v1/orders/{id}` | citoyen | Sondage de statut. Rend l'état de commande et celui du droit. |
| `GET /api/v1/orders/{id}/receipt` | citoyen | Reçu (§8.5). |
| `POST /api/v1/webhooks/payments/{provider}` | signature | Voir §6. |

Un citoyen ne peut lire que ses propres commandes : le filtrage est fait sur la requête,
jamais sur un identifiant fourni par le client.

Le schéma de sécurité `citizenToken` s'applique aux trois premiers ; l'endpoint webhook
déclare une sécurité vide et documentée. Les tests de contrat ajoutés au commit `ad420ef`
étendent automatiquement leur couverture aux nouveaux endpoints protégés.

---

## 9. Portail

Trois écrans s'ajoutent au parcours existant, dans la même contrainte de budget §12.1
(150 Ko gzip ; le portail est aujourd'hui à 3,7 Ko).

1. **Choix de l'offre** — les offres payantes de la zone, déjà servies par le contexte.
2. **Attente du push** — instruction, sondage du statut, compte à rebours jusqu'à
   l'expiration. Le sondage s'arrête sur un état terminal, jamais indéfiniment.
3. **Résultat** — accès actif et reçu, ou échec avec la raison et une reprise possible.

Le repli redirection affiche le lien avec l'incitation à ouvrir le navigateur complet
(ADR-0004). Les domaines de redirection devront figurer au walled garden par zone
(§13.2) : c'est une entrée de la Phase 5, notée ici pour ne pas être découverte alors.

---

## 10. Tests

### 10.1 Correspondance avec le §16.1

| Exigence §16.1 | Test |
|---|---|
| Achat réussi, échoué, annulé, expiré | `billing/tests/test_order_lifecycle.py` |
| Webhook valide, invalide, dupliqué | `billing/tests/test_webhooks.py` |
| Webhook reçu avant le retour navigateur | `test_webhooks.py` |
| Webhook après expiration : réactivation, activation unique, journalisation | `test_webhooks.py` |
| Push : succès, refus, timeout, fermeture du mini-navigateur | `billing/tests/test_payment_provider.py` |
| Paiement confirmé alors qu'OpenWISP est indisponible, puis reprise | `core/tests/test_outbox.py` |
| Activation RADIUS idempotente | `access/tests/test_activation.py` |
| Changement de tarif sans effet rétroactif | `test_order_lifecycle.py` |

### 10.2 Le test qui compte le plus

Celui du critère 6 du §17, qui exerce la raison d'être de toute la conception :

> `MockNetworkProvider.scenario = "temporary_error"` ; le webhook est traité ; la commande
> est `paid` et le droit existe en `pending_activation` ; le drain échoue et replanifie ;
> le scénario repasse à `success` ; le drain suivant active le droit. **Aucun paiement
> perdu, aucune double activation.**

Un test qui vérifierait seulement le chemin nominal ne dirait rien de l'architecture. La
Phase 3 l'a montré deux fois : les deux défauts corrigés n'étaient visibles que par un test
observant l'état **après** un refus.

### 10.3 Bout en bout (§16.2)

Ajout au parcours Playwright existant : connexion → achat → webhook → activation → statut,
sur le même profil Android d'entrée de gamme.

---

## 11. Réglages introduits

| Réglage | Défaut | Source |
|---|---|---|
| `ORDER_PENDING_TTL_SECONDS` | 1800 | §8.5, valeur à valider par prestataire |
| `PAYMENT_WEBHOOK_SECRET` | sentinelle refusée en production | §13.1 |
| `OUTBOX_MAX_ATTEMPTS` | 10 | |
| `OUTBOX_BACKOFF_BASE_SECONDS` | 5 | |
| `PAYMENT_RECONCILE_AFTER_SECONDS` | 300 | §8.5 |

`PAYMENT_PROVIDER` existe déjà. Le secret de webhook suit la forme déjà retenue pour
`JWT_SIGNING_KEY` : une sentinelle explicite en développement, dont `production.py` refuse
le démarrage.

---

## 12. Risques

| Risque | Traitement |
|---|---|
| Course entre deux webhooks concurrents | `OneToOneField` sur `Entitlement.order` et index unique partiel sur `WebhookEvent` : la base tranche, pas le code. |
| Outbox bloquée sans que personne ne le voie | Passage à `failed` après épuisement des tentatives, visible en administration. Compteur exposé pour supervision. |
| Sondage du portail sans fin | Arrêt sur état terminal et à l'expiration ; le client ne sonde jamais indéfiniment. |
| Format de signature réel divergeant du mock | Le contrat isole `verify_webhook` ; la Phase 7 valide chaque prestataire en bac à sable avant engagement (ADR-0004). |
| Budget du portail dépassé par les nouveaux écrans | Contrôle §12.1 déjà en CI, bloquant. Marge actuelle : 146 Ko. |

---

## 13. Ce dont dépend la suite

À la fin de cette phase, les critères 1 à 5 du §17 sont démontrables sur le terrain, et le
critère 6 l'est en simulation. La Phase 5 remplace le `MockNetworkProvider` par OpenWISP
sans toucher au code métier : c'est précisément ce que la frontière d'ADR-0006 et l'outbox
rendent possible.
