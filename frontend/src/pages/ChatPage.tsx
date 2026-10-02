import React, { useEffect, useRef, useState } from 'react';
import { sendChatMessage } from '../api';

interface Message {
  id: number;
  from: 'me' | 'priest';
  text: string;
}

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    { id: 0, from: 'priest', text: 'Мир вам! Чем могу помочь? Напишите свой вопрос.' },
  ]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || sending) return;
    setText('');
    setSending(true);
    setMessages((m) => [...m, { id: Date.now(), from: 'me', text: value }]);
    const reply = await sendChatMessage(value);
    setMessages((m) => [...m, { id: Date.now() + 1, from: 'priest', text: reply }]);
    setSending(false);
  };

  return (
    <div className="container narrow">
      <h1 className="page-title">Чат со священником</h1>
      <div className="card chat">
        <div className="chat-messages">
          {messages.map((m) => (
            <div key={m.id} className={m.from === 'me' ? 'bubble me' : 'bubble priest'}>
              {m.text}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <form className="chat-form" onSubmit={handleSend}>
          <input
            className="input"
            placeholder="Ваше сообщение…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={sending}>Отправить</button>
        </form>
      </div>
      <p className="muted small">
        Беседа в чате не заменяет таинство исповеди. Для исповеди приходите в храм.
      </p>
    </div>
  );
};
