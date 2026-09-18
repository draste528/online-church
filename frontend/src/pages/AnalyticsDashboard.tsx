import React, { useEffect, useState } from 'react';

interface SummaryItem {
  report_date: string;
  fund_type: string;
  total_amount: number;
  transaction_count: number;
  avg_donation: number;
}

export const AnalyticsDashboard: React.FC = () => {
  const [data, setData] = useState<SummaryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8000/api/v1/analytics/summary')
      .then((res) => res.json())
      .then((items) => {
        setData(items);
        setLoading(false);
      })
      .catch((err) => {
        console.warn('Backend DWH API offline, using fallback state:', err);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ padding: '32px', maxWidth: '1100px', margin: '0 auto' }}>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '2rem', color: '#e5c07b', marginBottom: '8px' }}>
          Аналитический Контур (Data Platform DWH)
        </h1>
        <p style={{ color: '#8b949e' }}>
          Витрины данных: агрегации Airflow ETL, расчет когорт прихожан и мониторинг сборов
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '20px' }}>
          <div style={{ fontSize: '0.85rem', color: '#8b949e' }}>Оркестратор</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>Apache Airflow</div>
          <div style={{ fontSize: '0.75rem', color: '#58a6ff', marginTop: '4px' }}>DAG: church_daily_etl</div>
        </div>
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '20px' }}>
          <div style={{ fontSize: '0.85rem', color: '#8b949e' }}>Архитектура хранилища</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#e5c07b', marginTop: '4px' }}>3-слойный DWH</div>
          <div style={{ fontSize: '0.75rem', color: '#8b949e', marginTop: '4px' }}>staging → core → marts</div>
        </div>
        <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '20px' }}>
          <div style={{ fontSize: '0.85rem', color: '#8b949e' }}>Качество данных</div>
          <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>Pydantic v2</div>
          <div style={{ fontSize: '0.75rem', color: '#3fb950', marginTop: '4px' }}>100% покрытие валидацией</div>
        </div>
      </div>

      <div style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '24px' }}>
        <h3 style={{ marginBottom: '16px', fontSize: '1.1rem', color: '#e6edf3' }}>Витрина: marts.mart_daily_finances</h3>
        {loading ? (
          <div style={{ color: '#8b949e' }}>Загрузка метрик из DWH API (порт 8000)...</div>
        ) : data.length > 0 ? (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e' }}>
                <th style={{ padding: '8px' }}>Дата</th>
                <th style={{ padding: '8px' }}>Целевой Фонд</th>
                <th style={{ padding: '8px' }}>Сумма (BYN/RUB)</th>
                <th style={{ padding: '8px' }}>Транзакций</th>
                <th style={{ padding: '8px' }}>Средний чек</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '10px 8px' }}>{row.report_date}</td>
                  <td style={{ padding: '10px 8px', color: '#e5c07b' }}>{row.fund_type}</td>
                  <td style={{ padding: '10px 8px', fontWeight: 600 }}>{row.total_amount}</td>
                  <td style={{ padding: '10px 8px' }}>{row.transaction_count}</td>
                  <td style={{ padding: '10px 8px' }}>{row.avg_donation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{ color: '#8b949e' }}>
            Данные еще не сгенерированы. Запустите пайплайн Airflow для расчета витрин DWH.
          </div>
        )}
      </div>
    </div>
  );
};
