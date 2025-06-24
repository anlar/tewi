# Tewi - Text-based interface for the Transmission BitTorrent daemon
# Copyright (C) 2024  Anton Larionov
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import math
from datetime import datetime, timedelta
from src.tewi.util.print import print_size, print_speed, print_ratio, print_time, print_time_ago


class TestPrintSize:
    """Test cases for print_size function."""

    def test_bytes(self):
        """Test formatting of byte values."""
        assert print_size(0) == "0 B"
        assert print_size(1) == "1 B"
        assert print_size(999) == "999 B"

    def test_kilobytes(self):
        """Test formatting of kilobyte values."""
        assert print_size(1000) == "1 kB"
        assert print_size(1500) == "1.5 kB"
        assert print_size(999999) == "1000 kB"

    def test_megabytes(self):
        """Test formatting of megabyte values."""
        assert print_size(1000000) == "1 MB"
        assert print_size(1500000) == "1.5 MB"
        assert print_size(999999999) == "1000 MB"

    def test_gigabytes(self):
        """Test formatting of gigabyte values."""
        assert print_size(1000000000) == "1 GB"
        assert print_size(1500000000) == "1.5 GB"

    def test_terabytes(self):
        """Test formatting of terabyte values."""
        assert print_size(1000000000000) == "1 TB"
        assert print_size(1500000000000) == "1.5 TB"

    def test_negative_values(self):
        """Test formatting of negative values."""
        assert print_size(-1000) == "-1 kB"
        assert print_size(-1500000) == "-1.5 MB"

    def test_custom_suffix(self):
        """Test formatting with custom suffix."""
        assert print_size(1000, suffix="iB") == "1 kiB"
        assert print_size(1000000, suffix="iB") == "1 MiB"

    def test_custom_size_bytes(self):
        """Test formatting with custom size_bytes (binary)."""
        assert print_size(1024, size_bytes=1024) == "1 kB"
        assert print_size(1048576, size_bytes=1024) == "1 MB"

    def test_decimal_rounding(self):
        """Test decimal rounding and trailing zero removal."""
        assert print_size(1100) == "1.1 kB"
        assert print_size(1000) == "1 kB"  # Should strip .00
        assert print_size(1001) == "1 kB"  # Should round to 1.00 then strip


class TestPrintRatio:
    """Test cases for print_ratio function."""

    def test_normal_ratios(self):
        """Test formatting of normal ratio values."""
        assert print_ratio(0.0) == "0.00"
        assert print_ratio(0.5) == "0.50"
        assert print_ratio(1.0) == "1.00"
        assert print_ratio(1.5) == "1.50"
        assert print_ratio(2.0) == "2.00"
        assert print_ratio(10.0) == "10.00"

    def test_high_precision_ratios(self):
        """Test formatting of high precision ratio values."""
        assert print_ratio(1.234) == "1.23"
        assert print_ratio(1.235) == "1.24"  # Should round up
        assert print_ratio(1.999) == "2.00"
        assert print_ratio(0.001) == "0.00"
        assert print_ratio(0.005) == "0.01"  # Should round up

    def test_negative_ratios(self):
        """Test formatting of negative ratio values."""
        assert print_ratio(-1.0) == "-1.00"
        assert print_ratio(-0.5) == "-0.50"
        assert print_ratio(-1.234) == "-1.23"

    def test_infinite_ratio(self):
        """Test formatting of infinite ratio values."""
        assert print_ratio(math.inf) == "∞"
        assert print_ratio(-math.inf) == "∞"  # Both positive and negative infinity should show ∞

    def test_very_large_ratios(self):
        """Test formatting of very large ratio values."""
        assert print_ratio(999.99) == "999.99"
        assert print_ratio(1000.0) == "1000.00"
        assert print_ratio(9999.999) == "10000.00"

    def test_very_small_ratios(self):
        """Test formatting of very small ratio values."""
        assert print_ratio(0.001) == "0.00"
        assert print_ratio(0.004) == "0.00"
        assert print_ratio(0.005) == "0.01"
        assert print_ratio(0.009) == "0.01"

    def test_edge_cases(self):
        """Test edge cases and special values."""
        # Test NaN (though it may not be expected in normal usage)
        nan_result = print_ratio(float('nan'))
        assert 'nan' in nan_result.lower() or nan_result == "nan"

        # Test zero variations
        assert print_ratio(0.0) == "0.00"
        assert print_ratio(-0.0) == "0.00"


class TestPrintSpeed:
    """Test cases for print_speed function."""

    def test_bytes_per_second(self):
        """Test formatting of bytes per second."""
        assert print_speed(0) == "0 B"
        assert print_speed(1) == "1 B"
        assert print_speed(999) == "999 B"

    def test_kilobytes_per_second(self):
        """Test formatting of kilobytes per second."""
        assert print_speed(1000) == "1 KB"
        assert print_speed(1500) == "2 KB"

    def test_megabytes_per_second(self):
        """Test formatting of megabytes per second."""
        assert print_speed(1000000) == "1 MB"
        assert print_speed(1500000) == "1.5 MB"

    def test_with_seconds_suffix(self):
        """Test formatting with /s suffix."""
        assert print_speed(1000, print_secs=True) == "1 KB/s"
        assert print_speed(1500000, print_secs=True) == "1.5 MB/s"
        assert print_speed(0, print_secs=True) == "0 B/s"

    def test_custom_suffix(self):
        """Test formatting with custom suffix."""
        assert print_speed(1000, suffix="iB") == "1 KiB"
        assert print_speed(1000, suffix="iB", print_secs=True) == "1 KiB/s"

    def test_custom_speed_bytes(self):
        """Test formatting with custom speed_bytes."""
        assert print_speed(1024, speed_bytes=1024) == "1 KB"
        assert print_speed(1048576, speed_bytes=1024) == "1 MB"

    def test_negative_values(self):
        """Test formatting of negative values."""
        assert print_speed(-1000) == "-1 KB"
        assert print_speed(-1500000, print_secs=True) == "-1.5 MB/s"

    def test_precision_rounding(self):
        """Test precision rounding for different units."""
        # Bytes and KB should have 0 decimal places
        assert print_speed(999) == "999 B"
        assert print_speed(1100) == "1 KB"  # Should round to 1.1 then to 1

        # MB and above should have 2 decimal places
        assert print_speed(1100000) == "1.1 MB"
        assert print_speed(1000000) == "1 MB"  # Should strip .00


class TestPrintTime:
    """Test cases for print_time function."""

    def test_seconds_only(self):
        """Test formatting of seconds only."""
        assert print_time(0) == ""
        assert print_time(1) == "1 second"
        assert print_time(30) == "30 seconds"
        assert print_time(59) == "59 seconds"

    def test_minutes_only(self):
        """Test formatting of minutes only."""
        assert print_time(60) == "1 minute"
        assert print_time(120) == "2 minutes"
        assert print_time(3540) == "59 minutes"

    def test_hours_only(self):
        """Test formatting of hours only."""
        assert print_time(3600) == "1 hour"
        assert print_time(7200) == "2 hours"
        assert print_time(82800) == "23 hours"

    def test_days_only(self):
        """Test formatting of days only."""
        assert print_time(86400) == "1 day"
        assert print_time(172800) == "2 days"

    def test_mixed_units(self):
        """Test formatting of mixed time units."""
        assert print_time(61) == "1 minute"
        assert print_time(3661) == "1 hour"
        assert print_time(90061) == "1 day"
        assert print_time(90121) == "1 day"

    def test_abbreviated_format(self):
        """Test abbreviated time format."""
        assert print_time(61, abbr=True) == "1m"
        assert print_time(3661, abbr=True) == "1h"
        assert print_time(90061, abbr=True) == "1d"
        assert print_time(90121, abbr=True) == "1d"

    def test_multiple_units(self):
        """Test formatting with multiple units."""
        assert print_time(90181, units=1) == "1 day"
        assert print_time(90181, units=2) == "1 day, 1 hour"
        assert print_time(90181, units=3) == "1 day, 1 hour, 3 minutes"
        assert print_time(90181, units=4) == "1 day, 1 hour, 3 minutes, 1 second"

    def test_abbreviated_multiple_units(self):
        """Test abbreviated format with multiple units."""
        assert print_time(3661, abbr=True, units=2) == "1h, 1m"
        assert print_time(90121, abbr=True, units=2) == "1d, 1h"
        assert print_time(90181, abbr=True, units=3) == "1d, 1h, 3m"

    def test_edge_cases(self):
        """Test edge cases."""
        # Large values
        assert print_time(31536000) == "365 days"  # 1 year

        # Exact boundaries
        assert print_time(86400) == "1 day"
        assert print_time(86401) == "1 day"  # Should only show days with units=1

        # Zero
        assert print_time(0) == ""

    def test_units_limit(self):
        """Test that units parameter limits the number of time units shown."""
        complex_time = 90182  # 1 day, 1 hour, 3 minutes, 2 seconds

        assert print_time(complex_time, units=1) == "1 day"
        assert print_time(complex_time, units=2) == "1 day, 1 hour"
        assert print_time(complex_time, units=3) == "1 day, 1 hour, 3 minutes"
        assert print_time(complex_time, units=4) == "1 day, 1 hour, 3 minutes, 2 seconds"


class TestPrintTimeAgo:
    """Test cases for print_time_ago function."""

    def test_none_input(self):
        """Test handling of None input."""
        assert print_time_ago(None) == ""

    def test_just_now(self):
        """Test formatting for very recent times."""
        now = datetime.now()
        recent = now - timedelta(seconds=30)
        assert print_time_ago(recent) == "just now"

        # Test edge case - exactly at boundary
        almost_minute = now - timedelta(seconds=59)
        assert print_time_ago(almost_minute) == "just now"

    def test_minutes_ago(self):
        """Test formatting for minutes ago."""
        now = datetime.now()

        one_minute = now - timedelta(minutes=1)
        assert print_time_ago(one_minute) == "1 minute ago"

        two_minutes = now - timedelta(minutes=2)
        assert print_time_ago(two_minutes) == "2 minutes ago"

        fifty_nine_minutes = now - timedelta(minutes=59)
        assert print_time_ago(fifty_nine_minutes) == "59 minutes ago"

    def test_hours_ago(self):
        """Test formatting for hours ago."""
        now = datetime.now()

        one_hour = now - timedelta(hours=1)
        assert print_time_ago(one_hour) == "1 hour ago"

        two_hours = now - timedelta(hours=2)
        assert print_time_ago(two_hours) == "2 hours ago"

        twenty_three_hours = now - timedelta(hours=23)
        assert print_time_ago(twenty_three_hours) == "23 hours ago"

    def test_days_ago(self):
        """Test formatting for days ago."""
        now = datetime.now()

        one_day = now - timedelta(days=1)
        assert print_time_ago(one_day) == "1 day ago"

        two_days = now - timedelta(days=2)
        assert print_time_ago(two_days) == "2 days ago"

        six_days = now - timedelta(days=6)
        assert print_time_ago(six_days) == "6 days ago"

    def test_weeks_ago(self):
        """Test formatting for weeks ago."""
        now = datetime.now()

        one_week = now - timedelta(weeks=1)
        assert print_time_ago(one_week) == "1 week ago"

        two_weeks = now - timedelta(weeks=2)
        assert print_time_ago(two_weeks) == "2 weeks ago"

        three_weeks = now - timedelta(weeks=3)
        assert print_time_ago(three_weeks) == "3 weeks ago"

    def test_months_ago(self):
        """Test formatting for months ago."""
        now = datetime.now()

        one_month = now - timedelta(days=30)
        assert print_time_ago(one_month) == "1 month ago"

        two_months = now - timedelta(days=60)
        assert print_time_ago(two_months) == "2 months ago"

        eleven_months = now - timedelta(days=330)
        assert print_time_ago(eleven_months) == "11 months ago"

    def test_years_ago(self):
        """Test formatting for years ago."""
        now = datetime.now()

        one_year = now - timedelta(days=365)
        assert print_time_ago(one_year) == "1 year ago"

        two_years = now - timedelta(days=730)
        assert print_time_ago(two_years) == "2 years ago"

        five_years = now - timedelta(days=1825)
        assert print_time_ago(five_years) == "5 years ago"

    def test_timezone_aware_datetime(self):
        """Test handling of timezone-aware datetime objects."""
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)
        one_hour_ago_utc = now_utc - timedelta(hours=1)

        # Should handle timezone-aware datetime by converting to naive
        result = print_time_ago(one_hour_ago_utc)
        assert "ago" in result  # Should return some valid time ago string

    def test_boundary_conditions(self):
        """Test boundary conditions between different time units."""
        now = datetime.now()

        # Exactly 1 minute
        exactly_minute = now - timedelta(seconds=60)
        assert print_time_ago(exactly_minute) == "1 minute ago"

        # Exactly 1 hour
        exactly_hour = now - timedelta(seconds=3600)
        assert print_time_ago(exactly_hour) == "1 hour ago"

        # Exactly 1 day
        exactly_day = now - timedelta(seconds=86400)
        assert print_time_ago(exactly_day) == "1 day ago"

        # Exactly 1 week
        exactly_week = now - timedelta(seconds=604800)
        assert print_time_ago(exactly_week) == "1 week ago"

    def test_singular_vs_plural(self):
        """Test correct singular vs plural forms."""
        now = datetime.now()

        # Singular forms
        assert "1 minute ago" == print_time_ago(now - timedelta(minutes=1))
        assert "1 hour ago" == print_time_ago(now - timedelta(hours=1))
        assert "1 day ago" == print_time_ago(now - timedelta(days=1))
        assert "1 week ago" == print_time_ago(now - timedelta(weeks=1))
        assert "1 month ago" == print_time_ago(now - timedelta(days=30))
        assert "1 year ago" == print_time_ago(now - timedelta(days=365))

        # Plural forms
        assert "2 minutes ago" == print_time_ago(now - timedelta(minutes=2))
        assert "2 hours ago" == print_time_ago(now - timedelta(hours=2))
        assert "2 days ago" == print_time_ago(now - timedelta(days=2))
        assert "2 weeks ago" == print_time_ago(now - timedelta(weeks=2))
        assert "2 months ago" == print_time_ago(now - timedelta(days=60))
        assert "2 years ago" == print_time_ago(now - timedelta(days=730))
