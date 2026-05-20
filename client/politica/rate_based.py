import logging
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR

logger = logging.getLogger(__name__)


class RateBasedABR(PoliticaABR):
    """Política ABR Rate-Based pura.

    Seleciona a maior representação cujo bitrate seja inferior à vazão
    média recente multiplicada por um fator de segurança. Sem histórico,
    inicia pela menor qualidade (slow-start conservador).
    """

    def __init__(
        self,
        representacoes: list[Representation],
        janela: int = 3,
        fator_seguranca: float = 0.9,
    ):
        super().__init__(representacoes)
        self.janela: int = janela
        self.fator_seguranca: float = fator_seguranca

    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        if not historico:
            escolha = self.representacoes[0]
            logger.debug(
                "Sem histórico, iniciando pela menor qualidade: %s", escolha.quality
            )
            return escolha

        recentes = historico[-self.janela:]
        vazao_media = sum(s.vazao_kbps for s in recentes) / len(recentes)
        vazao_estimada = vazao_media * self.fator_seguranca

        escolha = self.representacoes[0]
        for rep in self.representacoes:
            if rep.bitrate_kbps <= vazao_estimada:
                escolha = rep
            else:
                break

        logger.debug(
            "Rate-Based: vazão_média=%.2f kbps (janela=%d), estimada=%.2f kbps, escolha=%s (%d kbps)",
            vazao_media,
            len(recentes),
            vazao_estimada,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha
