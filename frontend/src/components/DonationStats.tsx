import React, { useEffect, useState } from 'react';
import { ApiError, fetchDonationSummary, type DonationSummary } from '../api';
import { useI18n } from '../i18n';
import { formatMoney } from '../utils/donation';
import { describeApiError } from '../utils/errors';

interface DonationStatsProps {
  /** Change this value to reload the statistics (e.g. after a new donation). */
  refreshKey?: number;
}

export const DonationStats: React.FC<DonationStatsProps> = ({ refreshKey = 0 }) => {
  const { m } = useI18n();
  const t = m.donate.stats;
  const fundLabel = (id: string) => (m.donate.funds as Record<string, string>)[id] ?? id;
  const [summary, setSummary] = useState<DonationSummary | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDonationSummary(controller.signal)
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err instanceof ApiError ? err : new ApiError('http'));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const maxHourCount = summary ? Math.max(1, ...summary.by_hour.map((h) => h.count)) : 1;

  return (
    <section className="card stats" aria-labelledby="stats-title">
      <h2 id="stats-title">{t.title}</h2>

      {loading && !summary && <p className="muted">{t.loading}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error.code === 'network' ? t.unavailable : describeApiError(error, m)}
        </p>
      )}

      {summary && summary.donations_count === 0 && (
        <p className="muted">{t.empty}</p>
      )}

      {summary && summary.donations_count > 0 && (
        <>
          <div className="stat-tiles">
            <div className="stat-tile">
              <span className="stat-value">{formatMoney(summary.total_amount, summary.currency)}</span>
              <span className="stat-label">{t.total}</span>
            </div>
            <div className="stat-tile">
              <span className="stat-value">{summary.donations_count}</span>
              <span className="stat-label">{t.count}</span>
            </div>
            <div className="stat-tile">
              <span className="stat-value">{formatMoney(summary.average_amount, summary.currency)}</span>
              <span className="stat-label">{t.average}</span>
            </div>
          </div>

          <h3>{t.byFund}</h3>
          <ul className="bars">
            {summary.by_fund.map((f) => (
              <li key={f.fund}>
                <div className="bar-head">
                  <span>{fundLabel(f.fund)}</span>
                  <span className="muted">{formatMoney(f.total, summary.currency)} · {f.share_percent}%</span>
                </div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${f.share_percent}%` }} />
                </div>
              </li>
            ))}
          </ul>

          <h3>{t.byHour}</h3>
          <div className="hours" role="img" aria-label={t.hoursLabel}>
            {summary.by_hour.map((h) => (
              <div
                key={h.hour}
                className={h.hour === summary.peak_hour ? 'hour-bar peak' : 'hour-bar'}
                style={{ height: `${Math.max(2, (h.count / maxHourCount) * 100)}%` }}
                title={`${String(h.hour).padStart(2, '0')}:00 — ${h.count}`}
              />
            ))}
          </div>
          <div className="hours-axis"><span>0</span><span>6</span><span>12</span><span>18</span><span>23</span></div>
          {summary.peak_hour !== null && (
            <p className="muted small">
              {t.peak(`${String(summary.peak_hour).padStart(2, '0')}:00`, summary.timezone)}
            </p>
          )}
        </>
      )}
    </section>
  );
};
