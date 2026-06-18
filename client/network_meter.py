from __future__ import annotations
from datetime import datetime, timedelta
import time
import statistics
import requests
import logging
from manifest import Representation, Server, Status
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

_t0 = time.monotonic()
_dt0 = datetime.now()

class InfoSegmento:
    def __init__(self, servidor: Server, representacao: Representation):
        self.servidor = servidor
        self.representacao = representacao


        self.timestamp = (
            _dt0 + timedelta(seconds=time.monotonic() - _t0)
        ).isoformat()

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


class _InfoNetwork:
    def __init__(self):
        self.indice_ultimo_segmento = None
        self.segmentos: list[InfoSegmento] = []
        self.jitter_ewma = 0.0
        self.failover_total = 0
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
            "failover_total": self.failover_total,
        }
        return __name__ + "\n" + "\n".join(f"{k}: {v}" for k, v in class_dict.items())

    def adicionar_segmento(self, info_segmento: InfoSegmento):
        troca_de_servidor = (
            len(self.segmentos) > 0
            and info_segmento.server_id != self.segmentos[-1].server_id
        )
        self.indice_ultimo_segmento = len(self.segmentos) + 1
        self.segmentos.append(info_segmento)
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
        if troca_de_servidor:
            self.failover_total += 1
            self._plt_troca_servidor.append(self.indice_ultimo_segmento)
        else:
            self._plt_troca_servidor.append(None)

    def plot_vazao(self, no_figure=False):
        self._plt_tempo = [t - self._plt_tempo[0] for t in self._plt_tempo]

        if not no_figure:
            plt.figure(figsize=(12, 8))

        plt.plot(self._plt_tempo, self._plt_vazao, marker="o")
        self._adicionar_troca_servidor_no_plot()
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
        self._adicionar_troca_servidor_no_plot()
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
        self._adicionar_troca_servidor_no_plot()
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

    def _adicionar_troca_servidor_no_plot(self):
        for idx in self._plt_troca_servidor:
            if idx is not None:
                servidor_id = self.segmentos[idx - 1].server_id
                t = self._plt_tempo[idx - 1]
                plt.axvline(x=t, color="red", linestyle="--", alpha=0.5)
                plt.text(
                    t + 0.01 * (self._plt_tempo[-1] - self._plt_tempo[0]),
                    plt.ylim()[1] * 0.95,
                    f"Troca para o servidor {servidor_id}",
                    rotation=90,
                    verticalalignment="top",
                    color="red",
                    fontsize=10,
                    alpha=0.8,
                )


def get_segmento(servidor: Server, representacao: Representation) -> InfoSegmento:
    info = InfoSegmento(servidor, representacao)
    url = f"{servidor.url}{representacao.url_path}"
    t_chunks_ms = []

    logger.debug("Medindo vazão para URL: %s", url)

    try:
        resposta = requests.get(url, stream=True)
        resposta.raise_for_status()

        # MOCK PARA SIMULAR FALHA!!!
        if (
            info_rede.indice_ultimo_segmento == 4
            or info_rede.indice_ultimo_segmento == 21
        ) and servidor.id == "A":
            # Simula falha de download para testar failover
            raise requests.exceptions.Timeout("Simulated download failure for testing.")
        elif (
            info_rede.indice_ultimo_segmento == 7
            or info_rede.indice_ultimo_segmento == 26
        ) and servidor.id == "srv-B":
            # Simula falha de download para testar failover
            raise requests.exceptions.ConnectionError(
                "Simulated connection error for testing."
            )

        t0 = time.monotonic()

        total_bytes = 0
        for chunk in resposta.iter_content(chunk_size=8192):
            if chunk:
                total_bytes += len(chunk)
                t_chunks_ms.append((time.monotonic() - t0) * 1000)

        tf = time.monotonic()
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
            "Download completo: %s bytes em %.2f segundos, vazão: %.2f kbps",
            total_bytes,
            info.download_time_s,
            info.vazao_kbps,
        )
    except Exception as e:
        logger.exception("Erro ao medir vazão: %s", e)
        servidor.status = Status.UNKNOWN
        raise

    info_rede.adicionar_segmento(info)

    return info


info_rede = _InfoNetwork()
