"use client";

import { CapabilityRadar } from "@/components/charts/CapabilityRadar";
import { getCandidateDetail } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function CandidateDetailPage() {
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

  if (loading) return <div className="p-10">Loading...</div>;
  if (error) return <div className="p-10 text-red-600">{error}</div>;
  if (!detail) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/dashboard" className="mb-6 inline-block text-sm text-violet-600 hover:underline">
        ← Back to dashboard
      </Link>

      <h1 className="mb-8 text-3xl font-bold">{detail.name}</h1>

      <div className="grid gap-8 lg:grid-cols-2">
        {detail.capability && (
          <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-4 text-lg font-semibold">Capability Profile</h2>
            <CapabilityRadar capability={detail.capability} />
            <p className="mt-4 text-center text-2xl font-bold text-violet-600">
              {detail.capability.capability_score.toFixed(1)}
            </p>
          </div>
        )}

        <div className="space-y-6">
          {detail.risk && (
            <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-4 text-lg font-semibold">Risk Breakdown</h2>
              <ul className="space-y-2 text-sm">
                <li>Evidence Risk: {detail.risk.evidence_risk.toFixed(1)}</li>
                <li>Role Gap Risk: {detail.risk.role_gap_risk.toFixed(1)}</li>
                <li>Credibility Risk: {detail.risk.credibility_risk.toFixed(1)}</li>
                <li className="font-semibold">Total Risk: {detail.risk.risk_score.toFixed(1)}</li>
              </ul>
            </div>
          )}

          {detail.hti && (
            <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-4 text-lg font-semibold">Hidden Talent Index</h2>
              <p className="text-sm text-zinc-500">Visibility: {detail.hti.visibility_score.toFixed(1)}</p>
              <p className="text-2xl font-bold text-violet-600">HTI: {detail.hti.hti_score.toFixed(1)}</p>
            </div>
          )}

          {detail.explanation && (
            <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">Explanation</h2>
                {detail.summary && (
                  <Link
                    href={`/candidates/${candidateId}/summary`}
                    className="shrink-0 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700"
                  >
                    📋 Brief Summary →
                  </Link>
                )}
              </div>
              <p className="mb-4 text-sm">{detail.explanation.reason}</p>
              {detail.explanation.strengths.length > 0 && (
                <div className="mb-2">
                  <p className="text-sm font-medium text-emerald-600">Strengths</p>
                  <ul className="list-inside list-disc text-sm">
                    {detail.explanation.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {detail.explanation.risks.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-amber-600">Risks</p>
                  <ul className="list-inside list-disc text-sm">
                    {detail.explanation.risks.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
