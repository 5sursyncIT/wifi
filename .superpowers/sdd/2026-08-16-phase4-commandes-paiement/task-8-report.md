# Task 8 report — Order API

## Status

Complete.

## Delivered

- Added authenticated `POST /api/v1/orders`, `GET /api/v1/orders/{order_id}`, and
  `GET /api/v1/orders/{order_id}/receipt` endpoints.
- Required `Idempotency-Key`, resolved zones from `nas_id`, and scoped reads to the
  authenticated citizen.
- Added order/request/receipt serializers and preserved the public payment webhook.
- Added the prescribed order API and authentication-contract tests.
- Regenerated `docs/api/openapi.yaml` and `packages/api-client/src/schema.d.ts`.
- Added `createOrder`, `getOrder`, and `getReceipt` to the TypeScript API client.

## TDD evidence

- RED: the new order API suite failed on the missing `/api/v1/orders` route (404).
- GREEN: the targeted order/schema suite passed (26 tests).
- Full API suite: 203 tests passed.

## Verification

- `pnpm typecheck`: passed.
- `uv run --directory services/core-api ruff check .`: passed.
- `uv run --directory services/core-api ruff format --check .`: passed.
- `uv run --directory services/core-api mypy .`: passed (115 files).
- `make test-api`: passed (203 tests).
- `git diff --check`: passed.

## Self-review

No blocking findings. `place_order` can legally return no payment for a replayed
cancelled draft, so the API returns an empty payment mode/instructions in that edge
case rather than dereferencing `None`. The view deliberately has no outer transaction,
preserving commit-before-provider behavior.
