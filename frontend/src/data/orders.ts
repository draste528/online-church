
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
