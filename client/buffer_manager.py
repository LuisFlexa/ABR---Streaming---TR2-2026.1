import threading, time
import matplotlib.pyplot as plt
import logging

_BUFFER_DT = 0.05
logger = logging.getLogger(__name__)


class _BufferManager:
    def __init__(self, dt: float = 0.1):
        self.buffer_level_s: float = 0.0
        self.buffer_can_play: bool = False
        self.rebuffer_event: bool = False
        self.stall_duration_s: float = 0.0
        self._dt: float = dt
        self._t0: float = time.monotonic()
        self._t: float = 0.0
        self._plt_buffer = []
        self._plt_tempo = []
        self._plt_rebuffer = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self._thread = threading.Thread(target=self._consumir, daemon=True)

    def __str__(self):
        with self._lock:
            class_dict = {
                "buffer_level_s": self.buffer_level_s,
                "buffer_can_play": self.buffer_can_play,
                "rebuffer_event": self.rebuffer_event,
                "stall_duration_s": self.stall_duration_s,
            }
            return (
                __name__ + "\n" + "\n".join(f"{k}: {v}" for k, v in class_dict.items())
            )

    def _reset(self):
        with self._lock:
            self.buffer_level_s = 0.0
            self.buffer_can_play = False
            self.rebuffer_event = False
            self.stall_duration_s = 0.0
            self._t0: float = time.monotonic()
            self._t: float = 0.0
            self._plt_buffer.clear()
            self._plt_tempo.clear()
            self._plt_rebuffer.clear()

    def iniciar(self):
        self._reset()
        self._stop_event.clear()
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._consumir, daemon=True)
            self._thread.start()

    def adicionar(self, valor):
        with self._lock:
            self.buffer_level_s += valor

    def plot(self, no_figure=False):
        with self._lock:
            tempo = list(self._plt_tempo)
            buffer_level = list(self._plt_buffer)
            rebuffer_t = list(self._plt_rebuffer)
        if not tempo:
            return
        if not no_figure:
            plt.figure(figsize=(10, 5))
        plt.plot(tempo, buffer_level)
        plt.ylim(0, max(buffer_level, default=0) + 1)
        if rebuffer_t:
            plt.plot(
                rebuffer_t,
                [0] * len(rebuffer_t),
                marker="x",
                linestyle="",
                color="red",
            )
        plt.xlabel("Tempo (s)")
        plt.ylabel("Nível de buffer (s)")
        plt.title("Nível de buffer ao longo do tempo")
        plt.legend(["Nível de buffer", "Rebuffering"])
        plt.grid()

        if not no_figure:
            plt.show()

    def encerrar(self):
        self._stop_event.set()

    def _consumir(self):
        while not self._stop_event.is_set():
            self._t = time.monotonic() - self._t0
            time.sleep(self._dt)

            with self._lock:
                if self.buffer_level_s > 0:
                    if int(self._t) != int(self._t - self._dt):
                        logger.debug(
                            "Consumindo buffer: nível=%fs", self.buffer_level_s
                        )
                    self.buffer_level_s = max(0.0, self.buffer_level_s - self._dt)
                    self.buffer_can_play = True
                    self.rebuffer_event = False
                    self.stall_duration_s = 0.0
                else:
                    if int(self._t) != int(self._t - self._dt):
                        logger.debug(
                            "Buffer vazio: tempo_parado=%fs", self.stall_duration_s
                        )
                    self.buffer_can_play = False
                    if any(
                        self._plt_buffer
                    ):  # Evita consierar rebuffer no primeiro segmento
                        self.rebuffer_event = True
                    self.stall_duration_s += self._dt

                self._plt_tempo.append(self._t)
                self._plt_buffer.append(self.buffer_level_s)
                if self.rebuffer_event:
                    self._plt_rebuffer.append(self._t)


buffer = _BufferManager(dt=_BUFFER_DT)
