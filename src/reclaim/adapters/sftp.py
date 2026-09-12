"""Real: paramiko SFTP against the mock-clearinghouse container (docker-compose.yml).

The atmoz/sftp container chroots the `reclaim` user to /home/reclaim, so paths below are
relative to that chroot: `outbound/835/<name>` and `claim-archive/837/<hospitalClaimId>.837`.
"""

import asyncio
import stat

import paramiko

from reclaim.adapters.protocols import RemitFileRef
from reclaim.config import Settings

OUTBOUND_835_DIR = "outbound/835"
CLAIM_ARCHIVE_DIR = "claim-archive/837"


def _connect(settings: Settings) -> paramiko.SFTPClient:
    transport = paramiko.Transport((settings.sftp_host, settings.sftp_port))
    transport.connect(username=settings.sftp_user, password=settings.sftp_password)
    return paramiko.SFTPClient.from_transport(transport)


class SftpRemitInbox:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def list_files(self) -> list[RemitFileRef]:
        return await asyncio.to_thread(self._list_files)

    def _list_files(self) -> list[RemitFileRef]:
        sftp = _connect(self.settings)
        try:
            return [
                RemitFileRef(name=entry.filename, size=entry.st_size, mtime=entry.st_mtime)
                for entry in sftp.listdir_attr(OUTBOUND_835_DIR)
                if stat.S_ISREG(entry.st_mode)
            ]
        finally:
            sftp.close()

    async def download(self, name: str) -> bytes:
        return await asyncio.to_thread(self._download, name)

    def _download(self, name: str) -> bytes:
        sftp = _connect(self.settings)
        try:
            with sftp.open(f"{OUTBOUND_835_DIR}/{name}", "rb") as f:
                return f.read()
        finally:
            sftp.close()

    async def deliver(self, name: str, content: bytes) -> None:
        await asyncio.to_thread(self._deliver, name, content)

    def _deliver(self, name: str, content: bytes) -> None:
        sftp = _connect(self.settings)
        try:
            with sftp.open(f"{OUTBOUND_835_DIR}/{name}", "wb") as f:
                f.write(content)
        finally:
            sftp.close()

    async def clear(self) -> None:
        await asyncio.to_thread(self._clear)

    def _clear(self) -> None:
        sftp = _connect(self.settings)
        try:
            for name in sftp.listdir(OUTBOUND_835_DIR):
                sftp.remove(f"{OUTBOUND_835_DIR}/{name}")
        finally:
            sftp.close()


class SftpClaimArchive:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def get_837(self, hospital_claim_id: str) -> bytes | None:
        return await asyncio.to_thread(self._get_837, hospital_claim_id)

    def _get_837(self, hospital_claim_id: str) -> bytes | None:
        sftp = _connect(self.settings)
        try:
            with sftp.open(f"{CLAIM_ARCHIVE_DIR}/{hospital_claim_id}.837", "rb") as f:
                return f.read()
        except FileNotFoundError:
            return None
        finally:
            sftp.close()
