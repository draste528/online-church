import React from 'react';
import { LANGUAGES, useI18n } from '../i18n';

export const LanguageSwitcher: React.FC = () => {
  const { lang, setLang, m } = useI18n();
  return (
    <div className="lang-switch" role="group" aria-label={m.lang.label}>
      {LANGUAGES.map((l) => (
        <button
          key={l.code}
          type="button"
          className={l.code === lang ? 'lang-btn active' : 'lang-btn'}
          aria-pressed={l.code === lang}
          title={l.label}
          onClick={() => setLang(l.code)}
        >
          {l.short}
        </button>
      ))}
    </div>
  );
};
