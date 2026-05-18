import threading, time
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)

class _BufferManager:
    def __init__(self):
        self.buffer_level_s: float = 0.0
        self.buffer_can_play: bool = False
        self.rebuffer_event: bool = False
        self.stall_duration_s: float = 0.0
        self._t0: float = time.monotonic()
        self._t: float = 0.0
        self._lock = threading.Lock()
        self._plt_buffer = []
        self._plt_tempo = []
        self._plt_rebuffer_t = []
        self._plt_rebuffer_buffer = []
        self._stop_event = threading.Event()

        self._thread = threading.Thread(target=self._consumir, daemon=True)
        self._thread.start()

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

    def reset(self):
        with self._lock:
            self.buffer_level_s = 0.0
            self.buffer_can_play = False
            self.rebuffer_event = False
            self.stall_duration_s = 0.0
            self._t0: float = time.monotonic()
            self._t: float = 0.0
            self._plt_buffer.clear()
            self._plt_tempo.clear()
            self._plt_rebuffer_t.clear()
            self._plt_rebuffer_buffer.clear()

    def adicionar(self, valor):
        with self._lock:
            self.buffer_level_s += valor

    def plot(self, no_figure=False):
        with self._lock:
            tempo = list(self._plt_tempo)
            buffer_level = list(self._plt_buffer)
            rebuffer_t = list(self._plt_rebuffer_t)
            rebuffer_buffer = list(self._plt_rebuffer_buffer)
        if not tempo:
            return
        if not no_figure:
            plt.figure(figsize=(10, 5))
        plt.plot(tempo, buffer_level)
        plt.ylim(0, max(buffer_level, default=0) + 1)
        if rebuffer_t:
            plt.plot(
                rebuffer_t,
                rebuffer_buffer,
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
        self._thread.join()

    def _consumir(self):
        while not self._stop_event.is_set():
            dt = 0.1
            self._t = time.monotonic() - self._t0
            time.sleep(dt)

            with self._lock:
                if self.buffer_level_s > 0:
                    self.buffer_level_s = max(0.0, self.buffer_level_s - dt)
                    self.buffer_can_play = True
                    self.rebuffer_event = False
                    self.stall_duration_s = 0.0
                else:
                    self.buffer_can_play = False
                    self.rebuffer_event = True
                    self.stall_duration_s += dt

                self._plt_tempo.append(self._t)
                self._plt_buffer.append(self.buffer_level_s)
                if self.rebuffer_event:
                    self._plt_rebuffer_t.append(self._t)
                    self._plt_rebuffer_buffer.append(self.buffer_level_s)


buffer = _BufferManager()
