import React from 'react';
import { Link, NavLink } from 'react-router-dom';
import { NAV_LINKS } from '../config';

export const Navbar: React.FC = () => (
  <header className="navbar">
    <Link to="/" className="brand">
      <span className="brand-mark" aria-hidden="true">☦</span>
      <span>
        <span className="brand-title">Онлайн-Церковь</span>
        <span className="brand-sub">Православный приход</span>
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
          {link.label}
        </NavLink>
      ))}
    </nav>
  </header>
);
