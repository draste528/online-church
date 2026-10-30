import React, { useState } from 'react';
import { CANDLE_INTENTIONS, CANDLE_OPTIONS, CURRENCY } from '../config';
import { useI18n } from '../i18n';
import { CandleSvg } from './CandleSvg';

export const CandleWidget: React.FC = () => {
  const { m } = useI18n();
  const t = m.candle;
  const [optionId, setOptionId] = useState<string>(CANDLE_OPTIONS[0].id);
  const [intention, setIntention] = useState<string>(CANDLE_INTENTIONS[0].id);
  const [name, setName] = useState('');
  const [lit, setLit] = useState(false);

  const option = CANDLE_OPTIONS.find((o) => o.id === optionId) ?? CANDLE_OPTIONS[0];
  const intentionLabel = t.intentions[intention as keyof typeof t.intentions] ?? '';

  const handleLight = (e: React.FormEvent) => {
    e.preventDefault();
    setLit(true);
  };

  return (
    <section id="candle" className="card candle">
      <div className="candle-visual" aria-hidden="true">
        <CandleSvg lit={lit} waxHeight={option.waxHeight} />
      </div>

      {lit ? (
        <div className="candle-form">
          <h2>{t.lit}</h2>
          <p className="muted">
            {intentionLabel}
            {name ? `: ${name}` : ''}. {t.blessing}
          </p>
          <button className="btn btn-secondary" onClick={() => setLit(false)}>
            {t.another}
          </button>
        </div>
      ) : (
        <form className="candle-form" onSubmit={handleLight}>
          <h2>{t.title}</h2>
          <p className="muted">{t.text}</p>

          <div className="chips" role="radiogroup" aria-label={t.intentionLabel}>
            {CANDLE_INTENTIONS.map((i) => (
              <button
                type="button"
                key={i.id}
                className={i.id === intention ? 'chip active' : 'chip'}
                onClick={() => setIntention(i.id)}
              >
                {t.intentions[i.id]}
              </button>
            ))}
          </div>

          <div className="chips" role="radiogroup" aria-label={t.candleLabel}>
            {CANDLE_OPTIONS.map((o) => (
              <button
                type="button"
                key={o.id}
                className={o.id === optionId ? 'chip active' : 'chip'}
                onClick={() => setOptionId(o.id)}
              >
                {t.options[o.id]} · {o.price} {CURRENCY}
              </button>
            ))}
          </div>

          <input
            className="input"
            placeholder={t.namePlaceholder}
            value={name}
            maxLength={60}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="btn btn-primary" type="submit">
            {t.submit} · {option.price} {CURRENCY}
          </button>
        </form>
      )}
    </section>
  );
};
