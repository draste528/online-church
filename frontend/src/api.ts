import { API_URL } from './config';
import { FALLBACK_ITEMS, type ShopItem } from './data/items';

/** Loads the catalogue from the backend, falls back to local data if it is offline. */
export async function fetchItems(signal?: AbortSignal): Promise<ShopItem[]> {
  try {
    const res = await fetch(`${API_URL}/api/v1/items`, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    // The backend names the key `item_id`; the UI uses `id`.
    const raw = (await res.json()) as (Partial<ShopItem> & { item_id?: string })[];
    const data = raw.map((r) => ({ ...r, id: r.id ?? r.item_id }) as ShopItem);
    return data.length > 0 ? data : FALLBACK_ITEMS;
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    return FALLBACK_ITEMS;
  }
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

async function readErrorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // The body is not JSON, fall through to the generic text.
  }
  if (res.status === 422) return 'Сообщение не принято сервером: оно пустое или слишком длинное.';
  return `Ошибка сервера (HTTP ${res.status}).`;
}

/**
 * Sends a chat message and returns the consultant's reply.
 * Throws an Error with a readable message when the message could not be delivered,
 * so the UI never shows a success text for a failed request.
 */
export async function sendChatMessage(text: string, history: ChatTurn[] = []): Promise<ChatReply> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/chats/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text, history: history.slice(-MAX_HISTORY) }),
    });
  } catch {
    throw new Error('Не удалось связаться с сервером. Проверьте, что backend запущен.');
  }
  if (!res.ok) throw new Error(await readErrorMessage(res));
  const data = (await res.json()) as Partial<ChatReply>;
  if (!data.reply) throw new Error('Сервер вернул пустой ответ.');
  return { reply: data.reply, mode: data.mode === 'ai' ? 'ai' : 'demo' };
}
