interface ScoreCardProps {
  label: string;
  score: number;
  /** Tailwind text/stroke color accent, e.g. "text-violet-600". */
  accent?: string;
}

/** A single 0-100 score shown as a circular progress ring. */
export function ScoreCard({
  label,
  score,
  accent = "text-violet-600",
}: ScoreCardProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="flex flex-col items-center rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="relative h-28 w-28">
        <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="8"
            className="stroke-zinc-200 dark:stroke-zinc-800"
          />
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`${accent} transition-[stroke-dashoffset] duration-700 ease-out`}
            stroke="currentColor"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${accent}`}>
            {clamped.toFixed(1)}
          </span>
          <span className="text-[10px] text-zinc-400">/ 100</span>
        </div>
      </div>
      <p className="mt-3 text-center text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
      </p>
    </div>
  );
}
