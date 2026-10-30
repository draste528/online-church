// Central place for everything that is meant to be customised.
// Visible texts live in i18n/ru.ts, en.ts and be.ts, not here.

/** Removes trailing slashes so that `${URL}/api/...` never becomes `//api/...`. */
const trimSlash = (url: string): string => url.replace(/\/+$/, '');

/** Base URL of the backend API (override with VITE_API_URL, see frontend/.env.example). */
export const API_URL: string = trimSlash(import.meta.env.VITE_API_URL || 'http://localhost:8080');

/** Base URL of the analytics API (override with VITE_ANALYTICS_URL). */
export const ANALYTICS_URL: string = trimSlash(import.meta.env.VITE_ANALYTICS_URL || 'http://localhost:8000');

/** Extra diagnostics (console warnings, "backend offline" notes) only while running `npm run dev`. */
export const SHOW_DEV_HINTS: boolean = import.meta.env.DEV;

/** Languages shown in the switcher; every one needs a dictionary registered in i18n/index.tsx. */
export const LANGUAGES = [
  { code: 'ru', short: 'RU', label: 'Русский' },
  { code: 'en', short: 'EN', label: 'English' },
  { code: 'be', short: 'BE', label: 'Беларуская' },
] as const;
export type LangCode = (typeof LANGUAGES)[number]['code'];
export const DEFAULT_LANG: LangCode = 'ru';

/** Main navigation. `key` is the label key in `messages.nav`; add the matching <Route> in App.tsx. */
export const NAV_LINKS = [
  { to: '/', key: 'home' },
  { to: '/shop', key: 'shop' },
  { to: '/forgiveness', key: 'forgiveness' },
  { to: '/library', key: 'library' },
  { to: '/donate', key: 'donate' },
  { to: '/chat', key: 'chat' },
] as const;

/** Feature cards on the home page. `id` is the key in `messages.home.features`. */
export const HOME_FEATURES = [
  { id: 'shop', to: '/shop', icon: '🕯' },
  { id: 'forgiveness', to: '/forgiveness', icon: '🕊' },
  { id: 'library', to: '/library', icon: '📖' },
  { id: 'donate', to: '/donate', icon: '🤍' },
  { id: 'chat', to: '/chat', icon: '✉' },
] as const;

/** Candle options offered on the home page (names: `messages.candle.options`). `waxHeight` is the drawn height (SVG units). */
export const CANDLE_OPTIONS = [
  { id: 'small', price: 1, waxHeight: 60 },
  { id: 'medium', price: 3, waxHeight: 84 },
  { id: 'large', price: 5, waxHeight: 108 },
] as const;

/** Candle intentions (names: `messages.candle.intentions`). */
export const CANDLE_INTENTIONS = [{ id: 'health' }, { id: 'repose' }] as const;

export const CURRENCY = 'BYN';

/** Donations (demo payment). Currency and limits mirror the backend validation (backend/app/api/donations.py). */
export const DONATION_CURRENCY = 'USD';
export const DONATION_MIN_AMOUNT = 1;
export const DONATION_MAX_AMOUNT = 5000;
export const DONATION_PRESETS = [5, 10, 25, 50, 100] as const;

/** Fund ids; their names are in `messages.donate.funds`. */
export const DONATION_FUNDS = [
  { id: 'general' },
  { id: 'temple_restoration' },
  { id: 'choir' },
  { id: 'charity' },
  { id: 'minecraft_church' },
] as const;

export type FundId = (typeof DONATION_FUNDS)[number]['id'];
