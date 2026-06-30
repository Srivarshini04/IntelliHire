import { ScoreRing } from "@/components/ui/ScoreRing";
import type { RankingItem } from "@/lib/types";
import Link from "next/link";

interface RankingTableProps {
  rankings: RankingItem[];
  jobId: string;
}

function riskTone(risk: number): "emerald" | "amber" {
  return risk < 35 ? "emerald" : "amber";
}
function riskPill(risk: number) {
  if (risk < 35) return "border-emerald-400/30 bg-emerald-400/10 text-emerald-300";
  if (risk < 60) return "border-amber-400/30 bg-amber-400/10 text-amber-300";
  return "border-red-400/30 bg-red-400/10 text-red-300";
}
function medal(rank: number) {
  if (rank === 1) return "border-amber-300/70 text-amber-200 shadow-[0_0_24px_-4px_rgba(251,191,36,0.8)]";
  if (rank === 2) return "border-zinc-300/60 text-zinc-200 shadow-[0_0_22px_-6px_rgba(212,212,216,0.7)]";
  if (rank === 3) return "border-orange-400/60 text-orange-300 shadow-[0_0_22px_-6px_rgba(251,146,60,0.7)]";
  return "border-violet-400/50 text-violet-300 shadow-[0_0_22px_-8px_rgba(139,92,246,0.7)]";
}

const SOURCES = ["GH", "LC", "in"];

function Bar({ value, tone }: { value: number; tone: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
      <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function RankingTable({ rankings, jobId }: RankingTableProps) {
  void jobId;
  if (rankings.length === 0) {
    return (
      <div className="glass border-dashed p-8 text-center text-white/45">
        No rankings yet. Upload candidates and run analysis.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Summary table */}
      <div className="glass overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-white/45">
            <tr className="border-b border-white/8">
              {["Rank", "Candidate", "Fit Score", "HTI", "Risk", "Confidence", "Action"].map((h) => (
                <th key={h} className="px-5 py-3 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rankings.map((r) => (
              <tr key={r.candidate_id} className="border-b border-white/5 last:border-0">
                <td className="px-5 py-3 font-semibold text-white">#{r.rank}</td>
                <td className="px-5 py-3 text-white/80">{r.candidate}</td>
                <td className="px-5 py-3 font-medium text-emerald-300">{r.fit_score.toFixed(1)}</td>
                <td className="px-5 py-3 font-medium text-violet-300">{r.hti.toFixed(1)}</td>
                <td className="px-5 py-3">
                  <span className={`rounded-md border px-2 py-0.5 text-xs ${riskPill(r.risk)}`}>{r.risk.toFixed(1)}</span>
                </td>
                <td className="px-5 py-3 text-white/70">{r.confidence.toFixed(1)}</td>
                <td className="px-5 py-3">
                  <Link href={`/candidates/${r.candidate_id}`} className="text-violet-300 hover:text-violet-200">
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M14 5h5v5M19 5l-9 9M19 14v5H5V5h5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Expanded rank cards */}
      <div className="space-y-5">
        {rankings.map((r) => (
          <div key={r.candidate_id} className={`glass p-5 ${r.rank === 1 ? "glow-ring" : ""}`}>
            <div className="flex items-center gap-5">
              {/* medallion */}
              <div
                className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 bg-white/[0.03] text-lg font-bold ${medal(
                  r.rank,
                )}`}
              >
                #{r.rank}
              </div>

              {/* name + bars */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <Link
                    href={`/candidates/${r.candidate_id}`}
                    className="truncate text-lg font-semibold text-white hover:text-violet-300"
                  >
                    {r.candidate}
                  </Link>
                  <span className="text-lg font-bold text-emerald-300">{r.fit_score.toFixed(1)}</span>
                </div>
                <p className="mb-1 mt-2 text-[11px] uppercase tracking-wide text-white/40">Fit Score</p>
                <Bar value={r.fit_score} tone="bg-linear-to-r from-violet-500 to-fuchsia-400" />
                <div className="mt-3 flex items-center gap-3">
                  <span className="text-[11px] uppercase tracking-wide text-white/40">HTI</span>
                  <div className="flex-1">
                    <Bar value={r.hti} tone="bg-linear-to-r from-emerald-500 to-teal-400" />
                  </div>
                  <span className="text-sm font-medium text-violet-300">{r.hti.toFixed(1)}</span>
                </div>
              </div>

              {/* risk ring */}
              <div className={`hidden shrink-0 rounded-xl border px-3 py-2 sm:block ${riskPill(r.risk)}`}>
                <ScoreRing value={r.risk} size={64} stroke={6} tone={riskTone(r.risk)} sublabel="risk" />
              </div>

              {/* confidence */}
              <div className="hidden shrink-0 text-center sm:block">
                <p className="text-lg font-semibold text-white">{r.confidence.toFixed(1)}</p>
                <p className="text-[11px] text-white/40">confidence</p>
              </div>

              {/* source nodes */}
              <div className="hidden shrink-0 grid-cols-1 gap-2 lg:grid">
                {SOURCES.map((s) => (
                  <span
                    key={s}
                    className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/12 bg-white/5 text-[10px] font-semibold text-white/70"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-4 flex justify-end">
              <Link
                href={`/candidates/${r.candidate_id}`}
                className="btn-ghost rounded-lg px-4 py-1.5 text-xs font-medium text-white/80"
              >
                {r.recommendation || "Review"} →
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
