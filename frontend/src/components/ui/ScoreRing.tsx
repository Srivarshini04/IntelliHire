// Glowing circular score gauge used across rankings, candidate detail and the
// brief summary. SVG arc with a gradient stroke + soft glow.

type Tone = "violet" | "emerald" | "amber" | "cyan" | "gold";

const TONES: Record<Tone, [string, string]> = {
  violet: ["#a855f7", "#7c3aed"],
  emerald: ["#34d399", "#10b981"],
  amber: ["#fbbf24", "#f59e0b"],
  cyan: ["#22d3ee", "#0ea5e9"],
  gold: ["#fde68a", "#f59e0b"],
};

export function ScoreRing({
  value,
  label,
  sublabel,
  size = 84,
  stroke = 7,
  tone = "violet",
  max = 100,
}: {
  value: number;
  label?: string;
  sublabel?: string;
  size?: number;
  stroke?: number;
  tone?: Tone;
  max?: number;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value / max));
  const [from, to] = TONES[tone];
  const gid = `ring-${tone}-${size}-${Math.round(value)}`;

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor={from} />
              <stop offset="100%" stopColor={to} />
            </linearGradient>
          </defs>
          <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(255,255,255,0.08)" strokeWidth={stroke} fill="none" />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={`url(#${gid})`}
            strokeWidth={stroke}
            strokeLinecap="round"
            fill="none"
            strokeDasharray={c}
            strokeDashoffset={c * (1 - pct)}
            style={{ filter: `drop-shadow(0 0 6px ${from}aa)` }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-bold leading-none text-white">{Math.round(value)}</span>
          {sublabel && <span className="mt-0.5 text-[9px] text-white/45">{sublabel}</span>}
        </div>
      </div>
      {label && <span className="text-xs text-white/55">{label}</span>}
    </div>
  );
}
