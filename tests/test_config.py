"""Tests for configuration loading."""

from pathlib import Path

from spierscraper.config import CategoryFilter, Config


class TestConfig:
    """Tests for Config class."""

    def test_load_from_yaml(self, tmp_path: Path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
filters:
  pants:
    fits:
      - Contemporary
    sizes:
      - "33"
rate_limit_seconds: 2.0
""")

        config = Config.load(config_file)

        assert "pants" in config.filters
        assert config.filters["pants"].fits == ["Contemporary"]
        assert config.filters["pants"].sizes == ["33"]
        assert config.rate_limit_seconds == 2.0

    def test_env_var_webhook(self, monkeypatch):
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.com/webhook")

        config = Config.load(None)

        assert config.discord_webhook_url == "https://example.com/webhook"

    def test_has_filters_for_category(self):
        config = Config(
            filters={
                "pants": CategoryFilter(fits=["Slim"], sizes=["33"]),
            }
        )

        assert config.has_filters_for_category("pants") is True
        assert config.has_filters_for_category("PANTS") is True
        assert config.has_filters_for_category("sport_coats") is False

    def test_get_filter_normalizes_category(self):
        config = Config(
            filters={
                "sport_coats": CategoryFilter(fits=["Moro"], sizes=["40R"]),
            }
        )

        # Various forms should work
        assert config.get_filter("sport_coats") is not None
        assert config.get_filter("sport-coats") is not None
        assert config.get_filter("SPORT_COATS") is not None

    def test_default_values(self):
        config = Config()

        assert config.rate_limit_seconds == 1.5
        assert config.cache_ttl_hours == 24
        assert config.cache_path is None
        assert config.base_url == "https://www.spierandmackay.com"
