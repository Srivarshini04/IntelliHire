import Link from "next/link";

const navItems = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/jobs/new", label: "New Job" },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-white/5 bg-[#05060f]/70 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-violet-400/40 bg-violet-500/10 text-violet-300 shadow-[0_0_20px_-4px_rgba(139,92,246,0.7)]">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 4v16M5 4c5 0 9 3 9 8s-4 8-9 8" strokeLinecap="round" />
            </svg>
          </span>
          <span className="text-lg font-bold tracking-[0.2em] text-white">DELULU</span>
        </Link>
        <nav className="flex gap-7 text-sm font-medium">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-white/60 transition hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
