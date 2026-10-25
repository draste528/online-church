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

interface StoredMessage {
  id: number;
  from: 'me' | 'ai' | 'error';
  text: string;
  errorCode?: any;
}

const MAX_LENGTH = 2000;
const CHAT_STORAGE_KEY = 'online_church_chat_session_v1';

/** Restores messages from sessionStorage so the dialogue survives tab/page navigation. */
function loadStoredChat(): { messages: Message[]; demo: boolean; draft: string } {
  try {
    const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
    if (!raw) return { messages: [], demo: false, draft: '' };
    const parsed = JSON.parse(raw);
    const messages: Message[] = Array.isArray(parsed.messages)
      ? parsed.messages.map((m: StoredMessage) => ({
          id: m.id,
          from: m.from,
          text: m.text,
          error: m.errorCode ? new ApiError(m.errorCode) : undefined,
        }))
      : [];
    return {
      messages,
      demo: Boolean(parsed.demo),
      draft: typeof parsed.draft === 'string' ? parsed.draft : '',
    };
  } catch {
    return { messages: [], demo: false, draft: '' };
  }
}

export const ChatPage: React.FC = () => {
  const { m } = useI18n();
  const t = m.chat;

  const [initialData] = useState(loadStoredChat);
  const [messages, setMessages] = useState<Message[]>(initialData.messages);
  const [text, setText] = useState<string>(initialData.draft);
  const [sending, setSending] = useState(false);
  const [demo, setDemo] = useState<boolean>(initialData.demo);

  const bottomRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(
    initialData.messages.length > 0 ? Math.max(...initialData.messages.map((msg) => msg.id)) + 1 : 1
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  // Persist messages and draft to sessionStorage whenever they change
  useEffect(() => {
    try {
      const payload = {
        messages: messages.map((msg) => ({
          id: msg.id,
          from: msg.from,
          text: msg.text,
          errorCode: msg.error?.code,
        })),
        demo,
        draft: text,
      };
      sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // Ignore quota/disabled storage in private browsing
    }
  }, [messages, demo, text]);

  const addMessage = (message: Omit<Message, 'id'>) =>
    setMessages((list) => [...list, { id: nextId.current++, ...message }]);

  const handleClearChat = () => {
    setMessages([]);
    setText('');
    try {
      sessionStorage.removeItem(CHAT_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  };

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="page-title">{t.title}</h1>
        {messages.length > 0 && (
          <button
            type="button"
            className="btn btn-secondary small"
            onClick={handleClearChat}
            style={{ marginBottom: '1rem' }}
          >
            {/* TODO(Tamara): add localized string t.clearChat to ru/be/en dictionary */}
            Очистить диалог
          </button>
        )}
      </div>

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