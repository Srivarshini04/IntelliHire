"use client";

import { createJob } from "@/lib/api";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function NewJobPage() {
  const router = useRouter();
  const [title, setTitle] = useState("AI Engineer");
  const [description, setDescription] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const job = await createJob(title, description);
      router.push(`/jobs/${job.job_id}/candidates`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create job");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl px-6 py-10">
      <h1 className="mb-2 text-3xl font-bold">Create Job</h1>
      <p className="mb-8 text-zinc-500">Paste the job description to generate a role blueprint.</p>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label className="mb-2 block text-sm font-medium">Job Title</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            required
          />
        </div>
        <div>
          <label className="mb-2 block text-sm font-medium">Job Description</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={12}
            className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="Senior AI Engineer with experience in Python, LLMs, FastAPI..."
            required
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-violet-600 px-6 py-3 font-medium text-white transition hover:bg-violet-700 disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create Job & Continue"}
        </button>
      </form>
    </div>
  );
}
