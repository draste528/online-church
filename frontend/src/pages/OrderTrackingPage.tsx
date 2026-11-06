
import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiError, getOrder, type OrderDetails, type OrderStatus } from '../api';
import { CURRENCY } from '../config';
import { useI18n } from '../i18n';

const STEPS: OrderStatus[] = [
  'accepted',
  'assembling',
  'ready',
  'completed',
];

export const OrderTrackingPage: React.FC = () => {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const { m, locale } = useI18n();
  const t = m.orderTracking;

  const [search, setSearch] = useState('');
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<'notFound' | 'network' | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!orderId) {
      setOrder(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setOrder(null);
    setError(null);

    getOrder(orderId, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setOrder(data);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;

        if (err instanceof ApiError && err.status === 404) {
          setError('notFound');
        } else {
          setError('network');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [orderId, refresh]);

  const findOrder = (e: React.FormEvent) => {
    e.preventDefault();
    const id = search.trim();

    if (id) navigate(`/orders/${encodeURIComponent(id)}`);
  };

  const formatDate = (value: string) =>
    new Date(value).toLocaleString(locale);

  const formatMoney = (value: number) =>
    `${value.toLocaleString(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ${CURRENCY}`;

  const currentStep = order ? STEPS.indexOf(order.status) : -1;

  return (
    <div className="container narrow order-tracking">
      <h1 className="page-title">{t.title}</h1>
      <p className="lead muted">{t.description}</p>

      <form className="card order-search" onSubmit={findOrder}>
        <label htmlFor="order-id">{t.orderNumber}</label>
        <div className="order-search-row">
          <input
            id="order-id"
            className="input"
            type="text"
            placeholder={t.placeholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            required
          />
          <button className="btn btn-primary" type="submit">
            {t.find}
          </button>
        </div>
      </form>

      {loading && (
        <p className="muted" role="status">{t.loading}</p>
      )}

      {error && !loading && (
        <div className="card" role="alert">
          <p className="error">
            {error === 'notFound' ? t.notFound : t.networkError}
          </p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setRefresh((n) => n + 1)}
          >
            {t.retry}
          </button>
        </div>
      )}

      {order && !loading && (
        <article className="card order-details">
          <div className="order-header">
            <div>
              <h2>{t.details}</h2>
              <p className="muted order-uuid">{order.order_id}</p>
              <p className="muted">
                {t.createdAt}: {formatDate(order.created_at)}
              </p>
            </div>
            <button
              className="btn btn-secondary btn-sm"
              type="button"
              onClick={() => setRefresh((n) => n + 1)}
            >
              {t.refresh}
            </button>
          </div>

          <section className="order-section">
            <h3>{t.statusTitle}</h3>

            {order.status === 'cancelled' ? (
              <div className="order-cancelled" role="status">
                {t.cancelled}
              </div>
            ) : (
              <ol className="order-stepper" aria-label={t.statusTitle}>
                {STEPS.map((status, index) => (
                  <li
                    key={status}
                    className={[
                      'order-step',
                      index < currentStep ? 'done' : '',
                      index === currentStep ? 'current' : '',
                    ].filter(Boolean).join(' ')}
                    aria-current={index === currentStep ? 'step' : undefined}
                  >
                    <span className="order-step-marker">
                      {index < currentStep ? '✓' : index + 1}
                    </span>
                    <span>{t.statuses[status]}</span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="order-section">
            <h3>{t.itemsTitle}</h3>
            <div className="order-items">
              {order.lines.map((line) => (
                <div className="order-item" key={line.item_id}>
                  <span>{line.title} × {line.quantity}</span>
                  <strong>{formatMoney(line.line_total)}</strong>
                </div>
              ))}
              <div className="order-item order-total">
                <strong>{t.total}</strong>
                <strong>{formatMoney(order.total)}</strong>
              </div>
            </div>
          </section>

          <section className="order-section">
            <h3>{t.historyTitle}</h3>
            {order.history.length === 0 ? (
              <p className="muted">{t.noHistory}</p>
            ) : (
              <ol className="order-history">
                {order.history.map((event, index) => (
                  <li key={`${event.at}-${index}`}>
                    <time dateTime={event.at}>
                      {formatDate(event.at)}
                    </time>
                    <strong>{t.statuses[event.status]}</strong>
                    {event.note && <p>{event.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </article>
      )}
    </div>
  );
};
