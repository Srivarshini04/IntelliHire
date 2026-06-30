import type { CandidateSummary, SourceSummary } from "@/lib/types";

const SOURCE_ICON: Record<string, string> = {
  github: "🐙",
  leetcode: "🧩",
  linkedin: "💼",
  portfolio: "🌐",
  resume: "📄",
};

function verdictClasses(verdict: string): string {
  if (verdict.startsWith("Strong")) return "border-emerald-400/40 bg-emerald-400/10 text-emerald-300";
  if (verdict.startsWith("Partial")) return "border-amber-400/40 bg-amber-400/10 text-amber-300";
  return "border-red-400/40 bg-red-400/10 text-red-300";
}

function SourceCard({ src }: { src: SourceSummary }) {
  if (!src.available) {
    return (
      <div className="rounded-xl border border-dashed border-white/12 bg-white/[0.02] p-4">
        <div className="mb-1 flex items-center gap-2">
          <span className="text-lg opacity-60">{SOURCE_ICON[src.source] ?? "•"}</span>
          <h3 className="font-semibold text-white/55">{src.title}</h3>
          <span className="ml-auto rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] font-medium text-white/45">
            Not available
          </span>
        </div>
        <p className="text-xs text-white/45">{src.headline}</p>
      </div>
    );
  }

  return (
    <div className="glass glass-hover p-4">
      <div className="mb-1 flex items-center gap-2">
        <span className="text-lg">{SOURCE_ICON[src.source] ?? "•"}</span>
        <h3 className="font-semibold text-white">{src.title}</h3>
      </div>
      <p className="mb-3 text-xs text-white/45">{src.headline}</p>

      {src.stats.length > 0 && (
        <dl className="mb-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
          {src.stats.map((st) => (
            <div key={st.label} className="flex justify-between gap-2 border-b border-white/5 py-0.5">
              <dt className="text-white/45">{st.label}</dt>
              <dd className="text-right font-medium text-white/90">{st.value}</dd>
            </div>
          ))}
        </dl>
      )}

      {src.strengths.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-semibold text-emerald-300">✓ Strengths</p>
          <ul className="list-inside list-disc text-xs text-white/70">
            {src.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {src.weaknesses.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-amber-300">△ Weaknesses</p>
          <ul className="list-inside list-disc text-xs text-white/70">
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
    <div className="space-y-7">
      {/* Role-fit hero */}
      <div className={`glass rounded-2xl border p-6 ${role_fit.verdict.startsWith("Strong") ? "glow-ring" : ""}`}>
        <div className="flex flex-wrap items-center gap-3">
          <span className={`rounded-full border px-4 py-1.5 text-base font-bold ${verdictClasses(role_fit.verdict)}`}>
            {role_fit.verdict}
          </span>
          <div className="flex items-baseline gap-1">
            <span className="text-2xl font-bold text-violet-300">{role_fit.fit_score.toFixed(0)}</span>
            <span className="text-sm text-white/45">/100 role fit</span>
          </div>
        </div>
        <p className="mt-3 text-sm text-white/65">{summary.headline}</p>
        <p className="mt-2 text-sm text-white/80">{role_fit.reason}</p>

        <div className="mt-4 flex flex-wrap gap-6 text-xs">
          {role_fit.matched_skills.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-emerald-300">Matched skills</p>
              <div className="flex flex-wrap gap-1.5">
                {role_fit.matched_skills.map((s) => (
                  <span key={s} className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-0.5 font-medium text-emerald-300">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
          {role_fit.missing_skills.length > 0 && (
            <div>
              <p className="mb-1 font-semibold text-red-300">Missing skills</p>
              <div className="flex flex-wrap gap-1.5">
                {role_fit.missing_skills.map((s) => (
                  <span key={s} className="rounded-full border border-red-400/30 bg-red-400/10 px-2.5 py-0.5 font-medium text-red-300">
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
        <h2 className="mb-3 text-lg font-semibold text-white">Evidence by source</h2>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {summary.sources.map((src) => (
            <SourceCard key={src.source} src={src} />
          ))}
        </div>
      </div>

      {/* Overall */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.06] p-5">
          <p className="mb-2 font-semibold text-emerald-300">Overall Strengths</p>
          {summary.overall_strengths.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-white/75">
              {summary.overall_strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-white/45">No notable strengths surfaced.</p>
          )}
        </div>
        <div className="rounded-2xl border border-amber-400/25 bg-amber-400/[0.06] p-5">
          <p className="mb-2 font-semibold text-amber-300">Overall Weaknesses</p>
          {summary.overall_weaknesses.length > 0 ? (
            <ul className="list-inside list-disc space-y-1 text-sm text-white/75">
              {summary.overall_weaknesses.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-white/45">No notable weaknesses surfaced.</p>
          )}
        </div>
      </div>
    </div>
  );
}
