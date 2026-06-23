import logging
from manifest import Representation
from network_meter import InfoSegmento, info_rede
from politica.base import PoliticaABR
from buffer_manager import buffer

logger = logging.getLogger(__name__)


class JitterBasedABR(PoliticaABR):
    """Política ABR Buffer-Based com penalidade por jitter.

    Estende o BBA-0 (Buffer-Based) incorporando o jitter como penalidade
    no nível efetivo do buffer:

        buffer_efetivo = max(0, buffer_nivel - jitter_ewma * fator_penalidade / 1000)

    Quando o jitter é alto, o buffer efetivo reduz, adiando subidas de
    qualidade e protegendo contra rebuffering. Quando o jitter é baixo,
    a penalidade é desprezível e o comportamento converge para o BBA-0
    puro.
    """

    def __init__(
        self,
        representacoes: list[Representation],
        reserva_s: float = 4.0,
        cheio_s: float = 12.0,
        fator_penalidade: float = 10.0,
    ):
        super().__init__(representacoes)
        if cheio_s <= reserva_s:
            raise ValueError("cheio_s deve ser maior que reserva_s")
        self.reserva_s = reserva_s
        self.cheio_s = cheio_s
        self.fator_penalidade = fator_penalidade

    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        nivel = buffer.buffer_level_s
        jitter = historico[-1].jitter_network_ms if historico else 0.0

        penalidade = jitter * self.fator_penalidade / 1000.0
        nivel_efetivo = max(0.0, nivel - penalidade)

        menor = self.representacoes[0]
        maior = self.representacoes[-1]

        if nivel_efetivo <= self.reserva_s:
            escolha = menor
            zona = "reserva"
        elif nivel_efetivo >= self.cheio_s:
            escolha = maior
            zona = "cheio"
        else:
            fracao = (nivel_efetivo - self.reserva_s) / (self.cheio_s - self.reserva_s)
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
            "Jitter-Based: nível=%.2fs, jitter_ewma=%.2fms, "
            "nível_efetivo=%.2fs (reserva=%.1fs, cheio=%.1fs), "
            "zona=%s, escolha=%s (%d kbps)",
            nivel,
            jitter,
            nivel_efetivo,
            self.reserva_s,
            self.cheio_s,
            zona,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha