import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import config


class LivePlot:
    """Affichage temps-réel de la phase respiratoire et du rythme estimé."""

    def __init__(self):
        n_points = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
        self._phase_buf = collections.deque([0.0] * n_points, maxlen=n_points)
        self._rate_history = collections.deque(maxlen=20)
        self._time  = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

        self._fig, (self._ax_phase, self._ax_rate) = plt.subplots(
            2, 1, figsize=(10, 6)
        )
        self._fig.suptitle("Monitoring respiratoire — Radar Doppler CW @ 2.4 GHz")

        # Graphe 1 : phase brute (signal respiratoire)
        (self._line_phase,) = self._ax_phase.plot(self._time, list(self._phase_buf), color="royalblue")
        self._ax_phase.set_ylabel("Phase (rad)")
        self._ax_phase.set_xlabel("Temps (s)")
        self._ax_phase.set_title("Signal de phase — mouvement thoracique")
        self._ax_phase.grid(True, alpha=0.3)

        # Graphe 2 : rythme respiratoire estimé
        self._bar = self._ax_rate.bar(["Rythme"], [0], color="steelblue", width=0.3)
        self._ax_rate.set_ylim(0, 40)
        self._ax_rate.set_ylabel("Respirations / min")
        self._ax_rate.axhline(config.BRADY_RPM, color="orange", linestyle="--", label=f"Min ({config.BRADY_RPM})")
        self._ax_rate.axhline(config.TACHY_RPM, color="red",    linestyle="--", label=f"Max ({config.TACHY_RPM})")
        self._ax_rate.legend(loc="upper right")
        self._text_rate = self._ax_rate.text(0, 2, "— rpm", ha="center", fontsize=18, fontweight="bold")

        self._fig.tight_layout()

    def update(self, new_phase_chunk: np.ndarray, rate_rpm: float | None):
        """Appelé à chaque nouveau bloc de phase décimée."""
        for v in new_phase_chunk:
            self._phase_buf.append(float(v))

        self._line_phase.set_ydata(list(self._phase_buf))
        self._ax_phase.relim()
        self._ax_phase.autoscale_view(scalex=False)

        if rate_rpm is not None:
            self._bar[0].set_height(rate_rpm)
            color = "green" if config.BRADY_RPM <= rate_rpm <= config.TACHY_RPM else "red"
            self._bar[0].set_color(color)
            self._text_rate.set_text(f"{rate_rpm:.1f} rpm")

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def show(self):
        plt.ion()
        plt.show()
