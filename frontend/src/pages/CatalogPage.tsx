import React from 'react';
import { FullscreenStub } from '../components/FullscreenStub';

export const CatalogPage: React.FC = () => {
  return (
    <FullscreenStub
      title="Церковная Лавка"
      subtitle="Приобретение восковых свечей, алтарного ладана, освященных икон и заказ просфор"
      iconSymbol="🕯️"
      responsibleDev="Тамара (UI) & Антон (Данные)"
      features={[
        'Каталог восковых и алтарных свечей с фильтрацией по стоимости',
        'Корзина заказов и выбор святого покровителя',
        'Интеграция с таблицей items операционной базы данных',
        'Расчет пожертвования: 1 рубль = +1 блок в соборе Minecraft'
      ]}
    />
  );
};
