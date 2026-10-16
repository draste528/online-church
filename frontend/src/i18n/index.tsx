import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LANG, LANGUAGES, type LangCode } from '../config';
import { be } from './be';
import { en } from './en';
import { ru, type Messages } from './ru';

const LOCALES: Record<LangCode, Messages> = { ru, en, be };

/** Locale used for date and number formatting in each language. */
const FORMAT_LOCALES: Record<LangCode, string> = { ru: 'ru-RU', en: 'en-US', be: 'be-BY' };

const STORAGE_KEY = 'oc.lang';

const isLangCode = (value: unknown): value is LangCode => LANGUAGES.some((l) => l.code === value);

function readStoredLang(): LangCode {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLangCode(saved)) return saved;
  } catch {
    /* storage can be unavailable (private mode) */
  }
  return DEFAULT_LANG;
}

interface I18nValue {
  lang: LangCode;
  setLang: (code: LangCode) => void;
  /** Messages for the current language. */
  m: Messages;
  /** Locale tag for `toLocaleString` and `Intl` in the current language. */
  locale: string;
}

const I18nContext = createContext<I18nValue | null>(null);

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<LangCode>(readStoredLang);
  const m = LOCALES[lang];

  const setLang = useCallback((code: LangCode) => {
    setLangState(code);
    try {
      localStorage.setItem(STORAGE_KEY, code);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = m.meta.title;
  }, [lang, m]);

  const value = useMemo(() => ({ lang, setLang, m, locale: FORMAT_LOCALES[lang] }), [lang, setLang, m]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>');
  return ctx;
}

export { LANGUAGES };
