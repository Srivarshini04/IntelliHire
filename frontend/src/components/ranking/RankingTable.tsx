import type { RankingItem } from "@/lib/types";
import Link from "next/link";

interface RankingTableProps {
  rankings: RankingItem[];
  jobId: string;
}

export function RankingTable({ rankings, jobId }: RankingTableProps) {
  if (rankings.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-zinc-500">
        No rankings yet. Upload candidates and run analysis.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-left text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900">
          <tr>
            <th className="px-4 py-3 font-medium">Rank</th>
            <th className="px-4 py-3 font-medium">Candidate</th>
            <th className="px-4 py-3 font-medium">Fit Score</th>
            <th className="px-4 py-3 font-medium">HTI</th>
            <th className="px-4 py-3 font-medium">Risk</th>
            <th className="px-4 py-3 font-medium">Confidence</th>
            <th className="px-4 py-3 font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {rankings.map((r) => (
            <tr key={r.candidate_id} className="border-t border-zinc-100 dark:border-zinc-800">
              <td className="px-4 py-3 font-semibold">#{r.rank}</td>
              <td className="px-4 py-3">{r.candidate}</td>
              <td className="px-4 py-3 text-emerald-600">{r.fit_score.toFixed(1)}</td>
              <td className="px-4 py-3 text-violet-600">{r.hti.toFixed(1)}</td>
              <td className="px-4 py-3 text-amber-600">{r.risk.toFixed(1)}</td>
              <td className="px-4 py-3">{r.confidence.toFixed(1)}</td>
              <td className="px-4 py-3">
                <Link
                  href={`/candidates/${r.candidate_id}`}
                  className="text-blue-600 hover:underline"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
