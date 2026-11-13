import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { useI18n } from '../i18n';
export function RequireAuth({ children, roles }: { children: ReactNode; roles?: string[] }) {
  const { status, user } = useAuth();
  const location = useLocation();
  const { m } = useI18n();
  if (status === 'loading') return <p role="status">{m.auth.loading}</p>;
  if (status === 'guest') return <Navigate replace to={`/login?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`} />;
  if (roles && (!user || !roles.includes(user.role))) return <p role="alert">{m.auth.forbidden}</p>;
  return <>{children}</>;
}
