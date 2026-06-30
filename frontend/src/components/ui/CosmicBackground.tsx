// Fixed, full-viewport cosmic backdrop: deep-space gradient, drifting purple
// glows, a faint star field and a bottom wave mesh. Pure CSS/SVG, no assets.
export function CosmicBackground() {
  // Deterministic "stars" so SSR and client markup match (no Math.random()).
  const stars = Array.from({ length: 70 }, (_, i) => {
    const x = (i * 97.13) % 100;
    const y = (i * 53.77) % 100;
    const s = (i % 3) + 1;
    const delay = (i % 7) * 0.6;
    return { x, y, s, delay };
  });

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-[#05060f]">
      {/* base radial depth */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(1200px 700px at 80% -10%, rgba(124,58,237,0.18), transparent 60%)," +
            "radial-gradient(900px 600px at -10% 30%, rgba(168,85,247,0.12), transparent 55%)," +
            "radial-gradient(900px 700px at 50% 120%, rgba(56,189,248,0.08), transparent 55%)",
        }}
      />

      {/* drifting glow blobs */}
      <div className="pulse-glow absolute -right-32 top-10 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
      <div className="pulse-glow absolute -left-24 top-1/3 h-80 w-80 rounded-full bg-fuchsia-600/10 blur-3xl" />

      {/* star field */}
      <div className="absolute inset-0">
        {stars.map((st, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-white"
            style={{
              left: `${st.x}%`,
              top: `${st.y}%`,
              width: st.s,
              height: st.s,
              opacity: 0.5,
              animation: `twinkle ${3 + (i % 4)}s ease-in-out ${st.delay}s infinite`,
            }}
          />
        ))}
      </div>

      {/* bottom wave mesh */}
      <svg
        className="absolute bottom-0 left-0 w-full opacity-40"
        viewBox="0 0 1440 320"
        preserveAspectRatio="none"
        style={{ height: "38vh" }}
      >
        <defs>
          <linearGradient id="wave" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.0" />
            <stop offset="50%" stopColor="#a855f7" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {Array.from({ length: 9 }).map((_, i) => (
          <path
            key={i}
            d={`M0 ${200 + i * 12} C 360 ${150 + i * 10}, 1080 ${260 + i * 8}, 1440 ${190 + i * 12}`}
            fill="none"
            stroke="url(#wave)"
            strokeWidth="1"
            opacity={0.5 - i * 0.04}
          />
        ))}
      </svg>

      {/* twinkle keyframe (scoped here so the component is self-contained) */}
      <style>{`@keyframes twinkle{0%,100%{opacity:.2}50%{opacity:1}}`}</style>
    </div>
  );
}
