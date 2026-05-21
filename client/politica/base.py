from abc import ABC, abstractmethod
from manifest import Representation
from network_meter import InfoSegmento


class PoliticaABR(ABC):
    """Interface base para algoritmos ABR (Adaptive Bitrate)."""

    def __init__(self, representacoes: list[Representation]):
        self.representacoes: list[Representation] = sorted(
            representacoes, key=lambda r: r.bitrate_kbps
        )

    @abstractmethod
    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        """Retorna a representação a ser baixada para o próximo segmento."""
        ...
