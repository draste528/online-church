import { DONATION_MAX_AMOUNT, DONATION_MIN_AMOUNT } from '../config';
import type { Messages } from '../i18n/ru';

type Validation = Messages['donate']['validation'];

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

/** Parses the amount field ("25", "49,5", "10.25"); returns null when it is not a valid amount. */
export function parseAmount(text: string): number | null {
  const value = text.trim().replace(',', '.');
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return null;
  const amount = Number(value);
  return amount >= DONATION_MIN_AMOUNT && amount <= DONATION_MAX_AMOUNT ? amount : null;
}

/** "$25.00", "$1,234.50": the same notation in every interface language. */
export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
}

/** Symbol for the form label ("Amount, $"). */
export function currencySymbol(currency: string): string {
  const part = new Intl.NumberFormat('en-US', { style: 'currency', currency }).formatToParts(0);
  return part.find((p) => p.type === 'currency')?.value ?? currency;
}

// The validators return an error text for the user, or null when the value is fine.
// They mirror backend/app/api/donations.py; the backend stays the source of truth.

export function validateAmount(text: string, v: Validation, currency: string): string | null {
  if (text.trim() === '') return v.amountEmpty;
  if (!/^\d+([.,]\d{1,2})?$/.test(text.trim())) return v.amountFormat;
  if (parseAmount(text) === null) {
    return v.amountRange(formatMoney(DONATION_MIN_AMOUNT, currency), formatMoney(DONATION_MAX_AMOUNT, currency));
  }
  return null;
}

export function validateCardNumber(text: string, v: Validation): string | null {
  return /^\d{4} \d{4} \d{4} \d{4}$/.test(text) ? null : v.cardNumber;
}

export function validateExpiry(text: string, v: Validation, now: Date = new Date()): string | null {
  const match = /^(0[1-9]|1[0-2])\/(\d{2})$/.exec(text);
  if (!match) return v.expiryFormat;
  const year = 2000 + Number(match[2]);
  const month = Number(match[1]);
  if (year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1)) {
    return v.expiryExpired;
  }
  return null;
}

export function validateCvc(text: string, v: Validation): string | null {
  return /^\d{3}$/.test(text) ? null : v.cvc;
}
