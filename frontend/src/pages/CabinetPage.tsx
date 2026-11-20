import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAuth } from '../auth/AuthProvider';
import { authFetch } from '../api';
import { AuthError, checked, jsonBody } from '../auth/client';
import { passwordIssue } from '../auth/validation';
import { AUTH_MOCK } from '../config';
import { useI18n } from '../i18n';
import { authErrorKey, DemographicFields, Field, PasswordField } from '../components/AuthFields';
import type { User } from '../auth/types';

export function CabinetPage() {
  const { user, reloadUser, logout } = useAuth();
  const { m } = useI18n();
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const [message, setMessage] = useState<keyof typeof m.auth | null>(null);
  const [error, setError] = useState<keyof typeof m.auth | null>(null);
  const [fields, setFields] = useState<Record<string, keyof typeof m.auth>>({});
  useEffect(() => {
    let active = true;
    reloadUser().then(value => { if (active) setProfile(value); }).catch(() => { if (active) setLoadFailed(true); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>, password: boolean) {
    event.preventDefault();
    if (pending.current) return;
    const form = event.currentTarget, data = new FormData(form);
    const get = (key: string) => String(data.get(key) ?? '');
    setMessage(null); setError(null); setFields({});
    if (password) {
      const issue = passwordIssue(get('new_password'), user?.email, user?.username);
      if (issue) { setFields({ new_password: issue }); return; }
      if (get('new_password') !== get('confirm')) { setFields({ confirm: 'mismatch' }); return; }
    }
    pending.current = true; setBusy(true);
    try {
      if (password) {
        await checked<void>(await authFetch('/api/v1/auth/change-password', jsonBody({ current_password: get('current_password'), new_password: get('new_password') })));
        setMessage('password_changed');
      } else {
        const consent = data.has('analytics_consent');
        await checked<User>(await authFetch('/api/v1/auth/me', { ...jsonBody({ first_name: get('first_name').trim(), last_name: get('last_name').trim(), analytics_consent: consent,
          ...(consent ? { city: get('city').trim() || null, birth_year: get('birth_year') ? Number(get('birth_year')) : null, preferred_language: get('preferred_language') } : {}),
        }), method: 'PATCH' }));
        setProfile(await reloadUser()); setMessage('saved');
      }
    } catch (failure) {
      setError(authErrorKey(failure));
      if (failure instanceof AuthError) {
        setFields(Object.fromEntries(Object.keys(failure.fields).map(key => [key, 'invalid'])));
        if (password && failure.status === 400) setFields({ current_password: 'invalid' });
      }
    } finally {
      if (password) for (const name of ['current_password','new_password','confirm']) { data.delete(name); (form.elements.namedItem(name) as HTMLInputElement).value = ''; }
      pending.current = false; setBusy(false);
    }
  }
  if (loading) return <p role="status">{m.auth.loading}</p>;
  if (loadFailed || !profile) return <p role="alert">{m.auth.network}</p>;
  const errors = Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, m.auth[value]]));
  return <section className="auth-page auth-page-wide"><h1>{m.auth.cabinet}</h1>{AUTH_MOCK && <p className="auth-notice">{m.auth.mock}</p>}
    <dl className="auth-identity"><dt>{m.auth.username}</dt><dd>{profile.username}</dd><dt>{m.auth.email}</dt><dd>{profile.email}</dd></dl>
    {message && <p className="auth-notice" role="status">{m.auth[message]}</p>}{error && <p className="field-error" role="alert">{m.auth[error]}</p>}
    <form className="auth-form" onSubmit={event => submit(event, false)} aria-busy={busy}><h2>{m.auth.profile}</h2><fieldset disabled={busy}><div className="auth-grid"><Field name="first_name" label={m.auth.first_name} autoComplete="given-name" maxLength={100} defaultValue={profile.first_name ?? ''} error={errors.first_name} /><Field name="last_name" label={m.auth.last_name} autoComplete="family-name" maxLength={100} defaultValue={profile.last_name ?? ''} error={errors.last_name} /></div><DemographicFields defaults={profile} errors={errors} /><label className="auth-consent"><input type="checkbox" name="analytics_consent" defaultChecked={profile.analytics_consent ?? false} />{m.auth.analytics_consent}</label><button className="btn">{m.auth.save}</button></fieldset></form>
    <form className="auth-form" onSubmit={event => submit(event, true)} aria-busy={busy}><h2>{m.auth.change_password}</h2><fieldset disabled={busy}><PasswordField name="current_password" label={m.auth.current_password} autoComplete="current-password" required error={errors.current_password} /><PasswordField name="new_password" label={m.auth.new_password} autoComplete="new-password" required strength error={errors.new_password} /><PasswordField name="confirm" label={m.auth.confirm} autoComplete="new-password" required error={errors.confirm} /><button className="btn">{m.auth.change_password}</button></fieldset></form>
    <button className="btn" disabled={busy} onClick={() => { void logout().catch(() => setError('logout_failed')); }}>{m.auth.logout}</button>
  </section>;
}
