import type { OrderDetails } from '../api';
/**
 * Mock order data for FE-004.
 * Remove the mock mode after BE-005 is merged.
 */

export const MOCK_ORDER = {
  order_id: '550e8400-e29b-41d4-a716-446655440000',
  status: 'accepted',
  created_at: '2026-11-06T10:00:00Z',
  total: 12.5,

  lines: [
    {
      item_id: '11111111-1111-4111-8111-111111111111',
      title: 'Свеча восковая',
      quantity: 2,
      unit_price: 3,
      line_total: 6,
    },
    {
      item_id: '22222222-2222-4222-8222-222222222222',
      title: 'Ладан',
      quantity: 1,
      unit_price: 6.5,
      line_total: 6.5,
    },
  ],

  history: [
    {
      status: 'accepted',
      at: '2026-11-06T10:00:00Z',
      note: null,
    },
  ],
};

/**
 * Save mock orders in the current browser tab.
 * Data survives page refreshes during development.
 */

const MOCK_ORDERS_KEY = 'church_mock_orders';

export function saveMockOrder(order: OrderDetails): void {
  try {
    const saved = sessionStorage.getItem(MOCK_ORDERS_KEY);

    const orders: Record<string, OrderDetails> = saved
      ? JSON.parse(saved)
      : {};

    orders[order.order_id] = order;

    sessionStorage.setItem(
      MOCK_ORDERS_KEY,
      JSON.stringify(orders)
    );
  } catch (error) {
    console.warn('Failed to save mock order', error);
  }
}

/**
 * Find an order by its full UUID.
 * Returns null when the order does not exist.
 */
export function getMockOrder(
  orderId: string
): OrderDetails | null {
  if (orderId === MOCK_ORDER.order_id) {
    return MOCK_ORDER as OrderDetails;
  }

  try {
    const saved = sessionStorage.getItem(MOCK_ORDERS_KEY);

    if (!saved) return null;

    const orders = JSON.parse(saved) as Record<
      string,
      OrderDetails
    >;

    return orders[orderId] ?? null;
  } catch {
    return null;
  }
}
