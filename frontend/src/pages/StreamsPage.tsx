import React from 'react';
import { FullscreenStub } from '../components/FullscreenStub';

export const StreamsPage: React.FC = () => {
  return (
    <FullscreenStub
      title="Прямые Трансляции Богослужений"
      subtitle="Видеотрансляции воскресных Литургий, Всенощных бдений и праздничных молебнов"
      iconSymbol="📹"
      responsibleDev="Костя (Архитектура) & Антон (Спецификация)"
      features={[
        'Плеер с низким временем задержки (RTMP / HLS / YouTube API)',
        'Чат соборной молитвы во время богослужения',
        'Моментальная подача пожертвования во время прямого эфира',
        'Сбор аналитических метрик зрителей для хранилища DWH'
      ]}
    />
  );
};
