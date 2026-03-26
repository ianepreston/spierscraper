"""CLI entry point for the scraper."""

import argparse
import asyncio
import logging
import sys
import traceback
from pathlib import Path

from .cache import MatchCache
from .config import Config
from .filters import filter_products
from .notifier import DiscordNotifier
from .scraper import SpierMackayScraper


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def run_discover(config: Config) -> int:
    """Discover all available options from the site."""
    logger = logging.getLogger(__name__)

    try:
        async with SpierMackayScraper(
            base_url=config.base_url,
            rate_limit=config.rate_limit_seconds,
        ) as scraper:
            logger.info("Discovering available options...")
            discovered = await scraper.discover_available_options()

        if not discovered.filters:
            logger.warning("No options discovered")
            return 1

        # Print as YAML for easy copy-paste into config
        print("\n# Discovered options (copy relevant sections to your config.yaml):\n")
        print(discovered.to_yaml())

        return 0

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return 1


async def run_scraper(config: Config, dry_run: bool = False) -> int:
    """Run the scraper and send notifications."""
    logger = logging.getLogger(__name__)

    # Initialize components
    cache = MatchCache(
        cache_path=config.cache_path,
        ttl_hours=config.cache_ttl_hours,
    )

    notifier = DiscordNotifier(config.discord_webhook_url or "")

    try:
        # Scrape products
        async with SpierMackayScraper(
            base_url=config.base_url,
            rate_limit=config.rate_limit_seconds,
            config=config,
        ) as scraper:
            logger.info("Starting scrape...")
            products = await scraper.scrape_all()

        if not products:
            logger.warning("No products found")
            return 0

        logger.info(f"Found {len(products)} products, applying filters...")

        # Filter to matches
        matches = filter_products(products, config)
        logger.info(f"Found {len(matches)} matches")

        if not matches:
            logger.info("No matches found for configured filters")
            return 0

        # Filter to new matches only
        new_matches = cache.filter_new(matches)
        logger.info(f"New matches (not seen in last {config.cache_ttl_hours}h): {len(new_matches)}")

        if not new_matches:
            logger.info("No new matches to notify")
            return 0

        # Send notifications
        if dry_run:
            logger.info("Dry run - would send these matches:")
            for match in new_matches:
                logger.info(f"  - {match.product.name}: {len(match.matching_variants)} variants")
            return 0

        if config.discord_webhook_url:
            success = await notifier.send_matches(new_matches)
            if not success:
                logger.error("Failed to send some notifications")
                return 1
        else:
            logger.warning("No Discord webhook configured - printing matches:")
            for match in new_matches:
                print(f"\n{match.product.name}")
                print(f"  URL: {match.product.url}")
                print(f"  Price: ${match.product.price}")
                for v in match.matching_variants:
                    print(f"  - {v.fit} {v.size}")

        return 0

    except Exception as e:
        logger.error(f"Scraper failed: {e}")
        logger.debug(traceback.format_exc())

        # Try to notify about the error
        if config.discord_webhook_url and not dry_run:
            await notifier.send_error(str(e))

        return 1

    finally:
        cache.close()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Scrape Spier & Mackay for clearance items matching your criteria"
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't send notifications, just print matches",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Alias for running against live site (default behavior)",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Discover all available category/fit/size options from the site",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    # Load config
    try:
        config = Config.load(args.config)
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(1)

    # Run discovery or normal scrape
    if args.discover:
        exit_code = asyncio.run(run_discover(config))
    else:
        # Check for filters
        if not config.filters:
            print("Warning: No filters configured. Will match nothing.", file=sys.stderr)
        exit_code = asyncio.run(run_scraper(config, args.dry_run))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
