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
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Candidate Rankings</h1>
          <p className="text-zinc-500">Evidence-based ranking with HTI scores</p>
        </div>
        <Link
          href={`/jobs/${jobId}/candidates`}
          className="text-sm text-violet-600 hover:underline"
        >
          ← Upload more candidates
        </Link>
      </div>

      {loading && <p>Loading rankings...</p>}
      {error && <p className="text-red-600">{error}</p>}
      {!loading && !error && <RankingTable rankings={rankings} jobId={jobId} />}
    </div>
  );
}
