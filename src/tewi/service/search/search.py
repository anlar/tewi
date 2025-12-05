"""Unified search client for multiple torrent search providers."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...common import SearchResultDTO, IndexerDTO
from .base_provider import BaseSearchProvider
from . import (
        YTSProvider,
        TorrentsCsvProvider,
        TPBProvider,
        NyaaProvider,
        JackettProvider
)


logger = logging.getLogger('tewi')


class SearchClient:
    """Unified search client that coordinates multiple torrent providers.

    This client manages multiple search providers (YTS, TorrentsCSV, TPB,
    Nyaa, Jackett) and provides a unified search interface. It handles:
    - Provider initialization and configuration
    - Parallel search execution across providers
    - Result deduplication based on info_hash
    - Error handling and logging

    Attributes:
        providers: List of initialized search provider instances
        indexers: List of all available indexers from all providers
    """

    def __init__(self, jackett_url: str | None, jackett_api_key: str | None):
        """Initialize search client with available providers.

        Args:
            jackett_url: Base URL of Jackett instance (optional)
            jackett_api_key: API key for Jackett authentication (optional)
        """
        self.providers = [
            YTSProvider(),
            TorrentsCsvProvider(),
            TPBProvider(),
            NyaaProvider()
        ]

        if jackett_url and jackett_api_key:
            self.providers.append(JackettProvider(jackett_url, jackett_api_key))

    def get_indexers(self) -> list[IndexerDTO]:
        """Get list of all available indexers from all providers.

        Returns:
            List of IndexerDTO objects representing all available indexers
        """
        return [idx for p in self.providers for idx in p.indexers()]

    def search(self, query: str, selected_indexers: list[str] | None) -> tuple[
            list[SearchResultDTO], list[str]]:
        """Search for torrents across multiple providers in parallel.

        Executes searches across all selected providers concurrently,
        deduplicates results by info_hash, and sorts by seeders.

        Args:
            query: Search term to query providers with
            selected_indexers: List of indexer IDs to search, or None for all

        Returns:
            Tuple of (results, errors) where:
            - results: List of SearchResultDTO objects, deduplicated and
                      sorted by seeders (highest first)
            - errors: List of error messages from failed providers
        """
        all_results = []
        errors = []

        # Filter providers based on selected indexers
        providers_to_search = self._filter_providers(selected_indexers)

        # Execute all provider searches in parallel
        with ThreadPoolExecutor(
                max_workers=len(providers_to_search)) as executor:
            # Submit all search tasks
            future_to_provider = {
                    executor.submit(provider.search, query): provider
                    for provider in providers_to_search
                    }

            # Collect results as they complete
            for future in as_completed(future_to_provider):
                provider = future_to_provider[future]
                try:
                    provider_results = future.result()
                    all_results.extend(provider_results)
                except Exception as e:
                    # Log error but continue with other providers
                    errors.append(f"{provider.short_name}: {str(e)}")
                    logger.exception(f"Failed to search {provider.short_name}")

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

        # Convert back to list and sort by seeders for relevance
        all_results = list(best_results.values())
        all_results.sort(key=lambda r: r.seeders, reverse=True)

        return all_results, errors

    def _filter_providers(self, selected_indexers: list[str] | None) -> list[BaseSearchProvider]:
        """Filter providers based on selected indexers.

        Processes the selected indexer IDs and returns the appropriate
        providers to search. Handles special cases like Jackett where
        individual indexers need to be configured.

        Args:
            selected_indexers: List of indexer IDs to search,
                              or None to search all providers

        Returns:
            List of BaseSearchProvider instances to search
        """
        if selected_indexers is None:
            # Search all providers
            return self.providers

        providers_to_search = []

        # Group selected indexers by provider
        regular_providers = set()
        jackett_indexers = []

        for indexer_id in selected_indexers:
            if indexer_id.startswith('jackett:'):
                # Extract jackett indexer ID (remove 'jackett:' prefix)
                jackett_indexers.append(indexer_id.removeprefix('jackett:'))
            else:
                # Regular provider
                regular_providers.add(indexer_id)

        # Add regular providers if selected
        for provider in self.providers:
            provider_id = provider.id()
            if provider_id == 'jackett':
                # Handle Jackett separately
                if jackett_indexers:
                    # Configure Jackett with selected indexers
                    provider.set_selected_indexers(jackett_indexers)
                    providers_to_search.append(provider)
            elif provider_id in regular_providers:
                # Add regular provider
                providers_to_search.append(provider)

        return providers_to_search
