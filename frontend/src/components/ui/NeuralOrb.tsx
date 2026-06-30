// A glowing "neural" orb: concentric rings + a network of nodes/edges inside a
// radial glow. Used as the hero illustration on Home and Create Job.
export function NeuralOrb({ size = 360 }: { size?: number }) {
  const nodes = [
    [50, 18], [72, 30], [80, 52], [70, 74], [48, 84], [28, 72], [20, 50], [30, 28],
    [50, 50], [60, 42], [40, 60], [58, 64], [42, 40],
  ];
  const edges = [
    [8, 0], [8, 1], [8, 2], [8, 3], [8, 4], [8, 5], [8, 6], [8, 7],
    [9, 1], [10, 5], [11, 3], [12, 7], [9, 2], [10, 4], [11, 4], [12, 0],
  ];

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <div className="pulse-glow absolute inset-0 rounded-full bg-violet-600/30 blur-3xl" />
      <div className="spin-slow absolute inset-6 rounded-full border border-violet-400/20" />
      <div className="absolute inset-12 rounded-full border border-fuchsia-400/15" />
      <svg viewBox="0 0 100 100" className="relative h-full w-full">
        <defs>
          <radialGradient id="orbGlow" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="#a855f7" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="edge" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#c4b5fd" />
            <stop offset="100%" stopColor="#e879f9" />
          </linearGradient>
        </defs>
        <circle cx="50" cy="50" r="46" fill="url(#orbGlow)" />
        {edges.map(([a, b], i) => (
          <line
            key={i}
            x1={nodes[a][0]}
            y1={nodes[a][1]}
            x2={nodes[b][0]}
            y2={nodes[b][1]}
            stroke="url(#edge)"
            strokeWidth="0.4"
            opacity="0.5"
          />
        ))}
        {nodes.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={i === 8 ? 2.4 : 1.3} fill="#e9d5ff">
            <animate
              attributeName="opacity"
              values="0.4;1;0.4"
              dur={`${2.5 + (i % 4)}s`}
              repeatCount="indefinite"
            />
          </circle>
        ))}
      </svg>
    </div>
  );
}
