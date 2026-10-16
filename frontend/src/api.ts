import { ANALYTICS_URL, API_URL, SHOW_DEV_HINTS } from './config';
import type { FundId } from './config';
import { FALLBACK_ITEMS, type ShopItem } from './data/items';

/** Dev-only console hint: the connection problem would otherwise be invisible behind the fallback data. */
function warnBackendProblem(what: string, reason: unknown, baseUrl: string = API_URL): void {
  if (!SHOW_DEV_HINTS) return;
  const text = reason instanceof Error ? reason.message : String(reason);
  console.warn(
    `[api] ${what}: ${text}. URL: ${baseUrl}. ` +
      'Is the service running (uvicorn on :8080 / :8000, or docker compose up) and are VITE_API_URL / VITE_ANALYTICS_URL correct?'
  );
}

/** Why a request failed. The UI maps the code to a text in the current language. */
export type ApiErrorCode = 'network' | 'http' | 'empty_reply' | 'invalid_input';

export class ApiError extends Error {
  code: ApiErrorCode;
  status?: number;
  /** Message sent by the backend itself (it is not translated). */
  detail?: string;

  constructor(code: ApiErrorCode, options: { status?: number; detail?: string } = {}) {
    super(options.detail ?? code);
    this.code = code;
    this.status = options.status;
    this.detail = options.detail;
  }
}

export interface ItemsResult {
  items: ShopItem[];
  /** "backend" — loaded from the API, "fallback" — the API failed or was empty and local data is shown. */
  source: 'backend' | 'fallback';
}

/** Loads the catalogue from the backend, falls back to local data (and says so) if it is offline. */
export async function fetchItems(signal?: AbortSignal): Promise<ItemsResult> {
  try {
    const res = await fetch(`${API_URL}/api/v1/items`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    // The backend names the key `item_id`; the UI uses `id`.
    const raw = (await res.json()) as (Partial<ShopItem> & { item_id?: string })[];
    const data = raw.map((r) => ({ ...r, id: r.id ?? r.item_id }) as ShopItem);
    if (data.length === 0) {
      warnBackendProblem('GET /api/v1/items returned an empty list', 'showing local data instead');
      return { items: FALLBACK_ITEMS, source: 'fallback' };
    }
    return { items: data, source: 'backend' };
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    warnBackendProblem('GET /api/v1/items failed', err);
    return { items: FALLBACK_ITEMS, source: 'fallback' };
  }
}

export interface OrderResult {
  order_id: string;
  total: number;
}

/** Sends the cart to the backend. Throws ApiError if the order is rejected (out of stock, offline, ...). */
export async function createOrder(lines: { item_id: string; quantity: number }[]): Promise<OrderResult> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines }),
    });
  } catch (err) {
    warnBackendProblem('POST /api/v1/orders failed', err);
    throw new ApiError('network');
  }
  if (!res.ok) throw new ApiError('http', { status: res.status });
  return (await res.json()) as OrderResult;
}

/** One earlier message of the dialogue, sent to the backend so the AI keeps the context. */
export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatReply {
  reply: string;
  /** "ai" — answered by the AI consultant, "demo" — the backend has no AI key configured. */
  mode: 'ai' | 'demo';
}

/** The backend keeps at most 20 history items; it uses the last 10 of them. */
export const MAX_HISTORY = 10;

/** The `detail` string of an error response, when the backend sent one. */
async function readErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // The body is not JSON.
  }
  return undefined;
}

/**
 * Sends a chat message and returns the consultant's reply.
 * Throws an ApiError when the message could not be delivered, so the UI never shows a success text for a failed request.
 */
export async function sendChatMessage(text: string, history: ChatTurn[] = []): Promise<ChatReply> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/chats/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text, history: history.slice(-MAX_HISTORY) }),
    });
  } catch (err) {
    warnBackendProblem('POST /api/v1/chats/messages failed', err);
    throw new ApiError('network');
  }
  if (res.status === 422) throw new ApiError('invalid_input', { status: 422 });
  if (!res.ok) throw new ApiError('http', { status: res.status, detail: await readErrorDetail(res) });
  const data = (await res.json()) as Partial<ChatReply>;
  if (!data.reply) throw new ApiError('empty_reply');
  return { reply: data.reply, mode: data.mode === 'ai' ? 'ai' : 'demo' };
}

export type DonationField = 'amount' | 'target_fund' | 'card_number' | 'card_expiry' | 'card_cvc';

export interface DonationRequest {
  amount: number;
  target_fund: FundId;
  card_number: string;
  card_expiry: string;
  card_cvc: string;
}

export interface DonationReceipt {
  donation_id: string;
  payment_status: 'completed';
  amount: number;
  currency: string;
  target_fund: FundId;
  transaction_reference: string;
  /** The backend returns only the last four digits; the full number is never stored. */
  card_last4: string;
  minecraft_blocks_awarded: number;
  created_at: string;
}

/** A rejected donation: a reason code plus, for a 422, the text of each wrong field (written by the backend). */
export class DonationError extends ApiError {
  fieldErrors: Partial<Record<DonationField, string>>;

  constructor(
    code: ApiErrorCode,
    options: { status?: number; detail?: string; fieldErrors?: Partial<Record<DonationField, string>> } = {}
  ) {
    super(code, options);
    this.fieldErrors = options.fieldErrors ?? {};
  }
}

const DONATION_FIELDS: readonly string[] = ['amount', 'target_fund', 'card_number', 'card_expiry', 'card_cvc'];

/** Sends the (fake) card payment. Throws DonationError with a reason code for every failure. */
export async function createDonation(request: DonationRequest): Promise<DonationReceipt> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/donations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  } catch (err) {
    warnBackendProblem('POST /api/v1/donations failed', err);
    throw new DonationError('network');
  }
  if (res.status === 422) {
    const fieldErrors: Partial<Record<DonationField, string>> = {};
    try {
      const body = (await res.json()) as { detail?: { loc?: unknown[]; msg?: string }[] };
      for (const item of body.detail ?? []) {
        const field = String(item.loc?.[item.loc.length - 1] ?? '');
        if (DONATION_FIELDS.includes(field) && item.msg) fieldErrors[field as DonationField] = item.msg;
      }
    } catch {
      // Not JSON: the generic message is shown.
    }
    throw new DonationError('invalid_input', { status: 422, fieldErrors });
  }
  if (!res.ok) throw new DonationError('http', { status: res.status, detail: await readErrorDetail(res) });
  return (await res.json()) as DonationReceipt;
}

export interface DonationSummary {
  currency: string;
  total_amount: number;
  donations_count: number;
  average_amount: number;
  by_fund: { fund: string; total: number; count: number; share_percent: number }[];
  /** Always 24 entries, hour 0..23, in the time zone named by `timezone`. */
  by_hour: { hour: number; count: number; total: number }[];
  peak_hour: number | null;
  timezone: string;
}

/** Loads the donation statistics from the analytics service. Throws ApiError. */
export async function fetchDonationSummary(signal?: AbortSignal): Promise<DonationSummary> {
  let res: Response;
  try {
    res = await fetch(`${ANALYTICS_URL}/api/v1/analytics/donations/summary`, { signal });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    warnBackendProblem('GET /api/v1/analytics/donations/summary failed', err, ANALYTICS_URL);
    throw new ApiError('network');
  }
  if (!res.ok) throw new ApiError('http', { status: res.status, detail: await readErrorDetail(res) });
  return (await res.json()) as DonationSummary;
}
