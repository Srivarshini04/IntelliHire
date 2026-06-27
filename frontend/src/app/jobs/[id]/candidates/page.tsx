"use client";

import { LeetCodeAnalysisCard } from "@/components/leetcode/LeetCodeAnalysisCard";
import { LeetCodeInput } from "@/components/leetcode/LeetCodeInput";
import { Toast } from "@/components/ui/Toast";
import { useLeetCodeAnalysis } from "@/hooks/useLeetCodeAnalysis";
import { runJobAnalysis, uploadCandidate } from "@/lib/api";
import { isValidLeetCodeUrl } from "@/lib/leetcode";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

export default function CandidateUploadPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [leetcodeUrl, setLeetcodeUrl] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [message, setMessage] = useState("");

  const leetcode = useLeetCodeAnalysis();
  const hasLeetcode = leetcodeUrl.trim().length > 0;
  const leetcodeValid = hasLeetcode && isValidLeetCodeUrl(leetcodeUrl);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const formData = new FormData();
      formData.append("job_id", jobId);
      formData.append("name", name);
      if (email) formData.append("email", email);
      if (githubUrl) formData.append("github_url", githubUrl);
      if (linkedinUrl) formData.append("linkedin_url", linkedinUrl);
      if (resume) formData.append("resume", resume);

      await uploadCandidate(formData);
      setMessage(`Uploaded ${name} successfully.`);

      // Run the optional LeetCode evaluation on demand.
      if (leetcodeValid) {
        await leetcode.analyze(leetcodeUrl.trim());
      }

      setName("");
      setEmail("");
      setGithubUrl("");
      setLinkedinUrl("");
      setResume(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyzeAll() {
    setAnalyzing(true);
    setMessage("");
    try {
      await runJobAnalysis(jobId);
      router.push(`/jobs/${jobId}/rankings`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }

  const analyzeDisabled = loading || (hasLeetcode && !leetcodeValid);

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
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

      <form
        onSubmit={handleUpload}
        className="mb-8 space-y-4 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900"
      >
        <input
          type="text"
          placeholder="Candidate name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-950"
          required
        />
        <input
          type="email"
          placeholder="Email (optional)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-950"
        />
        <input
          type="url"
          placeholder="GitHub URL"
          value={githubUrl}
          onChange={(e) => setGithubUrl(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-950"
        />
        <input
          type="url"
          placeholder="LinkedIn URL"
          value={linkedinUrl}
          onChange={(e) => setLinkedinUrl(e.target.value)}
          className="w-full rounded-lg border border-zinc-300 px-4 py-2 dark:border-zinc-700 dark:bg-zinc-950"
        />
        <LeetCodeInput value={leetcodeUrl} onChange={setLeetcodeUrl} />
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setResume(e.target.files?.[0] || null)}
          className="w-full text-sm"
        />
        <button
          type="submit"
          disabled={analyzeDisabled}
          className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-6 py-2 font-medium text-white hover:bg-violet-700 disabled:opacity-50"
        >
          {loading && (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          )}
          {loading ? "Analyzing..." : "Analyze Candidate"}
        </button>
      </form>

      {message && <p className="mb-4 text-sm text-zinc-600">{message}</p>}

      {/* LeetCode dashboard — hidden entirely when no URL was provided. */}
      {hasLeetcode && (
        <div className="mb-8">
          <LeetCodeAnalysisCard status={leetcode.status} data={leetcode.data} />
        </div>
      )}

      <button
        onClick={handleAnalyzeAll}
        disabled={analyzing}
        className="rounded-lg border border-violet-600 px-6 py-3 font-medium text-violet-600 transition hover:bg-violet-50 disabled:opacity-50 dark:hover:bg-violet-950"
      >
        {analyzing ? "Analyzing..." : "Run Analysis & View Rankings"}
      </button>

      {leetcode.status === "error" && leetcode.error && (
        <Toast message={leetcode.error} onClose={leetcode.reset} />
      )}
    </div>
  );
}
