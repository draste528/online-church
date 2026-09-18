import React from 'react';
import { FullscreenStub } from '../components/FullscreenStub';

export const ConfessionPage: React.FC = () => {
  return (
    <FullscreenStub
      title="Духовная Беседа и Исповедь"
      subtitle="Запись на личный разговор со священником или оперативная духовная консультация"
      iconSymbol="🕊️"
      responsibleDev="Костя (Team Lead, AI) & Евгений (API)"
      features={[
        'Календарь свободных слотов дежурных священников (таблица appointments)',
        'Интерфейс текстового чата (таблицы chats и messages)',
        'ИИ-помощник священнослужителя для ответов на канонические вопросы',
        'Строгая конфиденциальность тайны исповеди'
      ]}
    />
  );
};
