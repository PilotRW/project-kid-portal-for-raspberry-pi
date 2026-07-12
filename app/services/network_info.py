import socket
from pydantic import BaseModel


class NetworkAddress(BaseModel):
    address: str
    portal_url: str
    ssh_target: str


class NetworkInfo(BaseModel):
    hostname: str
    port: int
    addresses: list[NetworkAddress]


class NetworkInfoService:
    def __init__(self, port: int = 8080) -> None:
        self.port = port

    def get_info(self) -> NetworkInfo:
        hostname = socket.gethostname()
        addresses = sorted(self._local_ipv4_addresses(hostname))
        if not addresses:
            addresses = ["127.0.0.1"]
        return NetworkInfo(
            hostname=hostname,
            port=self.port,
            addresses=[
                NetworkAddress(
                    address=address,
                    portal_url=f"http://{address}:{self.port}",
                    ssh_target=f"ssh pi@{address}",
                )
                for address in addresses
            ],
        )

    def _local_ipv4_addresses(self, hostname: str) -> set[str]:
        addresses: set[str] = set()
        primary = self._primary_ipv4()
        if primary:
            addresses.add(primary)

        try:
            for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
                address = item[4][0]
                if not address.startswith("127."):
                    addresses.add(address)
        except socket.gaierror:
            pass

        return addresses

    @staticmethod
    def _primary_ipv4() -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                address = sock.getsockname()[0]
                if not address.startswith("127."):
                    return address
        except OSError:
            return None
        return None
