"""Unit tests for Ormatek scraper extraction helpers."""

from decimal import Decimal

import pytest

from lineaf.scrapers.ormatek import (
    parse_characteristics,
    OrmatemScraper,
)
from lineaf.scrapers.utils import parse_price


class TestOrmatemFieldMapping:
    """Tests for Russian label -> DB field mapping."""

    def test_full_characteristics_mapping(self):
        """Given typical Ormatek characteristics rows, maps to correct DB fields."""
        rows = [
            ("Жесткость", "Средняя"),
            ("Высота матраса", "22 см"),
            ("Наполнитель", "Латекс"),
            ("Материал чехла", "Жаккард"),
            ("Вес на спальное место", "15 кг"),
        ]
        result = parse_characteristics(rows)
        assert result == {
            "firmness": "Средняя",
            "height_cm": "22 см",
            "filler": "Латекс",
            "cover_material": "Жаккард",
            "weight_kg": "15 кг",
        }

    def test_alternative_label_variants(self):
        """Alternative Russian labels (Жёсткость with yo, Чехол) also map."""
        rows = [
            ("Жёсткость", "Жесткая"),
            ("Высота", "18 см"),
            ("Чехол", "Трикотаж"),
            ("Вес на 1 место", "12 кг"),
        ]
        result = parse_characteristics(rows)
        assert result == {
            "firmness": "Жесткая",
            "height_cm": "18 см",
            "cover_material": "Трикотаж",
            "weight_kg": "12 кг",
        }

    def test_first_match_wins(self):
        """If both specific and generic labels appear, first takes priority."""
        rows = [
            ("Высота матраса", "20 см"),
            ("Высота", "25 см"),
        ]
        result = parse_characteristics(rows)
        assert result["height_cm"] == "20 см"

    def test_missing_characteristics_returns_empty(self):
        """Empty rows returns empty dict -- all optional fields will be None."""
        result = parse_characteristics([])
        assert result == {}

    def test_unknown_labels_ignored(self):
        """Rows with unrecognized labels are silently skipped."""
        rows = [
            ("Гарантия", "3 года"),
            ("Нагрузка", "120 кг"),
        ]
        result = parse_characteristics(rows)
        assert result == {}

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace in labels and values is stripped."""
        rows = [
            ("  Жесткость  ", "  Средняя  "),
        ]
        result = parse_characteristics(rows)
        assert result["firmness"] == "Средняя"

    def test_empty_value_skipped(self):
        """Rows with empty values are not included."""
        rows = [
            ("Жесткость", ""),
            ("Высота", "  "),
        ]
        result = parse_characteristics(rows)
        assert result == {}

    def test_level_firmness_label(self):
        """'Уровень жесткости' label maps to firmness."""
        rows = [("Уровень жесткости", "Высокая")]
        result = parse_characteristics(rows)
        assert result["firmness"] == "Высокая"


class TestOrmatemPriceParsing:
    """Tests for parse_price with Ormatek-style price formats."""

    def test_price_with_ruble_sign(self):
        """Space-separated thousands with ruble sign."""
        assert parse_price("25 180 ₽") == Decimal("25180")

    def test_price_large(self):
        """Handles larger prices with multiple space groups."""
        assert parse_price("125 490 ₽") == Decimal("125490")

    def test_price_no_spaces(self):
        """Price without spaces also parses correctly."""
        assert parse_price("9990₽") == Decimal("9990")

    def test_price_with_rub_text(self):
        """Price with 'руб.' suffix."""
        assert parse_price("25 180 руб.") == Decimal("25180")

    def test_price_none(self):
        """None input returns None."""
        assert parse_price(None) is None

    def test_price_empty(self):
        """Empty string returns None."""
        assert parse_price("") is None


class TestOrmatemMissingFields:
    """Tests for handling missing optional fields."""

    def test_partial_characteristics(self):
        """Only some fields present -- missing ones not in result."""
        rows = [
            ("Жесткость", "Мягкая"),
        ]
        result = parse_characteristics(rows)
        assert result == {"firmness": "Мягкая"}
        assert "height_cm" not in result
        assert "filler" not in result

    def test_scraper_instance(self):
        """OrmatemScraper initializes with correct site_name and catalog_url."""
        s = OrmatemScraper()
        assert s.site_name == "ormatek"
        assert s.catalog_url == "https://www.ormatek.com/catalog/matrasy/160x200/"


@pytest.mark.integration
@pytest.mark.skip(reason="Requires live internet and Camoufox browser; ormatek.com returns 403 from datacenter IPs")
class TestOrmatemIntegration:
    """Integration test stubs for live Ormatek scraping."""

    def test_ormatek_catalog_urls(self):
        """Verify catalog pagination returns product URLs from ormatek.com."""
        pass
