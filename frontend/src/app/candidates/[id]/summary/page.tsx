"use client";

import { BriefSummary } from "@/components/summary/BriefSummary";
import { getCandidateDetail } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

function ScoreBadge({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 text-center dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`text-xl font-bold ${accent}`}>{value.toFixed(0)}</p>
    </div>
  );
}

export default function CandidateSummaryPage() {
  const params = useParams();
  const candidateId = params.id as string;
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getCandidateDetail(candidateId)
      .then(setDetail)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [candidateId]);

  if (loading) return <div className="p-10">Loading summary…</div>;
  if (error) return <div className="p-10 text-red-600">{error}</div>;
  if (!detail) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link
        href={`/candidates/${candidateId}`}
        className="mb-6 inline-block text-sm text-violet-600 hover:underline"
      >
        ← Back to candidate
      </Link>

      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-violet-600">Brief Summary</p>
          <h1 className="text-3xl font-bold">{detail.name}</h1>
        </div>
        <div className="flex gap-3">
          {detail.capability && (
            <ScoreBadge label="Capability" value={detail.capability.capability_score} accent="text-violet-600" />
          )}
          {detail.hti && <ScoreBadge label="HTI" value={detail.hti.hti_score} accent="text-violet-600" />}
          {detail.risk && <ScoreBadge label="Risk" value={detail.risk.risk_score} accent="text-amber-600" />}
        </div>
      </div>

      {detail.summary ? (
        <BriefSummary summary={detail.summary} />
      ) : (
        <p className="rounded-xl border border-zinc-200 bg-white p-6 text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
          No summary is available yet — the candidate may still be analyzing.
        </p>
      )}
    </div>
  );
}
