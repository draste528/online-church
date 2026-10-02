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

/**
 * Sends a chat message to the priest.
 * The backend endpoint is not implemented yet, so a polite placeholder reply is returned
 * when the request fails. Replace the body once POST /api/v1/chats/messages exists.
 */
export async function sendChatMessage(text: string): Promise<string> {
  try {
    const res = await fetch(`${API_URL}/api/v1/chats/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = (await res.json()) as { reply?: string };
    return data.reply ?? 'Ваше сообщение получено. Священник ответит в ближайшее время.';
  } catch {
    return 'Ваше сообщение получено. Священник ответит в ближайшее время.';
  }
}
