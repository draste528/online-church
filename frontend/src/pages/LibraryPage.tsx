import React, { useState } from 'react';
import { useI18n } from '../i18n';

type Tab = 'prayers' | 'bible';

export const LibraryPage: React.FC = () => {
  const { m } = useI18n();
  const t = m.library;
  const [tab, setTab] = useState<Tab>('prayers');

  return (
    <div className="container narrow">
      <h1 className="page-title">{t.title}</h1>
      <p className="muted lead">{t.intro}</p>

      <div className="chips" role="tablist">
        {(['prayers', 'bible'] as Tab[]).map((key) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            className={tab === key ? 'chip active' : 'chip'}
            onClick={() => setTab(key)}
          >
            {t.tabs[key]}
          </button>
        ))}
      </div>

      {tab === 'prayers' && (
        <div className="prayer-list">
          {t.prayers.map((p) => (
            <details key={p.id} className="card prayer">
              <summary>
                <span className="prayer-title">{p.title}</span>
                <span className="muted prayer-when">{p.when}</span>
              </summary>
              <p className="prayer-text">{p.text}</p>
            </details>
          ))}
        </div>
      )}

      {tab === 'bible' && (
        <>
          <p className="muted">{t.bible.intro}</p>
          <h2 className="section-title">{t.bible.sourcesTitle}</h2>
          <div className="link-list">
            {t.bible.sources.map((s) => (
              <a key={s.url} className="card link-card" href={s.url} target="_blank" rel="noopener noreferrer">
                <strong>{s.title}</strong>
                <span className="muted">{s.text}</span>
                <span className="link-open">{t.bible.open} ↗</span>
              </a>
            ))}
          </div>
          <h2 className="section-title">{t.bible.startTitle}</h2>
          <div className="chips">
            {t.bible.start.map((s) => (
              <a key={s.url} className="chip" href={s.url} target="_blank" rel="noopener noreferrer">
                {s.title} ↗
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
