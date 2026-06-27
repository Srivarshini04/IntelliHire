import type { LeetCodeAnalysis } from "@/lib/types";
import type { LeetCodeStatus } from "@/hooks/useLeetCodeAnalysis";
import { ImprovementList } from "./ImprovementList";
import { ScoreCard } from "./ScoreCard";
import { StrengthList } from "./StrengthList";

interface LeetCodeAnalysisCardProps {
  status: LeetCodeStatus;
  data: LeetCodeAnalysis | null;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3 text-center dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{value}</p>
      <p className="text-xs text-zinc-500">{label}</p>
    </div>
  );
}

function CardShell({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-5 flex items-center gap-2">
        <span aria-hidden className="text-lg">
          🟧
        </span>
        <h2 className="text-lg font-semibold">LeetCode Analysis</h2>
      </div>
      {children}
    </section>
  );
}

function AnalysisSkeleton() {
  return (
    <CardShell>
      <div className="animate-pulse space-y-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 rounded-lg bg-zinc-100 dark:bg-zinc-800" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-44 rounded-xl bg-zinc-100 dark:bg-zinc-800" />
          ))}
        </div>
        <div className="h-20 rounded-lg bg-zinc-100 dark:bg-zinc-800" />
      </div>
    </CardShell>
  );
}

/**
 * Candidate-dashboard card for LeetCode results.
 * Renders nothing when idle/empty, a skeleton while loading, and the full
 * breakdown on success. Errors are surfaced separately (via toast).
 */
export function LeetCodeAnalysisCard({ status, data }: LeetCodeAnalysisCardProps) {
  if (status === "loading") return <AnalysisSkeleton />;
  if (status !== "success" || !data) return null;

  return (
    <CardShell>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-zinc-500">
            Profile:{" "}
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">
              {data.username}
            </span>
          </p>
          <div className="flex flex-wrap gap-2 text-xs">
            {data.tier && (
              <span className="rounded-full bg-violet-100 px-2.5 py-1 font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                {data.tier}
              </span>
            )}
            {data.ranking != null && (
              <span className="rounded-full bg-zinc-100 px-2.5 py-1 font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                Rank #{data.ranking.toLocaleString()}
              </span>
            )}
            {data.contest_rating != null && (
              <span className="rounded-full bg-zinc-100 px-2.5 py-1 font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                Contest {Math.round(data.contest_rating)}
              </span>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Stat label="Username" value={data.username} />
          <Stat label="Easy" value={data.easy_solved} />
          <Stat label="Medium" value={data.medium_solved} />
          <Stat label="Hard" value={data.hard_solved} />
          <Stat label="Total Solved" value={data.total_solved} />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <ScoreCard
            label="Problem Solving"
            score={data.problem_solving}
            accent="text-violet-600"
          />
          <ScoreCard
            label="Algorithm Depth"
            score={data.algorithm_depth}
            accent="text-sky-600"
          />
          <ScoreCard
            label="Coding Skill"
            score={data.coding_skill}
            accent="text-emerald-600"
          />
        </div>

        <StrengthList strengths={data.strengths} />
        <ImprovementList improvements={data.improvements} />
      </div>
    </CardShell>
  );
}
