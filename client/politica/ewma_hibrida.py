import logging
import statistics
from buffer_manager import buffer
from manifest import Representation
from network_meter import InfoSegmento
from politica.base import PoliticaABR

logger = logging.getLogger(__name__)


class EWMAHibridaABR(PoliticaABR):
    """Política ABR 3 — híbrida (EWMA de vazão + desvio-padrão + penalidade de
    jitter + arbitragem por buffer).

    Motivação (deficiências das políticas anteriores):
      - A Rate-Based (P1) reage à vazão instantânea -> oscila e dá overshoot.
      - A Buffer-Based (P2) ignora a vazão -> pode demorar a reagir a quedas
        de banda enquanto o buffer ainda está cheio, e não trata jitter.

    Esta política combina três componentes:

    1. Estimativa estatística da vazão (EWMA + desvio-padrão).
       A vazão é estimada por uma média móvel exponencial (a vazão recente
       pesa mais que o passado distante), e dela subtraímos k desvios-padrão.
       Quanto mais instável a rede (maior dispersão), mais conservadora fica a
       estimativa -- o que ataca diretamente a oscilação do baseline.

           vazao_ewma = α·vazão_t + (1-α)·vazao_ewma_{t-1}
           est_base   = vazao_ewma − k_std · σ(vazões recentes)

    2. Penalidade de jitter (trata explicitamente o cenário de jitter alto).
       O jitter (variação no tempo de entrega) indica entrega irregular dos
       segmentos: mesmo com vazão média boa, picos de atraso esvaziam o buffer
       entre chegadas. Penalizamos a estimativa proporcionalmente ao jitter
       recente (EWMA do jitter), reduzindo a qualidade-alvo quando a rede está
       "nervosa":

           jitter_norm   = jitter_ewma_ms / JITTER_REF_MS
           fator_jitter  = 1 / (1 + k_jit · jitter_norm)   ∈ (0, 1]
           est           = est_base · fator_jitter

       Com JITTER_REF_MS=100 e k_jit=1: jitter 100ms -> fator 0.5 (corta a
       estimativa pela metade); jitter ~30ms (rede calma) -> fator ~0.77.

    3. Arbitragem por buffer (componente híbrido com a P2).
       O nível do buffer modula o quão agressiva é a decisão:
         - buffer < RESERVA  -> emergência: menor qualidade, proteja a
           continuidade independentemente da vazão estimada.
         - buffer > FOLGA    -> confortável: dispensa a margem de σ (o buffer
           absorve erro), permitindo arriscar qualidade maior.
         - caso contrário    -> normal: usa a estimativa conservadora completa.

    Referências: EWMA para estimativa de banda (p.ex. throughput predictor do
    DASH); margem média−k·σ é estimador conservador clássico; a arbitragem por
    buffer segue a ideia do BBA (Huang et al., 2014).
    """

    def __init__(
        self,
        representacoes: list[Representation],
        alpha: float = 0.4,
        janela_std: int = 5,
        k_std: float = 1.0,
        k_jit: float = 1.0,
        jitter_ref_ms: float = 100.0,
        reserva_s: float = 4.0,
        folga_s: float = 12.0,
    ):
        super().__init__(representacoes)
        self.alpha: float = alpha
        self.janela_std: int = janela_std
        self.k_std: float = k_std
        self.k_jit: float = k_jit
        self.jitter_ref_ms: float = jitter_ref_ms
        self.reserva_s: float = reserva_s
        self.folga_s: float = folga_s

    def _ewma(self, valores: list[float]) -> float:
        ewma = valores[0]
        for v in valores[1:]:
            ewma = self.alpha * v + (1 - self.alpha) * ewma
        return ewma

    def _maior_rep_ate(self, limite_kbps: float) -> Representation:
        escolha = self.representacoes[0]
        for rep in self.representacoes:
            if rep.bitrate_kbps <= limite_kbps:
                escolha = rep
            else:
                break
        return escolha

    def selecionar(self, historico: list[InfoSegmento]) -> Representation:
        if not historico:
            escolha = self.representacoes[0]
            logger.debug("Sem histórico, slow-start na menor qualidade: %s", escolha.quality)
            return escolha

        nivel = buffer.buffer_level_s

        # Emergência: buffer abaixo da reserva -> protege a continuidade.
        if nivel < self.reserva_s:
            escolha = self.representacoes[0]
            logger.debug(
                "Híbrida: buffer=%.2fs < reserva=%.1fs -> emergência, menor qualidade (%s)",
                nivel,
                self.reserva_s,
                escolha.quality,
            )
            return escolha

        # 1) Estimativa estatística da vazão (EWMA + desvio-padrão).
        vazoes = [s.vazao_kbps for s in historico]
        vazao_ewma = self._ewma(vazoes)
        recentes = vazoes[-self.janela_std:]
        std = statistics.pstdev(recentes) if len(recentes) >= 2 else 0.0

        if nivel > self.folga_s:
            # Buffer confortável: o buffer absorve o erro, dispensa a margem σ.
            est_base = vazao_ewma
            modo = "confortável"
        else:
            # Normal: estimativa conservadora.
            est_base = vazao_ewma - self.k_std * std
            modo = "normal"

        # 2) Penalidade de jitter (trata jitter alto).
        jitters = [s.jitter_network_ms for s in historico]
        jitter_ewma = self._ewma(jitters)
        jitter_norm = jitter_ewma / self.jitter_ref_ms
        fator_jitter = 1.0 / (1.0 + self.k_jit * jitter_norm)

        est = max(0.0, est_base) * fator_jitter

        # 3) Seleciona a maior representação cujo bitrate caiba na estimativa.
        escolha = self._maior_rep_ate(est)

        logger.debug(
            "Híbrida [%s]: ewma=%.0f σ=%.0f -> base=%.0f | jitter_ewma=%.1fms fator=%.2f "
            "-> est=%.0f kbps | buffer=%.2fs -> %s (%d kbps)",
            modo,
            vazao_ewma,
            std,
            est_base,
            jitter_ewma,
            fator_jitter,
            est,
            nivel,
            escolha.quality,
            escolha.bitrate_kbps,
        )
        return escolha
