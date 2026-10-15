import React, { useState } from 'react';
import { DemoPaymentBanner } from '../components/DemoPaymentBanner';
import { DonationForm } from '../components/DonationForm';
import { DonationStats } from '../components/DonationStats';

export const DonatePage: React.FC = () => {
  // Bumped after every successful donation so that the statistics reload.
  const [statsVersion, setStatsVersion] = useState(0);

  return (
    <div className="container narrow">
      <h1 className="page-title">Пожертвования</h1>
      <DemoPaymentBanner />
      {/* TODO(Tamara): styling of the donation page (spacing, typography, two-column layout on wide screens). */}
      <DonationForm onDonated={() => setStatsVersion((v) => v + 1)} />
      <DonationStats refreshKey={statsVersion} />
    </div>
  );
};
