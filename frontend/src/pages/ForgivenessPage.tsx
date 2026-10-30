import React, { useState } from 'react';
import { useI18n } from '../i18n';

export const ForgivenessPage: React.FC = () => {
  const { m } = useI18n();
  const t = m.forgiveness;
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [forgiven, setForgiven] = useState(false);

  const sin = t.sins.find((s) => s.id === selectedId) ?? null;

  const select = (id: string) => {
    setSelectedId(id);
    setForgiven(false);
  };
  const reset = () => {
    setSelectedId(null);
    setForgiven(false);
  };

  return (
    <div className="container narrow">
      <h1 className="page-title">{t.title}</h1>
      <p className="muted lead">{t.intro}</p>

      {!forgiven && (
        <>
          <h2 className="section-title">{t.choose}</h2>
          <div className="sin-grid">
            {t.sins.map((s) => (
              <button
                key={s.id}
                type="button"
                className={s.id === selectedId ? 'sin-card active' : 'sin-card'}
                aria-pressed={s.id === selectedId}
                onClick={() => select(s.id)}
              >
                {s.title}
              </button>
            ))}
          </div>
        </>
      )}

      {sin && !forgiven && (
        <section className="card sin-detail">
          <h3>{sin.title}</h3>
          <p className="muted">{sin.text}</p>
          <button className="btn btn-primary" onClick={() => setForgiven(true)}>{t.repent}</button>
        </section>
      )}

      {sin && forgiven && (
        <section className="card sin-detail forgiven" role="status">
          <span className="icon-circle" aria-hidden="true">🕊</span>
          <h2>{t.absolvedTitle}</h2>
          <p>{sin.absolution}</p>
          <p>
            <strong>{t.deedLabel}:</strong> {sin.deed}
          </p>
          <p className="muted">
            <strong>{t.prayerLabel}:</strong> {t.prayer}
          </p>
          <button className="btn btn-secondary" onClick={reset}>{t.another}</button>
        </section>
      )}

      <p className="muted small">{t.note}</p>
    </div>
  );
};
