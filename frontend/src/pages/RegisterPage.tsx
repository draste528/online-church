import { useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { safeNext } from '../auth/redirect';
import { AuthError } from '../auth/client';
import { passwordIssue } from '../auth/validation';
import { useI18n } from '../i18n';
import { AUTH_MOCK } from '../config';
import { authErrorKey, DemographicFields, Field, PasswordField } from '../components/AuthFields';

export function RegisterPage() {
  const { register, status } = useAuth();
  const { m } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [error, setError] = useState<ReturnType<typeof authErrorKey> | null>(null);
  const [errors, setErrors] = useState<Record<string, keyof typeof m.auth>>({});
  const next = safeNext(params.get('next') ?? '/cabinet');
  if (status === 'authenticated') return <Navigate to={next} replace />;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending.current) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    const get = (key: string) => String(data.get(key) ?? '');
    const email = get('email').trim(), username = get('username').trim();
    const issues: typeof errors = {};
    if (!/^[a-zA-Z0-9_.-]{3,30}$/.test(username)) issues.username = 'username_rule';
    const issue = passwordIssue(get('password'), email, username);
    if (issue) issues.password = issue;
    if (get('password') !== get('confirm')) issues.confirm = 'mismatch';
    setErrors(issues); setError(null);
    if (Object.keys(issues).length) return;
    pending.current = true; setBusy(true);
    const consent = data.has('analytics_consent');
    try {
      await register({ username, email, password: get('password'), first_name: get('first_name').trim(), last_name: get('last_name').trim(), analytics_consent: consent,
        ...(consent ? { ...(get('birth_year') ? { birth_year: Number(get('birth_year')) } : {}), ...(get('city').trim() ? { city: get('city').trim() } : {}), ...(get('acquisition_source') ? { acquisition_source: get('acquisition_source') } : {}), preferred_language: get('preferred_language') } : {}),
      });
      navigate(next, { replace: true });
    } catch (failure) {
      setError(authErrorKey(failure));
      if (failure instanceof AuthError) setErrors(Object.fromEntries(Object.keys(failure.fields).map(key => [key, 'invalid'])));
    } finally {
      for (const name of ['password','confirm']) { data.delete(name); (form.elements.namedItem(name) as HTMLInputElement).value = ''; }
      pending.current = false; setBusy(false);
    }
  }
  const translated = Object.fromEntries(Object.entries(errors).map(([key, value]) => [key, m.auth[value]]));
  return <section className="auth-page auth-page-wide"><h1>{m.auth.register}</h1>{AUTH_MOCK && <p className="auth-notice">{m.auth.mock}</p>}<form className="auth-form" onSubmit={submit} aria-busy={busy}>
    <div className="auth-grid"><Field name="username" label={m.auth.username} autoComplete="username" required minLength={3} maxLength={30} pattern="[a-zA-Z0-9_.\\-]+" error={translated.username} /><Field name="email" label={m.auth.email} type="email" autoComplete="email" required maxLength={254} error={translated.email} />
    <Field name="first_name" label={m.auth.first_name} autoComplete="given-name" maxLength={100} error={translated.first_name} /><Field name="last_name" label={m.auth.last_name} autoComplete="family-name" maxLength={100} error={translated.last_name} /></div>
    <PasswordField name="password" label={m.auth.password} autoComplete="new-password" required strength error={translated.password} />
    <PasswordField name="confirm" label={m.auth.confirm} autoComplete="new-password" required error={translated.confirm} />
    <fieldset><legend>{m.auth.optional}</legend><DemographicFields errors={translated} registration /><label className="auth-consent"><input name="analytics_consent" type="checkbox" />{m.auth.analytics_consent}</label></fieldset>
    {error && <p className="field-error" role="alert">{m.auth[error]}</p>}<button className="btn" disabled={busy || status === 'loading'}>{busy ? m.auth.loading : m.auth.register}</button><Link to="/login">{m.auth.login}</Link>
  </form></section>;
}
