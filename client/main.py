from manifest import get_manifesto
import logging
from network_meter import get_segmento

logging.basicConfig(level=logging.DEBUG)

manifest = get_manifesto()

print(f"Manifest recebido: {manifest}")
print(f"Manifest version: {manifest.version}")
print(f"Segment duration (s): {manifest.segment_duration_s}")
print("Available servers:")
for server in manifest.servers:
    print(f"  - {server.id}: {server.url}")
print("Available representations:")
for rep in manifest.representations:
    print(
        f"  - {rep.bitrate_kbps} kbps, {rep.segment_bytes} bytes, URL: {rep.url_path}"
    )

info_do_segmento = get_segmento(manifest.servers[0], manifest.representations[0])
print(info_do_segmento)
