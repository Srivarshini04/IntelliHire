"use client";

import { isValidLeetCodeUrl } from "@/lib/leetcode";

interface LeetCodeInputProps {
  value: string;
  onChange: (value: string) => void;
  id?: string;
}

/**
 * Optional LeetCode profile URL field with inline validation.
 * Empty is valid (the field is optional); a non-empty value must match the
 * canonical https://leetcode.com/u/username/ shape.
 */
export function LeetCodeInput({
  value,
  onChange,
  id = "leetcode-url",
}: LeetCodeInputProps) {
  const trimmed = value.trim();
  const showError = trimmed.length > 0 && !isValidLeetCodeUrl(trimmed);

  return (
    <div className="space-y-1">
      <label
        htmlFor={id}
        className="block text-sm font-medium text-zinc-700 dark:text-zinc-300"
      >
        LeetCode URL <span className="text-zinc-400">(optional)</span>
      </label>
      <input
        id={id}
        type="url"
        inputMode="url"
        placeholder="https://leetcode.com/u/username/"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={showError}
        className={`w-full rounded-lg border px-4 py-2 dark:bg-zinc-950 ${
          showError
            ? "border-red-400 dark:border-red-700"
            : "border-zinc-300 dark:border-zinc-700"
        }`}
      />
      {showError && (
        <p className="text-xs text-red-500">
          Enter a valid LeetCode profile URL, e.g. https://leetcode.com/u/username/
        </p>
      )}
    </div>
  );
}
