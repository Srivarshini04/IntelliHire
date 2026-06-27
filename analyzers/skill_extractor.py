def extract_skills(github_data):
    language_bytes = {}
    topics = set()

    for repo in github_data.get("repos", []):
        # Languages come as {language: bytes_of_code}
        for language, count in repo.get("languages", {}).items():
            language_bytes[language] = language_bytes.get(language, 0) + count

        for topic in repo.get("topics", []):
            topics.add(topic.lower())

    # Most-used languages first (by total bytes written across all repos)
    languages = sorted(
        language_bytes,
        key=language_bytes.get,
        reverse=True
    )

    return {
        "languages": languages,
        "topics": sorted(topics)
    }
