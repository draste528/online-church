import React, { useEffect, useMemo, useState } from 'react';
import { createOrder, fetchItems } from '../api';
import { CURRENCY, SHOW_DEV_HINTS } from '../config';
import { CATEGORIES, type CategoryFilter, type ShopItem } from '../data/items';
import { useI18n } from '../i18n';

type SortKey = 'default' | 'price_asc' | 'price_desc' | 'title';
const SORT_KEYS: SortKey[] = ['default', 'price_asc', 'price_desc', 'title'];

export const ShopPage: React.FC = () => {
  const { m, locale } = useI18n();
  const t = m.shop;
  const [items, setItems] = useState<ShopItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [offline, setOffline] = useState(false);
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState<SortKey>('default');
  const [cart, setCart] = useState<Record<string, number>>({});
  const [checkingOut, setCheckingOut] = useState(false);
  const [orderId, setOrderId] = useState<string | null>(null);
  const [orderError, setOrderError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetchItems(controller.signal)
      .then(({ items: loaded, source }) => {
        setItems(loaded);
        setOffline(source === 'fallback');
      })
      .catch(() => undefined) // fetchItems already falls back to local data; only an abort reaches here
      .finally(() => {
        // An aborted request (StrictMode remount) must not end the loading state of the next one.
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const list = items.filter(
      (i) =>
        i.is_available &&
        (category === 'all' || i.category === category) &&
        (!needle || `${i.title} ${i.description}`.toLowerCase().includes(needle))
    );
    if (sort === 'price_asc') list.sort((a, b) => a.price - b.price);
    else if (sort === 'price_desc') list.sort((a, b) => b.price - a.price);
    else if (sort === 'title') list.sort((a, b) => a.title.localeCompare(b.title, locale));
    return list;
  }, [items, category, query, sort, locale]);

  const cartLines = useMemo(
    () => items.filter((i) => cart[i.id]).map((i) => ({ item: i, qty: cart[i.id] })),
    [items, cart]
  );
  const total = cartLines.reduce((sum, l) => sum + l.item.price * l.qty, 0);

  const change = (id: string, delta: number) => {
    setOrderId(null);
    setOrderError(false);
    setCart((prev) => {
      const qty = Math.max(0, (prev[id] ?? 0) + delta);
      const next = { ...prev };
      if (qty === 0) delete next[id];
      else next[id] = qty;
      return next;
    });
  };

  const checkout = async () => {
    setCheckingOut(true);
    setOrderError(false);
    try {
      const result = await createOrder(cartLines.map((l) => ({ item_id: l.item.id, quantity: l.qty })));
      setOrderId(result.order_id);
      setCart({});
      // Stock has changed: reload the catalogue so that sold-out items disappear.
      fetchItems()
        .then(({ items: loaded, source }) => {
          setItems(loaded);
          setOffline(source === 'fallback');
        })
        .catch(() => undefined);
    } catch {
      setOrderError(true);
    } finally {
      setCheckingOut(false);
    }
  };

  return (
    <div className="container">
      <h1 className="page-title">{t.title}</h1>
      {SHOW_DEV_HINTS && offline && (
        <p className="dev-note" role="status">
          {t.offlineNote}
        </p>
      )}
      <div className="chips">
        {CATEGORIES.map((c) => (
          <button key={c} className={c === category ? 'chip active' : 'chip'} onClick={() => setCategory(c)}>
            {t.categories[c]}
          </button>
        ))}
      </div>

      <div className="shop-tools">
        <input
          className="input"
          type="search"
          placeholder={t.searchPlaceholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select className="input select" aria-label={t.sortLabel} value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
          {SORT_KEYS.map((k) => (
            <option key={k} value={k}>{t.sort[k]}</option>
          ))}
        </select>
      </div>

      <div className="shop-layout">
        <div className="grid-3">
          {loading && <p className="muted">{t.loading}</p>}
          {!loading && visible.length === 0 && <p className="muted">{t.empty}</p>}
          {visible.map((item) => (
            <article key={item.id} className="card product">
              <span className="tag">{t.categories[item.category]}</span>
              <h3>{item.title}</h3>
              <p className="muted">{item.description}</p>
              <div className="product-footer">
                <strong>{item.price} {CURRENCY}</strong>
                <button className="btn btn-primary btn-sm" onClick={() => change(item.id, 1)}>{t.addToCart}</button>
              </div>
            </article>
          ))}
        </div>

        <aside className="card cart">
          <h3>{t.cart}</h3>
          {orderId && (
            <p role="status">
              <strong>{t.orderDone}.</strong> {t.orderNumber}: <span className="muted">{orderId.slice(0, 8)}</span>
            </p>
          )}
          {orderError && <p className="error" role="alert">{t.orderError}</p>}
          {cartLines.length === 0 ? (
            !orderId && <p className="muted">{t.cartEmpty}</p>
          ) : (
            <>
              {cartLines.map(({ item, qty }) => (
                <div key={item.id} className="cart-line">
                  <span>{item.title}</span>
                  <span className="qty">
                    <button onClick={() => change(item.id, -1)} aria-label={t.remove}>−</button>
                    {qty}
                    <button onClick={() => change(item.id, 1)} aria-label={t.add}>+</button>
                  </span>
                </div>
              ))}
              <div className="cart-total">
                <span>{t.total}</span>
                <strong>{total.toFixed(2)} {CURRENCY}</strong>
              </div>
              <button className="btn btn-primary" onClick={checkout} disabled={checkingOut}>
                {checkingOut ? t.checkingOut : t.checkout}
              </button>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};
