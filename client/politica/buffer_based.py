import logging
from buffer_manager import buffer
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR

logger = logging.getLogger(__name__)


class BufferBasedABR(PoliticaABR):
    """Política ABR Buffer-Based (BBA-0).

    Decide a qualidade do próximo segmento a partir do NÍVEL DO BUFFER, e não
    diretamente da vazão medida. A motivação vem da deficiência do baseline
    Rate-Based: como ele reage à vazão instantânea, oscila em redes instáveis
    e não antecipa rebuffering quando a banda cai com o buffer já baixo.

    A função de mapeamento é a do BBA-0 (Huang et al., 2014, "A Buffer-Based
    Approach to Rate Adaptation", SIGCOMM):

      - buffer < reserva  -> menor qualidade (zona de reserva: protege contra
        rebuffering, prioriza continuidade)
      - buffer > cheio    -> maior qualidade (zona de folga: buffer cheio
        suporta o maior bitrate com segurança)
      - entre os dois     -> mapeamento linear do nível de buffer para um
        bitrate-alvo; escolhe a maior representação cujo bitrate caiba no alvo

    O nível de buffer é lido do BufferManager (singleton ``buffer``), que já é
    atualizado continuamente (+segment_duration por segmento recebido,
    -tempo_real a cada tick). Por isso ``historico`` não é necessário aqui.
    """

    def __init__(
        self,
        representacoes: list[Representation],
        reserva_s: float = 4.0,
        cheio_s: float = 12.0,
    ):
        super().__init__(representacoes)
        if cheio_s <= reserva_s:
            raise ValueError("cheio_s deve ser maior que reserva_s")
        self.reserva_s: float = reserva_s
        self.cheio_s: float = cheio_s

    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        nivel = buffer.buffer_level_s
        menor = self.representacoes[0]
        maior = self.representacoes[-1]

        if nivel <= self.reserva_s:
            escolha = menor
            zona = "reserva"
        elif nivel >= self.cheio_s:
            escolha = maior
            zona = "cheio"
        else:
            # Mapeamento linear: fração do buffer na faixa [reserva, cheio]
            # vira um bitrate-alvo na faixa [menor_bitrate, maior_bitrate].
            fracao = (nivel - self.reserva_s) / (self.cheio_s - self.reserva_s)
            bitrate_alvo = menor.bitrate_kbps + fracao * (
                maior.bitrate_kbps - menor.bitrate_kbps
            )
            escolha = menor
            for rep in self.representacoes:
                if rep.bitrate_kbps <= bitrate_alvo:
                    escolha = rep
                else:
                    break
            zona = f"linear (alvo={bitrate_alvo:.0f} kbps)"

        logger.debug(
            "Buffer-Based: nível=%.2fs (reserva=%.1fs, cheio=%.1fs), zona=%s, escolha=%s (%d kbps)",
            nivel,
            self.reserva_s,
            self.cheio_s,
            zona,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha
