import React from 'react';
import { DemoPaymentBanner } from '../components/DemoPaymentBanner';
import { DonationForm } from '../components/DonationForm';

export const DonatePage: React.FC = () => (
  <div className="container narrow">
    <h1 className="page-title">Пожертвования</h1>
    <DemoPaymentBanner />
    {/* TODO(Tamara): styling of the donation page (spacing, typography, two-column layout on wide screens). */}
    <DonationForm />
  </div>
);
