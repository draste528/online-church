import React from 'react';
import { FullscreenStub } from '../components/FullscreenStub';

export const TrebyPage: React.FC = () => {
  return (
    <FullscreenStub
      title="Поминовение и Требы"
      subtitle="Подача записок «О здравии» и «Об упокоении», заказ сорокоустов и молебнов онлайн"
      iconSymbol="📜"
      responsibleDev="Тамара (UI) & Евгений (Backend)"
      features={[
        'Форма ввода списка имен прихожан (до 15 имен в записке)',
        'Выбор типа службы: Простая записка, Заказная, Сорокоуст',
        'Отправка в таблицу treby_orders с валидацией статуса',
        'Моментальное внесение пожертвования на уставную деятельность'
      ]}
    />
  );
};
