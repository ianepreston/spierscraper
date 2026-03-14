"""Configuration management."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class CategoryFilter(BaseModel):
    """Filter criteria for a garment category."""

    fits: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """Application configuration loaded from YAML and environment."""

    # Discord webhook - prefer env var for security
    discord_webhook_url: str | None = None

    # Filters by category
    filters: dict[str, CategoryFilter] = Field(default_factory=dict)

    # Rate limiting
    rate_limit_seconds: float = 1.5

    # Cache settings
    cache_ttl_hours: int = 24
    cache_path: str | None = None  # None = in-memory only

    # Base URL
    base_url: str = "https://www.spierandmackay.com"

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Config":
        """Load configuration from YAML file and environment."""
        config_data: dict[str, Any] = {}

        # Try to load from file
        if config_path and config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
        else:
            # Try default locations
            for default_path in [Path("config.yaml"), Path("config.yml")]:
                if default_path.exists():
                    with open(default_path) as f:
                        config_data = yaml.safe_load(f) or {}
                    break

        # Convert filters to CategoryFilter objects
        if "filters" in config_data:
            config_data["filters"] = {
                category: CategoryFilter(**criteria)
                for category, criteria in config_data["filters"].items()
            }

        # Environment variables override file config
        env_webhook = os.environ.get("DISCORD_WEBHOOK_URL")
        if env_webhook:
            config_data["discord_webhook_url"] = env_webhook

        return cls(**config_data)

    def has_filters_for_category(self, category: str) -> bool:
        """Check if filters are defined for a category."""
        normalized = category.lower().replace(" ", "_").replace("-", "_")
        return normalized in self.filters

    def get_filter(self, category: str) -> CategoryFilter | None:
        """Get filter for a category, or None if not defined."""
        normalized = category.lower().replace(" ", "_").replace("-", "_")
        return self.filters.get(normalized)
