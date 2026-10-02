import React, { useEffect, useMemo, useState } from 'react';
import { fetchItems } from '../api';
import { CURRENCY } from '../config';
import { CATEGORY_LABELS, type Category, type ShopItem } from '../data/items';

export const ShopPage: React.FC = () => {
  const [items, setItems] = useState<ShopItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState<Category | 'all'>('all');
  const [cart, setCart] = useState<Record<string, number>>({});

  useEffect(() => {
    const controller = new AbortController();
    fetchItems(controller.signal)
      .then(setItems)
      .catch(() => undefined)
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const visible = useMemo(
    () => items.filter((i) => i.is_available && (category === 'all' || i.category === category)),
    [items, category]
  );

  const cartLines = useMemo(
    () => items.filter((i) => cart[i.id]).map((i) => ({ item: i, qty: cart[i.id] })),
    [items, cart]
  );
  const total = cartLines.reduce((sum, l) => sum + l.item.price * l.qty, 0);

  const change = (id: string, delta: number) =>
    setCart((prev) => {
      const qty = Math.max(0, (prev[id] ?? 0) + delta);
      const next = { ...prev };
      if (qty === 0) delete next[id];
      else next[id] = qty;
      return next;
    });

  return (
    <div className="container">
      <h1 className="page-title">Церковная лавка</h1>
      <div className="chips">
        {(Object.keys(CATEGORY_LABELS) as (Category | 'all')[]).map((c) => (
          <button key={c} className={c === category ? 'chip active' : 'chip'} onClick={() => setCategory(c)}>
            {CATEGORY_LABELS[c]}
          </button>
        ))}
      </div>

      <div className="shop-layout">
        <div className="grid-3">
          {loading && <p className="muted">Загрузка…</p>}
          {!loading && visible.length === 0 && <p className="muted">В этой категории пока ничего нет.</p>}
          {visible.map((item) => (
            <article key={item.id} className="card product">
              <span className="tag">{CATEGORY_LABELS[item.category]}</span>
              <h3>{item.title}</h3>
              <p className="muted">{item.description}</p>
              <div className="product-footer">
                <strong>{item.price} {CURRENCY}</strong>
                <button className="btn btn-primary btn-sm" onClick={() => change(item.id, 1)}>В корзину</button>
              </div>
            </article>
          ))}
        </div>

        <aside className="card cart">
          <h3>Корзина</h3>
          {cartLines.length === 0 ? (
            <p className="muted">Пока пусто.</p>
          ) : (
            <>
              {cartLines.map(({ item, qty }) => (
                <div key={item.id} className="cart-line">
                  <span>{item.title}</span>
                  <span className="qty">
                    <button onClick={() => change(item.id, -1)} aria-label="Убрать">−</button>
                    {qty}
                    <button onClick={() => change(item.id, 1)} aria-label="Добавить">+</button>
                  </span>
                </div>
              ))}
              <div className="cart-total">
                <span>Итого</span>
                <strong>{total.toFixed(2)} {CURRENCY}</strong>
              </div>
              <button className="btn btn-primary">Оформить заказ</button>
            </>
          )}
        </aside>
      </div>
    </div>
  );
};
