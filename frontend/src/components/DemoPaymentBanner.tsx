import React from 'react';

/** Loud notice shown above the donation form: the payment is a simulation. */
export const DemoPaymentBanner: React.FC = () => (
  <div className="demo-banner" role="note">
    <span className="demo-banner-icon" aria-hidden="true">!</span>
    <div>
      <strong>Демонстрационная оплата</strong>
      <p>Это имитация: настоящие данные карты не вводите. Деньги не списываются, номер карты и CVC не сохраняются.</p>
    </div>
  </div>
);
