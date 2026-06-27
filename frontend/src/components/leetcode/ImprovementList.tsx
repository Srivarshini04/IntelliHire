interface ImprovementListProps {
  improvements: string[];
}

/** Renders improvement areas as amber warning cards. */
export function ImprovementList({ improvements }: ImprovementListProps) {
  if (improvements.length === 0) return null;

  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Areas to Improve
      </h3>
      <ul className="space-y-2">
        {improvements.map((improvement) => (
          <li
            key={improvement}
            className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300"
          >
            <span aria-hidden className="mt-0.5">
              •
            </span>
            <span>{improvement}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
