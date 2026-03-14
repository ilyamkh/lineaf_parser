"""Unit tests for Askona JSON extraction logic + integration test stubs."""

from decimal import Decimal

import pytest

from lineaf.scrapers.askona import parse_askona_catalog_json, parse_askona_product_json


# ---------------------------------------------------------------------------
# Sample JSON fixtures mimicking Askona's __NEXT_DATA__ structure
# ---------------------------------------------------------------------------

CATALOG_JSON = {
    "props": {
        "pageProps": {
            "data": {
                "listing": {
                    "items": [
                        {
                            "type": "p",
                            "data": {
                                "productLink": "/matrasy/test-mattress.htm?SELECTED_HASH_SIZE=160x200-abc123",
                                "name": "Test Mattress",
                                "price": 25180,
                                "oldPrice": 35000,
                            },
                        },
                        {
                            "type": "p",
                            "data": {
                                "productLink": "/matrasy/comfort-plus.htm?SELECTED_HASH_SIZE=160x200-def456",
                                "name": "Comfort Plus",
                                "price": 18990,
                                "oldPrice": 0,
                            },
                        },
                        {
                            "type": "b",  # banner, not a product
                            "data": {
                                "productLink": "/promo/sale",
                                "name": "Banner Ad",
                            },
                        },
                    ]
                }
            }
        }
    }
}

PRODUCT_DETAIL_JSON = {
    "props": {
        "pageProps": {
            "productData": {
                "name": "Test Mattress Premium",
                "price": 25180,
                "oldPrice": 35000,
                "characteristics": [
                    {
                        "items": [
                            {"name": "Жесткость", "value": "Средняя"},
                            {"name": "Высота матраса", "value": "20 см"},
                            {"name": "Наполнитель", "value": "Пена"},
                            {"name": "Материал чехла", "value": "Хлопок"},
                            {"name": "Вес на спальное место, кг", "value": "15"},
                        ]
                    }
                ],
            }
        }
    }
}

PRODUCT_DETAIL_EMPTY_CHARS = {
    "props": {
        "pageProps": {
            "productData": {
                "name": "Basic Mattress",
                "price": 12000,
                "oldPrice": 15000,
                "characteristics": [],
            }
        }
    }
}

PRODUCT_DETAIL_ALT_FIELDS = {
    "props": {
        "pageProps": {
            "productData": {
                "name": "Alt Field Mattress",
                "price": 30000,
                "oldPrice": 40000,
                "characteristics": [
                    {
                        "items": [
                            {"name": "Жесткость", "value": "Жёсткий"},
                            {"name": "Высота матраса", "value": "25 см"},
                            {"name": "Наполнитель", "value": "Кокос"},
                            {"name": "Съемный чехол", "value": "Трикотаж"},
                            {"name": "Вес матраса", "value": "22"},
                        ]
                    }
                ],
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestAskonaCatalogParsing:
    """Tests for parse_askona_catalog_json."""

    def test_askona_catalog_urls_from_json(self):
        """Parse catalog JSON and get product URLs list."""
        urls = parse_askona_catalog_json(CATALOG_JSON)
        assert len(urls) == 2
        assert urls[0] == "https://www.askona.ru/matrasy/test-mattress.htm?SELECTED_HASH_SIZE=160x200-abc123"
        assert urls[1] == "https://www.askona.ru/matrasy/comfort-plus.htm?SELECTED_HASH_SIZE=160x200-def456"

    def test_askona_url_includes_size_hash(self):
        """Extracted URLs contain SELECTED_HASH_SIZE parameter."""
        urls = parse_askona_catalog_json(CATALOG_JSON)
        for url in urls:
            assert "SELECTED_HASH_SIZE=160x200" in url

    def test_askona_filters_non_product_items(self):
        """Catalog JSON with type='b' (banner) items are filtered out."""
        urls = parse_askona_catalog_json(CATALOG_JSON)
        # Original fixture has 3 items but only 2 are type="p"
        assert len(urls) == 2
        # No banner URL in results
        assert not any("/promo/" in u for u in urls)

    def test_askona_empty_catalog(self):
        """Empty items list returns empty URL list."""
        data = {"props": {"pageProps": {"data": {"listing": {"items": []}}}}}
        urls = parse_askona_catalog_json(data)
        assert urls == []


class TestAskonaProductParsing:
    """Tests for parse_askona_product_json."""

    def test_askona_product_fields_from_json(self):
        """Parse detail JSON and verify all fields are mapped correctly."""
        url = "https://www.askona.ru/matrasy/test.htm?SELECTED_HASH_SIZE=160x200-abc"
        result = parse_askona_product_json(PRODUCT_DETAIL_JSON, url)

        assert result["source_site"] == "askona"
        assert result["source_url"] == url
        assert result["name"] == "Test Mattress Premium"
        assert result["firmness"] == "Средняя"
        assert result["height_cm"] == "20 см"
        assert result["filler"] == "Пена"
        assert result["cover_material"] == "Хлопок"
        assert result["weight_kg"] == "15"

    def test_askona_prices_are_decimal(self):
        """Verify price_sale and price_original are Decimal type."""
        url = "https://www.askona.ru/matrasy/test.htm"
        result = parse_askona_product_json(PRODUCT_DETAIL_JSON, url)

        assert isinstance(result["price_sale"], Decimal)
        assert isinstance(result["price_original"], Decimal)
        assert result["price_sale"] == Decimal("25180")
        assert result["price_original"] == Decimal("35000")

    def test_askona_missing_characteristics(self):
        """Empty characteristics array -> all optional fields None, name and prices present."""
        url = "https://www.askona.ru/matrasy/basic.htm"
        result = parse_askona_product_json(PRODUCT_DETAIL_EMPTY_CHARS, url)

        assert result["name"] == "Basic Mattress"
        assert result["price_sale"] == Decimal("12000")
        assert result["price_original"] == Decimal("15000")
        # All optional fields should be None
        assert result["firmness"] is None
        assert result["height_cm"] is None
        assert result["filler"] is None
        assert result["cover_material"] is None
        assert result["weight_kg"] is None

    def test_askona_alternative_field_names(self):
        """Alternative Russian field names (Съемный чехол, Вес матраса) are mapped."""
        url = "https://www.askona.ru/matrasy/alt.htm"
        result = parse_askona_product_json(PRODUCT_DETAIL_ALT_FIELDS, url)

        assert result["cover_material"] == "Трикотаж"  # from "Съемный чехол"
        assert result["weight_kg"] == "22"  # from "Вес матраса"

    def test_askona_zero_old_price_is_none(self):
        """oldPrice of 0 should be treated as None (no original price)."""
        data = {
            "props": {
                "pageProps": {
                    "productData": {
                        "name": "No Discount",
                        "price": 10000,
                        "oldPrice": 0,
                        "characteristics": [],
                    }
                }
            }
        }
        url = "https://www.askona.ru/matrasy/nodiscount.htm"
        result = parse_askona_product_json(data, url)

        assert result["price_sale"] == Decimal("10000")
        assert result["price_original"] is None


# ---------------------------------------------------------------------------
# Integration test stubs (require Camoufox + internet)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skip(reason="requires Camoufox + internet")
def test_askona_catalog_urls():
    """Live test: scrape Askona catalog and verify product URLs are returned."""
    pass


@pytest.mark.integration
@pytest.mark.skip(reason="requires Camoufox + internet")
def test_camoufox_launches():
    """Smoke test: verify Camoufox browser launches without error."""
    pass
