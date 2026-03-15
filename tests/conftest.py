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
    """Sample HTML for product listing - matches actual site structure."""
    return """
    <html>
    <body>
        <div class="col-md-3 col-sm-4 col-xs-6 item-product">
            <a href="/product/brown-chino-ry-3038-chn-01-ss22">
                <div class="product-block">
                    <div class="product-info">
                        <div class="prod-name">Brown Chino</div>
                        <div class="prod-price">$24.99 CAD</div>
                        <div class="prod-price1">$68.00 CAD</div>
                    </div>
                </div>
            </a>
        </div>
        <div class="col-md-3 col-sm-4 col-xs-6 item-product">
            <a href="/product/navy-trousers-abc-123">
                <div class="product-block">
                    <div class="product-info">
                        <div class="prod-name">Navy Trousers</div>
                        <div class="prod-price">$49.99 CAD</div>
                        <div class="prod-price1">$120.00 CAD</div>
                    </div>
                </div>
            </a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_api_response() -> dict:
    """Sample JSON response from the collection API."""
    return {
        "status": True,
        "products": """
            <div class="col-md-3 col-sm-4 col-xs-6 item-product">
                <a href="/product/cream-birdseye-dress-shirt-11081-c7f5k">
                    <div class="product-block">
                        <div class="product-info">
                            <div class="prod-name">Cream Birdseye Dress Shirt - Final Sale</div>
                            <div class="prod-price">$24.99 CAD</div>
                            <div class="prod-price1">$68.00 CAD</div>
                        </div>
                    </div>
                </a>
            </div>
            <div class="col-md-3 col-sm-4 col-xs-6 item-product">
                <a href="/product/navy-stripe-trousers-ry-3456-tr-01">
                    <div class="product-block">
                        <div class="product-info">
                            <div class="prod-name">Navy Stripe Trousers</div>
                            <div class="prod-price">$49.99 CAD</div>
                            <div class="prod-price1">$148.00 CAD</div>
                        </div>
                    </div>
                </a>
            </div>
        """,
        "page_no": 2,
    }


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
