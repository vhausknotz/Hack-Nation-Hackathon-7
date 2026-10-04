"""Organization page fetching never reaches private, local or cloud-metadata addresses."""
import pytest

from atlas_mcp.page_fetch import org_id, public_url


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://localhost/admin", "http://169.254.169.254/metadata/instance",
                                 "http://10.0.0.5/", "http://192.168.1.1/", "http://[::1]/", "file:///etc/passwd",
                                 "ftp://example.org/", "https://user:pw@example.org/", "https://8.8.8.8:8443/", "http://0.0.0.0/"])
def test_private_or_unsafe_addresses_are_refused(url):
    with pytest.raises(ValueError):
        public_url(url)


def test_public_ip_literal_is_allowed():
    assert public_url("https://8.8.8.8/") == "https://8.8.8.8/"


def test_organization_ids_follow_the_homepage():
    assert org_id("https://www.umdf.org/what-is-mitochondrial-disease/") == "org:umdf-org"
    assert org_id("mitoaction.org") == "org:mitoaction-org"
