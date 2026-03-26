"""Tests for Discord notifier."""

from decimal import Decimal

import httpx
import pytest
import respx

from spierscraper.models import (
    CategoryOptions,
    DiscoveredOptions,
    GarmentCategory,
    Product,
    ProductMatch,
    ProductVariant,
)
from spierscraper.notifier import DiscordNotifier


@pytest.fixture
def sample_matches() -> list[ProductMatch]:
    """Create sample matches for testing."""
    matches = []
    for i in range(2):
        product = Product(
            name=f"Test Product {i}",
            url=f"http://example.com/product/{i}",
            sku=f"SKU-{i}",
            price=Decimal("25.00"),
            original_price=Decimal("50.00"),
            category=GarmentCategory.PANTS,
            collection="clearance-rack",
            variants=[
                ProductVariant(
                    fit="Contemporary", size="33", sku=f"SKU-{i}-C-33", in_stock=True, quantity=2
                ),
            ],
        )
        matches.append(ProductMatch(product=product, matching_variants=product.variants))
    return matches


class TestDiscordNotifier:
    """Tests for DiscordNotifier."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_matches_success(self, sample_matches: list[ProductMatch]):
        webhook_url = "https://discord.com/api/webhooks/test/test"
        route = respx.post(webhook_url).mock(return_value=httpx.Response(204))

        notifier = DiscordNotifier(webhook_url)
        result = await notifier.send_matches(sample_matches)

        assert result is True
        assert route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_matches_failure(self, sample_matches: list[ProductMatch]):
        webhook_url = "https://discord.com/api/webhooks/test/test"
        respx.post(webhook_url).mock(return_value=httpx.Response(500))

        notifier = DiscordNotifier(webhook_url)
        result = await notifier.send_matches(sample_matches)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_matches_no_webhook(self, sample_matches: list[ProductMatch]):
        notifier = DiscordNotifier("")
        result = await notifier.send_matches(sample_matches)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_empty_matches(self):
        notifier = DiscordNotifier("https://discord.com/api/webhooks/test/test")
        result = await notifier.send_matches([])

        assert result is True  # No-op success

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_error(self):
        webhook_url = "https://discord.com/api/webhooks/test/test"
        route = respx.post(webhook_url).mock(return_value=httpx.Response(204))

        notifier = DiscordNotifier(webhook_url)
        result = await notifier.send_error("Test error message")

        assert result is True
        assert route.called

    def test_build_embed_has_required_fields(self, sample_matches: list[ProductMatch]):
        notifier = DiscordNotifier("test")
        embed = notifier._build_embed(sample_matches[0])

        assert "title" in embed
        assert "url" in embed
        assert "fields" in embed
        assert len(embed["fields"]) >= 2

    def test_build_embed_shows_discount(self, sample_matches: list[ProductMatch]):
        notifier = DiscordNotifier("test")
        embed = notifier._build_embed(sample_matches[0])

        price_field = next(f for f in embed["fields"] if f["name"] == "Price")
        assert "50%" in price_field["value"]  # 50% off ($50 -> $25)

    @respx.mock
    @pytest.mark.asyncio
    async def test_send_discovered_options_success(self):
        webhook_url = "https://discord.com/api/webhooks/test/test"
        route = respx.post(webhook_url).mock(return_value=httpx.Response(204))

        discovered = DiscoveredOptions(
            filters={
                "pants": CategoryOptions(fits=["Slim", "Classic"], sizes=["32", "34"]),
            }
        )

        notifier = DiscordNotifier(webhook_url)
        result = await notifier.send_discovered_options(discovered)

        assert result is True
        assert route.called

    def test_build_discovered_messages_single(self):
        """Small discovered options should fit in a single message."""
        notifier = DiscordNotifier("test")
        discovered = DiscoveredOptions(
            filters={
                "pants": CategoryOptions(fits=["Slim"], sizes=["32"]),
            }
        )

        messages = notifier._build_discovered_messages(discovered)

        assert len(messages) == 1
        assert len(messages[0]["content"]) < 2000
        assert "filters:" in messages[0]["content"]
        assert "pants:" in messages[0]["content"]

    def test_build_discovered_messages_splits_large_content(self):
        """Large discovered options should split into multiple messages."""
        notifier = DiscordNotifier("test")

        # Create many categories with many fits/sizes to exceed the limit
        filters = {}
        for i in range(15):
            filters[f"category_{i}"] = CategoryOptions(
                fits=[f"Fit_{j}" for j in range(10)],
                sizes=[f"Size_{k}" for k in range(20)],
            )

        discovered = DiscoveredOptions(filters=filters)
        messages = notifier._build_discovered_messages(discovered)

        # Should split into multiple messages
        assert len(messages) > 1

        # All messages should be under 2000 chars
        for msg in messages:
            assert len(msg["content"]) < 2000, f"Message too long: {len(msg['content'])}"

        # First message should have full header
        assert "**Available Options on Site**" in messages[0]["content"]

        # Subsequent messages should have continuation header
        for msg in messages[1:]:
            assert "*(continued)*" in msg["content"]
