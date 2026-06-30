"use client";

import { deleteJob, listJobs } from "@/lib/api";
import type { Job } from "@/lib/types";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load jobs"))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(job: Job) {
    const count = job.candidate_count ?? 0;
    const confirmed = window.confirm(
      `Delete "${job.title}"?${count ? ` This will also remove ${count} candidate${count === 1 ? "" : "s"} and all their analysis data.` : ""}\n\nThis cannot be undone.`,
    );
    if (!confirmed) return;
    setDeletingId(job.job_id);
    setError("");
    try {
      await deleteJob(job.job_id);
      setJobs((prev) => prev.filter((j) => j.job_id !== job.job_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete job");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-10 flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white">Welcome back</h1>
          <p className="mt-2 text-white/50">Manage jobs, candidates, and rankings.</p>
        </div>
        <Link href="/jobs/new" className="btn-glow rounded-xl px-5 py-2.5 text-sm font-medium">
          + New Job
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Jobs column */}
        <div className="lg:col-span-2">
          <h2 className="mb-4 text-xl font-semibold text-white">Your Jobs</h2>

          {loading && <p className="text-white/50">Loading jobs…</p>}
          {error && <p className="text-red-400">{error}</p>}

          {!loading && !error && jobs.length === 0 && (
            <div className="glass border-dashed p-10 text-center">
              <p className="mb-3 text-white/50">No jobs yet.</p>
              <Link href="/jobs/new" className="font-medium text-violet-300 hover:underline">
                Create your first job →
              </Link>
            </div>
          )}

          <div className="space-y-4">
            {jobs.map((job, i) => (
              <div key={job.job_id} className={`glass glass-hover p-5 ${i === 0 ? "glow-ring" : ""}`}>
                <div className="mb-1 flex items-start justify-between gap-3">
                  <h3 className="text-lg font-semibold text-white">{job.title}</h3>
                  <span className="shrink-0 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-300">
                    {job.candidate_count ?? 0} applicant{(job.candidate_count ?? 0) === 1 ? "" : "s"}
                  </span>
                </div>
                {job.created_at && (
                  <p className="mb-4 text-xs text-white/35">
                    Created {new Date(job.created_at).toLocaleDateString()}
                  </p>
                )}
                <div className="flex items-center gap-4 text-sm">
                  <Link href={`/jobs/${job.job_id}/candidates`} className="font-medium text-violet-300 hover:underline">
                    Candidates →
                  </Link>
                  <Link href={`/jobs/${job.job_id}/rankings`} className="font-medium text-violet-300 hover:underline">
                    Rankings →
                  </Link>
                  <button
                    onClick={() => handleDelete(job)}
                    disabled={deletingId === job.job_id}
                    className="ml-auto font-medium text-red-400 hover:underline disabled:opacity-50"
                  >
                    {deletingId === job.job_id ? "Deleting…" : "Delete"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Visual column */}
        <div className="space-y-6">
          <AnalyticsPreview jobCount={jobs.length} />
          <div className="glass p-5">
            <h3 className="mb-3 text-lg font-semibold text-white">Visualizations</h3>
            <GlobeWire />
          </div>
          <ActivityTimeline />
        </div>
      </div>
    </div>
  );
}

function AnalyticsPreview({ jobCount }: { jobCount: number }) {
  return (
    <div className="glass relative overflow-hidden p-5">
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-violet-600/30 blur-2xl" />
      <p className="text-xs uppercase tracking-widest text-white/40">Intelligence dashboard</p>
      <div className="mt-3 flex items-end gap-2">
        <span className="text-3xl font-bold text-white">{jobCount}</span>
        <span className="pb-1 text-xs text-emerald-300">active roles</span>
      </div>
      <svg viewBox="0 0 240 70" className="mt-3 w-full">
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#a855f7" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M0 55 C 30 30, 50 50, 80 35 S 140 20, 170 38 S 220 25, 240 30 V70 H0 Z" fill="url(#area)" />
        <path d="M0 55 C 30 30, 50 50, 80 35 S 140 20, 170 38 S 220 25, 240 30" fill="none" stroke="#c4b5fd" strokeWidth="1.5" />
      </svg>
      <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-white/5 py-2">
          <p className="font-semibold text-white">3.28</p>
          <p className="text-white/40">signal</p>
        </div>
        <div className="rounded-lg bg-white/5 py-2">
          <p className="font-semibold text-white">3.2%</p>
          <p className="text-white/40">lift</p>
        </div>
        <div className="rounded-lg bg-white/5 py-2">
          <p className="font-semibold text-emerald-300">HTI</p>
          <p className="text-white/40">scored</p>
        </div>
      </div>
    </div>
  );
}

function GlobeWire() {
  return (
    <div className="flex justify-center py-2">
      <svg viewBox="0 0 200 200" className="h-44 w-44 text-white/30">
        <circle cx="100" cy="100" r="78" fill="none" stroke="currentColor" strokeWidth="0.6" />
        {[20, 40, 60].map((r) => (
          <ellipse key={r} cx="100" cy="100" rx={r} ry="78" fill="none" stroke="currentColor" strokeWidth="0.5" />
        ))}
        {[30, 60, 100, 140].map((y) => (
          <ellipse
            key={y}
            cx="100"
            cy="100"
            rx="78"
            ry={Math.max(8, 78 - Math.abs(100 - y))}
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
          />
        ))}
        <circle cx="138" cy="70" r="2.5" fill="#a855f7" />
        <circle cx="70" cy="120" r="2" fill="#22d3ee" />
        <circle cx="110" cy="150" r="2" fill="#e879f9" />
      </svg>
    </div>
  );
}

function ActivityTimeline() {
  const items = [
    { dir: "up", n: 1, ago: "3 days ago" },
    { dir: "down", n: 2, ago: "2 days ago" },
    { dir: "up", n: 1, ago: "3 days ago" },
  ];
  return (
    <div className="glass p-5">
      <h3 className="mb-4 text-lg font-semibold text-white">Activity Timeline</h3>
      <div className="space-y-4">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-3">
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${
                it.dir === "up" ? "bg-emerald-400/15 text-emerald-300" : "bg-amber-400/15 text-amber-300"
              }`}
            >
              {it.dir === "up" ? "↑" : "↓"}
            </span>
            <div className="flex-1">
              <p className="text-sm text-white">
                Ranking changed {it.dir === "up" ? "↑" : "↓"} {it.n}
              </p>
              <p className="text-xs text-white/35">Recent {it.ago}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
