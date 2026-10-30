import { useState, useRef, useEffect } from "react";
import type { KeyboardEvent } from "react";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [disabled]);

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

  return (
    <div className="border-t-2 border-crimson-dark/30 bg-cream p-3">
      <div className="flex items-end gap-2">
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
          className="max-h-28 min-h-[38px] flex-1 resize-none rounded-sm border-2 border-crimson-dark/40 bg-cream-dim px-3 py-1.5 text-sm text-ink placeholder:text-ink/40 focus:border-teal-dark focus:bg-cream focus:outline-none disabled:opacity-50"
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="plaque inline-flex h-[38px] items-center justify-center gap-1.5 rounded-sm bg-mustard px-4 text-xs font-bold uppercase tracking-wider text-ink transition hover:bg-saffron active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span>Send</span>
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
          </svg>
        </button>
      </div>

      <div className="mt-1 flex justify-between text-[10px] text-ink/50">
        <span>Enter to send · Shift+Enter for new line</span>
        {text.length > 200 && <span>{text.length}/1500</span>}
      </div>
    </div>
  );
}
