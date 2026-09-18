import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export const Navbar: React.FC = () => {
  const location = useLocation();

  const links = [
    { to: '/', label: 'Лавка (Товары)' },
    { to: '/treby', label: 'Подать записку' },
    { to: '/confession', label: 'Беседа с батюшкой' },
    { to: '/streams', label: 'Трансляции' },
    { to: '/analytics', label: 'DWH Аналитика' },
  ];

  return (
    <nav style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 32px',
      height: '70px',
      backgroundColor: '#161b22',
      borderBottom: '1px solid #30363d',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '24px' }}>☦</span>
        <span style={{ fontWeight: 700, fontSize: '1.1rem', color: '#e5c07b', letterSpacing: '0.5px' }}>
          Онлайн-Приход
        </span>
      </div>
      <div style={{ display: 'flex', gap: '8px' }}>
        {links.map((link) => {
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              style={{
                color: isActive ? '#e5c07b' : '#c9d1d9',
                textDecoration: 'none',
                padding: '8px 16px',
                borderRadius: '6px',
                fontSize: '0.9rem',
                backgroundColor: isActive ? '#21262d' : 'transparent',
                fontWeight: isActive ? 600 : 400,
                border: isActive ? '1px solid #d4af37' : '1px solid transparent',
              }}
            >
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
};
