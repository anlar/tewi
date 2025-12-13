"""Unified search client for multiple torrent search providers."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..util.log import get_logger
from .base import BaseSearchProvider
from .models import Category, Indexer, SearchResult
from .providers import (
    JackettProvider,
    NyaaProvider,
    ProwlarrProvider,
    TorrentsCsvProvider,
    TPBProvider,
    YTSProvider,
)

logger = get_logger()

# Available provider IDs
AVAILABLE_PROVIDERS = {
    "tpb": TPBProvider,
    "torrentscsv": TorrentsCsvProvider,
    "yts": YTSProvider,
    "nyaa": NyaaProvider,
    "jackett": JackettProvider,
    "prowlarr": ProwlarrProvider,
}


def print_available_providers() -> None:
    """Print list of all available search providers to stdout."""
    print("Available search providers:")
    for provider_id in sorted(AVAILABLE_PROVIDERS.keys()):
        provider_class = AVAILABLE_PROVIDERS[provider_id]
        # Create temporary instance to get name
        if provider_id in ("jackett", "prowlarr"):
            # Jackett and Prowlarr need dummy args to instantiate
            instance = provider_class(None, None)
        else:
            instance = provider_class()
        print(f"  - {provider_id}: {instance.name}")


class SearchClient:
    """Unified search client that coordinates multiple torrent providers.

    This client manages multiple search providers (YTS, TorrentsCSV, TPB,
    Nyaa, Jackett) and provides a unified search interface. It handles:
    - Lazy provider initialization (on first access)
    - Parallel search execution across providers
    - Result deduplication based on info_hash
    - Error handling and logging

    Providers are initialized lazily on first use for better performance.
    """

    def __init__(
        self,
        jackett_url: str | None,
        jackett_api_key: str | None,
        prowlarr_url: str | None,
        prowlarr_api_key: str | None,
        enabled_providers: str | None = None,
    ):
        """Initialize search client with available providers.

        Args:
            jackett_url: Base URL of Jackett instance (optional)
            jackett_api_key: API key for Jackett authentication (optional)
            prowlarr_url: Base URL of Prowlarr instance (optional)
            prowlarr_api_key: API key for Prowlarr authentication (optional)
            enabled_providers: Comma-separated list of provider IDs to enable,
                             or None to enable all providers
        """
        self._providers: list[BaseSearchProvider] | None = None
        self._jackett_url = jackett_url
        self._jackett_api_key = jackett_api_key
        self._prowlarr_url = prowlarr_url
        self._prowlarr_api_key = prowlarr_api_key
        self._enabled_providers = self._parse_enabled_providers(
            enabled_providers
        )

    def _parse_enabled_providers(
        self, enabled_providers: str | None
    ) -> set[str] | None:
        """Parse and validate enabled providers list.

        Args:
            enabled_providers: Comma-separated list of provider IDs,
                             or None to enable all

        Returns:
            Set of validated provider IDs, or None for all providers

        Raises:
            SystemExit: If unknown provider ID is specified
        """
        if not enabled_providers or not enabled_providers.strip():
            return None

        # Parse CSV list
        provider_ids = [
            p.strip() for p in enabled_providers.split(",") if p.strip()
        ]

        if not provider_ids:
            return None

        # Validate provider IDs
        unknown_providers = []
        for provider_id in provider_ids:
            if provider_id not in AVAILABLE_PROVIDERS:
                unknown_providers.append(provider_id)

        if unknown_providers:
            print(
                f"Error: Unknown search provider(s): "
                f"{', '.join(unknown_providers)}",
                file=sys.stderr,
            )
            print(
                f"Available providers: "
                f"{', '.join(sorted(AVAILABLE_PROVIDERS.keys()))}",
                file=sys.stderr,
            )
            sys.exit(1)

        return set(provider_ids)

    def get_providers(self) -> list[BaseSearchProvider]:
        """Get list of all search providers, initializing them if needed.

        Providers are created lazily on first access for better performance.
        Only enabled providers are initialized based on configuration.

        Returns:
            List of BaseSearchProvider instances
        """
        if self._providers is None:
            self._providers = []

            # Determine which providers to enable
            if self._enabled_providers is None:
                # All providers enabled
                enabled_ids = set(AVAILABLE_PROVIDERS.keys())
            else:
                # Only specified providers enabled
                enabled_ids = self._enabled_providers

            # Initialize enabled providers (sorted for consistent order)
            for provider_id in sorted(enabled_ids):
                if provider_id == "jackett":
                    # Jackett requires configuration
                    if self._jackett_url and self._jackett_api_key:
                        provider_class = AVAILABLE_PROVIDERS[provider_id]
                        self._providers.append(
                            provider_class(
                                self._jackett_url, self._jackett_api_key
                            )
                        )
                elif provider_id == "prowlarr":
                    # Prowlarr requires configuration
                    if self._prowlarr_url and self._prowlarr_api_key:
                        provider_class = AVAILABLE_PROVIDERS[provider_id]
                        self._providers.append(
                            provider_class(
                                self._prowlarr_url, self._prowlarr_api_key
                            )
                        )
                else:
                    # Regular providers
                    provider_class = AVAILABLE_PROVIDERS[provider_id]
                    self._providers.append(provider_class())

        return self._providers

    def get_indexers(self) -> list[Indexer]:
        """Get list of all available indexers from all providers.

        Fetches indexers from all providers in parallel for better performance.

        Returns:
            List of Indexer objects representing all available indexers
        """
        providers = self.get_providers()
        if not providers:
            return []

        all_indexers = []
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            future_to_provider = {
                executor.submit(provider.indexers): provider
                for provider in providers
            }

            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    indexers = future.result()
                    all_indexers.extend(indexers)
                except Exception as e:
                    # Log error but continue with other providers
                    logger.warning(
                        f"Failed to fetch indexers from {provider.name}: {e}"
                    )

        return all_indexers

    def search(
        self,
        query: str,
        selected_indexers: list[str] | None,
        selected_categories: list[Category] | None,
    ) -> tuple[list[SearchResult], list[str]]:
        """Search for torrents across multiple providers in parallel.

        Executes searches across all selected providers concurrently,
        deduplicates results by info_hash, filters by category, and
        sorts by seeders.

        Args:
            query: Search term to query providers with
            selected_indexers: List of indexer IDs to search, or None for all
            selected_categories: List of Category objects to filter by,
                                or None for all

        Returns:
            Tuple of (results, errors) where:
            - results: List of SearchResult objects, deduplicated,
                      filtered by category, and sorted by seeders
                      (highest first)
            - errors: List of error messages from failed providers
        """
        all_results = []
        errors = []

        # Filter providers based on selected indexers
        providers_to_search = self._filter_providers(selected_indexers)

        # Execute all provider searches in parallel
        with ThreadPoolExecutor(
            max_workers=len(providers_to_search)
        ) as executor:
            # Submit all search tasks with category filter and indexers
            future_to_provider = {
                executor.submit(
                    provider.search, query, selected_categories, indexers
                ): provider
                for provider, indexers in providers_to_search
            }

            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    all_results.extend(provider_results)
                except Exception as e:
                    # Log error but continue with other providers
                    errors.append(f"{provider.name}: {str(e)}")
                    logger.exception(f"Failed to search {provider.name}")

        # Deduplicate by info_hash, keeping result with highest seeders
        best_results = {}
        for result in all_results:
            # Use info_hash as key; fall back to title:size for results without
            if result.info_hash:
                hash_key = result.info_hash
            else:
                # Deduplicate by title + size when hash unavailable
                hash_key = f"__no_hash__{result.title}:{result.size}"

            if hash_key not in best_results:
                best_results[hash_key] = result
            else:
                # Keep the result with more seeders
                if result.seeders > best_results[hash_key].seeders:
                    best_results[hash_key] = result

        # Convert back to list
        all_results = list(best_results.values())

        # Filter by categories if specified
        if selected_categories:
            all_results = self._filter_by_categories(
                all_results, selected_categories
            )

        # Sort by seeders for relevance
        all_results.sort(key=lambda r: r.seeders, reverse=True)

        return all_results, errors

    def _group_indexers(
        self, selected_indexers: list[str]
    ) -> tuple[set[str], list[str], list[str]]:
        """Group selected indexers by provider type.

        Args:
            selected_indexers: List of indexer IDs

        Returns:
            Tuple of (regular_providers, jackett_indexers, prowlarr_indexers)
        """
        regular_providers = set()
        jackett_indexers = []
        prowlarr_indexers = []

        for indexer_id in selected_indexers:
            if indexer_id.startswith("jackett:"):
                jackett_indexers.append(indexer_id.removeprefix("jackett:"))
            elif indexer_id.startswith("prowlarr:"):
                prowlarr_indexers.append(indexer_id.removeprefix("prowlarr:"))
            else:
                regular_providers.add(indexer_id)

        return regular_providers, jackett_indexers, prowlarr_indexers

    def _filter_providers(
        self, selected_indexers: list[str] | None
    ) -> list[tuple[BaseSearchProvider, list[str] | None]]:
        """Filter providers based on selected indexers.

        Processes the selected indexer IDs and returns the appropriate
        providers to search with their specific indexers.

        Args:
            selected_indexers: List of indexer IDs to search,
                              or None to search all providers

        Returns:
            List of tuples (provider, indexers) where indexers is
            a list of indexer IDs for that provider or None for all
        """
        if selected_indexers is None:
            return [(p, None) for p in self.get_providers()]

        regular, jackett, prowlarr = self._group_indexers(selected_indexers)
        providers_to_search = []

        for provider in self.get_providers():
            provider_id = provider.id
            if provider_id == "jackett" and jackett:
                providers_to_search.append((provider, jackett))
            elif provider_id == "prowlarr" and prowlarr:
                providers_to_search.append((provider, prowlarr))
            elif provider_id in regular:
                providers_to_search.append((provider, None))

        return providers_to_search

    def _filter_by_categories(
        self,
        results: list[SearchResult],
        selected_categories: list[Category],
    ) -> list[SearchResult]:
        """Filter search results by categories.

        Keeps results that have at least one category matching the
        selected categories. Matches both exact category IDs and
        parent categories.

        Args:
            results: List of search results to filter
            selected_categories: List of Category objects to match

        Returns:
            Filtered list of search results
        """
        if not selected_categories:
            return results

        # Extract category IDs from Category objects
        selected_cat_ids = {cat.id for cat in selected_categories}

        filtered_results = []
        for result in results:
            if not result.categories:
                # No categories assigned - skip
                continue

            # Check if any result category matches selected categories
            for category in result.categories:
                # Match exact category ID
                if category.id in selected_cat_ids:
                    filtered_results.append(result)
                    break
                # Match parent category ID
                if category.parent and category.parent.id in selected_cat_ids:
                    filtered_results.append(result)
                    break

        return filtered_results
