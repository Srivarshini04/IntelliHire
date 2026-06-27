// Accepts canonical profile URLs like: https://leetcode.com/u/username/
// (http/https, optional www, optional trailing slash).
const LEETCODE_URL_RE =
  /^https?:\/\/(www\.)?leetcode\.com\/u\/[A-Za-z0-9_-]+\/?$/;

export function isValidLeetCodeUrl(url: string): boolean {
  return LEETCODE_URL_RE.test(url.trim());
}
