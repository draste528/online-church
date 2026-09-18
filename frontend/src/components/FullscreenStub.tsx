import React from 'react';

interface FullscreenStubProps {
  title: string;
  subtitle: string;
  iconSymbol: string;
  responsibleDev: string;
  features: string[];
}

export const FullscreenStub: React.FC<FullscreenStubProps> = ({
  title,
  subtitle,
  iconSymbol,
  responsibleDev,
  features,
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - 70px)',
      padding: '40px 20px',
      textAlign: 'center',
      background: 'radial-gradient(circle at center, #1b2030 0%, #0d1017 100%)',
      color: '#e6edf3',
    }}>
      <div style={{ fontSize: '72px', marginBottom: '16px', filter: 'drop-shadow(0 0 12px #d4af37)' }}>
        {iconSymbol}
      </div>
      <h1 style={{ fontSize: '2.5rem', fontWeight: 700, color: '#e5c07b', marginBottom: '8px' }}>
        {title}
      </h1>
      <p style={{ fontSize: '1.2rem', color: '#8b949e', maxWidth: '600px', marginBottom: '24px' }}>
        {subtitle}
      </p>
      
      <div style={{
        background: '#161b22',
        border: '1px solid #30363d',
        borderRadius: '8px',
        padding: '20px 30px',
        maxWidth: '500px',
        width: '100%',
        textAlign: 'left',
        marginBottom: '20px'
      }}>
        <div style={{ fontSize: '0.85rem', color: '#58a6ff', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
          Зона ответственности: <strong>{responsibleDev}</strong>
        </div>
        <div style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '8px' }}>Запланированный функционал:</div>
        <ul style={{ paddingLeft: '20px', color: '#8b949e', fontSize: '0.9rem', lineHeight: '1.6' }}>
          {features.map((feat, index) => (
            <li key={index}>{feat}</li>
          ))}
        </ul>
      </div>
      
      <div style={{ fontSize: '0.8rem', color: '#484f58' }}>
        Служебная заглушка спринта | API эндпоинты подключены
      </div>
    </div>
  );
};
