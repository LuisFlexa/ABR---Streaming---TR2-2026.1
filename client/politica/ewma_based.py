import logging
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR
from buffer_manager import buffer

logger = logging.getLogger(__name__)


class EWMABasedABR(PoliticaABR):
    """Política ABR EWMA-Based.

      Similar à Rate-Based, mas a vazão estimada é uma média móvel exponencial (EWMA) das vazões passadas, que dá mais peso às mais recentes. Isso torna a política mais responsiva a mudanças rápidas na banda, mas ainda suaviza as oscilações da vazão instantânea. O fator de suavização (alpha) controla o peso das observações passadas: alpha próximo de 1 torna a estimativa mais sensível, enquanto alpha próximo de 0 torna a estimativa mais estável.
    """

    def __init__(
        self,
        representacoes: list[Representation],
        max_buffer_s: float = 12.0,
        min_buffer_s: float = 4.0,
        alpha: float = 0.2,
    ):
        super().__init__(representacoes)
        self.min_buffer_s: float = min_buffer_s
        self.max_buffer_s: float = max_buffer_s
        self.alpha: float = alpha
        self.vazao_estimada: float = 0.0
        self.ultima_qualidade: Representation = self.representacoes[0]
        
    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        if not historico:
            self.ultima_escolha = self.representacoes[0]
            logger.debug(
                "Sem histórico, iniciando pela menor qualidade: %s", self.ultima_escolha.quality
            )
            return self.ultima_escolha
        
        if buffer.buffer_level_s <= self.min_buffer_s:
            self.ultima_escolha = (
                self.representacoes[
                    self.representacoes.index(self.ultima_qualidade) - 1
                ]
                if self.ultima_qualidade != self.representacoes[0]
                else self.representacoes[0]
            )
            return self.ultima_escolha
        elif buffer.buffer_level_s >= self.max_buffer_s:
            self.ultima_escolha = (
                self.representacoes[
                    self.representacoes.index(self.ultima_qualidade) + 1
                ]
                if self.ultima_qualidade != self.representacoes[-1]
                else self.representacoes[-1]
            )
            return self.ultima_escolha

        ultima_vazao = historico[-1].vazao_kbps
        self.vazao_estimada = (
            self.alpha * ultima_vazao + (1 - self.alpha) * self.vazao_estimada
        )

        self.ultima_escolha = self.representacoes[0]
        for rep in self.representacoes:
            if rep.bitrate_kbps <= self.vazao_estimada:
                self.ultima_escolha = rep
            else:
                break

        logger.debug(
            "EWMA-Based: última vazão=%.2f kbps, estimada=%.2f kbps (alpha=%.2f), self.ultima_escolha=%s (%d kbps)",
            ultima_vazao,
            self.vazao_estimada,
            self.alpha,
            self.ultima_escolha.quality,
            self.ultima_escolha.bitrate_kbps,
        )
        return self.ultima_escolha