import React, { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { NAV_LINKS } from '../config';
import { useI18n } from '../i18n';
import { LanguageSwitcher } from './LanguageSwitcher';
import { useAuth } from '../auth/AuthProvider';

export const Navbar: React.FC = () => {
  const { m } = useI18n();
  const { user, status, logout } = useAuth();
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const signOut = async () => {
    setBusy(true); setError(false);
    try { await logout(); } catch { setError(true); } finally { setBusy(false); }
  };
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
      <div className="auth-nav">
        {status === 'guest' && <><Link to="/login">{m.auth.login}</Link><Link to="/register">{m.auth.register}</Link></>}
        {status === 'authenticated' && <details><summary>{user?.first_name || user?.username}</summary><Link to="/cabinet">{m.auth.cabinet}</Link><button type="button" disabled={busy} onClick={signOut}>{m.auth.logout}</button></details>}
        {error && <div role="alert">{m.auth.logout_failed}<button type="button" disabled={busy} onClick={signOut}>{m.auth.logout}</button></div>}
      </div>
    </header>
  );
};
