import { ANALYTICS_URL } from '../config';

const SESSION_STORAGE_KEY = 'church_parishioner_session_v1';

export interface SessionData {
  session_id: string;
  started_at: string;
  ended_at: string;
  duration_seconds: number;
  pages_visited: string[];
  total_donated: number;
  total_ordered: number;
  chat_questions_count: number;
  candles_lit_count: number;
  language: string;
}

function generateSessionId(): string {
  return 'sess_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now();
}

class SessionTracker {
  private data: SessionData;

  constructor() {
    this.data = this.loadOrInit();
  }

  private loadOrInit(): SessionData {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch {
      // Fallback to fresh session
    }
    const fresh: SessionData = {
      session_id: generateSessionId(),
      started_at: new Date().toISOString(),
      ended_at: new Date().toISOString(),
      duration_seconds: 0,
      pages_visited: [],
      total_donated: 0,
      total_ordered: 0,
      chat_questions_count: 0,
      candles_lit_count: 0,
      language: 'ru',
    };
    this.persist(fresh);
    return fresh;
  }

  private persist(data: SessionData): void {
    this.data = data;
    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data));
    } catch {
      // Ignore storage errors
    }
  }

  public recordPageView(pathname: string, language: string = 'ru'): void {
    const now = new Date();
    const started = new Date(this.data.started_at);
    const duration = Math.max(0, Math.floor((now.getTime() - started.getTime()) / 1000));

    const pages = this.data.pages_visited.includes(pathname)
      ? this.data.pages_visited
      : [...this.data.pages_visited, pathname];

    this.persist({
      ...this.data,
      ended_at: now.toISOString(),
      duration_seconds: duration,
      pages_visited: pages,
      language,
    });
  }

  public recordDonation(amount: number): void {
    this.persist({
      ...this.data,
      total_donated: Number((this.data.total_donated + amount).toFixed(2)),
    });
    this.syncWithBackend();
  }

  public recordOrder(total: number): void {
    this.persist({
      ...this.data,
      total_ordered: Number((this.data.total_ordered + total).toFixed(2)),
    });
    this.syncWithBackend();
  }

  public recordChatQuestion(): void {
    this.persist({
      ...this.data,
      chat_questions_count: this.data.chat_questions_count + 1,
    });
  }

  public recordCandleLit(): void {
    this.persist({
      ...this.data,
      candles_lit_count: this.data.candles_lit_count + 1,
    });
  }

  public syncWithBackend(): void {
    const now = new Date();
    const started = new Date(this.data.started_at);
    const duration = Math.max(0, Math.floor((now.getTime() - started.getTime()) / 1000));

    const payload = {
      ...this.data,
      ended_at: now.toISOString(),
      duration_seconds: duration,
    };

    // Use sendBeacon if available, otherwise fetch
    const url = `${ANALYTICS_URL}/api/v1/analytics/sessions`;
    try {
      if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
        navigator.sendBeacon(url, JSON.stringify(payload));
      } else {
        fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
          keepalive: true,
        }).catch(() => {});
      }
    } catch {
      // Silent error in analytics
    }
  }
}

export const sessionTracker = new SessionTracker();