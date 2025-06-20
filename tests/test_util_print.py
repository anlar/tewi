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

from src.tewi.util.print import print_size, print_speed, print_time


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
