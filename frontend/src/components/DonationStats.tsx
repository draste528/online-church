import React, { useEffect, useState } from 'react';
import { fetchDonationSummary, type DonationSummary } from '../api';
import { DONATION_FUNDS } from '../config';
import { formatMoney } from '../utils/donation';

interface DonationStatsProps {
  /** Change this value to reload the statistics (e.g. after a new donation). */
  refreshKey?: number;
}

const fundLabel = (id: string) => DONATION_FUNDS.find((f) => f.id === id)?.label ?? id;

export const DonationStats: React.FC<DonationStatsProps> = ({ refreshKey = 0 }) => {
  const [summary, setSummary] = useState<DonationSummary | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    fetchDonationSummary(controller.signal)
      .then((data) => {
        setSummary(data);
        setError('');
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [refreshKey]);

  const maxHourCount = summary ? Math.max(1, ...summary.by_hour.map((h) => h.count)) : 1;

  return (
    <section className="card stats" aria-labelledby="stats-title">
      <h2 id="stats-title">Статистика пожертвований</h2>

      {loading && !summary && <p className="muted">Загрузка…</p>}
      {error && <p className="form-error" role="alert">{error}</p>}

      {summary && summary.donations_count === 0 && (
        <p className="muted">Пока нет ни одного пожертвования. Станьте первым!</p>
      )}

      {summary && summary.donations_count > 0 && (
        <>
          <div className="stat-tiles">
            <div className="stat-tile">
              <span className="stat-value">{formatMoney(summary.total_amount, summary.currency)}</span>
              <span className="stat-label">Всего собрано</span>
            </div>
            <div className="stat-tile">
              <span className="stat-value">{summary.donations_count}</span>
              <span className="stat-label">Пожертвований</span>
            </div>
            <div className="stat-tile">
              <span className="stat-value">{formatMoney(summary.average_amount, summary.currency)}</span>
              <span className="stat-label">Средний чек</span>
            </div>
          </div>

          <h3>По фондам</h3>
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

          <h3>В какое время жертвуют</h3>
          <div className="hours" role="img" aria-label="Количество пожертвований по часам суток">
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
              Чаще всего жертвуют около {String(summary.peak_hour).padStart(2, '0')}:00 ({summary.timezone}).
            </p>
          )}
        </>
      )}
    </section>
  );
};
