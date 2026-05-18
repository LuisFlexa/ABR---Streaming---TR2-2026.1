from manifest import get_manifesto
import logging
from network_meter import get_segmento, info_rede
from buffer_manager import buffer
from random import randint
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.DEBUG)

logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

manifest = get_manifesto()

logger.debug(f"Manifest recebido: {manifest}")
logger.debug(f"Manifest version: {manifest.version}")
logger.debug(f"Segment duration (s): {manifest.segment_duration_s}")
logger.debug("Available servers:")
for server in manifest.servers:
    logger.debug(f"  - {server.id}: {server.url}")
logger.debug("Available representations:")
for rep in manifest.representations:
    logger.debug(
        f"  - {rep.bitrate_kbps} kbps, {rep.segment_bytes} bytes, URL: {rep.url_path}"
    )

buffer.reset()

for i in range(10):
    info_do_segmento = get_segmento(
        manifest.servers[0],
        manifest.representations[randint(0, len(manifest.representations) - 1)],
    )

    buffer.adicionar(manifest.segment_duration_s)
    
    logger.debug(info_do_segmento)
    logger.debug(buffer)

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
