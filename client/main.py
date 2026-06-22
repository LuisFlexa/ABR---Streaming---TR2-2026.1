from requests import RequestException

from manifest import Status, get_manifesto
import argparse
import logging
import time
from network_meter import get_segmento, info_rede
from buffer_manager import buffer
from politica import BufferBasedABR, RateBasedABR, EWMAHibridaABR
import matplotlib.pyplot as plt
import csv

# Parâmetros de simulação do player (controle de continuous play).
NUM_SEGMENTOS = 20  # quantos segmentos baixar na sessão
BUFFER_MAX_S = 30  # teto do buffer: nunca acumula mais que isso
BUFFER_TARGET_S = 15  # nível-alvo: acima dele, pace no ritmo do playback

# Políticas ABR disponíveis (P1, P2, P3). O CSV é nomeado pela classe.
POLITICAS = {
    "rate": RateBasedABR,  # P1 baseline
    "buffer": BufferBasedABR,  # P2 buffer-based
    "hibrida": EWMAHibridaABR,  # P3 híbrida (EWMA + jitter + buffer)
}

parser = argparse.ArgumentParser(description="Cliente de streaming adaptativo (ABR).")
parser.add_argument(
    "--politica",
    choices=POLITICAS.keys(),
    default="hibrida",
    help="Política ABR: rate (P1), buffer (P2) ou hibrida (P3).",
)
args = parser.parse_args()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s (%(name)s) - %(message)s", level=logging.DEBUG
)
for h in logging.getLogger().handlers:
    h.formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
    h.formatter.default_msec_format = "%s.%06d"

logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

manifest = get_manifesto()

logger.debug("Manifest recebido: %s", manifest)
logger.debug("Manifest version: %s", manifest.version)
logger.debug("Segment duration (s): %s", manifest.segment_duration_s)
logger.debug("Available servers:")
for server in manifest.servers:
    logger.debug("  - %s: %s", server.id, server.url)
logger.debug("Available representations:")
for rep in manifest.representations:
    logger.debug(
        "  - %s kbps, %s bytes, URL: %s",
        rep.bitrate_kbps,
        rep.segment_bytes,
        rep.url_path,
    )

politica = POLITICAS[args.politica](manifest.representations)
logger.info("Política ABR selecionada: %s (%s)", args.politica, politica.__class__.__name__)

buffer.iniciar()
buffer.limite_max_s = BUFFER_MAX_S

with open(
    "metricas_streaming_{}.csv".format(politica.__class__.__name__), mode="w", newline=""
) as csvfile:
    csvwriter = csv.writer(csvfile)

    csvwriter.writerow(
        [
            "segment",
            "timestamp",
            "server_id",
            "quality",
            "bitrate_kbps",
            "vazão_kbps",
            "download_time_s",
            "variação de atraso (jitter)_network_ms",
            "variação de atraso (jitter)_ewma_ms",
            "buffer_level_s",
            "buffer_can_play",
            "rebuffer_event",
            "stall_duration_s",
            "failover_total",
        ]
    )

    i_servidor = 0
    servidor = manifest.servers[i_servidor]

    while (
        info_rede.indice_ultimo_segmento == None
        or info_rede.indice_ultimo_segmento < NUM_SEGMENTOS
    ):
        representacao = politica.selecionar(info_rede.segmentos)

        try:
            info_do_segmento = get_segmento(servidor, representacao)

            # Conteúdo novo entra no buffer (a thread do BufferManager já drenou
            # o buffer em tempo real durante o download). O teto BUFFER_MAX_S é
            # aplicado dentro de adicionar().
            buffer.adicionar(manifest.segment_duration_s)

            # buffer_can_play: há buffer suficiente para cobrir o próximo
            # download? Estimamos o próximo pelo tempo do segmento recém-baixado.
            buffer_can_play = buffer.buffer_level_s > info_do_segmento.download_time_s

            csvwriter.writerow(
                [
                    info_rede.indice_ultimo_segmento,
                    info_do_segmento.timestamp,
                    "B" if info_do_segmento.server_id == "srv-B" else "A",
                    info_do_segmento.quality,
                    info_do_segmento.bitrate_kbps,
                    f"{info_do_segmento.vazao_kbps:.3f}",
                    f"{info_do_segmento.download_time_s:.3f}",
                    f"{info_do_segmento.jitter_network_ms:.3f}",
                    f"{info_rede.jitter_ewma:.3f}",
                    f"{buffer.buffer_level_s:.3f}",
                    1 if buffer_can_play else 0,
                    1 if buffer.rebuffer_event else 0,
                    f"{buffer.stall_duration_s:.3f}",
                    info_rede.failover_total,
                ]
            )

            logger.info("Segmento %s salvo em CSV", info_rede.indice_ultimo_segmento)

            # Simula o consumo do player: espera o tempo que ele levaria para
            # reproduzir o segmento. Na fase de enchimento (buffer abaixo do
            # alvo) baixa o mais rápido possível; depois pace no ritmo real. A
            # thread do BufferManager drena o buffer durante esta espera.
            espera = max(
                0.0, manifest.segment_duration_s - info_do_segmento.download_time_s
            )
            if buffer.buffer_level_s < BUFFER_TARGET_S:
                espera = 0.0  # ainda enchendo o buffer até o alvo
            if espera > 0:
                logger.debug(
                    "Pacing playback: aguardando %.2fs (buffer=%.2fs)",
                    espera,
                    buffer.buffer_level_s,
                )
            time.sleep(espera)
        except RequestException as e:
            logger.error("Erro ao obter segmento. Tentando obter segmento do próximo servidor disponível...")

            # Envia o servidor com falha para o final da lista (dá última chance antes de marcar como DOWN)
            manifest.servers.append(manifest.servers.pop(i_servidor))

            for s in filter(
                lambda x: x.status != Status.DOWN,
                manifest.servers,
            ):
                logger.debug("Verificando saúde do servidor %s...", s.id)

                health = s.get_health()

                if health == Status.OK:
                    logger.info(
                        "Servidor %s está saudável. Retentando download...", s.id
                    )
                    i_servidor = (i_servidor + 1) % len(manifest.servers)
                    servidor = manifest.servers[i_servidor]
                    break
                else:
                    logger.warning("Servidor %s está indisponível.", s.id)

            if all(s.status == Status.DOWN for s in manifest.servers):
                logger.error("Todos os servidores estão indisponíveis. Encerrando.")
                break


buffer.encerrar()

plt.figure(figsize=(12, 8))
plt.subplot(2, 2, 1)
buffer.plot(no_figure=True)
plt.subplot(2, 2, 2)
info_rede.plot_vazao(no_figure=True)
plt.subplot(2, 2, 3)
info_rede.plot_qualidade(no_figure=True)
plt.subplot(2, 2, 4)
info_rede.plot_jitter(no_figure=True)    
plt.savefig("metricas_streaming_{}.png".format(politica.__class__.__name__))
plt.show()
plt.close()
