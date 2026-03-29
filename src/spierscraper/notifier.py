"""Discord webhook notification system."""

import logging
from typing import Any

import httpx

from .models import DiscoveredOptions, ProductMatch

logger = logging.getLogger(__name__)

# Discord embed color (green)
EMBED_COLOR = 0x2ECC71

# Max embeds per message (Discord limit is 10)
MAX_EMBEDS_PER_MESSAGE = 10


class DiscordNotifier:
    """Send notifications to Discord via webhook."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send_matches(self, matches: list[ProductMatch]) -> bool:
        """Send product matches to Discord."""
        if not matches:
            logger.info("No matches to notify")
            return True

        if not self.webhook_url:
            logger.warning("No Discord webhook URL configured")
            return False

        # Build embeds
        embeds = [self._build_embed(match) for match in matches]

        # Send in batches
        success = True
        for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE):
            batch = embeds[i : i + MAX_EMBEDS_PER_MESSAGE]
            batch_success = await self._send_embeds(batch, i == 0, len(matches))
            success = success and batch_success

        return success

    def _build_embed(self, match: ProductMatch) -> dict[str, Any]:
        """Build a Discord embed for a product match."""
        product = match.product

        # Build variant list
        variant_lines = []
        for v in match.matching_variants:
            qty_str = f" ({v.quantity} in stock)" if v.quantity else ""
            variant_lines.append(f"- {v.fit} {v.size}{qty_str}")

        variants_text = "\n".join(variant_lines[:10])  # Limit to 10 variants
        if len(match.matching_variants) > 10:
            variants_text += f"\n... and {len(match.matching_variants) - 10} more"

        # Price info
        if product.discount_percent:
            price_text = (
                f"**${product.price}** ~~${product.original_price}~~ "
                f"({product.discount_percent}% off)"
            )
        else:
            price_text = f"**${product.price}**"

        return {
            "title": product.name,
            "url": product.url,
            "color": EMBED_COLOR,
            "fields": [
                {
                    "name": "Price",
                    "value": price_text,
                    "inline": True,
                },
                {
                    "name": "Category",
                    "value": product.category.value.replace("_", " ").title(),
                    "inline": True,
                },
                {
                    "name": "Fit",
                    "value": ", ".join(sorted({v.fit for v in match.matching_variants})),
                    "inline": True,
                },
                {
                    "name": "Size",
                    "value": ", ".join(sorted({v.size for v in match.matching_variants})),
                    "inline": True,
                },
                {
                    "name": "Available Sizes",
                    "value": variants_text or "See product page",
                    "inline": False,
                },
            ],
            "footer": {
                "text": f"SKU: {product.sku} | Collection: {product.collection}",
            },
        }

    async def _send_embeds(
        self, embeds: list[dict[str, Any]], is_first: bool, total_count: int
    ) -> bool:
        """Send a batch of embeds to Discord."""
        payload: dict[str, Any] = {"embeds": embeds}

        # Add header message to first batch
        if is_first:
            payload["content"] = f"**{total_count} matching item(s) found!**"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                logger.info(f"Sent {len(embeds)} embeds to Discord")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(f"Discord API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    async def send_error(self, error_message: str) -> bool:
        """Send an error notification to Discord."""
        if not self.webhook_url:
            return False

        payload = {
            "content": f"**Scraper Error**\n```\n{error_message[:1900]}\n```",
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            return False

    async def send_discovered_options(self, discovered: DiscoveredOptions) -> bool:
        """Send discovered category/fit/size options to Discord.

        This sends a summary of all available options found on the site,
        formatted as YAML for easy copying to config. Splits into multiple
        messages if content exceeds Discord's 2000 char limit.
        """
        if not self.webhook_url:
            logger.warning("No Discord webhook URL configured")
            return False

        if not discovered.filters:
            logger.info("No discovered options to send")
            return True

        # Build messages, splitting by category to stay under Discord's limit
        messages = self._build_discovered_messages(discovered)

        success = True
        async with httpx.AsyncClient() as client:
            for payload in messages:
                try:
                    response = await client.post(
                        self.webhook_url,
                        json=payload,
                        timeout=10.0,
                    )
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.error(f"Discord API error: {e.response.status_code} - {e.response.text}")
                    success = False
                except Exception as e:
                    logger.error(f"Failed to send discovered options: {e}")
                    success = False

        if success:
            logger.info(f"Sent discovered options to Discord ({len(messages)} message(s))")
        return success

    def _build_discovered_messages(self, discovered: DiscoveredOptions) -> list[dict[str, str]]:
        """Build Discord messages for discovered options, splitting if needed."""
        import yaml

        messages: list[dict[str, str]] = []
        header = (
            "**Available Options on Site**\n"
            "All category/fit/size combinations found in sale items:\n"
        )

        # Discord limit is 2000 chars; leave room for code block markers and header
        max_content_per_msg = 1850

        current_yaml_lines: list[str] = ["filters:"]
        current_len = len("filters:\n")

        for category, opts in sorted(discovered.filters.items()):
            # Format this category as YAML
            category_data = {category: {"fits": opts.fits, "sizes": opts.sizes}}
            category_yaml = yaml.dump(category_data, default_flow_style=False)
            # Indent to nest under 'filters:'
            indented = "\n".join("  " + line for line in category_yaml.strip().split("\n"))
            category_len = len(indented) + 1  # +1 for newline

            # Check if adding this category would exceed the limit
            if current_len + category_len > max_content_per_msg and len(current_yaml_lines) > 1:
                # Flush current message
                yaml_content = "\n".join(current_yaml_lines)
                content = f"{header}```yaml\n{yaml_content}\n```"
                messages.append({"content": content})
                # Start new message (continuation doesn't need full header)
                header = "*(continued)*\n"
                current_yaml_lines = ["filters:"]
                current_len = len("filters:\n")

            current_yaml_lines.append(indented)
            current_len += category_len

        # Flush remaining content
        if len(current_yaml_lines) > 1:
            yaml_content = "\n".join(current_yaml_lines)
            content = f"{header}```yaml\n{yaml_content}\n```"
            messages.append({"content": content})

        return messages
