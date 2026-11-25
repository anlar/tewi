"""Shared helpers for search tests."""

from src.tewi.search.models import DetailsLink, DetailsSection


def details_fields(
    sections: list[DetailsSection],
) -> dict[str, str | DetailsLink]:
    """Field values by label, from all sections."""
    return {label: value for s in sections for label, value in s.fields}


def details_section(
    sections: list[DetailsSection], title: str
) -> DetailsSection | None:
    """Section with title, or None if there is no such section."""
    return next((s for s in sections if s.title == title), None)
