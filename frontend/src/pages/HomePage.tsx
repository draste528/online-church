import React from 'react';
import { Link } from 'react-router-dom';
import { CandleWidget } from '../components/CandleWidget';
import { HOME_FEATURES } from '../config';
import { useI18n } from '../i18n';

export const HomePage: React.FC = () => {
  const { m } = useI18n();
  return (
    <>
      <section className="hero">
        <p className="hero-kicker">{m.home.kicker}</p>
        <h1>{m.home.title}</h1>
        <p className="hero-text">{m.home.text}</p>
        <div className="hero-actions">
          <a href="#candle" className="btn btn-primary">{m.home.lightCandle}</a>
          <Link to="/shop" className="btn btn-secondary">{m.home.openShop}</Link>
        </div>
        <div className="ornament" aria-hidden="true"><span /> ☦ <span /></div>
      </section>

      <div className="container">
        <CandleWidget />
        <div className="grid-2">
          {HOME_FEATURES.map((f) => (
            <Link key={f.to} to={f.to} className="card feature">
              <span className="icon-circle" aria-hidden="true">{f.icon}</span>
              <h3>{m.home.features[f.id].title}</h3>
              <p className="muted">{m.home.features[f.id].text}</p>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
};
