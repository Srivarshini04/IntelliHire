"use client";

import { CapabilityRadar } from "@/components/charts/CapabilityRadar";
import { getCandidateDetail } from "@/lib/api";
import type { CandidateDetail } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

const SOURCE_NODES = [
  { label: "GitHub", x: "6%", y: "60%" },
  { label: "Skills", x: "34%", y: "78%" },
  { label: "LeetCode", x: "16%", y: "92%" },
  { label: "LinkedIn", x: "40%", y: "100%" },
];

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

  if (loading) return <div className="p-10 text-white/60">Loading…</div>;
  if (error) return <div className="p-10 text-red-400">{error}</div>;
  if (!detail) return null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <Link href="/dashboard" className="mb-4 inline-block text-sm text-violet-300 hover:underline">
        ← Back to dashboard
      </Link>

      <h1 className="mb-8 text-4xl font-bold gradient-text">{detail.name}</h1>

      <div className="grid gap-7 lg:grid-cols-2">
        {/* Capability + constellation */}
        {detail.capability && (
          <div className="glass relative overflow-hidden p-6">
            <h2 className="mb-2 text-lg font-semibold text-white">Capability Profile</h2>
            <CapabilityRadar capability={detail.capability} />

            {/* glowing score bubble */}
            <div className="mt-2 flex justify-center">
              <div className="relative flex h-20 w-20 items-center justify-center rounded-full">
                <div className="absolute inset-0 rounded-full bg-violet-600/30 blur-lg pulse-glow" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-violet-400/40 bg-white/[0.04] text-xl font-bold text-white">
                  {detail.capability.capability_score.toFixed(1)}
                </div>
              </div>
            </div>

            {/* source constellation */}
            <div className="relative mt-6 h-28">
              <svg className="absolute inset-0 h-full w-full" viewBox="0 0 400 120" preserveAspectRatio="none">
                <g stroke="rgba(168,85,247,0.35)" strokeWidth="1" fill="none">
                  <path d="M40 40 C 120 20, 180 80, 250 70" />
                  <path d="M60 90 C 140 60, 200 100, 300 96" />
                  <path d="M250 70 C 300 60, 340 90, 360 80" />
                </g>
              </svg>
              <div className="absolute inset-0">
                {SOURCE_NODES.map((n) => (
                  <span
                    key={n.label}
                    className="absolute flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/12 bg-white/[0.05] text-[11px] text-white/70 backdrop-blur"
                    style={{ left: n.x, top: n.y }}
                  >
                    {n.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Right column */}
        <div className="space-y-6">
          {detail.risk && (
            <div className="glass p-6">
              <h2 className="mb-4 text-lg font-semibold text-white">Risk Breakdown</h2>
              <ul className="space-y-2 text-sm text-white/75">
                <li>Evidence Risk: {detail.risk.evidence_risk.toFixed(1)}</li>
                <li>Role Gap Risk: {detail.risk.role_gap_risk.toFixed(1)}</li>
                <li>Credibility Risk: {detail.risk.credibility_risk.toFixed(1)}</li>
                <li className="font-semibold text-white">Total Risk: {detail.risk.risk_score.toFixed(1)}</li>
              </ul>
            </div>
          )}

          {detail.hti && (
            <div className="glass relative overflow-hidden p-6">
              <h2 className="mb-3 text-lg font-semibold text-white">Hidden Talent Index</h2>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-white/45">Visibility: {detail.hti.visibility_score.toFixed(1)}</p>
                  <p className="text-3xl font-bold gradient-text">HTI: {detail.hti.hti_score.toFixed(1)}</p>
                </div>
                <div className="relative h-16 w-16">
                  <div className="absolute inset-0 rounded-full bg-fuchsia-500/30 blur-lg pulse-glow" />
                  <div className="relative h-16 w-16 rounded-full border border-fuchsia-300/40 bg-linear-to-br from-violet-500/40 to-fuchsia-500/20" />
                </div>
              </div>
            </div>
          )}

          {detail.explanation && (
            <div className="glass p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-white">Explanation</h2>
                {detail.summary && (
                  <Link
                    href={`/candidates/${candidateId}/summary`}
                    className="btn-glow shrink-0 rounded-lg px-4 py-2 text-sm font-medium"
                  >
                    📋 Brief Summary →
                  </Link>
                )}
              </div>
              <p className="mb-4 text-sm text-white/75">{detail.explanation.reason}</p>
              {detail.explanation.strengths.length > 0 && (
                <div className="mb-3">
                  <p className="text-sm font-medium text-emerald-300">Strengths</p>
                  <ul className="list-inside list-disc text-sm text-white/70">
                    {detail.explanation.strengths.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {detail.explanation.risks.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-amber-300">Risks</p>
                  <ul className="list-inside list-disc text-sm text-white/70">
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
