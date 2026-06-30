// Decorative 4-point sparkle, fixed bottom-right (matches the mockups).
export function Sparkle() {
  return (
    <svg
      aria-hidden
      className="floaty pointer-events-none fixed bottom-10 right-12 -z-[5] h-12 w-12 text-white/40"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M12 0c.5 6 1.5 11 12 12-10.5 1-11.5 6-12 12-.5-6-1.5-11-12-12 10.5-1 11.5-6 12-12z" />
    </svg>
  );
}
