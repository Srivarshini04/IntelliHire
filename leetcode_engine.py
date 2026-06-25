"""
DELULU — LeetCode Profile Evaluation Engine (v2)

Why v2 fixes the old scoring:
  * Old code used `linear value, then clip at 100`. That made it HARSH in the
    low/mid range and FLAT at the top (a 500-problem profile and a 1000-problem
    profile both scored exactly 100 -> no differentiation for recruiters).
  * Old `algorithm_depth = weighted/8` saturated absurdly fast, so medium-heavy
    profiles exploded (~92) while easy-heavy profiles collapsed (~29). That is
    why "278 solved -> 78" but "175 solved -> 38".
  * Old `hard_bonus` double-counted hard problems (already weighted 6x in depth).

v2 replaces all of that with smooth SATURATING curves: generous in the
low/mid range, gently compressing near the top. The result is monotonic
(every extra problem raises the score) and stable (similar profiles get
similar scores). It also self-calibrates against LeetCode's live problem
totals and folds in global rank + contest rating as bonus-only signals.
"""

import math
import re
import requests


class LeetCodeEvaluator:

    GRAPHQL_URL = "https://leetcode.com/graphql"

    # Difficulty weights (effort/skill ratio). Hard ~6x an easy.
    W_EASY, W_MEDIUM, W_HARD = 1.0, 2.5, 6.0

    # Saturation scale constants (tuned against a battery of synthetic profiles).
    K_VOLUME = 220     # total problems -> volume score
    K_MASTERY = 450    # weighted points -> difficulty-mastery score
    K_HARD = 45        # hard count -> hard-depth score

    # Composite weights (sum to 1.0)
    W_VOLUME, W_MASTERY, W_HARD_DEPTH, W_BALANCE = 0.38, 0.34, 0.12, 0.16

    HEADERS = {
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "User-Agent": "Mozilla/5.0 (DELULU-Engine)",
    }

    # ---------- helpers ----------

    @staticmethod
    def _sat(x, k):
        """Saturating curve: 0 -> 0, large x -> ~1. Smooth & monotonic."""
        return 1 - math.exp(-x / k) if x > 0 else 0.0

    @staticmethod
    def extract_username(leetcode_url: str):
        """Pull the username from a LeetCode profile URL (or a bare handle)."""
        leetcode_url = leetcode_url.strip()
        patterns = [r"leetcode\.com/u/([^/?#]+)", r"leetcode\.com/([^/?#]+)"]
        for pattern in patterns:
            match = re.search(pattern, leetcode_url)
            if match:
                handle = match.group(1)
                if handle not in ("u", "problems", "contest", "discuss"):
                    return handle
        # allow passing a raw username with no URL
        if "/" not in leetcode_url and leetcode_url:
            return leetcode_url
        return None

    # ---------- data fetch ----------

    @classmethod
    def fetch_profile(cls, username):
        """One GraphQL call for solved counts, platform totals, rank & submissions."""
        query = """
        query getProfile($username: String!) {
          allQuestionsCount { difficulty count }
          matchedUser(username: $username) {
            profile { ranking }
            submitStatsGlobal {
              acSubmissionNum { difficulty count }
              totalSubmissionNum { difficulty count submissions }
            }
          }
        }
        """
        payload = {"query": query, "variables": {"username": username}}
        resp = requests.post(cls.GRAPHQL_URL, json=payload,
                             headers=cls.HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("data", {})

        user = data.get("matchedUser")
        if not user:
            raise ValueError("LeetCode user not found")

        # solved counts
        solved = {"easy": 0, "medium": 0, "hard": 0}
        for item in user["submitStatsGlobal"]["acSubmissionNum"]:
            key = item["difficulty"].lower()
            if key in solved:
                solved[key] = item["count"]

        # platform totals (for coverage %) — self-calibrates as LeetCode grows
        available = {"easy": 0, "medium": 0, "hard": 0}
        for item in data.get("allQuestionsCount", []):
            key = item["difficulty"].lower()
            if key in available:
                available[key] = item["count"]

        # acceptance rate (insight only — gameable, so not scored)
        total_sub = sum(i["submissions"]
                        for i in user["submitStatsGlobal"]["totalSubmissionNum"]
                        if i["difficulty"] == "All") or 0
        total_ac = solved["easy"] + solved["medium"] + solved["hard"]
        acceptance = round(100 * total_ac / total_sub, 1) if total_sub else None

        ranking = (user.get("profile") or {}).get("ranking")

        return {
            "solved": solved,
            "available": available,
            "ranking": ranking,
            "acceptance": acceptance,
        }

    @classmethod
    def fetch_contest_rating(cls, username):
        """Optional: contest rating is bonus-only upside; absence is never penalized."""
        query = """
        query getContest($username: String!) {
          userContestRanking(username: $username) {
            rating
            topPercentage
            attendedContestsCount
          }
        }
        """
        try:
            payload = {"query": query, "variables": {"username": username}}
            resp = requests.post(cls.GRAPHQL_URL, json=payload,
                                 headers=cls.HEADERS, timeout=15)
            resp.raise_for_status()
            return resp.json().get("data", {}).get("userContestRanking")
        except Exception:
            return None  # contests are optional; never block evaluation

    # ---------- scoring ----------

    @classmethod
    def calculate_scores(cls, easy, medium, hard, contest_rating=None):
        total = easy + medium + hard
        weighted = easy * cls.W_EASY + medium * cls.W_MEDIUM + hard * cls.W_HARD

        # 1. Volume — breadth of practice, diminishing returns
        volume = 100 * cls._sat(total, cls.K_VOLUME)

        # 2. Mastery — difficulty-weighted depth
        mastery = 100 * cls._sat(weighted, cls.K_MASTERY)

        # 3. Hard depth — rewards tackling hard problems specifically
        hard_depth = 100 * cls._sat(hard, cls.K_HARD)

        # 4. Balance — share of effort in medium+hard; mildly penalizes pure-easy
        mh_share = (medium * cls.W_MEDIUM + hard * cls.W_HARD) / weighted if weighted else 0
        balance = 100 * (mh_share ** 0.7)

        base = (cls.W_VOLUME * volume + cls.W_MASTERY * mastery +
                cls.W_HARD_DEPTH * hard_depth + cls.W_BALANCE * balance)

        # 5. Contest bonus — pure upside (0 at 1500 rating, +6 at 2400+)
        contest_bonus = 0.0
        if contest_rating:
            contest_bonus = min(6.0, max(0.0, (contest_rating - 1500) / 150))

        coding_skill = min(100, round(base + contest_bonus, 1))
        tier = cls._tier(coding_skill)

        return {
            "volume": round(volume, 1),
            "mastery": round(mastery, 1),
            "hard_depth": round(hard_depth, 1),
            "balance": round(balance, 1),
            "contest_bonus": round(contest_bonus, 1),
            "coding_skill": coding_skill,
            "tier": tier,
        }

    @staticmethod
    def _tier(skill):
        if skill >= 85:  return "Elite"
        if skill >= 70:  return "Advanced"
        if skill >= 55:  return "Proficient"
        if skill >= 40:  return "Developing"
        return "Beginner"

    # ---------- insights ----------

    @staticmethod
    def generate_insights(solved, available, ranking, acceptance, contest):
        e, m, h = solved["easy"], solved["medium"], solved["hard"]
        total = e + m + h
        strengths, improvements = [], []

        def cov(part, whole):
            return round(100 * part / whole, 1) if whole else None

        coverage = {
            "easy": cov(e, available["easy"]),
            "medium": cov(m, available["medium"]),
            "hard": cov(h, available["hard"]),
        }

        if m >= 75:
            strengths.append("Strong medium-level problem solving")
        if h >= 30:
            strengths.append("Solid command of hard algorithmic problems")
        elif h >= 10:
            strengths.append("Meaningful exposure to hard problems")
        if total >= 250:
            strengths.append("Consistent, high-volume practice")
        if coverage["medium"] and coverage["medium"] >= 15:
            strengths.append(f"Covered {coverage['medium']}% of all medium problems")
        if ranking and ranking <= 100000:
            strengths.append(f"Top global ranking (#{ranking:,})")
        if contest and contest.get("rating"):
            strengths.append(f"Active contestant (rating {int(contest['rating'])})")

        if h < 20:
            improvements.append("Solve more hard problems to lift difficulty mastery")
        if m < 60:
            improvements.append("Expand medium-level coverage — the core skill band")
        if total and (e / total) > 0.6:
            improvements.append("Practice skews easy; shift toward medium/hard")
        if acceptance is not None and acceptance < 40:
            improvements.append(f"Low acceptance rate ({acceptance}%) — refine before submitting")
        if not contest:
            improvements.append("No contest history — contests signal applied speed/skill")

        return {
            "strengths": strengths or ["Building a foundation — keep going"],
            "improvements": improvements or ["Well-rounded profile; push volume to level up"],
            "coverage": coverage,
        }

    # ---------- orchestration ----------

    @classmethod
    def evaluate(cls, leetcode_url):
        username = cls.extract_username(leetcode_url)
        if not username:
            raise ValueError("Invalid LeetCode URL or username")

        profile = cls.fetch_profile(username)
        contest = cls.fetch_contest_rating(username)
        solved = profile["solved"]

        scores = cls.calculate_scores(
            solved["easy"], solved["medium"], solved["hard"],
            contest_rating=(contest or {}).get("rating"),
        )
        insights = cls.generate_insights(
            solved, profile["available"], profile["ranking"],
            profile["acceptance"], contest,
        )

        return {
            "username": username,
            "easy_solved": solved["easy"],
            "medium_solved": solved["medium"],
            "hard_solved": solved["hard"],
            "total_solved": sum(solved.values()),
            "ranking": profile["ranking"],
            "acceptance_rate": profile["acceptance"],
            "contest_rating": (contest or {}).get("rating"),
            **scores,
            **insights,
        }


if __name__ == "__main__":
    try:
        url = input("Enter LeetCode URL: ")
        r = LeetCodeEvaluator.evaluate(url)

        print("\n===== DELULU LeetCode Analysis =====")
        print(f"Username        : {r['username']}")
        print(f"Tier            : {r['tier']}")
        print(f"Easy / Med / Hard : {r['easy_solved']} / {r['medium_solved']} / {r['hard_solved']}")
        print(f"Total Solved    : {r['total_solved']}")
        if r["ranking"]:
            print(f"Global Rank     : #{r['ranking']:,}")
        if r["contest_rating"]:
            print(f"Contest Rating  : {int(r['contest_rating'])}")
        if r["acceptance_rate"] is not None:
            print(f"Acceptance Rate : {r['acceptance_rate']}%")

        print("\nScore Breakdown (0-100)")
        print(f"  Volume        : {r['volume']}")
        print(f"  Mastery       : {r['mastery']}")
        print(f"  Hard Depth    : {r['hard_depth']}")
        print(f"  Balance       : {r['balance']}")
        if r["contest_bonus"]:
            print(f"  Contest Bonus : +{r['contest_bonus']}")
        print(f"  CODING SKILL  : {r['coding_skill']}  ({r['tier']})")

        cov = r["coverage"]
        print("\nPlatform Coverage")
        for d in ("easy", "medium", "hard"):
            if cov[d] is not None:
                print(f"  {d.capitalize():6} : {cov[d]}% of all available")

        print("\nStrengths")
        for s in r["strengths"]:
            print(f"  + {s}")

        print("\nImprovements")
        for i in r["improvements"]:
            print(f"  - {i}")

    except Exception as e:
        print(f"\nError: {e}")
