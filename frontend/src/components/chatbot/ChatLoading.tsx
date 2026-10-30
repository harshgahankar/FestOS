export function ChatLoading({ label = "Querying FestOS database…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-3 text-ink/70">
      <div className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-crimson-dark" style={{ animationDelay: "0ms" }} />
        <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-mustard" style={{ animationDelay: "150ms" }} />
        <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-teal-dark" style={{ animationDelay: "300ms" }} />
      </div>
      <span className="text-xs font-semibold uppercase tracking-wider text-ink/60">{label}</span>
    </div>
  );
}
