import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { NAV_LINKS } from '../config';
import { useI18n } from '../i18n';
import { LanguageSwitcher } from './LanguageSwitcher';

export const Navbar: React.FC = () => {
  const { m } = useI18n();
  return (
    <header className="navbar">
      <Link to="/" className="brand">
        <span className="brand-mark" aria-hidden="true">☦</span>
        <span>
          <span className="brand-title">{m.brand.title}</span>
          <span className="brand-sub">{m.brand.sub}</span>
        </span>
      </Link>
      <nav className="nav-links">
        {NAV_LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === '/'}
            className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
          >
            {m.nav[link.key]}
          </NavLink>
        ))}
      </nav>
      <LanguageSwitcher />
    </header>
  );
};
