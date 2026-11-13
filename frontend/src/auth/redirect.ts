export function safeNext(value: string | null, fallback = '/'): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || /[\\\x00-\x20]/.test(value)) return fallback;
  try {
    if (new URL(value, window.location.origin).origin !== window.location.origin) return fallback;
    return value;
  } catch { return fallback; }
}
