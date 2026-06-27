"use client";

import { listJobCandidates, uploadCandidate } from "@/lib/api";
import type { CandidateListItem } from "@/lib/types";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function CandidateUploadPage() {
  const params = useParams();
  const jobId = params.id as string;

  const [resume, setResume] = useState<File | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [candidates, setCandidates] = useState<CandidateListItem[]>([]);

  const loadCandidates = useCallback(() => {
    listJobCandidates(jobId)
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, [jobId]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  // Auto-refresh while any candidate is still being analyzed in the background.
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

      const created = await uploadCandidate(formData);
      setMessage(`Uploaded ${created.name ?? "candidate"} — analyzing in the background…`);
      setResume(null);
      setFileKey((k) => k + 1);
      loadCandidates();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const pending = candidates.filter((c) => !c.analyzed).length;

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Upload Candidates</h1>
          <p className="text-zinc-500">Job ID: {jobId}</p>
        </div>
        <Link
          href={`/jobs/${jobId}/rankings`}
          className="text-sm text-violet-600 hover:underline"
        >
          View Rankings →
        </Link>
      </div>

      <form onSubmit={handleUpload} className="mb-8 space-y-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-sm text-zinc-500">
          Upload a resume PDF — the candidate&apos;s name, email, GitHub and LinkedIn are
          extracted and the candidate is analyzed automatically.
        </p>
        <input
          key={fileKey}
          type="file"
          accept=".pdf"
          onChange={(e) => setResume(e.target.files?.[0] || null)}
          className="w-full text-sm"
          required
        />
        <button
          type="submit"
          disabled={loading || !resume}
          className="rounded-lg bg-violet-600 px-6 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? "Uploading..." : "Upload Candidate"}
        </button>
      </form>

      {message && <p className="mb-4 text-sm text-zinc-600">{message}</p>}

      <div className="mb-8">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            Uploaded Applications ({candidates.length})
          </h2>
          {pending > 0 && (
            <span className="text-xs text-amber-600">{pending} analyzing…</span>
          )}
        </div>
        {candidates.length === 0 ? (
          <p className="text-sm text-zinc-500">No candidates uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-200 rounded-xl border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
            {candidates.map((c) => (
              <li key={c.candidate_id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="min-w-0">
                  <Link
                    href={`/candidates/${c.candidate_id}`}
                    className="font-medium text-violet-600 hover:underline"
                  >
                    {c.name}
                  </Link>
                  {c.email && <p className="truncate text-xs text-zinc-500">{c.email}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-2 text-xs">
                  {c.analyzed ? (
                    <span className="rounded-full bg-green-100 px-2 py-1 font-medium text-green-700 dark:bg-green-950 dark:text-green-300">
                      Analyzed
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                      Analyzing…
                    </span>
                  )}
                  {c.github_url && (
                    <span className="rounded-full bg-zinc-100 px-2 py-1 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                      GitHub
                    </span>
                  )}
                  {c.linkedin_url && (
                    <span className="rounded-full bg-zinc-100 px-2 py-1 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                      LinkedIn
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Link
        href={`/jobs/${jobId}/rankings`}
        className="inline-block rounded-lg border border-violet-600 px-6 py-3 font-medium text-violet-600 transition hover:bg-violet-50 dark:hover:bg-violet-950"
      >
        View Rankings →
      </Link>
    </div>
  );
}
