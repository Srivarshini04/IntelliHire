"""Resolve LinkedIn input from URL scrape or pasted text."""

from __future__ import annotations

from app.pipeline.linkedin_scraper import LinkedInScrapeResult, scrape_linkedin_url


def resolve_linkedin_text(
    linkedin_url: str | None,
    linkedin_profile: str | None,
) -> tuple[str | None, LinkedInScrapeResult | None]:
    """
    Priority: linkedin_url (scrape) > linkedin_profile (paste).
    Returns profile text and optional scrape metadata.
    """
    if linkedin_url and linkedin_url.strip():
        scraped = scrape_linkedin_url(linkedin_url.strip())
        return scraped.profile_text, scraped

    if linkedin_profile and linkedin_profile.strip():
        return linkedin_profile.strip(), None

    return None, None
