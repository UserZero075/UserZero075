from datetime import date, timedelta
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_activity import CalendarParser, render


def calendar_html(count=365):
    start = date(2025, 11, 16)
    return "".join(
        f'<td id="day-{index}" data-date="{start + timedelta(days=index)}" '
        f'data-level="{index % 5}"></td>'
        f'<tool-tip for="day-{index}">{index % 5} contributions on a date.</tool-tip>'
        for index in range(count)
    )


class CalendarTests(unittest.TestCase):
    def test_complete_calendar_is_sorted(self):
        parser = CalendarParser()
        parser.feed(calendar_html())
        days = parser.days()
        self.assertEqual(len(days), 365)
        self.assertEqual(days[0], (date(2025, 11, 16), 0, 0))
        self.assertEqual(days[-1][0], date(2026, 11, 15))

    def test_accessible_tooltip_count_formats(self):
        parser = CalendarParser()
        parser.feed(
            '<tool-tip for="zero">No contributions on a date.</tool-tip>'
            '<tool-tip for="one">1 contribution on a date.</tool-tip>'
            '<tool-tip for="many"><span>1,234 contributions</span> on a date.</tool-tip>'
        )
        self.assertEqual(parser.counts, {"zero": 0, "one": 1, "many": 1234})

    def test_partial_calendar_fails_instead_of_publishing_zeroes(self):
        parser = CalendarParser()
        parser.feed(calendar_html(10))
        with self.assertRaises(ValueError):
            parser.days()

    def test_missing_tooltip_fails(self):
        parser = CalendarParser()
        parser.feed(calendar_html())
        del parser.counts["day-2"]
        with self.assertRaises(ValueError):
            parser.days()

    def test_unknown_intensity_fails(self):
        parser = CalendarParser()
        parser.feed(calendar_html().replace('data-level="4"', 'data-level="5"', 1))
        with self.assertRaises(ValueError):
            parser.days()

    def test_svg_is_valid_escapes_text_and_excludes_forks_from_language_counts(self):
        parser = CalendarParser()
        parser.feed(calendar_html())
        repos = [
            {"fork": False, "stargazers_count": 7, "language": "Python"},
            {"fork": False, "stargazers_count": 1, "language": "A&B"},
            {"fork": False, "stargazers_count": 0, "language": None},
            {"fork": True, "stargazers_count": 99, "language": "ForkOnly"},
        ]
        svg = render(parser.days(), repos)
        root = ElementTree.fromstring(svg)
        content = " ".join(root.itertext())
        self.assertIn("4 repositorios públicos y 8 estrellas", content)
        self.assertIn("Python 1", content)
        self.assertIn("A&amp;B", svg)
        self.assertNotIn("ForkOnly", svg)
        self.assertEqual(svg.count(" contribuciones</title>"), 365)


if __name__ == "__main__":
    unittest.main()
