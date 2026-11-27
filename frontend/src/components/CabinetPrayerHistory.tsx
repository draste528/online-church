import { useEffect, useState } from 'react';
import { useI18n } from '../i18n';
import { loadPrayerRequestHistory, type PrayerRequestHistoryItem } from '../data/cabinetHistory';

export function CabinetPrayerHistory() {
  const { m, locale } = useI18n();
  const [items, setItems] = useState<PrayerRequestHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const t = m.cabinetHistory;

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setFailed(false);
    loadPrayerRequestHistory(controller.signal)
      .then(setItems)
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <section className="cabinet-history" aria-labelledby="cabinet-prayer-history-title" aria-busy={loading}>
      <h2 id="cabinet-prayer-history-title">{t.prayerTitle}</h2>
      <p className="cabinet-history-demo">{t.demoData}</p>
      {loading ? (
        <p role="status">{t.loading}</p>
      ) : failed ? (
        <div className="cabinet-history-error" role="alert">
          <p>{t.error}</p>
          <button className="btn" type="button" onClick={() => setAttempt(value => value + 1)}>{t.retry}</button>
        </div>
      ) : items.length === 0 ? (
        <p className="muted">{t.empty}</p>
      ) : (
        <ol className="cabinet-history-list">
          {items.map(item => (
            <li className="cabinet-history-item" key={item.id}>
              <div>
                <strong>{t.types[item.type]}</strong>
                <p>{t.names}: {item.names.join(', ')}</p>
                {item.donationAmount > 0 && (
                  <p>{t.donation}: {item.donationAmount.toLocaleString(locale, { style: 'currency', currency: 'USD' })}</p>
                )}
              </div>
              <div className="cabinet-history-meta">
                <span className={`cabinet-history-status status-${item.status}`}>{t.statuses[item.status]}</span>
                <time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString(locale)}</time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
