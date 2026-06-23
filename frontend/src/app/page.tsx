import Link from "next/link";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-20 text-center">
      <p className="mb-4 text-sm font-medium uppercase tracking-widest text-violet-600">
        Hiring Intelligence Platform
      </p>
      <h1 className="mb-6 text-5xl font-bold tracking-tight">DELULU</h1>
      <p className="mb-2 text-xl text-zinc-600 dark:text-zinc-400">
        We don&apos;t rank resumes. We rank evidence.
      </p>
      <p className="mb-10 text-zinc-500">
        Discover high-potential candidates overlooked by traditional ATS systems.
      </p>
      <div className="flex justify-center gap-4">
        <Link
          href="/jobs/new"
          className="rounded-lg bg-violet-600 px-6 py-3 font-medium text-white transition hover:bg-violet-700"
        >
          Create Job
        </Link>
        <Link
          href="/dashboard"
          className="rounded-lg border border-zinc-300 px-6 py-3 font-medium transition hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}
