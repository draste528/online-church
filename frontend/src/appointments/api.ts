import { authFetch } from '../api';
import { APPOINTMENTS_MOCK, AUTH_MOCK } from '../config';
import { AuthError } from '../auth/client';

export interface Priest {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
}

export interface Slot {
  slot_id: string;
  scheduled_at: string;
  is_free: boolean;
}

export interface AppointmentPerson {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
}

export type AppointmentType = 'confession' | 'pastoral_talk' | 'baptism_counseling';
export type AppointmentStatus = 'requested' | 'approved' | 'rejected' | 'completed';
export type AppointmentAction = 'approved' | 'rejected' | 'completed';

export interface Appointment {
  appointment_id: string;
  scheduled_at: string;
  created_at: string;
  appointment_type: AppointmentType;
  status: AppointmentStatus;
  priest: AppointmentPerson;
  parishioner: AppointmentPerson;
}

export interface AppointmentPage {
  items: Appointment[];
  total: number;
  limit: number;
  offset: number;
}

export interface AppointmentCreated {
  appointment_id: string;
  status: 'requested';
}

export class AppointmentApiError extends Error {
  constructor(
    public status: number | 'network',
    public code?: string,
    public fields: Record<string, string> = {},
  ) {
    super(typeof status === 'number' ? `Appointment API HTTP ${status}` : 'Appointment API network error');
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    if (APPOINTMENTS_MOCK && AUTH_MOCK) {
      response = await (await import('../data/appointmentsMock')).appointmentsMock(path, init);
    } else {
      response = await authFetch(`/api/v1${path}`, init);
    }
  } catch (error) {
    // authFetch owns refresh, logout and safe redirect behavior for 401s.
    if (error instanceof AuthError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new AppointmentApiError('network');
  }
  if (!response.ok) {
    let code: string | undefined;
    const fields: Record<string, string> = {};
    try {
      const body = await response.json();
      const detail = body?.detail;
      if (typeof detail?.code === 'string') code = detail.code;
      if (Array.isArray(detail)) {
        for (const item of detail) {
          const field = item.loc?.at(-1);
          if (typeof field === 'string') fields[field] = 'invalid';
        }
      }
    } catch { /* Status is enough to show the translated fallback. */ }
    throw new AppointmentApiError(response.status, code, fields);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getPriests(signal?: AbortSignal): Promise<Priest[]> {
  return request('/priests', { signal });
}

export function getSlots(priestId: string, date: string, signal?: AbortSignal): Promise<Slot[]> {
  const query = new URLSearchParams({ priest_id: priestId, date });
  return request(`/appointments/slots?${query}`, { signal });
}

export function getAppointments(signal?: AbortSignal): Promise<AppointmentPage> {
  return request('/appointments?limit=100&offset=0', { signal });
}

export function createAppointment(
  value: { priest_id: string; scheduled_at: string; appointment_type: AppointmentType },
  idempotencyKey: string,
): Promise<AppointmentCreated> {
  return request('/appointments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(value),
  });
}

export function openSlot(scheduledAt: string): Promise<Slot> {
  return request('/appointments/slots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_at: scheduledAt }),
  });
}

export function closeSlot(slotId: string): Promise<void> {
  return request(`/appointments/slots/${encodeURIComponent(slotId)}`, { method: 'DELETE' });
}

export function updateAppointment(appointmentId: string, status: AppointmentAction): Promise<Appointment> {
  return request(`/appointments/${encodeURIComponent(appointmentId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
}
