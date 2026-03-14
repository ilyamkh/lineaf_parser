"""Unit tests for Sonum scraper HTML extraction helpers."""

from decimal import Decimal

import pytest

from lineaf.scrapers.sonum import (
    extract_filler_from_description,
    parse_characteristics,
)
from lineaf.scrapers.utils import parse_price


class TestParseCharacteristics:
    """Tests for Russian label -> DB field mapping."""

    def test_full_characteristics_mapping(self):
        """Given typical Sonum characteristics rows, maps to correct DB fields."""
        rows = [
            ("Жесткость матраса", "Средняя"),
            ("Высота матраса", "22 см"),
            ("Материал чехла", "Жаккард"),
            ("Вес на 1 место", "15 кг"),
        ]
        result = parse_characteristics(rows)
        assert result == {
            "firmness": "Средняя",
            "height_cm": "22 см",
            "cover_material": "Жаккард",
            "weight_kg": "15 кг",
        }

    def test_short_label_variants(self):
        """Short label forms (without 'матраса') also map correctly."""
        rows = [
            ("Жесткость", "Жесткая"),
            ("Высота", "18 см"),
            ("Вес", "12 кг"),
        ]
        result = parse_characteristics(rows)
        assert result == {
            "firmness": "Жесткая",
            "height_cm": "18 см",
            "weight_kg": "12 кг",
        }

    def test_first_match_wins(self):
        """If both long and short label appear, first one takes priority."""
        rows = [
            ("Жесткость матраса", "Средняя"),
            ("Жесткость", "Жесткая"),
        ]
        result = parse_characteristics(rows)
        assert result["firmness"] == "Средняя"

    def test_missing_characteristics_returns_empty(self):
        """Given empty rows, returns empty dict — all optional fields will be None."""
        result = parse_characteristics([])
        assert result == {}

    def test_unknown_labels_ignored(self):
        """Rows with unrecognized labels are silently skipped."""
        rows = [
            ("Гарантия", "3 года"),
            ("Страна производства", "Россия"),
        ]
        result = parse_characteristics(rows)
        assert result == {}

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace in labels and values is stripped."""
        rows = [
            ("  Жесткость матраса  ", "  Средняя  "),
        ]
        result = parse_characteristics(rows)
        assert result["firmness"] == "Средняя"

    def test_empty_value_skipped(self):
        """Rows with empty values are not included."""
        rows = [
            ("Жесткость матраса", ""),
            ("Высота матраса", "  "),
        ]
        result = parse_characteristics(rows)
        assert result == {}


class TestExtractFillerFromDescription:
    """Tests for regex-based filler extraction from description text."""

    def test_filler_from_description(self):
        """Extracts filler material after 'Наполнитель:' label."""
        text = "Описание модели. Наполнитель: пена с эффектом памяти. Остальной текст."
        assert extract_filler_from_description(text) == "пена с эффектом памяти"

    def test_filler_lowercase(self):
        """Handles lowercase 'наполнитель' start."""
        text = "Характеристики: наполнитель: латекс и кокос. Прочее."
        assert extract_filler_from_description(text) == "латекс и кокос"

    def test_filler_with_space_separator(self):
        """Handles space instead of colon after 'Наполнитель'."""
        text = "Наполнитель пенополиуретан. Другие данные."
        assert extract_filler_from_description(text) == "пенополиуретан"

    def test_filler_not_found(self):
        """Returns None when description has no filler mention."""
        text = "Отличный матрас для всей семьи. Высокое качество."
        assert extract_filler_from_description(text) is None

    def test_filler_empty_text(self):
        """Returns None for empty text."""
        assert extract_filler_from_description("") is None

    def test_filler_none_text(self):
        """Returns None for None input."""
        assert extract_filler_from_description(None) is None


class TestSonumPriceParsing:
    """Tests for parse_price with Sonum-style price formats."""

    def test_sonum_price_with_ruble_sign(self):
        """Sonum uses space-separated thousands with ruble sign."""
        assert parse_price("15 990 ₽") == Decimal("15990")

    def test_sonum_price_large(self):
        """Handles larger prices with multiple space groups."""
        assert parse_price("125 490 ₽") == Decimal("125490")

    def test_sonum_price_no_spaces(self):
        """Price without spaces also parses correctly."""
        assert parse_price("9990₽") == Decimal("9990")

    def test_sonum_price_with_rub_text(self):
        """Price with 'руб.' suffix."""
        assert parse_price("15 990 руб.") == Decimal("15990")

    def test_sonum_price_none(self):
        """None input returns None."""
        assert parse_price(None) is None

    def test_sonum_price_empty(self):
        """Empty string returns None."""
        assert parse_price("") is None


@pytest.mark.integration
@pytest.mark.skip(reason="Requires live internet and Camoufox browser")
class TestSonumIntegration:
    """Integration test stubs for live Sonum scraping."""

    def test_sonum_catalog_urls(self):
        """Verify catalog pagination returns product URLs from sonum.ru."""
        pass
