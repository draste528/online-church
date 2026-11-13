import React, { useState } from 'react';
import { useI18n } from '../i18n';
import { LANGUAGES } from '../config';
import { passwordStrength } from '../auth/validation';
import { AuthError } from '../auth/client';

export function authErrorKey(error: unknown): 'duplicate' | 'credentials' | 'locked' | 'rate' | 'invalid' | 'network' {
  if (!(error instanceof AuthError)) return 'network';
  return ({ 409: 'duplicate', 401: 'credentials', 423: 'locked', 429: 'rate', 422: 'invalid' } as const)[error.status as 409] ?? 'network';
}
export function Field({ name, label, error, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { name: string; label: string; error?: string }) {
  return <label className="auth-field" htmlFor={name}><span>{label}</span><input {...props} id={name} name={name} aria-invalid={!!error} aria-describedby={error ? `${name}-error` : undefined} />{error && <span className="field-error" id={`${name}-error`}>{error}</span>}</label>;
}
export function PasswordField({ name, label, error, strength = false, ...props }: React.InputHTMLAttributes<HTMLInputElement> & { name: string; label: string; error?: string; strength?: boolean }) {
  const [show, setShow] = useState(false);
  const [score, setScore] = useState(0);
  const { m } = useI18n();
  return <div className="password-field"><Field {...props} name={name} label={label} error={error} type={show ? 'text' : 'password'} maxLength={128} onInput={event => setScore(passwordStrength(event.currentTarget.value))} /><button className="password-toggle" type="button" aria-pressed={show} onClick={() => setShow(!show)}>{show ? m.auth.hide : m.auth.show}</button>{strength && <div className="password-strength"><meter min={0} max={2} value={score} aria-label={m.auth.strength} /> {m.auth.strength}: {[m.auth.weak, m.auth.medium, m.auth.strong][score]}<p>{m.auth.password_rule}</p></div>}</div>;
}
export function DemographicFields({ errors, defaults = {}, registration = false }: { errors: Record<string, string>; defaults?: { birth_year?: number | null; city?: string | null; preferred_language?: string }; registration?: boolean }) {
  const { m, lang } = useI18n();
  return <div className="auth-grid">
    <Field name="birth_year" label={m.auth.birth_year} type="number" min={1900} max={new Date().getFullYear() - 14} defaultValue={defaults.birth_year ?? ''} error={errors.birth_year} />
    <Field name="city" label={m.auth.city} maxLength={80} autoComplete="address-level2" defaultValue={defaults.city ?? ''} error={errors.city} />
    {registration && <label className="auth-field">{m.auth.acquisition_source}<select name="acquisition_source" defaultValue=""><option value="">{m.auth.choose}</option>{(['friends','search','social','parish','other'] as const).map(key => <option key={key} value={key}>{m.auth[key]}</option>)}</select>{errors.acquisition_source && <span className="field-error">{errors.acquisition_source}</span>}</label>}
    <label className="auth-field">{m.auth.preferred_language}<select name="preferred_language" defaultValue={defaults.preferred_language ?? lang}>{LANGUAGES.map(item => <option key={item.code} value={item.code}>{item.label}</option>)}</select>{errors.preferred_language && <span className="field-error">{errors.preferred_language}</span>}</label>
  </div>;
}
