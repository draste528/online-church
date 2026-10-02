import React from 'react';
import { Link } from 'react-router-dom';
import { CandleWidget } from '../components/CandleWidget';

const FEATURES = [
  { to: '/shop', icon: '🕯', title: 'Церковная лавка', text: 'Свечи, ладан, иконы и просфоры с доставкой.' },
  { to: '/chat', icon: '✉', title: 'Чат со священником', text: 'Задайте вопрос и получите духовный совет.' },
];

export const HomePage: React.FC = () => (
  <>
    <section className="hero">
      <p className="hero-kicker">Мир вам</p>
      <h1>Молитва, которая всегда рядом</h1>
      <p className="hero-text">
        Зажгите свечу, побеседуйте со священником и приобретите всё необходимое для домашней молитвы — онлайн.
      </p>
      <div className="hero-actions">
        <a href="#candle" className="btn btn-primary">Поставить свечу</a>
        <Link to="/shop" className="btn btn-secondary">Церковная лавка</Link>
      </div>
      <div className="ornament" aria-hidden="true"><span /> ☦ <span /></div>
    </section>

    <div className="container">
      <CandleWidget />
      <div className="grid-2">
        {FEATURES.map((f) => (
          <Link key={f.to} to={f.to} className="card feature">
            <span className="icon-circle" aria-hidden="true">{f.icon}</span>
            <h3>{f.title}</h3>
            <p className="muted">{f.text}</p>
          </Link>
        ))}
      </div>
    </div>
  </>
);
