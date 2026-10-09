import React, { useEffect, useRef, useState } from 'react';
import { sendChatMessage, type ChatTurn } from '../api';

interface Message {
  id: number;
  from: 'me' | 'ai' | 'error';
  text: string;
}

const MAX_LENGTH = 2000;

const GREETING: Message = {
  id: 0,
  from: 'ai',
  text: 'Мир вам! Я ИИ-консультант прихода. Задайте вопрос о церковной жизни, а для исповеди и личной беседы приходите в храм.',
};

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [demo, setDemo] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const addMessage = (from: Message['from'], body: string) =>
    setMessages((m) => [...m, { id: nextId.current++, from, text: body }]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || sending) return;
    // The greeting and error notes are UI-only and must not reach the AI.
    const history = messages
      .filter((m) => m.id !== GREETING.id && m.from !== 'error')
      .map((m): ChatTurn => ({ role: m.from === 'me' ? 'user' : 'assistant', content: m.text }));
    setText('');
    setSending(true);
    addMessage('me', value);
    try {
      const { reply, mode } = await sendChatMessage(value, history);
      setDemo(mode === 'demo');
      addMessage('ai', reply);
    } catch (err) {
      addMessage('error', (err as Error).message);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="container narrow">
      <h1 className="page-title">Чат с консультантом</h1>
      <div className="card chat">
        <div className="chat-messages">
          {messages.map((m) => (
            <div key={m.id} className={`bubble ${m.from}`}>
              {m.from === 'ai' && <span className="bubble-label">ИИ-консультант</span>}
              {m.text}
            </div>
          ))}
          {sending && <div className="bubble ai typing">ИИ-консультант печатает…</div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-form" onSubmit={handleSend}>
          <input
            className="input"
            placeholder="Ваше сообщение…"
            value={text}
            maxLength={MAX_LENGTH}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={sending}>
            {sending ? 'Отправка…' : 'Отправить'}
          </button>
        </form>
      </div>
      {demo && (
        <p className="muted small">
          Демонстрационный режим: ключ ИИ-сервиса не настроен, поэтому ответы не генерируются.
        </p>
      )}
      <p className="muted small">
        Ответы даёт ИИ-консультант, а не священник. Беседа в чате не заменяет таинство исповеди: для исповеди
        приходите в храм.
      </p>
    </div>
  );
};
