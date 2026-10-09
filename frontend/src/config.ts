// Central place for everything that is meant to be customised.

/** Base URL of the backend API (override with VITE_API_URL in .env). */
export const API_URL: string = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

/** Main navigation. Add or remove entries here and in App.tsx routes. */
export const NAV_LINKS = [
  { to: '/', label: 'Главная' },
  { to: '/shop', label: 'Лавка' },
  { to: '/chat', label: 'ИИ-консультант' },
] as const;

/** Candle options offered on the home page. */
export const CANDLE_OPTIONS = [
  { id: 'small', label: 'Малая свеча', price: 1 },
  { id: 'medium', label: 'Средняя свеча', price: 3 },
  { id: 'large', label: 'Большая свеча', price: 5 },
] as const;

export const CANDLE_INTENTIONS = [
  { id: 'health', label: 'О здравии' },
  { id: 'repose', label: 'Об упокоении' },
] as const;

export const CURRENCY = 'BYN';
