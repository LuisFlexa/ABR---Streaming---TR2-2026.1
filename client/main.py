from manifest import get_manifesto
import logging
from network_meter import get_segmento, info_rede
from buffer_manager import buffer
from random import randint
import matplotlib.pyplot as plt
import locale

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

for i in range(10):
    info_do_segmento = get_segmento(
        manifest.servers[0 if i < 5 else 1],
        manifest.representations[randint(0, len(manifest.representations) - 1)],
    )

    buffer.adicionar(manifest.segment_duration_s)

    # testando se dados para csv estão disponíveis
    logger.info("Segmento: %s", info_rede.indice_ultimo_segmento)
    logger.info("Timestamp: %s", info_do_segmento.timestamp)
    logger.info("Server ID: %s", info_do_segmento.server_id)
    logger.info("Quality: %s", info_do_segmento.quality)
    logger.info("Bitrate (kbps): %.3f", info_do_segmento.bitrate_kbps)
    logger.info("Vazão (kbps): %.3f", info_do_segmento.vazao_kbps)
    logger.info("Download time (s): %.3f", info_do_segmento.download_time_s)
    logger.info("Jitter (ms): %.3f", info_do_segmento.jitter_network_ms)
    logger.info("Jitter EWMA (ms): %.3f", info_rede.jitter_ewma)
    logger.info("Buffer level (s): %.3f", buffer.buffer_level_s)
    logger.info("Buffer can play: %s", buffer.buffer_can_play)
    logger.info("Rebuffer event: %s", buffer.rebuffer_event)
    logger.info("Stall duration: %.3f", buffer.stall_duration_s)
    logger.info("Failover total: %s", info_rede.failover_total)

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
