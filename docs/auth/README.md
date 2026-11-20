# FE-005 / SCRUM-31

Frontend implementation follows the contract in SCRUM-30 (read 2026-11-13).
The backend authentication endpoints are not present on `dev` yet.

## Running

`cd frontend && npm run build` builds the production application.
`npm run test:auth` runs the refresh, concurrency, logout-race, redirect and
password-validation tests with Node's test runner and the existing TypeScript dependency.

`VITE_AUTH_MOCK` defaults to `false`. Set it to `true` in `frontend/.env.local`
and restart Vite to use the in-memory demo in `src/data/authMock.ts`.
Register a new account in that demo; it does not have a preset account.
It never writes tokens, passwords or profile data to browser storage.
Reloading the demo clears its accounts and session. JavaScript cannot issue an
HttpOnly cookie, so the real F5/cookie acceptance check requires SCRUM-30.

With the real API, registration returns a profile summary, then the frontend
logs in and loads `/auth/me`. Startup refresh is shared even with React StrictMode.
Access tokens are held in AuthProvider state; auth requests include cookies.
Parallel 401 responses share a refresh, and late 401s reuse the refreshed token.
Logout invalidates in-flight refresh results and waits for cookie rotation before
revoking the session. Failed logout shows a retry action because local state
clearance alone cannot revoke a server cookie.

The current checkout had no SCRUM-20 cabinet implementation. `/cabinet` now hosts
the protected profile and password forms; future cabinet sections can share its
RequireAuth wrapper. Roles are accepted by the wrapper; backend permissions remain
authoritative.

Validation follows SCRUM-30 defaults: username 3–30 ASCII letters/digits/`_.-`,
password 10–128 characters with a letter and digit, differing from email/username,
birth year 1900 through current year minus 14, city at most 80 characters.
The configurable backend password minimum and common-password denylist are not
available in this checkout. The server remains authoritative and 422 errors are
mapped to translated messages beneath the corresponding field.

## Browser verification and screenshots

`frontend/tests/auth-browser.mjs` uses Chrome DevTools Protocol without extra npm
dependencies. Start production preview on `localhost:3017` and a disposable
headless Chrome with remote debugging on port 9223, then run the script.
Use a browser profile outside `frontend/` so Vite does not watch Chrome's files.

The script intercepts auth HTTP requests with a SCRUM-30 fixture. It checks
registration, omission of demographics without consent, automatic login, F5,
absence of secrets/PII in storage, an HttpOnly test cookie invisible to JS,
profile editing, password clearing, ru/en/be, logout, unsafe `next` rejection,
and no horizontal overflow at 375 px. This validates frontend behavior against
an emulated contract, not the security or behavior of the future backend.

Screenshots contain synthetic test data:

| Page | Desktop | Mobile |
| --- | --- | --- |
| Registration | [register.png](register.png) | [register-mobile.png](register-mobile.png) |
| Login | [login.png](login.png) | [login-mobile.png](login-mobile.png) |
| Cabinet | [cabinet.png](cabinet.png) | [cabinet-mobile.png](cabinet-mobile.png) |

After SCRUM-30 is merged, repeat the browser acceptance flow with interception
disabled, explicit CORS credentials enabled, and the same hostname for frontend
and API (for example `localhost` on different ports). Verify the actual
`refresh_token` cookie has HttpOnly, SameSite and production Secure flags.
