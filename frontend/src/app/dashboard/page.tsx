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
    <div className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="mb-2 text-3xl font-bold">Dashboard</h1>
          <p className="text-zinc-500">Manage jobs, candidates, and rankings.</p>
        </div>
        <Link
          href="/jobs/new"
          className="rounded-lg bg-violet-600 px-5 py-2 font-medium text-white transition hover:bg-violet-700"
        >
          + New Job
        </Link>
      </div>

      <h2 className="mb-4 text-xl font-semibold">Your Jobs</h2>

      {loading && <p className="text-zinc-500">Loading jobs…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && !error && jobs.length === 0 && (
        <div className="rounded-xl border border-dashed border-zinc-300 p-10 text-center dark:border-zinc-700">
          <p className="mb-3 text-zinc-500">No jobs yet.</p>
          <Link href="/jobs/new" className="font-medium text-violet-600 hover:underline">
            Create your first job →
          </Link>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {jobs.map((job) => (
          <div
            key={job.job_id}
            className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div className="mb-1 flex items-start justify-between gap-3">
              <h3 className="text-lg font-semibold">{job.title}</h3>
              <span className="shrink-0 rounded-full bg-violet-100 px-3 py-1 text-xs font-medium text-violet-700 dark:bg-violet-950 dark:text-violet-300">
                {job.candidate_count ?? 0} applicant{(job.candidate_count ?? 0) === 1 ? "" : "s"}
              </span>
            </div>
            {job.created_at && (
              <p className="mb-4 text-xs text-zinc-400">
                Created {new Date(job.created_at).toLocaleDateString()}
              </p>
            )}
            <div className="flex items-center gap-4 text-sm">
              <Link
                href={`/jobs/${job.job_id}/candidates`}
                className="font-medium text-violet-600 hover:underline"
              >
                Candidates →
              </Link>
              <Link
                href={`/jobs/${job.job_id}/rankings`}
                className="font-medium text-violet-600 hover:underline"
              >
                Rankings →
              </Link>
              <button
                onClick={() => handleDelete(job)}
                disabled={deletingId === job.job_id}
                className="ml-auto font-medium text-red-600 hover:underline disabled:opacity-50"
              >
                {deletingId === job.job_id ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
