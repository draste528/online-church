import { DONATION_MAX_AMOUNT, DONATION_MIN_AMOUNT } from '../config';

/** "4111111111111111" -> "4111 1111 1111 1111" (digits only, at most 16). */
export function formatCardNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 16);
  return digits.replace(/(\d{4})(?=\d)/g, '$1 ');
}

/** Types "1227" as "12/27". The slash is not forced while the user is deleting. */
export function formatExpiry(raw: string, previous: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 4);
  const typingForward = raw.length >= previous.length;
  if (digits.length > 2 || (digits.length === 2 && typingForward)) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  return digits;
}

export function formatCvc(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, 3);
}

/** Parses the amount field ("500", "99,5", "10.25"); returns null when it is not a valid amount. */
export function parseAmount(text: string): number | null {
  const value = text.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const amount = Number(value);
  return amount >= DONATION_MIN_AMOUNT && amount <= DONATION_MAX_AMOUNT ? amount : null;
}

export function formatMoney(amount: number, currency: string): string {
  const symbol = currency === 'RUB' ? '₽' : currency;
  return `${amount.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${symbol}`;
}

// The validators return an error text for the user, or null when the value is fine.
// They mirror backend/app/api/donations.py; the backend stays the source of truth.

export function validateAmount(text: string): string | null {
  if (text.trim() === '') return 'Укажите сумму.';
  if (!/^\d+([.,]\d{1,2})?$/.test(text.trim())) return 'Введите число, например 500 или 99,50.';
  if (parseAmount(text) === null) {
    return `Сумма — от ${DONATION_MIN_AMOUNT} до ${DONATION_MAX_AMOUNT.toLocaleString('ru-RU')} ₽.`;
  }
  return null;
}

export function validateCardNumber(text: string): string | null {
  return /^\d{4} \d{4} \d{4} \d{4}$/.test(text) ? null : 'Номер карты: 16 цифр.';
}

export function validateExpiry(text: string, now: Date = new Date()): string | null {
  const match = /^(0[1-9]|1[0-2])\/(\d{2})$/.exec(text);
  if (!match) return 'Срок действия: ММ/ГГ, например 08/27.';
  const year = 2000 + Number(match[2]);
  const month = Number(match[1]);
  if (year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1)) {
    return 'Срок действия карты истёк.';
  }
  return null;
}

export function validateCvc(text: string): string | null {
  return /^\d{3}$/.test(text) ? null : 'CVC: три цифры.';
}
