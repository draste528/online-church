import type { AppointmentApiError } from './api';

export function localDateInMoscow(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function shiftDate(date: string, days: number): string {
  const value = new Date(`${date}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
}

export function moscowIso(date: string, time: string): string {
  return `${date}T${time}:00+03:00`;
}

export function moscowTime(iso: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Europe/Moscow', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).format(new Date(iso));
}

export function formatAppointmentDate(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    timeZone: 'Europe/Moscow', dateStyle: 'medium', timeStyle: 'short',
  }).format(new Date(iso));
}

export type AppointmentErrorKey =
  | 'network' | 'unauthorized' | 'forbidden' | 'notFound' | 'conflict' | 'slotTaken'
  | 'slotExists' | 'slotNotClosable' | 'invalidTransition' | 'validation' | 'unavailable' | 'generic';

export function appointmentErrorKey(error: unknown): AppointmentErrorKey {
  if (!(error as AppointmentApiError)?.status) return 'generic';
  const value = error as AppointmentApiError;
  if (value.status === 'network') return 'network';
  if (value.status === 401) return 'unauthorized';
  if (value.status === 403) return 'forbidden';
  if (value.status === 404) return 'notFound';
  if (value.status === 422) return 'validation';
  if (value.status === 503) return 'unavailable';
  if (value.status === 409) {
    if (value.code === 'SLOT_TAKEN') return 'slotTaken';
    if (value.code === 'SLOT_ALREADY_EXISTS') return 'slotExists';
    if (value.code === 'SLOT_NOT_CLOSABLE') return 'slotNotClosable';
    if (value.code === 'INVALID_TRANSITION') return 'invalidTransition';
    return 'conflict';
  }
  return 'generic';
}

export function personName(person: { first_name: string | null; last_name: string | null }): string {
  return [person.first_name, person.last_name].filter(Boolean).join(' ') || '—';
}
