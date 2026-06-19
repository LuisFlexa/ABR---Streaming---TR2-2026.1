import logging
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR
from buffer_manager import buffer

logger = logging.getLogger(__name__)


class BufferRateBasedABR(PoliticaABR):
    """Política ABR Buffer-Rate-Based.

    Combina as abordagens Buffer-Based e Rate-Based: seleciona a maior representação cujo bitrate seja inferior à vazão média recente multiplicada por um fator de segurança, mas apenas se o nível de buffer estiver acima de uma reserva mínima. Se o buffer estiver baixo, prioriza a continuidade escolhendo a menor qualidade, mesmo que a vazão estimada permita algo melhor. Sem histórico, inicia pela menor qualidade (slow-start conservador).
    """

    def __init__(
        self,
        representacoes: list[Representation],
        reserva_s: float = 4.0,
        cheio_s: float = 15.0,
        janela: int = 5,
        fator_seguranca: float = 0.9,
    ):
        super().__init__(representacoes)
        if cheio_s <= reserva_s:
            raise ValueError("cheio_s deve ser maior que reserva_s")
        self.reserva_s: float = reserva_s
        self.cheio_s: float = cheio_s
        self.janela: int = janela
        self.fator_seguranca: float = fator_seguranca

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
            recentes = historico[-self.janela:]
            vazao_media = sum(s.vazao_kbps for s in recentes) / len(recentes)
            vazao_estimada = vazao_media * self.fator_seguranca

            escolha = menor
            for rep in self.representacoes:
                if rep.bitrate_kbps <= vazao_estimada:
                    escolha = rep
                else:
                    break
            zona = f"buffer={nivel:.2f}s, vazão={vazao_estimada:.2f}kbps"
        
        logger.debug(
            "Buffer-Rate-Based: nível_buffer=%.2f s (reserva=%.2f s, cheio=%.2f s), zona=%s, escolha=%s (%d kbps)",
            nivel,
            self.reserva_s,
            self.cheio_s,
            zona,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha
