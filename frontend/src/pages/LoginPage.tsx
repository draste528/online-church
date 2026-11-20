import { useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { safeNext } from '../auth/redirect';
import { AuthError } from '../auth/client';
import { useI18n } from '../i18n';
import { AUTH_MOCK } from '../config';
import { authErrorKey, Field, PasswordField } from '../components/AuthFields';

export function LoginPage() {
  const { login, status } = useAuth();
  const { m } = useI18n();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState<ReturnType<typeof authErrorKey> | null>(null);
  const [fields, setFields] = useState<string[]>([]);
  const next = safeNext(params.get('next') ?? '/cabinet');
  if (status === 'authenticated') return <Navigate to={next} replace />;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    pending.current = true; setBusy(true); setError(null); setFields([]);
    try { await login({ email: String(data.get('email')).trim(), password: String(data.get('password')) }); navigate(next, { replace: true }); }
    catch (failure) { setError(authErrorKey(failure)); if (failure instanceof AuthError) setFields(Object.keys(failure.fields)); }
    finally { data.delete('password'); (form.elements.namedItem('password') as HTMLInputElement).value = ''; pending.current = false; setBusy(false); }
  }
  return <section className="auth-page"><h1>{m.auth.login}</h1>{AUTH_MOCK && <p className="auth-notice">{m.auth.mock}</p>}<form className="auth-form" onSubmit={submit} aria-busy={busy}>
    <Field name="email" label={m.auth.email} type="email" autoComplete="email" required maxLength={254} error={fields.includes('email') ? m.auth.invalid : undefined} />
    <PasswordField name="password" label={m.auth.password} autoComplete="current-password" required error={fields.includes('password') ? m.auth.invalid : undefined} />
    {error && <p role="alert" className="field-error">{m.auth[error]}</p>}
    <button className="btn" disabled={busy || status === 'loading'}>{busy ? m.auth.loading : m.auth.login}</button>
    <Link to={`/register${params.has('next') ? `?next=${encodeURIComponent(next)}` : ''}`}>{m.auth.no_account}</Link>
  </form></section>;
}
