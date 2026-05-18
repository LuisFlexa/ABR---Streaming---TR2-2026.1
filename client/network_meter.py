from datetime import datetime
import time
import statistics
import requests
import logging
from manifest import Representation, Server
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class _InfoNetwork:
    def __init__(self):
        self.segmentos: list[(int, InfoSegmento)] = []
        self.jitter_ewma = 0.0
        self._jitter_ewma_alpha: float = 0.1
        self._plt_tempo = []
        self._plt_vazao = []
        self._plt_qualidade = []
        self._plt_jitter = []
        self._plt_jitter_ewma = []
        self._plt_troca_servidor = []

    def __str__(self):
        class_dict = {
            "segmentos": self.segmentos,
            "jitter_ewma": self.jitter_ewma,
        }
        return __name__ + "\n" + "\n".join(f"{k}: {v}" for k, v in class_dict.items())

    def adicionar_segmento(self, info_segmento: InfoSegmento):
        self.segmentos.append((len(self.segmentos) + 1, info_segmento))
        self.jitter_ewma = (
            self._jitter_ewma_alpha * info_segmento.jitter_network_ms
            + (1 - self._jitter_ewma_alpha) * self.jitter_ewma
        )  # https://github.com/jonnieZG/EWMA: output = alpha * reading + (1 - alpha) * lastOutput
        self._plt_jitter_ewma.append(self.jitter_ewma)
        self._plt_tempo.append(
            datetime.fromisoformat(info_segmento.timestamp).timestamp()
        )
        self._plt_vazao.append(info_segmento.vazao_kbps)
        self._plt_qualidade.append(int(info_segmento.quality.rstrip("p")))
        self._plt_jitter.append(info_segmento.jitter_network_ms)
        if (
            len(self.segmentos) > 1
            and info_segmento.server_id != self.segmentos[-2][1].server_id
        ):
            self._plt_troca_servidor.append(
                (len(self.segmentos) - 1, info_segmento.server_id)
            )

    def plot_vazao(self, no_figure=False):
        self._plt_tempo = [t - self._plt_tempo[0] for t in self._plt_tempo]

        if not no_figure:
            plt.figure(figsize=(12, 8))

        plt.plot(self._plt_tempo, self._plt_vazao, marker="o")
        plt.title("Vazão ao longo do tempo")
        plt.xlabel("Tempo")
        plt.ylabel("Vazão (kbps)")
        plt.grid()
        plt.tight_layout()

        if not no_figure:
            plt.show()

    def plot_jitter(self, no_figure=False):
        self._plt_tempo = [t - self._plt_tempo[0] for t in self._plt_tempo]

        if not no_figure:
            plt.figure(figsize=(12, 8))

        plt.plot(self._plt_tempo, self._plt_jitter, marker="o", label="Jitter")
        plt.plot(
            self._plt_tempo, self._plt_jitter_ewma, marker="x", label="EWMA Jitter"
        )
        plt.title("Jitter ao longo do tempo")
        plt.xlabel("Tempo")
        plt.ylabel("Jitter (ms)")
        plt.grid()
        plt.legend()
        plt.tight_layout()

        if not no_figure:
            plt.show()

    def plot_qualidade(self, no_figure=False):
        self._plt_tempo = [t - self._plt_tempo[0] for t in self._plt_tempo]

        if not no_figure:
            plt.figure(figsize=(12, 8))

        plt.plot(self._plt_tempo, self._plt_qualidade, marker="o")
        plt.yticks(
            sorted(set(self._plt_qualidade)),
            labels=[f"{q}p" for q in sorted(set(self._plt_qualidade))],
        )
        plt.title("Qualidade ao longo do tempo")
        plt.xlabel("Tempo")
        plt.ylabel("Qualidade")
        plt.grid()
        plt.tight_layout()

        if not no_figure:
            plt.show()


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
        return __name__ + "\n" + "\n".join(f"{k}: {v}" for k, v in class_dict.items())


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

    info_rede.adicionar_segmento(info)

    return info


info_rede = _InfoNetwork()
