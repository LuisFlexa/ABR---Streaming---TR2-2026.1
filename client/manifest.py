import requests
from dotenv import load_dotenv
import os
import logging

load_dotenv()
server_url = os.getenv("SERVER_URL")
fallback_url = os.getenv("FALLBACK_URL")


class Server:
    def __init__(self, data: dict):
        self.id: str = data["id"]
        self.url: str = data["url"]
        self.priority: int = data["priority"]
        self.bandwidth_kbps: int = data["bandwidth_kbps"]
        self.jitter_ms: int = data["jitter_ms"]


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
        self.servers: list[Server] = [self.Server(s) for s in data["servers"]]
        self.representations: list[Representation] = [
            self.Representation(r) for r in data["representations"]
        ]

    def __str__(self) -> str:
        return self._raw.__str__()


def _get_url_manifesto() -> str | None:
    try:
        response = requests.get(server_url, timeout=5)
        response.raise_for_status()
        return server_url + "/manifest"
    except requests.RequestException:
        logging.debug("Servidor principal inacessível. Tentando fallback...")
        try:
            response = requests.get(fallback_url, timeout=5)
            response.raise_for_status()
            return fallback_url + "/manifest"
        except requests.RequestException:
            pass

    return None


def get_manifesto() -> Manifesto:
    manifest_url = _get_url_manifesto()

    if manifest_url is None:
        raise RuntimeError("Nenhum servidor acessível para obter o manifesto.")

    response = requests.get(manifest_url)
    response.raise_for_status()

    manifesto = Manifesto(response.json())
    return manifesto
