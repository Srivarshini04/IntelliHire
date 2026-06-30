"use client";

import { BriefSummary } from "@/components/summary/BriefSummary";
import { ScoreRing } from "@/components/ui/ScoreRing";
import { getCandidateDetail } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

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

  if (loading) return <div className="p-10 text-white/60">Loading summary…</div>;
  if (error) return <div className="p-10 text-red-400">{error}</div>;
  if (!detail) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link href={`/candidates/${candidateId}`} className="mb-4 inline-block text-sm text-violet-300 hover:underline">
        ← Back to candidate
      </Link>

      <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.3em] text-violet-300">Brief Summary</p>
          <h1 className="mt-1 text-3xl font-bold gradient-text">{detail.name}</h1>
        </div>
        <div className="flex gap-5">
          {detail.capability && (
            <ScoreRing value={detail.capability.capability_score} label="Capability" tone="violet" sublabel="cap" />
          )}
          {detail.hti && <ScoreRing value={detail.hti.hti_score} label="HTI" tone="cyan" sublabel="hti" />}
          {detail.risk && <ScoreRing value={detail.risk.risk_score} label="Risk" tone="amber" sublabel="risk" />}
        </div>
      </div>

      {detail.summary ? (
        <BriefSummary summary={detail.summary} />
      ) : (
        <p className="glass p-6 text-sm text-white/50">
          No summary is available yet — the candidate may still be analyzing.
        </p>
      )}
    </div>
  );
}
