// Central place for everything that is meant to be customised.

/** Removes trailing slashes so that `${URL}/api/...` never becomes `//api/...`. */
const trimSlash = (url: string): string => url.replace(/\/+$/, '');

/** Base URL of the backend API (override with VITE_API_URL, see frontend/.env.example). */
export const API_URL: string = trimSlash(import.meta.env.VITE_API_URL || 'http://localhost:8080');

/** Base URL of the analytics API (override with VITE_ANALYTICS_URL). */
export const ANALYTICS_URL: string = trimSlash(import.meta.env.VITE_ANALYTICS_URL || 'http://localhost:8000');

/** Extra diagnostics (console warnings, "backend offline" notes) only while running `npm run dev`. */
export const SHOW_DEV_HINTS: boolean = import.meta.env.DEV;

/** Main navigation. Add or remove entries here and in App.tsx routes. */
export const NAV_LINKS = [
  { to: '/', label: 'Главная' },
  { to: '/shop', label: 'Лавка' },
  { to: '/chat', label: 'ИИ-консультант' },
] as const;

/** Candle options offered on the home page. `waxHeight` is the height of the drawn candle (SVG units). */
export const CANDLE_OPTIONS = [
  { id: 'small', label: 'Малая свеча', price: 1, waxHeight: 60 },
  { id: 'medium', label: 'Средняя свеча', price: 3, waxHeight: 84 },
  { id: 'large', label: 'Большая свеча', price: 5, waxHeight: 108 },
] as const;

export const CANDLE_INTENTIONS = [
  { id: 'health', label: 'О здравии' },
  { id: 'repose', label: 'Об упокоении' },
] as const;

export const CURRENCY = 'BYN';
