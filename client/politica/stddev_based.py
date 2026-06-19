import logging
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR

logger = logging.getLogger(__name__)


class StdDevBasedABR(PoliticaABR):
    """Política ABR StdDev-Based.

    Seleciona a maior representação cujo bitrate seja inferior à vazão média recente menos k vezes o desvio padrão das vazões recentes. Sem histórico, inicia pela menor qualidade (slow-start conservador).
    """

    def __init__(
        self,
        representacoes: list[Representation],
        k: float = 1.0,
    ):
        super().__init__(representacoes)
        self.k: float = k
        self.vazao_media: float = 0.0
        self.desvio_padrao: float = 0.0

    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        if not historico:
            escolha = self.representacoes[0]
            logger.debug(
                "Sem histórico, iniciando pela menor qualidade: %s", escolha.quality
            )
            return escolha

        recentes = historico[
            -max(1, len(historico) // 2) :
        ]  # Considera os últimos 1/3 dos segmentos
        self.vazao_media = sum(s.vazao_kbps for s in recentes) / len(recentes)
        self.desvio_padrao = (
            sum((s.vazao_kbps - self.vazao_media) ** 2 for s in recentes)
            / len(recentes)
        ) ** 0.5
        vazao_estimada = self.vazao_media - self.k * self.desvio_padrao

        escolha = self.representacoes[0]
        for rep in self.representacoes:
            if rep.bitrate_kbps <= vazao_estimada:
                escolha = rep
            else:
                break

        logger.debug(
            "StdDev-Based: vazão_média=%.2f kbps, desvio_padrão=%.2f kbps (k=%.2f), estimada=%.2f kbps, escolha=%s (%d kbps)",
            self.vazao_media,
            self.desvio_padrao,
            self.k,
            vazao_estimada,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha
