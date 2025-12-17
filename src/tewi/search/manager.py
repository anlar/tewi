"""Unified search client for multiple torrent search providers."""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..util.log import get_logger
from .base import BaseSearchProvider
from .models import Category, Indexer, SearchResult
from .providers import (
    BitmagnetProvider,
    JackettProvider,
    NyaaProvider,
    ProwlarrProvider,
    TorrentsCsvProvider,
    Torrentz2Provider,
    TPBProvider,
    YTSProvider,
)

logger = get_logger()

# Available provider IDs
AVAILABLE_PROVIDERS = {
    "tpb": TPBProvider,
    "torrentscsv": TorrentsCsvProvider,
    "torrentz2": Torrentz2Provider,
    "yts": YTSProvider,
    "nyaa": NyaaProvider,
    "jackett": JackettProvider,
    "prowlarr": ProwlarrProvider,
    "bitmagnet": BitmagnetProvider,
}

# Default provider order (used when no providers are configured)
DEFAULT_PROVIDER_ORDER = [
    "tpb",
    "yts",
    "nyaa",
    "torrentscsv",
    "jackett",
    "prowlarr",
    "bitmagnet",
    "torrentz2",
]


def print_available_providers() -> None:
    """Print list of all available search providers to stdout.

    Providers are listed in default order.
    """
    print("Available search providers (default order):")
    for provider_id in DEFAULT_PROVIDER_ORDER:
        provider_class = AVAILABLE_PROVIDERS[provider_id]
        # Create temporary instance to get name
        if provider_id in ("jackett", "prowlarr"):
            # Jackett and Prowlarr need dummy args to instantiate
            instance = provider_class(None, None)
        elif provider_id == "bitmagnet":
            # Bitmagnet needs URL arg
            instance = provider_class(None)
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
        jackett_multi: bool,
        prowlarr_url: str | None,
        prowlarr_api_key: str | None,
        prowlarr_multi: bool,
        bitmagnet_url: str | None,
        enabled_providers: list[str] | None = None,
    ):
        """Initialize search client with available providers.

        Args:
            jackett_url: Base URL of Jackett instance (optional)
            jackett_api_key: API key for Jackett authentication (optional)
            jackett_multi: Load all Jackett indexers individually (optional)
            prowlarr_url: Base URL of Prowlarr instance (optional)
            prowlarr_api_key: API key for Prowlarr authentication (optional)
            prowlarr_multi: Load all Prowlarr indexers individually (optional)
            bitmagnet_url: Base URL of Bitmagnet instance (optional)
            enabled_providers: List of provider IDs to enable,
                             or None to enable all providers
        """
        self._providers: list[BaseSearchProvider] | None = None
        self._jackett_url = jackett_url
        self._jackett_api_key = jackett_api_key
        self._jackett_multi = jackett_multi
        self._prowlarr_url = prowlarr_url
        self._prowlarr_api_key = prowlarr_api_key
        self._prowlarr_multi = prowlarr_multi
        self._bitmagnet_url = bitmagnet_url
        self._enabled_providers = self._parse_enabled_providers(
            enabled_providers
        )

    def _parse_enabled_providers(
        self, enabled_providers: list[str] | None
    ) -> list[str] | None:
        """Parse and validate enabled providers list.

        Args:
            enabled_providers: List of provider IDs,
                             or None to enable all

        Returns:
            List of validated provider IDs (preserving order),
            or None for all providers

        Raises:
            SystemExit: If unknown provider ID is specified
        """
        if not enabled_providers:
            return None

        # Validate provider IDs
        unknown_providers = []
        for provider_id in enabled_providers:
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

        return enabled_providers

    def get_providers(self) -> list[BaseSearchProvider]:
        """Get list of all search providers, initializing them if needed.

        Providers are created lazily on first access for better performance.
        Only enabled providers are initialized based on configuration.
        Provider order is preserved from configuration or uses default order.

        Returns:
            List of BaseSearchProvider instances in configured order
        """
        if self._providers is None:
            self._providers = []

            # Determine which providers to enable and their order
            if self._enabled_providers is None:
                # All providers enabled - use default order
                # Only include providers that exist
                enabled_ids = [
                    p
                    for p in DEFAULT_PROVIDER_ORDER
                    if p in AVAILABLE_PROVIDERS
                ]
            else:
                # Use configured order
                enabled_ids = self._enabled_providers

            # Initialize enabled providers in order
            for provider_id in enabled_ids:
                if provider_id == "jackett":
                    # Jackett requires configuration
                    if self._jackett_url and self._jackett_api_key:
                        provider_class = AVAILABLE_PROVIDERS[provider_id]
                        self._providers.append(
                            provider_class(
                                self._jackett_url,
                                self._jackett_api_key,
                                self._jackett_multi,
                            )
                        )
                elif provider_id == "prowlarr":
                    # Prowlarr requires configuration
                    if self._prowlarr_url and self._prowlarr_api_key:
                        provider_class = AVAILABLE_PROVIDERS[provider_id]
                        self._providers.append(
                            provider_class(
                                self._prowlarr_url,
                                self._prowlarr_api_key,
                                self._prowlarr_multi,
                            )
                        )
                elif provider_id == "bitmagnet":
                    # Bitmagnet requires URL configuration
                    if self._bitmagnet_url:
                        provider_class = AVAILABLE_PROVIDERS[provider_id]
                        self._providers.append(
                            provider_class(self._bitmagnet_url)
                        )
                else:
                    # Regular providers
                    provider_class = AVAILABLE_PROVIDERS[provider_id]
                    self._providers.append(provider_class())

        return self._providers

    def get_indexers(self) -> list[Indexer]:
        """Get list of all available indexers from all providers.

        Fetches indexers from all providers in parallel for better performance.
        Returns indexers in provider order (as configured or default).
        Indexers within each provider are sorted alphabetically by name.

        Returns:
            List of Indexer objects in provider order
        """
        providers = self.get_providers()
        if not providers:
            return []

        all_indexers = []
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:
            # Submit all tasks and maintain provider order
            future_to_provider = {
                executor.submit(provider.indexers): provider
                for provider in providers
            }

            # Collect results in provider order, not completion order
            for provider in providers:
                # Find the future for this provider
                future = next(
                    f for f, p in future_to_provider.items() if p is provider
                )
                try:
                    indexers = future.result()
                    # Sort indexers alphabetically within this provider
                    indexers.sort(key=lambda idx: idx.name.lower())
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
        sorts by seeders. When deduplicating, results from providers
        earlier in the configuration take priority.

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

        # Execute all provider searches in parallel, maintaining order
        with ThreadPoolExecutor(
            max_workers=len(providers_to_search)
        ) as executor:
            # Submit all search tasks with category filter and indexers
            future_to_provider = {
                executor.submit(
                    provider.search, query, selected_categories, indexers
                ): (provider, idx)
                for idx, (provider, indexers) in enumerate(providers_to_search)
            }

            # Collect results in provider order for proper deduplication
            results_by_provider = {}
            for future in as_completed(future_to_provider):
                provider, idx = future_to_provider[future]
                try:
                    provider_results = future.result()
                    results_by_provider[idx] = provider_results
                except Exception as e:
                    # Log error but continue with other providers
                    errors.append(f"{provider.name}: {str(e)}")
                    logger.exception(f"Failed to search {provider.name}")
                    results_by_provider[idx] = []

            # Process results in provider order
            for idx in sorted(results_by_provider.keys()):
                all_results.extend(results_by_provider[idx])

        # Deduplicate by info_hash, keeping first occurrence (by provider
        # order)
        best_results = {}
        for result in all_results:
            # Use info_hash as key; fall back to title:size for results without
            if result.info_hash:
                hash_key = result.info_hash
            else:
                # Deduplicate by title + size when hash unavailable
                hash_key = f"__no_hash__{result.title}:{result.size}"

            if hash_key not in best_results:
                # First occurrence - keep it
                best_results[hash_key] = result
            # Else: duplicate - skip it (first provider takes priority)

        # Convert back to list
        all_results = list(best_results.values())

        # Filter by categories if specified
        if selected_categories:
            all_results = self._filter_by_categories(
                all_results, selected_categories
            )

        # Sort by seeders for relevance
        all_results.sort(key=lambda r: r.seeders or 0, reverse=True)

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
