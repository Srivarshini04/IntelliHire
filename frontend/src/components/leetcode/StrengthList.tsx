interface StrengthListProps {
  strengths: string[];
}

/** Renders candidate strengths as green check badges. */
export function StrengthList({ strengths }: StrengthListProps) {
  if (strengths.length === 0) return null;

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Strengths
      </h3>
      <div className="flex flex-wrap gap-2">
        {strengths.map((strength) => (
          <span
            key={strength}
            className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300"
          >
            <span aria-hidden>✓</span>
            {strength}
          </span>
        ))}
      </div>
    </div>
  );
}
