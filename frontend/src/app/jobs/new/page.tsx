"use client";

import { NeuralOrb } from "@/components/ui/NeuralOrb";
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
    <div className="mx-auto max-w-6xl px-6 py-14">
      <div className="grid items-start gap-10 lg:grid-cols-2">
        <div>
          <h1 className="text-4xl font-bold text-white">Create Job</h1>
          <p className="mt-2 text-white/50">Paste the job description to generate a role blueprint.</p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-white/50">
                Job Title
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="field w-full px-4 py-3 text-sm"
                required
              />
            </div>
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-white/50">
                Job Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={11}
                className="field w-full px-4 py-3 text-sm"
                placeholder="Senior AI Engineer with experience in Python, LLMs, FastAPI..."
                required
              />
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <button type="submit" disabled={loading} className="btn-glow rounded-xl px-6 py-3 font-medium disabled:opacity-60">
              {loading ? "Creating..." : "Create Job & Continue"}
            </button>
          </form>
        </div>

        {/* Neural blueprint preview panel */}
        <div className="glass relative overflow-hidden p-8">
          <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-violet-600/25 blur-3xl" />
          <div className="flex justify-center">
            <div className="floaty">
              <NeuralOrb size={260} />
            </div>
          </div>

          <div className="relative mt-6 flex justify-center">
            <div className="relative flex h-44 w-44 items-center justify-center rounded-full border border-white/10 bg-white/[0.03]">
              <div className="absolute inset-0 rounded-full bg-violet-600/15 blur-xl" />
              <div className="relative text-center">
                <p className="text-xs text-white/50">Score</p>
                <p className="text-4xl font-bold text-white">100</p>
              </div>
            </div>
            {["Python", "LLMs", "FastAPI", "Typing", "Eval"].map((s, i) => {
              const pos = [
                "left-2 top-10",
                "right-2 top-8",
                "right-0 bottom-12",
                "right-10 -bottom-1",
                "left-4 bottom-2",
              ][i];
              return (
                <span key={s} className={`chip absolute ${pos} px-3 py-1 text-xs`}>
                  {s}
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
