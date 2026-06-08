import requests
from dotenv import load_dotenv
import os
import logging

load_dotenv()
server_url = os.getenv("SERVER_URL")
fallback_url = os.getenv("FALLBACK_URL")

logger = logging.getLogger(__name__)


class Status:
    OK = "ok"
    DOWN = "down"
    UNKNOWN = "unknown"


class Server:
    def __init__(self, data: dict):
        self.id: str = data["id"]
        self.url: str = data["url"]
        self.priority: int = data["priority"]
        self.bandwidth_kbps: int = data["bandwidth_kbps"]
        self.jitter_ms: int = data["jitter_ms"]
        self.status: Status = Status.UNKNOWN

    def get_health(self) -> Status:
        try:
            response = requests.get(self.url + "/health", timeout=5)
            response.raise_for_status()
            health_status = response.json().get("status")
            if health_status == "ok":
                self.status = Status.OK
            else:
                self.status = Status.DOWN
        except requests.RequestException:
            self.status = Status.DOWN
        return self.status


class Representation:
    def __init__(self, data: dict):
        self.quality: str = data["quality"]
        self.bitrate_kbps: int = data["bitrate_kbps"]
        self.segment_bytes: int = data["segment_bytes"]
        self.url_path: str = data["url_path"]


class Manifesto:

    def __init__(self, data: dict):
        self._raw: dict = data
        self.version: str = data["version"]
        self.segment_duration_s: int = data["segment_duration_s"]
        self.servers: list[Server] = [
            Server(s) for s in sorted(data["servers"], key=lambda s: s["priority"])
        ]
        self.representations: list[Representation] = [
            Representation(r) for r in data["representations"]
        ]

    def __str__(self) -> str:
        return self._raw.__str__()


def _get_url_manifesto() -> str | None:
    if consultar_health_do_servidor(server_url):
        return server_url + "/manifest"
    else:
        logger.debug("Servidor principal inacessível. Tentando fallback...")

        if consultar_health_do_servidor(fallback_url):
            return fallback_url + "/manifest"
        else:
            logger.debug("Servidor fallback também inacessível.")
            return None


def consultar_health_do_servidor(url: str) -> bool:
    try:
        response = requests.get(url + "/health", timeout=5)
        response.raise_for_status()
        return response.json().get("status") == "ok"
    except requests.RequestException:
        logger.debug("Servidor %s inacessível ou com health check DOWN.", url)
        return False


def get_manifesto() -> Manifesto:
    manifest_url = _get_url_manifesto()

    if manifest_url is None:
        raise RuntimeError("Nenhum servidor acessível para obter o manifesto.")

    response = requests.get(manifest_url)
    response.raise_for_status()

    manifesto = Manifesto(response.json())
    return manifesto
