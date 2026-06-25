import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.github_intel.database import Base


class GitHubProfile(Base):
    __tablename__ = "gh_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    github_username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    github_url: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    repositories: Mapped[list["GitHubRepository"]] = relationship(back_populates="profile")


class GitHubRepository(Base):
    __tablename__ = "gh_repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gh_profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    topics_json: Mapped[str] = mapped_column(Text, default="[]")
    stars: Mapped[int] = mapped_column(Integer, default=0)
    forks: Mapped[int] = mapped_column(Integer, default=0)
    size_kb: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    clone_url: Mapped[str] = mapped_column(String(512))
    default_branch: Mapped[str] = mapped_column(String(128), default="main")
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    commit_activity: Mapped[float] = mapped_column(Float, default=0.0)
    analyzed: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped["GitHubProfile"] = relationship(back_populates="repositories")
    analysis: Mapped["GitHubRepoAnalysis | None"] = relationship(
        back_populates="repository", uselist=False
    )

    @property
    def topics(self) -> list[str]:
        return json.loads(self.topics_json)

    @topics.setter
    def topics(self, value: list[str]) -> None:
        self.topics_json = json.dumps(value)


class GitHubRepoAnalysis(Base):
    __tablename__ = "gh_repository_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("gh_repositories.id"), unique=True, index=True
    )
    architecture_features_json: Mapped[str] = mapped_column(Text, default="{}")
    dependencies_json: Mapped[str] = mapped_column(Text, default="[]")
    architecture_layers_json: Mapped[str] = mapped_column(Text, default="{}")
    patterns_json: Mapped[str] = mapped_column(Text, default="{}")
    features_json: Mapped[str] = mapped_column(Text, default="{}")
    git_history_json: Mapped[str] = mapped_column(Text, default="{}")
    complexity_json: Mapped[str] = mapped_column(Text, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")

    repository: Mapped["GitHubRepository"] = relationship(back_populates="analysis")


class Skill(Base):
    __tablename__ = "gh_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")


class Capability(Base):
    __tablename__ = "gh_capabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255))


class EngineeringFeature(Base):
    __tablename__ = "gh_engineering_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(255))


class SkillCapabilityEdge(Base):
    __tablename__ = "gh_skill_capability_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("gh_skills.id"), index=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("gh_capabilities.id"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class FeatureCapabilityEdge(Base):
    __tablename__ = "gh_feature_capability_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_id: Mapped[int] = mapped_column(ForeignKey("gh_engineering_features.id"), index=True)
    capability_id: Mapped[int] = mapped_column(ForeignKey("gh_capabilities.id"), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
