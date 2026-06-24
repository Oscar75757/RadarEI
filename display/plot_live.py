import collections
import matplotlib.pyplot as plt
import numpy as np
import config


class LivePlot:
    """Affichage temps-réel cardio-respiratoire — 3 panneaux."""

    def __init__(self):
        n_points = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
        self._resp_buf    = collections.deque([0.0] * n_points, maxlen=n_points)
        self._cardiac_buf = collections.deque([0.0] * n_points, maxlen=n_points)
        self._time = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

        self._fig, (self._ax_resp, self._ax_cardiac, self._ax_rate) = plt.subplots(
            3, 1,
            figsize=(12, 10),
            gridspec_kw={"height_ratios": [3, 3, 2]},
        )
        self._fig.suptitle("Monitoring cardio-respiratoire — Radar Doppler CW @ 2.4 GHz")

        # Panneau 1 : signal respiratoire filtré (0.1–0.8 Hz)
        (self._line_resp,) = self._ax_resp.plot(
            self._time, list(self._resp_buf), color="royalblue", lw=1.5
        )
        self._ax_resp.set_ylabel("Phase resp. (rad)")
        self._ax_resp.set_title(f"Respiration — {config.F_LOW}–{config.F_HIGH} Hz")
        self._ax_resp.grid(True, alpha=0.3)
        self._ax_resp.set_xticklabels([])

        # Panneau 2 : signal cardiaque filtré (0.8–2.5 Hz)
        # Autoscale essentiel : amplitude typ. 0.01–0.05 rad (20-50x plus faible que resp)
        (self._line_cardiac,) = self._ax_cardiac.plot(
            self._time, list(self._cardiac_buf), color="crimson", lw=1.0
        )
        self._ax_cardiac.set_ylabel("Phase cardiaque (rad)")
        self._ax_cardiac.set_title(
            f"Cardiaque — {config.CARDIAC_F_LOW}–{config.CARDIAC_F_HIGH} Hz"
            "   (amplitude typ. 0.01–0.05 rad)"
        )
        self._ax_cardiac.grid(True, alpha=0.3)
        self._ax_cardiac.set_xlabel("Temps (s)")

        # Panneau 3 : double barre de rythme
        self._bars = self._ax_rate.bar(
            [0, 1], [0, 0],
            color=["steelblue", "crimson"],
            width=0.4,
        )
        self._ax_rate.set_xticks([0, 1])
        self._ax_rate.set_xticklabels(["Respiration (rpm)", "Cardiaque (bpm)"])
        self._ax_rate.set_ylim(0, 160)
        self._ax_rate.set_ylabel("Cycles / min")
        self._ax_rate.axhline(
            config.BRADY_RPM, color="dodgerblue", ls="--", lw=0.8,
            label=f"Brady resp ({config.BRADY_RPM} rpm)"
        )
        self._ax_rate.axhline(
            config.TACHY_RPM, color="navy", ls="--", lw=0.8,
            label=f"Tachy resp ({config.TACHY_RPM} rpm)"
        )
        self._ax_rate.axhline(
            config.BRADY_BPM, color="salmon", ls=":", lw=0.8,
            label=f"Brady card. ({config.BRADY_BPM} bpm)"
        )
        self._ax_rate.axhline(
            config.TACHY_BPM, color="darkred", ls=":", lw=0.8,
            label=f"Tachy card. ({config.TACHY_BPM} bpm)"
        )
        self._ax_rate.legend(loc="upper right", fontsize=7)
        self._text_resp    = self._ax_rate.text(0, 4, "— rpm", ha="center",
                                                 fontsize=14, fontweight="bold",
                                                 color="steelblue")
        self._text_cardiac = self._ax_rate.text(1, 4, "— bpm", ha="center",
                                                 fontsize=14, fontweight="bold",
                                                 color="crimson")

        self._fig.tight_layout()

    def update(
        self,
        resp_chunk: np.ndarray,
        cardiac_chunk: np.ndarray,
        rate_rpm: float | None,
        rate_bpm: float | None,
    ) -> None:
        for v in resp_chunk:
            self._resp_buf.append(float(v))
        for v in cardiac_chunk:
            self._cardiac_buf.append(float(v))

        self._line_resp.set_ydata(list(self._resp_buf))
        self._ax_resp.relim()
        self._ax_resp.autoscale_view(scalex=False)

        self._line_cardiac.set_ydata(list(self._cardiac_buf))
        self._ax_cardiac.relim()
        self._ax_cardiac.autoscale_view(scalex=False)

        if rate_rpm is not None:
            self._bars[0].set_height(rate_rpm)
            ok = config.BRADY_RPM <= rate_rpm <= config.TACHY_RPM
            self._bars[0].set_color("green" if ok else "red")
            self._text_resp.set_text(f"{rate_rpm:.1f} rpm")

        if rate_bpm is not None:
            self._bars[1].set_height(rate_bpm)
            ok = config.BRADY_BPM <= rate_bpm <= config.TACHY_BPM
            self._bars[1].set_color("green" if ok else "red")
            self._text_cardiac.set_text(f"{rate_bpm:.0f} bpm")

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()

    def show(self):
        plt.ion()
        plt.show()
