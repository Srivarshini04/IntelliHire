"""Step 10 — Evidence-based recruiter explanation."""

from __future__ import annotations

from app.pipeline.aggregation import CandidateProfile
from app.pipeline.evidence_graph import EvidenceGraph
from app.pipeline.skill_assessment import SkillAssessment
from app.pipeline.verification import VerifiedSkill


def build_recruiter_assessment(
    profile: CandidateProfile,
    skill_assessments: dict[str, SkillAssessment],
    verified: dict[str, VerifiedSkill],
    jd_skills: list[str],
    jd_capabilities: list[str] | None = None,
    graph: EvidenceGraph | None = None,
    jd_match: dict | None = None,
    maturity: dict[str, int] | None = None,
) -> dict:
    jd_capabilities = jd_capabilities or []
    matched: list[str] = []
    supporting: list[str] = []
    missing: list[str] = []
    verified_claims: list[str] = []
    unverified_claims: list[str] = []

    for skill in jd_skills:
        v = verified.get(skill)
        a = skill_assessments.get(skill)
        if v and v.verified:
            matched.append(skill)
            verified_claims.append(f"{skill}: {v.explanation}")
            if v.github_evidence:
                supporting.append(f"{skill} — {v.github_evidence[0]}")
            elif a and a.evidence:
                supporting.append(f"{skill} — {a.evidence[0]}")
        elif v and v.status == "claimed":
            unverified_claims.append(f"{skill}: {v.explanation}")
            missing.append(f"{skill} — claimed on {', '.join(v.claim_sources)} but not verified in code")
        elif v and v.status == "weak":
            missing.append(f"{skill} — weak GitHub evidence only ({'; '.join(v.github_evidence[:2])})")
            if v.github_evidence:
                supporting.append(f"Partial {skill}: {v.github_evidence[0]}")
        elif v and v.status == "demonstrated":
            matched.append(skill)
            supporting.append(f"{skill} demonstrated in GitHub without profile claim")
        else:
            missing.append(f"{skill} — no evidence or claims (unknown)")

    for feat_id, feat in profile.features.items():
        if feat.detected and feat.depth >= 0.35:
            repos = profile.feature_sources.get(feat_id, [])
            repo_note = f" across {len(repos)} repos" if len(repos) > 1 else ""
            supporting.append(
                f"{feat.label} depth {int(feat.depth * 100)}%{repo_note}: {', '.join(feat.evidence[:2])}"
            )

    if graph:
        supporting.extend(graph.recruiter_lines()[:4])

    if maturity and maturity.get("overall", 0) >= 50:
        supporting.append(
            f"Engineering maturity {maturity['overall']}/100 "
            f"(architecture {maturity.get('architecture', 0)}, "
            f"testing {maturity.get('testing', 0)}, "
            f"deployment {maturity.get('deployment', 0)})"
        )

    cap_gaps: list[str] = []
    if jd_capabilities:
        for cap in jd_capabilities:
            cap_key = cap.lower().replace(" ", "_")
            # caller passes normalized capability keys in jd_match if available
            pass

    if jd_match:
        for jd_skill, match in jd_match.get("skills", {}).items():
            if match.get("verification_status") == "verified" and match.get("evidence_score"):
                pass  # already in matched
            elif match.get("verification_status") == "claimed":
                if f"{jd_skill} — claimed" not in " ".join(missing):
                    unverified_claims.append(f"JD {jd_skill}: unverified claim")

    verified_count = len([s for s in jd_skills if verified.get(s) and verified[s].verified])
    demonstrated_features = [
        f.label for f in profile.features.values() if f.detected and f.depth >= 0.5
    ]

    if verified_count >= len(jd_skills) * 0.7 and demonstrated_features:
        assessment = (
            f"Meets {verified_count}/{len(jd_skills)} JD skills with verified engineering evidence. "
            f"Demonstrated features: {', '.join(demonstrated_features[:5])}."
        )
    elif verified_count > 0:
        assessment = (
            f"Partial JD fit: {verified_count}/{len(jd_skills)} skills verified in code. "
            f"Unverified claims must not be scored as demonstrated."
        )
    elif demonstrated_features:
        assessment = (
            f"No JD skills fully verified, but GitHub shows {', '.join(demonstrated_features[:4])}. "
            "Review claim vs evidence gap before proceeding."
        )
    else:
        assessment = (
            "Insufficient engineering evidence for JD requirements — "
            "no verified skills or production features detected in analyzed repositories."
        )

    return {
        "matched_requirements": matched,
        "supporting_evidence": list(dict.fromkeys(supporting))[:12],
        "missing_requirements": missing,
        "verified_claims": verified_claims,
        "unverified_claims": unverified_claims,
        "overall_assessment": assessment,
    }
