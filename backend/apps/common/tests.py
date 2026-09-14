from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.test import SimpleTestCase
from django.utils import formats, timezone


class TimezoneDisplayTests(SimpleTestCase):
    def test_default_display_time_is_ist_with_an_explicit_suffix(self):
        utc_value = datetime(2026, 8, 31, 12, 0, tzinfo=datetime_timezone.utc)
        displayed = formats.date_format(timezone.localtime(utc_value), settings.DATETIME_FORMAT)

        self.assertEqual(settings.TIME_ZONE, "Asia/Kolkata")
        self.assertIn("5:30 PM", displayed)
        self.assertTrue(displayed.endswith("IST"))
