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

## Analytics (port 8000)
- `GET /api/v1/analytics/orders/summary?days=14&top=5` - counts by status, funnel, revenue, best-selling items,
  daily series and fulfilment times. Code: `analytics/src/api/routes/orders.py`, tests: `analytics/tests/test_orders_summary.py`.
- Reads `shop_orders` and `shop_order_lines`; `shop_order_events` is optional and is picked up automatically once
  SCRUM-27 creates it (`fulfilment.tracking_available` turns true).
- SQL versions of the reports for the DWH: sections 4-6 of `analytics/sql/02_analytical_queries.sql`.
