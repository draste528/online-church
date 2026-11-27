import { useEffect, useMemo, useState } from 'react';
import {
  fetchDailyFinanceSummary,
  fetchDonationSummary,
  fetchFundsDistribution,
  fetchOrderAnalytics,
  fetchRegistrationAnalytics,
  type DailyFinanceSummary,
  type DonationSummary,
  type FundDistribution,
  type OrderAnalyticsSummary,
  type RegistrationAnalyticsSummary,
} from '../api';
import { useI18n } from '../i18n';

type Period = 7 | 30 | 90;

interface DashboardData {
  dailyFinance: DailyFinanceSummary[] | null;
  funds: FundDistribution[] | null;
  donations: DonationSummary | null;
  orders: OrderAnalyticsSummary | null;
  registrations: RegistrationAnalyticsSummary | null;
}

const EMPTY_DATA: DashboardData = {
  dailyFinance: null,
  funds: null,
  donations: null,
  orders: null,
  registrations: null,
};

function resultValue<T>(result: PromiseSettledResult<T>): T | null {
  return result.status === 'fulfilled' ? result.value : null;
}

export function AnalyticsDashboard() {
  const { m, locale } = useI18n();
  const t = m.analyticsDashboard;
  const [period, setPeriod] = useState<Period>(30);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<DashboardData>(EMPTY_DATA);
  const [failedSources, setFailedSources] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setData(EMPTY_DATA);
    setFailedSources([]);

    Promise.allSettled([
      fetchDailyFinanceSummary(controller.signal),
      fetchFundsDistribution(controller.signal),
      fetchDonationSummary(controller.signal),
      fetchOrderAnalytics(period, controller.signal),
      fetchRegistrationAnalytics(period, controller.signal),
    ] as const).then((results) => {
      if (controller.signal.aborted) return;
      setData({
        dailyFinance: resultValue(results[0]),
        funds: resultValue(results[1]),
        donations: resultValue(results[2]),
        orders: resultValue(results[3]),
        registrations: resultValue(results[4]),
      });
      setFailedSources(results.flatMap((result, index) => result.status === 'rejected' ? [index] : []));
    }).finally(() => {
      if (!controller.signal.aborted) setLoading(false);
    });

    return () => controller.abort();
  }, [period, refresh]);

  const financeByDay = useMemo(() => {
    if (!data.dailyFinance) return [];
    const totals = new Map<string, { amount: number; transactions: number }>();
    data.dailyFinance.forEach((row) => {
      const current = totals.get(row.report_date) ?? { amount: 0, transactions: 0 };
      current.amount += row.total_amount;
      current.transactions += row.transaction_count;
      totals.set(row.report_date, current);
    });
    return [...totals.entries()]
      .sort(([left], [right]) => left.localeCompare(right))
      .slice(-period)
      .map(([date, values]) => ({ date, ...values }));
  }, [data.dailyFinance, period]);

  const formatMoney = (amount: number, currency: string) =>
    new Intl.NumberFormat(locale, { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount);
  const formatNumber = (value: number) => value.toLocaleString(locale, { maximumFractionDigits: 1 });
  const formatPercent = (value: number | null) => value === null ? '—' : `${formatNumber(value)}%`;
  const formatDate = (value: string) =>
    new Date(`${value}T12:00:00`).toLocaleDateString(locale, { day: 'numeric', month: 'short' });
  const groupLabel = (key: string) =>
    (t.groups as Record<string, string>)[key] ?? key.replace(/_/g, ' ');

  const hasData = Object.values(data).some((value) => value !== null);
  const collectedTotal = data.funds?.reduce((sum, fund) => sum + fund.total_collected, 0)
    ?? data.donations?.total_amount
    ?? null;

  return (
    <div className="container analytics-dashboard" aria-busy={loading}>
      <header className="analytics-header">
        <div>
          <h1 className="page-title">{t.title}</h1>
          <p className="lead muted">{t.subtitle}</p>
        </div>
        <div className="analytics-controls">
          <label htmlFor="analytics-period">{t.periodLabel}</label>
          <select
            id="analytics-period"
            className="input select"
            value={period}
            onChange={(event) => setPeriod(Number(event.target.value) as Period)}
          >
            <option value={7}>{t.periods.days7}</option>
            <option value={30}>{t.periods.days30}</option>
            <option value={90}>{t.periods.days90}</option>
          </select>
          <button className="btn btn-secondary btn-sm" type="button" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>
            {t.refresh}
          </button>
        </div>
      </header>

      {loading && <p className="muted" role="status">{t.loading}</p>}
      {!loading && failedSources.length > 0 && (
        <p className="analytics-warning" role="alert">
          {hasData ? t.partialError : t.error}
        </p>
      )}
      {!loading && failedSources.length === 5 && (
        <button className="btn btn-primary" type="button" onClick={() => setRefresh((value) => value + 1)}>{t.retry}</button>
      )}

      {hasData && (
        <>
          <section className="analytics-metrics" aria-label={t.subtitle}>
            <Metric label={t.metrics.collected} value={collectedTotal === null ? '—' : formatNumber(collectedTotal)} />
            <Metric label={t.metrics.donations} value={data.donations ? formatNumber(data.donations.donations_count) : '—'} />
            <Metric label={t.metrics.averageDonation} value={data.donations ? formatMoney(data.donations.average_amount, data.donations.currency) : '—'} />
            <Metric label={t.metrics.orders} value={data.orders ? formatNumber(data.orders.orders_count) : '—'} />
            <Metric label={t.metrics.revenue} value={data.orders ? formatMoney(data.orders.revenue, data.orders.currency) : '—'} />
            <Metric label={t.metrics.cancellationRate} value={data.orders ? formatPercent(data.orders.cancellation_rate_percent) : '—'} />
            <Metric label={t.metrics.registrations} value={data.registrations ? formatNumber(data.registrations.new_users) : '—'} />
            <Metric label={t.metrics.growth} value={data.registrations ? formatPercent(data.registrations.growth_percent) : '—'} />
            <Metric label={t.metrics.activation} value={data.registrations ? formatPercent(data.registrations.activation.activation_rate_percent) : '—'} />
            <Metric label={t.metrics.activeOrders} value={data.orders ? formatNumber(data.orders.active_orders) : '—'} />
          </section>

          <div className="analytics-grid">
            <section className="card analytics-panel">
              <h2>{t.sections.dailyFinance}</h2>
              {data.dailyFinance === null || financeByDay.length === 0 ? <p className="muted">{t.noData}</p> : (
                <DailyBars
                  values={financeByDay.map((point) => ({
                    key: point.date,
                    date: formatDate(point.date),
                    value: point.amount,
                    detail: `${formatMoney(point.amount, data.donations?.currency ?? 'USD')} · ${formatNumber(point.transactions)} ${t.labels.transactions.toLocaleLowerCase(locale)}`,
                  }))}
                  formatValue={(value) => formatMoney(value, data.donations?.currency ?? 'USD')}
                  label={t.sections.dailyFinance}
                  sumLabel={t.labels.sum}
                  peakLabel={t.labels.peak}
                />
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.funds}</h2>
              {!data.funds?.length ? <p className="muted">{t.noData}</p> : (
                <ul className="analytics-breakdown">
                  {data.funds.map((fund) => (
                    <BreakdownRow
                      key={fund.fund_type}
                      label={groupLabel(fund.fund_type)}
                      value={formatMoney(fund.total_collected, data.donations?.currency ?? 'USD')}
                      percent={fund.percentage}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.ordersByDay}</h2>
              {!data.orders?.by_day.length ? <p className="muted">{t.noData}</p> : (
                <DailyBars
                  values={data.orders.by_day.map((point) => ({
                    key: point.date,
                    date: formatDate(point.date),
                    value: point.revenue,
                    detail: `${formatMoney(point.revenue, data.orders!.currency)} · ${formatNumber(point.orders)} ${t.labels.orderCount.toLocaleLowerCase(locale)}`,
                  }))}
                  formatValue={(value) => formatMoney(value, data.orders!.currency)}
                  label={t.sections.ordersByDay}
                  sumLabel={t.labels.sum}
                  peakLabel={t.labels.peak}
                />
              )}
              {data.orders && (
                <p className="analytics-caption">
                  {t.metrics.activeOrders}: {formatNumber(data.orders.active_orders)} · {t.metrics.revenue}: {formatMoney(data.orders.revenue, data.orders.currency)}
                </p>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.registrationsByDay}</h2>
              {!data.registrations?.by_day.length ? <p className="muted">{t.noData}</p> : (
                <DailyBars
                  values={data.registrations.by_day.map((point) => ({
                    key: point.date,
                    date: formatDate(point.date),
                    value: point.registrations,
                    detail: `${formatNumber(point.registrations)} ${t.labels.registrations.toLocaleLowerCase(locale)}`,
                  }))}
                  formatValue={(value) => formatNumber(value)}
                  label={t.sections.registrationsByDay}
                  sumLabel={t.labels.sum}
                  peakLabel={t.labels.peak}
                />
              )}
              {data.registrations && (
                <p className="analytics-caption">
                  {t.labels.count}: {formatNumber(data.registrations.total_users)} · {t.metrics.growth}: {formatPercent(data.registrations.growth_percent)}
                </p>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.orderStatuses}</h2>
              {!data.orders?.by_status.length ? <p className="muted">{t.noData}</p> : (
                <ul className="analytics-breakdown">
                  {data.orders.by_status.map((status) => (
                    <BreakdownRow
                      key={status.status}
                      label={m.orderTracking.statuses[status.status]}
                      value={formatNumber(status.count)}
                      percent={status.share_percent}
                    />
                  ))}
                </ul>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.topItems}</h2>
              {!data.orders?.top_items.length ? <p className="muted">{t.noData}</p> : (
                <ul className="analytics-top-items">
                  {data.orders.top_items.map((item) => (
                    <li key={item.title}>
                      <span>{item.title}</span>
                      <strong>{formatNumber(item.quantity)} × · {formatMoney(item.revenue, data.orders!.currency)}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.registrationSources}</h2>
              {!data.registrations?.by_source.length ? <p className="muted">{t.noData}</p> : (
                <ul className="analytics-breakdown">
                  {data.registrations.by_source.map((source) => (
                    <BreakdownRow key={source.key} label={groupLabel(source.key)} value={formatNumber(source.count)} percent={source.share_percent} />
                  ))}
                </ul>
              )}
            </section>

            <section className="card analytics-panel">
              <h2>{t.sections.devices}</h2>
              {!data.registrations?.by_device.length ? <p className="muted">{t.noData}</p> : (
                <ul className="analytics-breakdown">
                  {data.registrations.by_device.map((device) => (
                    <BreakdownRow key={device.key} label={groupLabel(device.key)} value={formatNumber(device.count)} percent={device.share_percent} />
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <article className="analytics-metric"><span className="analytics-metric-value">{value}</span><span className="analytics-metric-label">{label}</span></article>;
}

interface DailyBarPoint {
  key: string;
  date: string;
  value: number;
  detail: string;
}

function DailyBars({ values, formatValue, label, sumLabel, peakLabel }: {
  values: DailyBarPoint[];
  formatValue: (value: number) => string;
  label: string;
  sumLabel: string;
  peakLabel: string;
}) {
  const peak = Math.max(0, ...values.map((point) => point.value));
  const scale = Math.max(1, peak);
  return (
    <>
      <div className="analytics-daily-bars" role="img" aria-label={label}>
        {values.map((point) => (
          <span
            className="analytics-daily-bar"
            key={point.key}
            title={`${point.date}: ${point.detail}`}
            style={{ height: `${Math.max(3, (point.value / scale) * 100)}%` }}
          />
        ))}
      </div>
      <div className="analytics-chart-axis"><span>{values[0]?.date}</span><span>{values[values.length - 1]?.date}</span></div>
      <p className="analytics-chart-summary">{sumLabel}: {formatValue(values.reduce((sum, point) => sum + point.value, 0))} · {peakLabel}: {formatValue(peak)}</p>
    </>
  );
}

function BreakdownRow({ label, value, percent }: { label: string; value: string; percent: number }) {
  return (
    <li>
      <div className="analytics-breakdown-label"><span>{label}</span><strong>{value}</strong></div>
      <div className="bar-track" role="img" aria-label={`${label}: ${percent}%`}><div className="bar-fill" style={{ width: `${Math.max(0, Math.min(percent, 100))}%` }} /></div>
    </li>
  );
}
