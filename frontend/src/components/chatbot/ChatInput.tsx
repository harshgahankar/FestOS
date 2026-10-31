import { useState, useRef, useEffect } from "react";
import type { KeyboardEvent } from "react";
import { createRecognizer, micPermissionError, sttSupported } from "./voice";
import type { Recognizer } from "./voice";

type Props = {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
};

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Ask about participants, conflicts, accommodation, inventory…",
}: Props) {
  const [text, setText] = useState("");
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognizerRef = useRef<Recognizer | null>(null);
  const autoSendRef = useRef<((m: string) => void) | null>(null);
  autoSendRef.current = onSend;

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

  const stopListening = () => {
    const rec = recognizerRef.current;
    recognizerRef.current = null;
    setListening(false);
    if (rec) {
      rec.onresult = null;
      rec.onerror = null;
      rec.onend = null;
      rec.stop();
    }
  };

  const startListening = () => {
    if (!sttSupported || disabled || listening) return;
    const rec = createRecognizer(
      navigator.language || "en-US",
      (interim) => setText(interim),
      (final) => {
        const send = autoSendRef.current;
        stopListening();
        if (final && send) send(final);
      },
      (err) => {
        setMicError(micPermissionError(err));
        stopListening();
      },
    );
    if (!rec) return;
    setMicError(null);
    try {
      rec.start();
    } catch {
      setMicError(micPermissionError("unknown"));
      stopListening();
      return;
    }
    recognizerRef.current = rec;
    setListening(true);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  };

  const canSend = Boolean(text.trim()) && !disabled;

  return (
    <div className="border-t border-crimson-dark/15 bg-cream/90 backdrop-blur-sm p-3.5">
      <div className="relative flex items-end rounded-xl border border-crimson-dark/25 bg-white/95 p-1.5 shadow-2xs focus-within:border-crimson-dark focus-within:ring-2 focus-within:ring-crimson-dark/15 transition-all">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onInput={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          maxLength={1500}
          placeholder={placeholder}
          className="max-h-28 min-h-[40px] flex-1 resize-none bg-transparent px-3 py-2 text-sm text-ink placeholder:text-ink/40 focus:outline-none disabled:opacity-50 font-sans"
        />

        {sttSupported && (
          <button
            type="button"
            onClick={listening ? stopListening : startListening}
            disabled={disabled}
            title={listening ? "Stop listening" : "Speak your question"}
            aria-label={listening ? "Stop voice input" : "Start voice input"}
            className={`relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-all ${
              listening
                ? "bg-crimson-dark text-cream hover:bg-crimson-deep"
                : "text-ink/50 hover:bg-ink/10 hover:text-crimson-deep"
            }`}
          >
            {listening && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-crimson/40" />
            )}
            <svg className="relative h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
              <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
              <line x1="12" y1="18" x2="12" y2="22" />
            </svg>
          </button>
        )}

        <button
          type="button"
          onClick={handleSend}
          disabled={!canSend}
          title="Send message (Enter)"
          aria-label="Send message"
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-all ${
            canSend
              ? "bg-crimson-dark text-mustard hover:bg-crimson-deep hover:scale-105 active:scale-95 shadow-xs"
              : "bg-ink/10 text-ink/30 cursor-not-allowed"
          }`}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>

      <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-ink/45 font-mono">
        <span>{listening ? "listening… speak now" : "Enter ↵ to send · Shift+Enter for new line"}</span>
        {text.length > 200 && <span>{text.length}/1500</span>}
      </div>
      {micError && (
        <button
          type="button"
          onClick={() => setMicError(null)}
          title="Dismiss"
          className="mt-1 block w-full rounded-md border border-saffron/60 bg-crimson-dark/10 px-2 py-1 text-left text-[11px] font-semibold text-crimson-deep"
        >
          mic: {micError}
        </button>
      )}
    </div>
  );
}
