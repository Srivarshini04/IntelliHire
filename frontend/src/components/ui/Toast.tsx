"use client";

import { useEffect } from "react";

interface ToastProps {
  message: string;
  variant?: "error" | "success";
  onClose: () => void;
  duration?: number;
}

/** Lightweight fixed-position toast, auto-dismisses after `duration` ms. */
export function Toast({
  message,
  variant = "error",
  onClose,
  duration = 5000,
}: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, duration);
    return () => clearTimeout(timer);
  }, [onClose, duration]);

  const styles =
    variant === "error"
      ? "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
      : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300";

  return (
    <div
      role="alert"
      className={`fixed bottom-6 right-6 z-50 flex max-w-sm items-start gap-3 rounded-lg border px-4 py-3 shadow-lg ${styles}`}
    >
      <span className="mt-0.5 shrink-0">{variant === "error" ? "⚠" : "✓"}</span>
      <p className="flex-1 text-sm">{message}</p>
      <button
        onClick={onClose}
        aria-label="Dismiss"
        className="shrink-0 text-current opacity-60 transition hover:opacity-100"
      >
        ✕
      </button>
    </div>
  );
}
