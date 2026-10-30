type Props = {
  onClick: () => void;
  isOpen?: boolean;
};

/**
 * Compact circular floating launcher for FestOS AI.
 * Fixed at the bottom-right of the viewport with a chat message icon
 * and subtle online status indicator.
 */
export function ChatbotLauncher({ onClick, isOpen = false }: Props) {
  if (isOpen) return null;

  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Open FestOS AI chat"
      title="Open FestOS AI operations assistant"
      className="group relative flex h-14 w-14 items-center justify-center rounded-full border-2 border-crimson-dark/40 bg-mustard text-ink shadow-[0_4px_12px_rgba(64,16,18,0.25)] transition-all duration-200 hover:scale-105 hover:bg-saffron hover:border-crimson-dark hover:shadow-[0_6px_16px_rgba(64,16,18,0.35)] active:translate-y-px focus:outline-none focus:ring-2 focus:ring-crimson-deep focus:ring-offset-2 focus:ring-offset-cream"
    >
      {/* Message / Chat icon */}
      <svg
        className="h-6 w-6 text-ink transition-transform duration-200 group-hover:scale-110"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="2.2"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
        />
      </svg>

      {/* Small teal online status indicator */}
      <span className="absolute -top-0.5 -right-0.5 flex h-3.5 w-3.5 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full border border-cream bg-teal" />
      </span>
    </button>
  );
}
