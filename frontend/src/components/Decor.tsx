/** Decorative pieces lifted from the Aarohan poster style. */

export function Bunting({ className = "" }: { className?: string }) {
  const colors = ["#f0a82f", "#2fa79f", "#e07b2a", "#f7e8ca"];
  const flags = Array.from({ length: 9 }, (_, i) => colors[i % colors.length]);
  return (
    <svg viewBox="0 0 900 60" className={className} aria-hidden="true" preserveAspectRatio="none">
      <line x1="0" y1="6" x2="900" y2="10" stroke="#5c0f13" strokeWidth="2" />
      {flags.map((c, i) => (
        <path
          key={i}
          d={`M ${i * 100 + 8} 8 L ${i * 100 + 78} 9 L ${i * 100 + 44} 54 Z`}
          fill={c}
          stroke="#40101266"
          strokeWidth="1.5"
        />
      ))}
    </svg>
  );
}

export function Mandala({ className = "" }: { className?: string }) {
  const petals = Array.from({ length: 12 }, (_, i) => i);
  return (
    <svg viewBox="-50 -50 100 100" className={className} aria-hidden="true">
      <g fill="none" stroke="#f0a82f" strokeWidth="1.6" opacity="0.55">
        <circle r="46" strokeWidth="2.5" />
        <circle r="34" />
        <circle r="22" strokeDasharray="4 3" />
        <circle r="8" fill="#f0a82f" stroke="none" opacity="0.7" />
        {petals.map((i) => {
          const a = (i * Math.PI) / 6;
          return (
            <ellipse
              key={i}
              cx={34 * Math.cos(a)}
              cy={34 * Math.sin(a)}
              rx="11"
              ry="4.5"
              transform={`rotate(${(a * 180) / Math.PI} ${34 * Math.cos(a)} ${34 * Math.sin(a)})`}
            />
          );
        })}
        {petals.map((i) => {
          const a = ((i + 0.5) * Math.PI) / 6;
          return (
            <ellipse
              key={i}
              cx={22 * Math.cos(a)}
              cy={22 * Math.sin(a)}
              rx="7"
              ry="3"
              transform={`rotate(${(a * 180) / Math.PI} ${22 * Math.cos(a)} ${22 * Math.sin(a)})`}
            />
          );
        })}
      </g>
    </svg>
  );
}
