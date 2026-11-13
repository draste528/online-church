// Requires production preview on localhost:3017 and a disposable Chrome CDP session on :9223.
// Emulates the SCRUM-30 HTTP contract; does not validate backend implementation.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const pages = await (await fetch('http://localhost:9223/json/list')).json();
const ws = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }));
let id = 0, user = null, signedIn = false, token = 'test-access', registerBody;
const pending = new Map();
const failures = [];
function send(method, params = {}) {
  return new Promise((resolve, reject) => { const key = ++id; pending.set(key, { resolve, reject }); ws.send(JSON.stringify({ id: key, method, params })); });
}
ws.addEventListener('message', async event => {
  const message = JSON.parse(event.data);
  if (message.id) { const task = pending.get(message.id); pending.delete(message.id); message.error ? task?.reject(message.error) : task?.resolve(message.result); return; }
  if (message.method === 'Runtime.exceptionThrown') failures.push(message.params.exceptionDetails.text);
  if (message.method !== 'Fetch.requestPaused') return;
  const { requestId, request } = message.params;
  const path = new URL(request.url).pathname;
  let status = 200, body = {}, cookie;
  if (request.method === 'OPTIONS') status = 204;
  else if (path.endsWith('/register')) {
    registerBody = JSON.parse(request.postData);
    const { password: ignored, ...data } = registerBody;
    user = { ...data, user_id: 'qa-user', role: 'parishioner' }; status = 201; body = user;
  } else if (path.endsWith('/login')) {
    signedIn = true; body = { access_token: token, token_type: 'bearer', role: 'parishioner', expires_in: 900 };
    cookie = 'refresh_token=qa-refresh; HttpOnly; SameSite=Strict; Path=/api/v1/auth';
  } else if (path.endsWith('/refresh')) { status = signedIn ? 200 : 401; body = { access_token: token, role: 'parishioner' }; }
  else if (path.endsWith('/logout')) { signedIn = false; status = 204; cookie = 'refresh_token=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/api/v1/auth'; }
  else if (path.endsWith('/change-password')) status = 204;
  else if (path.endsWith('/me')) {
    if (!signedIn || Object.entries(request.headers).find(([key]) => key.toLowerCase() === 'authorization')?.[1] !== `Bearer ${token}`) status = 401;
    else { if (request.method === 'PATCH') user = { ...user, ...JSON.parse(request.postData) }; body = user; }
  }
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': 'http://localhost:3017', 'Access-Control-Allow-Credentials': 'true', 'Access-Control-Allow-Headers': 'content-type,authorization', 'Access-Control-Allow-Methods': 'GET,POST,PATCH,OPTIONS', ...(cookie ? { 'Set-Cookie': cookie } : {}) };
  await send('Fetch.fulfillRequest', { requestId, responseCode: status, responseHeaders: Object.entries(headers).map(([name, value]) => ({ name, value })), ...(status !== 204 ? { body: Buffer.from(JSON.stringify(body)).toString('base64') } : {}) });
});
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
};
async function wait(expression) {
  for (let i = 0; i < 100; i++) { if (await evaluate(`Boolean(${expression})`)) return; await new Promise(resolve => setTimeout(resolve, 100)); }
  throw new Error(`Timeout: ${expression}`);
}
const delay = () => new Promise(resolve => setTimeout(resolve, 350));
async function go(path) { await send('Page.navigate', { url: `http://localhost:3017${path}` }); await delay(); await wait("document.querySelector('h1') !== null"); }
async function fill(values) { await evaluate(`(() => { for (const [name,value] of Object.entries(${JSON.stringify(values)})) { const input = document.querySelector('[name="'+name+'"]'); input.value = value; input.dispatchEvent(new Event('input',{bubbles:true})); } })()`); }
async function screenshot(name) {
  const { cssContentSize } = await send('Page.getLayoutMetrics');
  const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: cssContentSize.width, height: cssContentSize.height, scale: 1 } });
  await writeFile(new URL(`../../docs/auth/${name}.png`, import.meta.url), Buffer.from(image.data, 'base64'));
}
try {
  await mkdir(new URL('../../docs/auth/', import.meta.url), { recursive: true });
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: '*:8080/api/v1/auth/*' }, { urlPattern: '*:8000/*' }] });
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await go('/cabinet'); await wait("location.pathname === '/login' && !document.querySelector('button.btn').disabled");
  assert.equal(await evaluate("new URLSearchParams(location.search).get('next')"), '/cabinet');
  await screenshot('login');
  await go('/register'); await wait("!document.querySelector('button.btn').disabled");
  assert.equal(await evaluate("document.querySelector('[name=analytics_consent]').checked"), false);
  await fill({ username: 'parishioner', email: 'qa@example.com', first_name: 'Anna', last_name: 'Ivanova', password: 'SecureParish2026!', confirm: 'SecureParish2026!', city: 'Minsk', birth_year: '1995' });
  await screenshot('register');
  await evaluate("document.querySelector('form').requestSubmit()");
  await wait("location.pathname === '/cabinet' && document.querySelector('[name=first_name]')");
  assert.equal(registerBody.analytics_consent, false);
  for (const key of ['city','birth_year','preferred_language','acquisition_source']) assert.ok(!(key in registerBody));
  await screenshot('cabinet');
  await send('Page.reload'); await delay(); await wait("document.querySelector('[name=first_name]') !== null");
  assert.equal(await evaluate('location.pathname'), '/cabinet');
  const storage = await evaluate('JSON.stringify({...localStorage,...sessionStorage})');
  assert.ok(!storage.includes(token)); assert.ok(!storage.includes('SecureParish2026!')); assert.ok(!storage.includes('qa@example.com'));
  const cookies = await send('Network.getCookies', { urls: ['http://localhost:8080/api/v1/auth/me'] });
  assert.ok(cookies.cookies.find(cookie => cookie.name === 'refresh_token' && cookie.httpOnly));
  assert.ok(!(await evaluate('document.cookie')).includes('refresh_token'));
  await fill({ first_name: 'Maria' }); await evaluate("document.querySelector('form').requestSubmit()");
  await wait("document.querySelector('[role=status]') !== null"); assert.equal(user.first_name, 'Maria');
  await fill({ current_password: 'SecureParish2026!', new_password: 'NewSecureParish2026!', confirm: 'NewSecureParish2026!' });
  await evaluate("document.querySelectorAll('form')[1].requestSubmit()");
  await wait("document.querySelector('[name=new_password]').value === ''");
  for (const lang of ['en','be','ru']) {
    await evaluate(`localStorage.setItem('oc.lang','${lang}')`); await send('Page.reload'); await delay();
    await wait(`document.documentElement.lang === '${lang}' && document.querySelector('[name=first_name]')`);
    assert.ok(!(await evaluate("document.querySelector('h1').textContent")).includes('?'));
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 375, height: 812, deviceScaleFactor: 1, mobile: true });
  await screenshot('cabinet-mobile');
  assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
  await evaluate("document.querySelector('.auth-nav details').open = true; document.querySelector('.auth-nav button').click()");
  await wait("location.pathname === '/login'");
  await go('/login?next=https://evil.com'); await wait("!document.querySelector('button.btn').disabled");
  await screenshot('login-mobile');
  await fill({ email: 'qa@example.com', password: 'SecureParish2026!' }); await evaluate("document.querySelector('form').requestSubmit()");
  await wait("location.pathname === '/'");
  signedIn = false;
  await go('/register'); await wait("document.querySelector('[name=username]') !== null");
  await screenshot('register-mobile'); assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth'));
  assert.deepEqual(failures, []);
  console.log('PASS: registration, consent payload, login, F5, storage, HttpOnly fixture, profile, password, ru/en/be, logout, safe redirect, mobile; 6 screenshots saved.');
} finally { ws.close(); }
