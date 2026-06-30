"use client";

import { RankingTable } from "@/components/ranking/RankingTable";
import { getRankings } from "@/lib/api";
import type { RankingItem } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function RankingsPage() {
  const params = useParams();
  const jobId = params.id as string;
  const [rankings, setRankings] = useState<RankingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getRankings(jobId)
      .then(setRankings)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [jobId]);

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white">Candidate Rankings</h1>
          <p className="mt-1 text-white/50">Evidence-based ranking with HTI scores</p>
        </div>
        <Link href={`/jobs/${jobId}/candidates`} className="text-sm text-violet-300 hover:underline">
          ← Upload more candidates
        </Link>
      </div>

      {loading && <p className="text-white/50">Loading rankings…</p>}
      {error && <p className="text-red-400">{error}</p>}
      {!loading && !error && <RankingTable rankings={rankings} jobId={jobId} />}
    </div>
  );
}
