"""
Phase 1c — Alertes et journalisation en conditions réelles
==========================================================
On part de la chaîne validée en 1b (rythme respiratoire temps-réel) et on ajoute
la surveillance clinique :

  - APNÉE     : amplitude d'oscillation sous le seuil pendant > APNEA_DELAY_S.
                (détection par ABSENCE de mouvement, pas par niveau absolu —
                 le passe-haut fait retomber un signal figé vers zéro.)
  - BRADYPNÉE : rythme < BRADY_RPM (respiration présente).
  - TACHYPNÉE : rythme > TACHY_RPM (respiration présente).

Chaque évaluation est journalisée dans logs/session_*.csv.

Affichage à deux panneaux :
  - haut : onde respiratoire filtrée (rouge si alerte active) ;
  - bas  : amplitude (écart-type glissant) vs seuil d'apnée — pour visualiser
           l'apnée et calibrer APNEA_AMP_THRESH.

Utilisation :
    source .venv/bin/activate
    python3 phase1c.py
"""

import collections
import time
import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery   import resolve_master
from hardware.tx          import init_master, start_tx, stop_tx
from hardware.rx          import config_master_rx, capture
from processing.phase     import decimate, Downconverter, PhaseTracker, oscillation_amplitude
from processing.filters   import RespiratoryFilter
from processing.estimator import RateEstimator
from processing.alerts    import AlertSystem
from processing.logger    import SessionLogger


def main():
    print("=== Phase 1c — alertes & journalisation ===\n")

    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    mixer     = Downconverter()
    tracker   = PhaseTracker()
    bandpass  = RespiratoryFilter()
    estimator = RateEstimator()
    alerter   = AlertSystem()
    logger    = SessionLogger()
    print(f"[log] Journalisation → {logger.path}")

    fs = config.DECIMATED_FS

    # --- Tampons ---
    n_plot  = int(config.PLOT_WINDOW_S * fs)
    wave    = collections.deque([0.0] * n_plot, maxlen=n_plot)          # onde filtrée (affichage)
    raw_win = collections.deque(maxlen=int(config.AMP_WINDOW_S * fs))   # phase BRUTE (détection apnée)
    t_wave  = np.linspace(-config.PLOT_WINDOW_S, 0, n_plot)

    n_amp_hist = int(config.PLOT_WINDOW_S / 0.16) + 1
    amp_hist   = collections.deque([0.0] * n_amp_hist, maxlen=n_amp_hist)
    t_amp      = np.linspace(-config.PLOT_WINDOW_S, 0, n_amp_hist)

    # --- Figure ---
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6.5), height_ratios=[2, 1],
                                   sharex=True)
    (line_wave,) = ax1.plot(t_wave, list(wave), color="seagreen", lw=1.6)
    ax1.set_ylabel("Onde respiratoire (rad)")
    ax1.grid(True, alpha=0.3)
    title = ax1.set_title("Acquisition en cours…")
    banner = ax1.text(0.01, 0.95, "", transform=ax1.transAxes, va="top", ha="left",
                      fontsize=12, fontweight="bold",
                      bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.8))

    (line_amp,) = ax2.plot(t_amp, list(amp_hist), color="steelblue", lw=1.4)
    ax2.axhline(config.APNEA_AMP_THRESH, color="red", ls="--", lw=1.0,
                label=f"seuil apnée ({config.APNEA_AMP_THRESH} rad)")
    ax2.set_ylabel("Amplitude (rad)")
    ax2.set_xlabel("Temps (s)")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    plt.show()

    print(">>> Respire normalement. Teste l'apnée (> 15 s sans bouger).")
    print(">>> Ctrl+C pour arrêter.\n")

    last_rate  = None
    amplitude  = 0.0
    last_draw  = 0.0
    last_eval  = 0.0
    DRAW_EVERY = 0.16   # s
    EVAL_EVERY = 1.0    # s — cadence alertes + journal + console

    try:
        while True:
            iq     = capture(sdr)
            iq_bb  = mixer.process(iq)
            iq_dec = decimate(iq_bb)
            phase  = tracker.process(iq_dec)
            filt   = bandpass.apply(phase)

            for v in filt:
                wave.append(float(v))      # onde filtrée → affichage
            for v in phase:
                raw_win.append(float(v))   # phase brute → détection d'apnée

            r = estimator.push(filt)
            if r is not None:
                last_rate = r

            # amplitude d'oscillation sur la phase brute détrendée (réaction rapide)
            amplitude = oscillation_amplitude(np.asarray(raw_win))

            now = time.time()

            # --- Alertes + journal + console (cadence lente) ---
            if now - last_eval >= EVAL_EVERY:
                last_eval = now
                alerts = alerter.evaluate(last_rate, amplitude)
                logger.log(last_rate, amplitude, alerts)
                print("  " + alerter.status_line(last_rate, amplitude, alerts))
            else:
                alerts = alerter.evaluate(last_rate, amplitude)  # MAJ chrono apnée

            # --- Affichage (cadence rapide, découplé de la capture) ---
            if now - last_draw >= DRAW_EVERY:
                last_draw = now
                amp_hist.append(amplitude)
                alert_on = bool(alerts)

                line_wave.set_ydata(np.array(wave))
                line_wave.set_color("crimson" if alert_on else "seagreen")
                line_amp.set_ydata(np.array(amp_hist))
                for ax in (ax1, ax2):
                    ax.relim(); ax.autoscale_view(scalex=False)

                rate_str = f"{last_rate:.1f} resp/min" if last_rate is not None else "— resp/min"
                title.set_text(f"Rythme : {rate_str}    |    Amplitude : {amplitude:.3f} rad")
                if alert_on:
                    banner.set_text("  ".join("⚠️ " + a.split(" — ")[0] for a in alerts))
                    banner.set_color("crimson")
                else:
                    banner.set_text("✅ Normal")
                    banner.set_color("green")

                fig.canvas.draw_idle()
                fig.canvas.flush_events()
                plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        stop_tx(sdr)
        logger.close()
        print(f"Journal enregistré : {logger.path}")
        print("Phase 1c terminée.")


if __name__ == "__main__":
    main()
