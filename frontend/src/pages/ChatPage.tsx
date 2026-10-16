import React, { useEffect, useRef, useState } from 'react';
import { ApiError, sendChatMessage, type ChatTurn } from '../api';
import { useI18n } from '../i18n';
import { describeApiError } from '../utils/errors';

interface Message {
  id: number;
  from: 'me' | 'ai' | 'error';
  text: string;
  /** For `error` messages: the failure, turned into text in the current language when rendered. */
  error?: ApiError;
}

const MAX_LENGTH = 2000;

export const ChatPage: React.FC = () => {
  const { m } = useI18n();
  const t = m.chat;
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [demo, setDemo] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const addMessage = (message: Omit<Message, 'id'>) =>
    setMessages((list) => [...list, { id: nextId.current++, ...message }]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || sending) return;
    // The greeting is not part of `messages` and error notes are UI-only: neither reaches the AI.
    const history = messages
      .filter((msg) => msg.from !== 'error')
      .map((msg): ChatTurn => ({ role: msg.from === 'me' ? 'user' : 'assistant', content: msg.text }));
    setText('');
    setSending(true);
    addMessage({ from: 'me', text: value });
    try {
      const { reply, mode } = await sendChatMessage(value, history);
      setDemo(mode === 'demo');
      addMessage({ from: 'ai', text: reply });
    } catch (err) {
      addMessage({ from: 'error', text: '', error: err instanceof ApiError ? err : new ApiError('http') });
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="container narrow">
      <h1 className="page-title">{t.title}</h1>
      <div className="card chat">
        <div className="chat-messages">
          <div className="bubble ai">
            <span className="bubble-label">{t.aiLabel}</span>
            {t.greeting}
          </div>
          {messages.map((msg) => (
            <div key={msg.id} className={`bubble ${msg.from}`}>
              {msg.from === 'ai' && <span className="bubble-label">{t.aiLabel}</span>}
              {msg.error ? describeApiError(msg.error, m) : msg.text}
            </div>
          ))}
          {sending && <div className="bubble ai typing">{t.typing}</div>}
          <div ref={bottomRef} />
        </div>
        <form className="chat-form" onSubmit={handleSend}>
          <input
            className="input"
            placeholder={t.placeholder}
            value={text}
            maxLength={MAX_LENGTH}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={sending}>
            {sending ? t.sending : t.send}
          </button>
        </form>
      </div>
      {demo && <p className="muted small">{t.demo}</p>}
      <p className="muted small">{t.disclaimer}</p>
    </div>
  );
};
