# Order tracking

Shared branch: `feature/order-tracking` (backend SCRUM-27, frontend SCRUM-28, tests SCRUM-29).

## Statuses
`accepted` -> `assembling` -> `ready` -> `completed`; `cancelled` only from `accepted` or `assembling`.
Any other transition returns 409. Cancelling returns items to stock.

## API
- `GET /api/v1/orders/{order_id}` -> 200 `{order_id, status, created_at, total, lines[], history[{status, at, note}]}`, 404 if not found, 422 for an invalid UUID.
- `PATCH /api/v1/orders/{order_id}/status` body `{status, note?}` (note <= 200 chars) -> 200 / 404 / 409 / 422.

## Frontend
- `/orders` - search by order number, `/orders/:orderId` - status stepper, lines, total, history.
- Mock mode: `ORDER_TRACKING_MOCK` in `src/config.ts` until the backend part is merged.
