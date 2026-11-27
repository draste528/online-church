import { AUTH_MOCK_ROLE } from '../config';
import type { Appointment, AppointmentAction, AppointmentType, Priest, Slot } from '../appointments/api';
import { localDateInMoscow } from '../appointments/presentation';

const priest: Priest = {
  user_id: '8c40a9dd-e193-4a31-a088-9eebeaef3522', first_name: 'Иоанн', last_name: 'Петров',
};
const parishioner = {
  user_id: '103bcf9a-bd1c-49f5-b9f6-1a5d2de8c009', first_name: 'Анна', last_name: 'Иванова',
};
const slots: Slot[] = [];
const appointments: Appointment[] = [];
const idempotency = new Map<string, { body: string; result: { appointment_id: string; status: 'requested' } }>();

if (AUTH_MOCK_ROLE === 'priest') {
  const scheduledAt = new Date(Date.now() + 2 * 60 * 60 * 1000);
  scheduledAt.setUTCSeconds(0, 0);
  scheduledAt.setUTCMinutes(scheduledAt.getUTCMinutes() < 30 ? 30 : 60);
  const appointmentId = crypto.randomUUID();
  slots.push({ slot_id: crypto.randomUUID(), scheduled_at: scheduledAt.toISOString(), is_free: false });
  appointments.push({
    appointment_id: appointmentId, scheduled_at: scheduledAt.toISOString(), created_at: new Date().toISOString(),
    appointment_type: 'pastoral_talk', status: 'requested', priest, parishioner,
  });
}

const response = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});
const apiError = (status: number, code?: string) => response(status, {
  detail: code ? { code, message: code } : status === 422 ? [{ loc: ['body', 'scheduled_at'], msg: 'invalid', type: 'value_error' }] : 'Request failed',
});

function seedSlot(date: string): Slot | null {
  let scheduledAt = new Date(`${date}T10:00:00+03:00`);
  while (scheduledAt.getTime() <= Date.now() && localDateInMoscow(scheduledAt) === date) {
    scheduledAt = new Date(scheduledAt.getTime() + 30 * 60 * 1000);
  }
  if (localDateInMoscow(scheduledAt) !== date) return null;
  return { slot_id: crypto.randomUUID(), scheduled_at: scheduledAt.toISOString(), is_free: true };
}

export async function appointmentsMock(path: string, init: RequestInit): Promise<Response> {
  const url = new URL(path, 'http://appointments.local');
  const method = init.method ?? 'GET';
  if (url.pathname === '/priests' && method === 'GET') return response(200, [priest]);
  if (url.pathname === '/appointments/slots' && method === 'GET') {
    const date = url.searchParams.get('date') ?? '';
    const values = slots.filter(slot => localDateInMoscow(new Date(slot.scheduled_at)) === date);
    if (AUTH_MOCK_ROLE === 'priest') {
      if (values.length) return response(200, values);
      const slot = seedSlot(date);
      if (slot) { slots.push(slot); return response(200, [slot]); }
      return response(200, []);
    }
    const free = values.filter(slot => slot.is_free);
    if (free.length) return response(200, free);
    const scheduledAt = new Date(`${date}T07:00:00.000Z`);
    if (scheduledAt.getTime() <= Date.now()) return response(200, []);
    const slot = { slot_id: crypto.randomUUID(), scheduled_at: scheduledAt.toISOString(), is_free: true };
    slots.push(slot);
    return response(200, [slot]);
  }
  if (url.pathname === '/appointments/slots' && method === 'POST') {
    const body = JSON.parse(String(init.body ?? '{}')) as { scheduled_at?: string };
    if (!body.scheduled_at || !Number.isFinite(Date.parse(body.scheduled_at))) return apiError(422);
    if (slots.some(slot => slot.scheduled_at === new Date(body.scheduled_at!).toISOString())) return apiError(409, 'SLOT_ALREADY_EXISTS');
    const slot: Slot = { slot_id: crypto.randomUUID(), scheduled_at: new Date(body.scheduled_at).toISOString(), is_free: true };
    slots.push(slot);
    return response(201, slot);
  }
  const closeMatch = url.pathname.match(/^\/appointments\/slots\/([^/]+)$/);
  if (closeMatch && method === 'DELETE') {
    const slot = slots.find(item => item.slot_id === closeMatch[1]);
    if (!slot) return apiError(404);
    if (!slot.is_free) return apiError(409, 'SLOT_NOT_CLOSABLE');
    slots.splice(slots.indexOf(slot), 1);
    return response(204);
  }
  if (url.pathname === '/appointments' && method === 'POST') {
    const body = JSON.parse(String(init.body ?? '{}')) as { priest_id: string; scheduled_at: string; appointment_type: AppointmentType };
    const key = new Headers(init.headers).get('Idempotency-Key') ?? '';
    const bodyText = JSON.stringify(body);
    const prior = idempotency.get(key);
    if (prior) return prior.body === bodyText ? response(201, prior.result) : apiError(409, 'IDEMPOTENCY_KEY_REUSED');
    const slot = slots.find(item => item.scheduled_at === new Date(body.scheduled_at).toISOString());
    if (!slot) return apiError(404);
    if (!slot.is_free) return apiError(409, 'SLOT_TAKEN');
    slot.is_free = false;
    const result = { appointment_id: crypto.randomUUID(), status: 'requested' as const };
    const item: Appointment = {
      ...result, scheduled_at: slot.scheduled_at, created_at: new Date().toISOString(),
      appointment_type: body.appointment_type, priest,
      parishioner: { ...parishioner, user_id: AUTH_MOCK_ROLE === 'parishioner' ? parishioner.user_id : crypto.randomUUID() },
    };
    appointments.unshift(item);
    idempotency.set(key, { body: bodyText, result });
    return response(201, result);
  }
  if (url.pathname === '/appointments' && method === 'GET') {
    const limit = Number(url.searchParams.get('limit') ?? 20);
    const offset = Number(url.searchParams.get('offset') ?? 0);
    const visible = appointments.filter(item => AUTH_MOCK_ROLE === 'priest' || item.parishioner.user_id === parishioner.user_id);
    return response(200, { items: visible.slice(offset, offset + limit), total: visible.length, limit, offset });
  }
  const updateMatch = url.pathname.match(/^\/appointments\/([^/]+)$/);
  if (updateMatch && method === 'PATCH') {
    const item = appointments.find(value => value.appointment_id === updateMatch[1]);
    if (!item) return apiError(404);
    const body = JSON.parse(String(init.body ?? '{}')) as { status?: AppointmentAction };
    const allowed = item.status === 'requested' && ['approved', 'rejected'].includes(body.status ?? '')
      || item.status === 'approved' && body.status === 'completed';
    if (!allowed) return apiError(409, 'INVALID_TRANSITION');
    item.status = body.status!;
    return response(200, item);
  }
  return apiError(404);
}
