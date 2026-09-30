"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Role = "user" | "assistant";

type Message = {
  id: string;
  role: Role;
  content: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

const SUGGESTIONS = [
  "What is RAG in one sentence?",
  "Explain embeddings without the jargon",
  "Draft a short standup update",
];

function nextId(): string {
  return crypto.randomUUID();
}

export function ChatApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const threadRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const title = messages.find((message) => message.role === "user")?.content;

  useEffect(() => {
    const thread = threadRef.current;
    if (!thread) return;
    thread.scrollTop = thread.scrollHeight;
  }, [messages]);

  function resizeInput(element: HTMLTextAreaElement) {
    element.style.height = "0px";
    element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
  }

  function resetChat() {
    abortRef.current?.abort();
    setMessages([]);
    setDraft("");
    setError("");
    setStreaming(false);
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || streaming) return;

    const history = [...messages, { id: nextId(), role: "user" as const, content: question }];
    const assistantId = nextId();
    setMessages([...history, { id: assistantId, role: "assistant", content: "" }]);
    setDraft("");
    setError("");
    setStreaming(true);
    if (inputRef.current) inputRef.current.style.height = "auto";

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: history.map(({ role, content }) => ({ role, content })),
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        const detail = await response.text();
        throw new Error(detail || `Request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const event of events) {
          const line = event.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          const data = line.slice(6);
          if (data === "[DONE]") continue;
          const payload = JSON.parse(data) as { token?: string; error?: string };
          if (payload.error) throw new Error(payload.error);
          if (!payload.token) continue;
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantId
                ? { ...message, content: message.content + payload.token }
                : message,
            ),
          );
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setError(message);
      setMessages((current) => current.filter((item) => item.id !== assistantId || item.content));
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <p className="brand">
          Ask<span>.</span>
        </p>
        <button className="new-chat" type="button" onClick={resetChat}>
          New chat
        </button>
        {title ? <p className="thread-title">{title}</p> : null}
        <p className="sidebar-note">gpt-4o-mini · streaming</p>
      </aside>

      <section className="stage">
        <header className="topbar">
          <p className="brand">
            Ask<span>.</span>
          </p>
          <button className="new-chat" type="button" onClick={resetChat}>
            New chat
          </button>
        </header>

        <div className="thread" ref={threadRef}>
          <div className="column">
            {messages.length === 0 ? (
              <div className="empty">
                <p className="kicker">A quieter chat</p>
                <h2>Think out loud.</h2>
                <p>Ask a question. The answer arrives word by word, in a typeface meant for reading.</p>
                <div className="suggestions">
                  {SUGGESTIONS.map((suggestion) => (
                    <button
                      key={suggestion}
                      className="suggestion"
                      type="button"
                      onClick={() => void send(suggestion)}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages" aria-busy={streaming}>
                {messages.map((message) => (
                  <article key={message.id} className={`message ${message.role}`}>
                    <div className="bubble">
                      {message.role === "assistant" ? (
                        <>
                          <div className="prose">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {message.content || " "}
                            </ReactMarkdown>
                          </div>
                          {streaming && message.id === messages[messages.length - 1]?.id ? (
                            <span className="caret" />
                          ) : null}
                        </>
                      ) : (
                        message.content
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </div>

        {error ? <div className="error">{error}</div> : null}

        <div className="composer-wrap">
          <form className="composer" onSubmit={onSubmit}>
            <textarea
              ref={inputRef}
              value={draft}
              rows={1}
              placeholder="Ask anything"
              aria-label="Message"
              onChange={(event) => {
                setDraft(event.target.value);
                resizeInput(event.target);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send(draft);
                }
              }}
            />
            {streaming ? (
              <button
                className="stop"
                type="button"
                aria-label="Stop generating"
                onClick={() => abortRef.current?.abort()}
              >
                <Square />
              </button>
            ) : (
              <button className="send" type="submit" aria-label="Send message" disabled={!draft.trim()}>
                <Arrow />
              </button>
            )}
          </form>
          <p className="hint">Enter to send · Shift+Enter for a new line</p>
        </div>
      </section>
    </div>
  );
}

function Arrow() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 13V3M8 3l-4 4M8 3l4 4" fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

function Square() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
      <rect x="1" y="1" width="10" height="10" rx="1.5" fill="currentColor" />
    </svg>
  );
}
