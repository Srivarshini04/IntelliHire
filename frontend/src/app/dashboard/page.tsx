import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="mb-2 text-3xl font-bold">Dashboard</h1>
      <p className="mb-8 text-zinc-500">Manage jobs, candidates, and rankings.</p>

      <div className="grid gap-6 md:grid-cols-3">
        <Link
          href="/jobs/new"
          className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm transition hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
        >
          <h2 className="mb-2 text-lg font-semibold">1. Create Job</h2>
          <p className="text-sm text-zinc-500">Paste a JD and generate a role blueprint.</p>
        </Link>
        <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-2 text-lg font-semibold">2. Upload Candidates</h2>
          <p className="text-sm text-zinc-500">Add resumes, GitHub, and LinkedIn profiles.</p>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h2 className="mb-2 text-lg font-semibold">3. View Rankings</h2>
          <p className="text-sm text-zinc-500">See fit scores, HTI, and hidden talent.</p>
        </div>
      </div>
    </div>
  );
}
