import React from 'react';
import { useI18n } from '../i18n';

/** Loud notice shown above the donation form: the payment is a simulation. */
export const DemoPaymentBanner: React.FC = () => {
  const { m } = useI18n();
  return (
    <div className="demo-banner" role="note">
      <span className="demo-banner-icon" aria-hidden="true">!</span>
      <div>
        <strong>{m.donate.banner.title}</strong>
        <p>{m.donate.banner.text}</p>
      </div>
    </div>
  );
};
