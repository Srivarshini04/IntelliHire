import { NeuralOrb } from "@/components/ui/NeuralOrb";
import Link from "next/link";

const features = [
  {
    title: "GitHub Analysis",
    body: "Deep cross-repo evidence: features, engineering maturity, hidden gems.",
    grad: "from-violet-500/30 to-fuchsia-500/10",
  },
  {
    title: "LeetCode Intelligence",
    body: "Algorithmic depth, problem volume and contest signal — scored 0–100.",
    grad: "from-fuchsia-500/30 to-cyan-500/10",
  },
  {
    title: "LinkedIn Evidence",
    body: "Roles, ownership and production experience, verified against claims.",
    grad: "from-cyan-500/30 to-violet-500/10",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 pb-24 pt-16">
      <section className="grid items-center gap-10 lg:grid-cols-2">
        <div>
          <p className="mb-5 text-sm font-medium uppercase tracking-[0.35em] text-violet-300">
            Hiring Intelligence Platform
          </p>
          <h1 className="text-7xl font-bold tracking-tight text-white">
            <span className="gradient-text">DELULU</span>
            <span className="cursor-blink ml-1 font-light text-violet-300">|</span>
          </h1>
          <p className="mt-5 text-xl text-white/70">
            We don&apos;t rank resumes. We rank evidence.
          </p>
          <p className="mt-2 max-w-md text-white/45">
            Discover high-potential candidates overlooked by traditional ATS systems.
          </p>
          <div className="mt-9 flex gap-4">
            <Link href="/jobs/new" className="btn-glow rounded-xl px-6 py-3 font-medium">
              Create Job
            </Link>
            <Link href="/dashboard" className="btn-ghost rounded-xl px-6 py-3 font-medium">
              Dashboard
            </Link>
          </div>
        </div>

        <div className="flex justify-center lg:justify-end">
          <div className="floaty">
            <NeuralOrb size={380} />
          </div>
        </div>
      </section>

      <section className="mt-20 grid gap-5 md:grid-cols-3">
        {features.map((f) => (
          <div key={f.title} className="glass glass-hover relative overflow-hidden p-6">
            <div
              className={`pointer-events-none absolute -right-10 -top-10 h-40 w-40 rounded-full bg-linear-to-br ${f.grad} blur-2xl`}
            />
            <h3 className="relative text-lg font-semibold text-white">{f.title}</h3>
            <p className="relative mt-2 text-sm text-white/55">{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
