import React, { useState } from 'react';
import { DemoPaymentBanner } from '../components/DemoPaymentBanner';
import { DonationForm } from '../components/DonationForm';
import { DonationStats } from '../components/DonationStats';
import { useI18n } from '../i18n';

export const DonatePage: React.FC = () => {
  const { m } = useI18n();
  const t = m.donate;
  // Bumped after every successful donation so that the statistics reload.
  const [statsVersion, setStatsVersion] = useState(0);

  return (
    <div className="container narrow">
      <h1 className="page-title">{t.title}</h1>
      <section className="donate-intro">
        <h2>{t.lead}</h2>
        <p className="reassure">{t.reassure}</p>
        <p className="muted">{t.reassureSub}</p>
      </section>
      <DemoPaymentBanner />
      {/* TODO(Tamara): styling of the donation page (spacing, typography, two-column layout on wide screens). */}
      <DonationForm onDonated={() => setStatsVersion((v) => v + 1)} />
      <DonationStats refreshKey={statsVersion} />
    </div>
  );
};
