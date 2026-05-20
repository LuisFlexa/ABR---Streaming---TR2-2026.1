from manifest import get_manifesto
import logging
from network_meter import get_segmento, info_rede
from buffer_manager import buffer
from politica import RateBasedABR
import matplotlib.pyplot as plt
import csv

logging.basicConfig(
    format="%(asctime)s - %(levelname)s (%(name)s) - %(message)s", 
    level=logging.DEBUG
)
for h in logging.getLogger().handlers:
    h.formatter.default_time_format = '%Y-%m-%dT%H:%M:%S'
    h.formatter.default_msec_format = '%s.%06d'

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

buffer.reset()

with open("metricas_streaming.csv",mode="w",newline="") as csvfile:
    csvwriter = csv.writer(csvfile)

    csvwriter.writerow([
        "segment", "timestamp", "server_id", "quality", "bitrate_kbps",
        "vazão_kbps", "download_time_s", "variação de atraso (jitter)_network_ms",
        "variação de atraso (jitter)_ewma_ms", "buffer_level_s", "buffer_can_play",
        "rebuffer_event", "stall_duration_s", "failover_total"
    ])
    
    politica = RateBasedABR(manifest.representations)
    servidor = manifest.servers[0]
    
    for i in range(10):
        representacao = politica.selecionar(info_rede.segmentos)
        info_do_segmento = get_segmento(servidor, representacao)

        buffer.adicionar(manifest.segment_duration_s)

        csvwriter.writerow([
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
            1 if buffer.buffer_can_play else 0,
            1 if buffer.rebuffer_event else 0,
            f"{buffer.stall_duration_s:.3f}",
            info_rede.failover_total
        ])

        logger.info("Segmento %s salvo em CSV",info_rede.indice_ultimo_segmento)

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
plt.show()
