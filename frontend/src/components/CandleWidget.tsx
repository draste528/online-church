import React, { useState } from 'react';
import { CANDLE_INTENTIONS, CANDLE_OPTIONS, CURRENCY } from '../config';

export const CandleWidget: React.FC = () => {
  const [optionId, setOptionId] = useState<string>(CANDLE_OPTIONS[0].id);
  const [intention, setIntention] = useState<string>(CANDLE_INTENTIONS[0].id);
  const [name, setName] = useState('');
  const [lit, setLit] = useState(false);

  const option = CANDLE_OPTIONS.find((o) => o.id === optionId) ?? CANDLE_OPTIONS[0];
  const intentionLabel = CANDLE_INTENTIONS.find((i) => i.id === intention)?.label ?? '';

  const handleLight = (e: React.FormEvent) => {
    e.preventDefault();
    setLit(true);
  };

  return (
    <section id="candle" className="card candle">
      <div className="candle-visual" aria-hidden="true">
        <div className={lit ? 'flame lit' : 'flame'} />
        <div className="wax" />
      </div>

      {lit ? (
        <div className="candle-form">
          <h2>Свеча поставлена</h2>
          <p className="muted">
            {intentionLabel}
            {name ? `: ${name}` : ''}. Да хранит вас Господь.
          </p>
          <button className="btn btn-secondary" onClick={() => setLit(false)}>
            Поставить ещё одну
          </button>
        </div>
      ) : (
        <form className="candle-form" onSubmit={handleLight}>
          <h2>Поставить свечу онлайн</h2>
          <p className="muted">Выберите свечу и помолитесь о близких — свеча будет зажжена от вашего имени.</p>

          <div className="chips" role="radiogroup" aria-label="Намерение">
            {CANDLE_INTENTIONS.map((i) => (
              <button
                type="button"
                key={i.id}
                className={i.id === intention ? 'chip active' : 'chip'}
                onClick={() => setIntention(i.id)}
              >
                {i.label}
              </button>
            ))}
          </div>

          <div className="chips" role="radiogroup" aria-label="Свеча">
            {CANDLE_OPTIONS.map((o) => (
              <button
                type="button"
                key={o.id}
                className={o.id === optionId ? 'chip active' : 'chip'}
                onClick={() => setOptionId(o.id)}
              >
                {o.label} · {o.price} {CURRENCY}
              </button>
            ))}
          </div>

          <input
            className="input"
            placeholder="Имя (необязательно)"
            value={name}
            maxLength={60}
            onChange={(e) => setName(e.target.value)}
          />
          <button className="btn btn-primary" type="submit">
            Поставить свечу · {option.price} {CURRENCY}
          </button>
        </form>
      )}
    </section>
  );
};
