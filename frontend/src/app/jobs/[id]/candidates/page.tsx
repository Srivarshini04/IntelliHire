"use client";

import { listJobCandidates, uploadCandidate } from "@/lib/api";
import type { CandidateListItem } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

type LinkField = "github_url" | "linkedin_url" | "leetcode_url" | "portfolio_url";

const LINK_FIELDS: { field: LinkField; label: string; placeholder: string }[] = [
  { field: "github_url", label: "GitHub", placeholder: "https://github.com/username" },
  { field: "linkedin_url", label: "LinkedIn", placeholder: "https://www.linkedin.com/in/username" },
  { field: "leetcode_url", label: "LeetCode", placeholder: "https://leetcode.com/u/username" },
  { field: "portfolio_url", label: "Portfolio", placeholder: "https://yoursite.dev" },
];

const SOURCE_CHIPS: { key: keyof CandidateListItem; label: string }[] = [
  { key: "github_url", label: "GitHub" },
  { key: "linkedin_url", label: "LinkedIn" },
  { key: "leetcode_url", label: "LeetCode" },
  { key: "portfolio_url", label: "Portfolio" },
];

export default function CandidateUploadPage() {
  const params = useParams();
  const jobId = params.id as string;

  const [resume, setResume] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [candidates, setCandidates] = useState<CandidateListItem[]>([]);

  const [links, setLinks] = useState({
    github_url: "",
    linkedin_url: "",
    leetcode_url: "",
    portfolio_url: "",
  });
  const [showLinks, setShowLinks] = useState(false);

  const loadCandidates = useCallback(() => {
    listJobCandidates(jobId)
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [jobId]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  useEffect(() => {
    if (!candidates.some((c) => !c.analyzed)) return;
    const timer = setInterval(loadCandidates, 4000);
    return () => clearInterval(timer);
  }, [candidates, loadCandidates]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!resume) {
      setMessage("Please choose a resume PDF.");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const formData = new FormData();
      formData.append("job_id", jobId);
      formData.append("resume", resume);
      for (const [field, value] of Object.entries(links)) {
        if (value.trim()) formData.append(field, value.trim());
      }

      const created = await uploadCandidate(formData);
      setMessage(`Uploaded ${created.name ?? "candidate"} — analyzing in the background…`);
      setResume(null);
      setFileKey((k) => k + 1);
      setLinks({ github_url: "", linkedin_url: "", leetcode_url: "", portfolio_url: "" });
      loadCandidates();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const pending = candidates.filter((c) => !c.analyzed).length;

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white">Upload Candidates</h1>
          <p className="mt-1 font-mono text-xs text-white/40">Job ID: {jobId}</p>
        </div>
        <Link href={`/jobs/${jobId}/rankings`} className="text-sm text-violet-300 hover:underline">
          View Rankings →
        </Link>
      </div>

      <form onSubmit={handleUpload} className="space-y-5">
        {/* Glowing drop zone */}
        <label
          className={`glass glow-ring relative flex cursor-pointer flex-col items-center justify-center gap-3 overflow-hidden border-dashed py-12 text-center transition ${
            resume ? "" : ""
          }`}
        >
          <div className="pointer-events-none absolute -left-10 top-0 h-40 w-40 rounded-full bg-violet-600/20 blur-3xl" />
          <div className="pointer-events-none absolute -right-10 bottom-0 h-40 w-40 rounded-full bg-cyan-500/15 blur-3xl" />
          <DropArt />
          <p className="relative text-sm font-medium text-white/80">
            {resume ? resume.name : "Drag & Drop Resume PDF"}
          </p>
          <p className="relative text-xs text-white/40">PDF — name, email and profile links are auto-extracted</p>
          <input
            key={fileKey}
            type="file"
            accept=".pdf"
            onChange={(e) => setResume(e.target.files?.[0] || null)}
            className="hidden"
            required
          />
        </label>

        {/* manual links */}
        <div className="glass p-4">
          <button
            type="button"
            onClick={() => setShowLinks((s) => !s)}
            className="text-sm font-medium text-violet-300 hover:underline"
          >
            {showLinks ? "▾" : "▸"} Add profile links manually (optional)
          </button>
          {showLinks && (
            <div className="mt-3 space-y-3">
              <p className="text-xs text-white/45">
                Links are read from the resume first. Fill these in only as a fallback — for example
                when a link is missing from the resume or can&apos;t be extracted.
              </p>
              {LINK_FIELDS.map(({ field, label, placeholder }) => (
                <div key={field}>
                  <label className="mb-1 block text-xs font-medium text-white/55">{label}</label>
                  <input
                    type="url"
                    inputMode="url"
                    value={links[field]}
                    onChange={(e) => setLinks((prev) => ({ ...prev, [field]: e.target.value }))}
                    placeholder={placeholder}
                    className="field w-full px-3 py-2 text-sm"
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !resume}
          className="btn-glow rounded-xl px-6 py-2.5 font-medium disabled:opacity-50"
        >
          {loading ? "Uploading..." : "Upload Candidate"}
        </button>
      </form>

      {message && <p className="mt-4 text-sm text-white/60">{message}</p>}

      <div className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Uploaded Applications ({candidates.length})</h2>
          {pending > 0 && <span className="text-xs text-amber-300">{pending} analyzing…</span>}
        </div>

        {candidates.length === 0 ? (
          <p className="text-sm text-white/45">No candidates uploaded yet.</p>
        ) : (
          <div className="glass divide-y divide-white/5 overflow-hidden">
            {candidates.map((c) => (
              <div key={c.candidate_id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                <div className="min-w-0">
                  <Link href={`/candidates/${c.candidate_id}`} className="font-medium text-white hover:text-violet-300">
                    {c.name}
                  </Link>
                  {c.email && <p className="truncate text-xs text-white/40">{c.email}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-2 text-xs">
                  {c.analyzed ? (
                    <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2.5 py-1 font-medium text-emerald-300">
                      Analyzed
                    </span>
                  ) : (
                    <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 font-medium text-amber-300">
                      Analyzing…
                    </span>
                  )}
                  {SOURCE_CHIPS.filter((s) => c[s.key]).map((s) => (
                    <span key={s.label} className="chip px-2.5 py-1 text-white/60">
                      {s.label}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Link
        href={`/jobs/${jobId}/rankings`}
        className="btn-ghost mt-8 inline-block rounded-xl px-6 py-3 font-medium"
      >
        View Rankings →
      </Link>
    </div>
  );
}

function DropArt() {
  return (
    <svg viewBox="0 0 120 60" className="relative h-16 w-40">
      <g opacity="0.9">
        <rect x="10" y="22" width="16" height="16" rx="2" fill="#a855f7" opacity="0.7" transform="rotate(8 18 30)" />
        <rect x="30" y="14" width="14" height="14" rx="2" fill="#c4b5fd" opacity="0.6" />
        <rect x="20" y="36" width="12" height="12" rx="2" fill="#7c3aed" opacity="0.5" />
      </g>
      <g stroke="#94a3b8" strokeWidth="0.6" opacity="0.5">
        <line x1="78" y1="20" x2="98" y2="14" />
        <line x1="78" y1="20" x2="98" y2="30" />
        <line x1="78" y1="40" x2="98" y2="30" />
        <line x1="78" y1="40" x2="98" y2="46" />
        <line x1="98" y1="14" x2="112" y2="22" />
        <line x1="98" y1="46" x2="112" y2="38" />
      </g>
      <g fill="#8b5cf6">
        <circle cx="78" cy="20" r="2.4" />
        <circle cx="78" cy="40" r="2.4" />
        <circle cx="98" cy="14" r="2" fill="#22d3ee" />
        <circle cx="98" cy="30" r="2" fill="#e879f9" />
        <circle cx="98" cy="46" r="2" fill="#22d3ee" />
        <circle cx="112" cy="22" r="2" />
        <circle cx="112" cy="38" r="2" />
      </g>
    </svg>
  );
}
