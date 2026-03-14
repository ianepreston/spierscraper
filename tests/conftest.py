"""Pytest configuration and fixtures."""

import pytest

from spierscraper.config import CategoryFilter, Config


@pytest.fixture
def sample_config() -> Config:
    """Sample configuration for testing."""
    return Config(
        filters={
            "pants": CategoryFilter(fits=["Contemporary", "Slim"], sizes=["33", "34"]),
            "chinos": CategoryFilter(fits=["Contemporary"], sizes=["33", "34"]),
        },
        discord_webhook_url="https://discord.com/api/webhooks/test/test",
        rate_limit_seconds=0.1,  # Fast for tests
    )


@pytest.fixture
def sample_products_html() -> str:
    """Sample HTML for product listing."""
    return """
    <html>
    <body>
        <div class="product-card" data-product-id="123">
            <a href="/product/brown-chino-ry-3038-chn-01-ss22">
                <h3 class="product-name">Brown Chino</h3>
            </a>
            <span class="sale-price">$24.99</span>
            <span class="original-price">$68.00</span>
        </div>
        <div class="product-card" data-product-id="456">
            <a href="/product/navy-trousers-abc-123">
                <h3 class="product-name">Navy Trousers</h3>
            </a>
            <span class="sale-price">$49.99</span>
            <span class="original-price">$120.00</span>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_product_page_html() -> str:
    """Sample HTML for product detail page."""
    return """
    <html>
    <body>
        <div data-option-name="fit">
            <button>Extra Slim</button>
            <button>Slim</button>
            <button>Contemporary</button>
        </div>
        <div data-option-name="size">
            <button>30</button>
            <button>31</button>
            <button>32</button>
            <button>33</button>
            <button>34</button>
        </div>
        <span class="sku">RY-3038-CHN-01-SS22</span>
    </body>
    </html>
    """
