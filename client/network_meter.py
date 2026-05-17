from datetime import datetime
import time
import statistics
import requests
import logging
from manifest import Representation, Server

logger = logging.getLogger(__name__)


class InfoSegmento:
    def __init__(self, servidor: Server, representacao: Representation):
        self.servidor = servidor
        self.representacao = representacao

        self.timestamp = datetime.now().isoformat()

        self.server_id = servidor.id
        self.quality = self.representacao.quality
        self.bitrate_kbps = representacao.bitrate_kbps

        self.vazao_kbps = 0.0
        self.download_time_s = 0.0
        self.jitter_network_ms = 0.0

    def __str__(self):
        class_dict = {
            "timestamp": self.timestamp,
            "server_id": self.server_id,
            "quality": self.quality,
            "bitrate_kbps": self.bitrate_kbps,
            "vazao_kbps": self.vazao_kbps,
            "download_time_s": self.download_time_s,
            "jitter_network_ms": self.jitter_network_ms,
        }
        return str(class_dict)


def get_segmento(servidor: Server, representacao: Representation) -> InfoSegmento:
    info = InfoSegmento(servidor, representacao)
    url = f"{servidor.url}{representacao.url_path}"
    t_chunks_ms = []

    logger.debug(f"Medindo vazão para URL: {url}")

    try:
        t0 = time.time()
        resposta = requests.get(url, stream=True)
        resposta.raise_for_status()

        total_bytes = 0
        for chunk in resposta.iter_content(chunk_size=8192):
            if chunk:
                total_bytes += len(chunk)
                t_chunks_ms.append((time.time() - t0) * 1000)

        tf = time.time()
        info.jitter_network_ms = (
            statistics.mean(
                [
                    abs(t_chunks_ms[i] - t_chunks_ms[i + 1])
                    for i in range(len(t_chunks_ms) - 1)
                ]
            )
            if t_chunks_ms
            else 0.0
        )
        info.download_time_s = tf - t0
        info.vazao_kbps = (total_bytes * 8) / (info.download_time_s * 1000)

        logger.debug(
            f"Download completo: {total_bytes} bytes em {info.download_time_s:.2f} segundos, vazão: {info.vazao_kbps:.2f} kbps"
        )
    except Exception as e:
        logger.exception(f"Erro ao medir vazão: {e}")
        raise

    return info
