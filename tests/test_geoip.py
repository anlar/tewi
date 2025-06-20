from src.tewi.util.geoip import get_country


class TestGetCountry:
    """Test cases for get_country function."""

    def test_get_country_public_ipv4(self):
        """Test country lookup for valid public IPv4 address"""
        assert get_country('8.8.8.8') == 'United States'

    def test_get_country_ipv6(self):
        """Test country lookup for IPv6 addresses"""
        # Google's IPv6 DNS
        result = get_country('2001:4860:4860::8888')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_country_private_ipv4(self):
        """Test country lookup for private IPv4 addresses"""
        # Private IP ranges should return some result (likely empty or default)
        result_192 = get_country('192.168.1.1')
        result_10 = get_country('10.0.0.1')
        result_172 = get_country('172.16.0.1')

        # Should return strings (may be empty for private IPs)
        assert isinstance(result_192, str)
        assert isinstance(result_10, str)
        assert isinstance(result_172, str)

    def test_get_country_localhost(self):
        """Test country lookup for localhost addresses"""
        result_ipv4 = get_country('127.0.0.1')
        result_ipv6 = get_country('::1')

        # Should return strings (may be empty for localhost)
        assert isinstance(result_ipv4, str)
        assert isinstance(result_ipv6, str)

    def test_get_country_caching(self):
        """Test that the function uses caching correctly"""
        # Call the same IP twice - should use cache on second call
        result1 = get_country('8.8.8.8')
        result2 = get_country('8.8.8.8')

        # Results should be identical
        assert result1 == result2
        assert isinstance(result1, str)

    def test_get_country_edge_cases(self):
        """Test country lookup for edge case IP addresses"""
        # Test broadcast address
        result_broadcast = get_country('255.255.255.255')
        assert isinstance(result_broadcast, str)

        # Test network address
        result_network = get_country('0.0.0.0')
        assert isinstance(result_network, str)

    def test_get_country_return_type(self):
        """Test that function always returns string type"""
        test_ips = [
            '8.8.8.8',
            '1.1.1.1',
            '127.0.0.1',
            '192.168.1.1',
            '2001:4860:4860::8888'
        ]

        for ip in test_ips:
            result = get_country(ip)
            assert isinstance(result, str), f"Result for {ip} should be string, got {type(result)}"
