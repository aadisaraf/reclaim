"""Contract tests for adapters/sftp.py against the real docker-compose mock-clearinghouse
container (atmoz/sftp). Skipped unless RECLAIM_DOCKER_TESTS=1 (see tests/conftest.py).
"""

import pytest

from reclaim.adapters.sftp import SftpClaimArchive, SftpRemitInbox
from reclaim.config import Settings

pytestmark = pytest.mark.docker


@pytest.fixture
def settings() -> Settings:
    return Settings(sftp_host="localhost", sftp_port=2222)


async def test_get_837_returns_fixture_bytes(settings, fixtures_dir):
    archive = SftpClaimArchive(settings)
    content = await archive.get_837("HSP-CLM-100028")
    assert content == (fixtures_dir / "x12" / "HSP-CLM-100028.837").read_bytes()


async def test_get_837_unknown_claim_returns_none(settings):
    archive = SftpClaimArchive(settings)
    assert await archive.get_837("HSP-CLM-000000") is None


async def test_deliver_list_download_roundtrip(settings):
    inbox = SftpRemitInbox(settings)
    await inbox.clear()
    await inbox.deliver("roundtrip-test.835", b"synthetic 835 bytes")

    files = await inbox.list_files()
    assert "roundtrip-test.835" in [f.name for f in files]

    content = await inbox.download("roundtrip-test.835")
    assert content == b"synthetic 835 bytes"

    await inbox.clear()
    assert await inbox.list_files() == []
