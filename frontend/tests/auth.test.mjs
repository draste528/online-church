import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

async function moduleFrom(path, replace = value => value) {
  const source = replace(await readFile(new URL(path, import.meta.url), 'utf8'));
  const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}#${Math.random()}`);
}
const client = () => moduleFrom('../src/auth/client.ts', source => source.replace("import { API_URL, AUTH_MOCK } from '../config';", "const API_URL = 'https://api.test'; const AUTH_MOCK = false;"));
const json = (status, body = {}) => new Response(JSON.stringify(body), { status });

test('parallel and delayed 401 responses share one refresh and retry with new access', async () => {
  const api = await client();
  let token = 'old', refreshes = 0, expired = 0;
  api.connectAuth({ token: () => token, accept: reply => { token = reply.access_token; }, expire: () => { expired++; } });
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (url.endsWith('/refresh')) {
      refreshes++;
      assert.equal(init.credentials, 'include');
      await new Promise(resolve => setTimeout(resolve, 15));
      return json(200, { access_token: 'new' });
    }
    const bearer = new Headers(init.headers).get('Authorization');
    if (bearer === 'Bearer old') {
      if (url.endsWith('/slow')) await new Promise(resolve => setTimeout(resolve, 40));
      return json(401);
    }
    assert.equal(bearer, 'Bearer new');
    return json(200);
  };
  try {
    const results = await Promise.all(Array.from({ length: 10 }, (_, index) => api.authenticatedFetch(`/api/v1/${index === 9 ? 'slow' : index}`)));
    assert.ok(results.every(result => result.status === 200));
    assert.equal(refreshes, 1); assert.equal(expired, 0);
  } finally { globalThis.fetch = original; }
});

test('refresh 401 expires the session without an infinite retry', async () => {
  const api = await client(); let refreshes = 0, expired = 0;
  api.connectAuth({ token: () => 'old', accept() {}, expire() { expired++; api.invalidateAuth(); } });
  const original = globalThis.fetch;
  globalThis.fetch = async url => { if (url.endsWith('/refresh')) refreshes++; return json(401); };
  try {
    await assert.rejects(api.authenticatedFetch('/api/v1/auth/me'), { status: 401 });
    assert.equal(refreshes, 1); assert.equal(expired, 1);
  } finally { globalThis.fetch = original; }
});

test('logout invalidates an in-flight refresh', async () => {
  const api = await client(); let accept = 0, release;
  api.connectAuth({ token: () => null, accept() { accept++; }, expire() {} });
  const original = globalThis.fetch;
  globalThis.fetch = () => new Promise(resolve => { release = resolve; });
  try {
    const refresh = api.refreshAuth(); api.invalidateAuth();
    release(json(200, { access_token: 'stale' }));
    await assert.rejects(refresh, { status: 401 }); assert.equal(accept, 0);
  } finally { globalThis.fetch = original; }
});

test('network failure does not revoke the session', async () => {
  const api = await client(); let expired = 0;
  api.connectAuth({ token: () => 'old', accept() {}, expire() { expired++; } });
  const original = globalThis.fetch;
  globalThis.fetch = async url => { if (url.endsWith('/refresh')) throw new TypeError('offline'); return json(401); };
  try { await assert.rejects(api.authenticatedFetch('/api/v1/auth/me')); assert.equal(expired, 0); }
  finally { globalThis.fetch = original; }
});

test('redirect rejects external, protocol-relative and backslash paths', async () => {
  globalThis.window = { location: { origin: 'https://church.test' } };
  const { safeNext } = await moduleFrom('../src/auth/redirect.ts');
  for (const path of ['https://evil.com', '//evil.com', '/\\evil.com', '/\nevil.com', 'javascript:alert(1)']) assert.equal(safeNext(path), '/');
  assert.equal(safeNext('/cabinet?tab=profile#name'), '/cabinet?tab=profile#name');
  delete globalThis.window;
});

test('password rules match SCRUM-30 length, letters, digits and identity', async () => {
  const { passwordIssue } = await moduleFrom('../src/auth/validation.ts');
  for (const value of ['short1', 'OnlyLettersHere', '12345678900', 'a1'.repeat(65)]) assert.equal(passwordIssue(value), 'password_rule');
  assert.equal(passwordIssue('Username123', '', 'username123'), 'identity_rule');
  assert.equal(passwordIssue('Приход2026!'), undefined);
});
