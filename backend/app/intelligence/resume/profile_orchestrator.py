"""Resume profile orchestration using shared runtime stages."""

from __future__ import annotations

import json
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.artifacts import save_artifact
from app.intelligence.base_orchestrator import BaseDocumentOrchestrator
from app.intelligence.resume.profile_validator import validate_profile
from app.intelligence.resume.url_extractor import extract_urls
from app.intelligence.telemetry import OrchestratorTelemetry
from app.llm.factory import get_llm_provider
from app.schemas.artifacts import ArtifactStatus, ArtifactType
from app.schemas.candidate import CandidateProfile
from app.schemas.document import Document
from app.schemas.fields import ExtractedField, SkillField, VersioningMeta
from app.skills.normalizer import normalize_skill_record


class ResumeProfileOrchestrator(BaseDocumentOrchestrator[CandidateProfile]):
    def __init__(self, db: AsyncSession | None = None):
        super().__init__()
        self.db = db

    def normalize(self, sections: dict[str, str]) -> dict[str, str]:
        # URL extraction happens pre-LLM and is deterministic.
        text = "\n".join(v for v in sections.values() if v)
        urls = extract_urls(text)
        sections["_urls"] = json.dumps(urls)
        return sections

    async def extract(
        self,
        document: Document,
        sections: dict[str, str],
        telemetry: OrchestratorTelemetry,
    ) -> CandidateProfile:
        urls = json.loads(sections.get("_urls", "{}"))
        text = document.cleaned_text

        # Deterministic pre-normalized skill candidates from ontology.
        ontology_hits = self._extract_skill_candidates(text)
        skills = [
            SkillField(
                skill_id=hit.skill_id,
                name=hit.canonical_name,
                normalized_name=hit.canonical_name,
                canonical_name=hit.canonical_name,
                aliases=hit.aliases,
                category=hit.category,
                domain=hit.domain,
                confidence=hit.confidence,
                source=hit.source,
            )
            for hit in ontology_hits
        ]

        fallback = self._heuristic_profile(document, skills, urls)

        llm = get_llm_provider()
        telemetry.provider = type(llm).__name__.replace("Provider", "").lower()
        telemetry.model = llm.model_name
        prompt = (
            "Extract resume profile JSON with keys: name,email,phone,"
            "github_url,linkedin_url,leetcode_url,portfolio_url. "
            "Return JSON only.\n"
            f"Resume text:\n{text[:6000]}"
        )
        try:
            raw = await llm.generate_text(prompt, temperature=0.0)
            data = json.loads(raw)
            profile = fallback.model_copy(
                update={
                    "name": ExtractedField(value=data.get("name") or fallback.name.value, confidence=0.8),
                    "email": ExtractedField(value=data.get("email"), confidence=0.75)
                    if data.get("email")
                    else fallback.email,
                    "phone": ExtractedField(value=data.get("phone"), confidence=0.7)
                    if data.get("phone")
                    else fallback.phone,
                }
            )
        except Exception:
            profile = fallback

        # URLs from deterministic stage override LLM/fallback if found.
        profile = profile.model_copy(
            update={
                "github_url": self._url_field(urls.get("github_url"), profile.github_url),
                "linkedin_url": self._url_field(urls.get("linkedin_url"), profile.linkedin_url),
                "leetcode_url": self._url_field(urls.get("leetcode_url"), profile.leetcode_url),
                "portfolio_url": self._url_field(urls.get("portfolio_url"), profile.portfolio_url),
            }
        )
        telemetry.average_confidence = self._avg_confidence(profile)
        return profile

    def validate(self, result: CandidateProfile, telemetry: OrchestratorTelemetry) -> None:
        warnings = validate_profile(result, min_confidence=0.55)
        telemetry.validation_errors.extend(warnings)

    async def persist(
        self,
        document: Document,
        result: CandidateProfile,
        telemetry: OrchestratorTelemetry,
    ) -> None:
        if not self.db:
            return
        await save_artifact(
            self.db,
            document.id,
            ArtifactType.PROFILE_DRAFT,
            result.model_dump(mode="json"),
            status=ArtifactStatus.PENDING_REVIEW,
        )
        telemetry.artifact_count += 1
        await self.db.commit()

    def _heuristic_profile(
        self,
        document: Document,
        skills: list[SkillField],
        urls: dict[str, str],
    ) -> CandidateProfile:
        lines = [line.strip() for line in document.cleaned_text.splitlines() if line.strip()]
        name = lines[0] if lines else "Unknown Candidate"
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", document.cleaned_text)
        phone_match = re.search(r"\+?\d[\d\s\-().]{7,}\d", document.cleaned_text)

        return CandidateProfile(
            name=ExtractedField(value=name, confidence=0.7, source=name),
            email=ExtractedField(value=email_match.group(0), confidence=0.8, source=email_match.group(0))
            if email_match
            else None,
            phone=ExtractedField(value=phone_match.group(0), confidence=0.65, source=phone_match.group(0))
            if phone_match
            else None,
            skills=skills,
            github_url=ExtractedField(value=urls.get("github_url"), confidence=0.95, source=urls.get("github_url"))
            if urls.get("github_url")
            else None,
            linkedin_url=ExtractedField(value=urls.get("linkedin_url"), confidence=0.95, source=urls.get("linkedin_url"))
            if urls.get("linkedin_url")
            else None,
            leetcode_url=ExtractedField(value=urls.get("leetcode_url"), confidence=0.95, source=urls.get("leetcode_url"))
            if urls.get("leetcode_url")
            else None,
            portfolio_url=ExtractedField(value=urls.get("portfolio_url"), confidence=0.85, source=urls.get("portfolio_url"))
            if urls.get("portfolio_url")
            else None,
            versioning=VersioningMeta(parser_version="3.0.0", prompt_version="resume_profile_v1"),
        )

    @staticmethod
    def _url_field(url: str | None, fallback: ExtractedField[str] | None) -> ExtractedField[str] | None:
        if url:
            return ExtractedField(value=url, confidence=0.95, source=url)
        return fallback

    @staticmethod
    def _avg_confidence(profile: CandidateProfile) -> float:
        values = [profile.name.confidence]
        if profile.email:
            values.append(profile.email.confidence)
        if profile.phone:
            values.append(profile.phone.confidence)
        values.extend(s.confidence for s in profile.skills[:10])
        return round(sum(values) / max(len(values), 1), 3)

    @staticmethod
    def _extract_skill_candidates(text: str):
        # Heuristic skill tokenization by commas/newlines + normalization.
        chunks = re.split(r"[,/\n]|\\band\\b", text, flags=re.I)
        hits = []
        seen: set[str] = set()
        for chunk in chunks:
            token = chunk.strip()
            if len(token) < 2 or len(token) > 40:
                continue
            record = normalize_skill_record(token, source="resume")
            if record.skill_id == "SKILL_UNKNOWN":
                continue
            if record.skill_id in seen:
                continue
            seen.add(record.skill_id)
            hits.append(record)
        return hits
