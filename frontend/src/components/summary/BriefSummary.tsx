import type { CandidateSummary, SourceSummary } from "@/lib/types";

const SOURCE_ICON: Record<string, string> = {
  github: "🐙",
  leetcode: "🧩",
  linkedin: "💼",
  portfolio: "🌐",
  resume: "📄",
};

function verdictClasses(verdict: string): string {
  if (verdict.startsWith("Strong"))
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300";
  if (verdict.startsWith("Partial"))
    return "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300";
  return "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300";
}

function SourceCard({ src }: { src: SourceSummary }) {
  if (!src.available) {
    return (
      <div className="rounded-xl border border-dashed border-zinc-300 bg-zinc-50 p-4 dark:border-zinc-700 dark:bg-zinc-900/40">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-lg opacity-60">{SOURCE_ICON[src.source] ?? "•"}</span>
          <h3 className="font-semibold text-zinc-500">{src.title}</h3>
          <span className="ml-auto rounded-full bg-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-500 dark:bg-zinc-800">
            Not available
          </span>
        </div>
        <p className="text-xs text-zinc-500">{src.headline}</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-lg">{SOURCE_ICON[src.source] ?? "•"}</span>
        <h3 className="font-semibold">{src.title}</h3>
      </div>
      <p className="mb-3 text-xs text-zinc-500">{src.headline}</p>

      {src.stats.length > 0 && (
        <dl className="mb-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          {src.stats.map((st) => (
            <div
              key={st.label}
              className="flex justify-between gap-2 border-b border-zinc-100 py-0.5 dark:border-zinc-800"
            >
              <dt className="text-zinc-500">{st.label}</dt>
              <dd className="text-right font-medium">{st.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {src.strengths.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-semibold text-emerald-600">✓ Strengths</p>
          <ul className="list-inside list-disc text-xs text-zinc-700 dark:text-zinc-300">
            {src.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {src.weaknesses.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-600">△ Weaknesses</p>
          <ul className="list-inside list-disc text-xs text-zinc-700 dark:text-zinc-300">
            {src.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function BriefSummary({ summary }: { summary: CandidateSummary }) {
  const { role_fit } = summary;

  return (
    <div className="space-y-6">
      {/* Role-fit hero */}
      <div className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex flex-wrap items-center gap-3">
          <span className={`rounded-full px-4 py-1.5 text-base font-bold ${verdictClasses(role_fit.verdict)}`}>
            {role_fit.verdict}
          </span>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-violet-600">{role_fit.fit_score.toFixed(0)}</span>
            <span className="text-sm text-zinc-500">/100 role fit</span>
          </div>
        </div>
        <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-300">{summary.headline}</p>
        <p className="mt-2 text-sm">{role_fit.reason}</p>

        <div className="mt-4 flex flex-wrap gap-6 text-xs">
          {role_fit.matched_skills.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-emerald-600">Matched skills</p>
              <div className="flex flex-wrap gap-1.5">
                {role_fit.matched_skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-emerald-100 px-2.5 py-0.5 font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {role_fit.missing_skills.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-red-600">Missing skills</p>
              <div className="flex flex-wrap gap-1.5">
                {role_fit.missing_skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-full bg-red-100 px-2.5 py-0.5 font-medium text-red-700 dark:bg-red-950 dark:text-red-300"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Per-source breakdown */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Evidence by source</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {summary.sources.map((src) => (
            <SourceCard key={src.source} src={src} />
          ))}
        </div>
      </div>

      {/* Overall */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-5 dark:border-emerald-900 dark:bg-emerald-950/20">
          <p className="mb-2 font-semibold text-emerald-600">Overall Strengths</p>
          {summary.overall_strengths.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
              {summary.overall_strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500">No notable strengths surfaced.</p>
          )}
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-5 dark:border-amber-900 dark:bg-amber-950/20">
          <p className="mb-2 font-semibold text-amber-600">Overall Weaknesses</p>
          {summary.overall_weaknesses.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
              {summary.overall_weaknesses.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-zinc-500">No notable weaknesses surfaced.</p>
          )}
        </div>
      </div>
    </div>
  );
}
