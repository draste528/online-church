import type { Registration, User } from '../auth/types';

// Browser-memory demo only: no fake JS-readable refresh cookie, no persistent PII.
// Real refresh persistence and HttpOnly cookies must be verified against SCRUM-30.
let user: User | null = null;
let passwordHash = '';
let session = false;
let token = '';
let failed = 0;
let lockedUntil = 0;
let attempts: number[] = [];
const reply = (status: number, body?: unknown) => new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
async function digest(value: string) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('');
}
function access() {
  token = crypto.randomUUID();
  return reply(200, { access_token: token, token_type: 'bearer', expires_in: 900, role: user?.role });
}
export async function authMock(path: string, init: RequestInit): Promise<Response> {
  attempts = attempts.filter(at => Date.now() - at < 60000);
  attempts.push(Date.now());
  if (attempts.length > 20) return reply(429);
  const body = init.body ? JSON.parse(String(init.body)) : {};
  if (path === '/register') {
    const data = body as Registration;
    if (user) return reply(409);
    passwordHash = await digest(data.password);
    const { password: _password, ...profile } = data;
    user = { ...profile, user_id: crypto.randomUUID(), email: data.email.toLowerCase(), role: 'parishioner' };
    return reply(201, user);
  }
  if (path === '/login') {
    if (Date.now() < lockedUntil) return reply(423);
    if (!user || user.email !== String(body.email).toLowerCase() || passwordHash !== await digest(body.password)) {
      failed++;
      if (failed >= 5) { lockedUntil = Date.now() + 900000; return reply(423); }
      return reply(401);
    }
    failed = 0; session = true; return access();
  }
  if (path === '/refresh') return session ? access() : reply(401);
  if (path === '/logout') { session = false; token = ''; return reply(204); }
  if (!user || new Headers(init.headers).get('Authorization') !== `Bearer ${token}` || !token) return reply(401);
  if (path === '/me' && init.method === 'PATCH') {
    const allowed = ['first_name','last_name','city','birth_year','preferred_language','analytics_consent'] as const;
    const changes = Object.fromEntries(allowed.filter(key => key in body).map(key => [key, body[key]]));
    user = { ...user, ...changes }; return reply(200, user);
  }
  if (path === '/me') return reply(200, user);
  if (path === '/change-password') {
    if (await digest(body.current_password) !== passwordHash) return reply(422, { detail: [{ loc: ['body','current_password'] }] });
    passwordHash = await digest(body.new_password); session = false; return reply(204);
  }
  return reply(404);
}
