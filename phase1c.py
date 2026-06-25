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
  - bas  : amplitude (crête-à-crête glissant) vs seuil d'apnée adaptatif —
           le seuil (relatif à la respiration) se recale tout seul.

Utilisation :
    source .venv/bin/activate
    python3 phase1c.py
"""

import collections
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

import config
from hardware.discovery   import resolve_master
from hardware.tx          import init_master, start_tx, stop_tx
from hardware.rx          import config_master_rx, capture
from processing.phase     import decimate, Downconverter, PhaseTracker, oscillation_amplitude
from processing.filters   import RespiratoryFilter
from processing.estimator import RateEstimator
from processing.peak_rate  import PeakRateEstimator
from processing.alerts    import AlertSystem
from processing.adaptive  import AdaptiveApneaThreshold
from processing.logger    import SessionLogger
from processing.recording import RecordWriter


def _fmt_hms(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def main(record: bool = False, duration_h: float | None = None):
    print("=== Phase 1c — alertes & journalisation ===\n")

    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    mixer     = Downconverter()
    tracker   = PhaseTracker()
    bandpass  = RespiratoryFilter()
    estimator = RateEstimator()       # FFT — calculs & alertes (robuste)
    peak_rate = PeakRateEstimator()   # intervalle entre pics — affichage (réactif)
    alerter   = AlertSystem()
    adaptive  = AdaptiveApneaThreshold()   # seuil d'apnée auto-calibré
    logger    = SessionLogger()
    print(f"[log] Journalisation → {logger.path}")

    fs = config.DECIMATED_FS

    recorder = None
    if record:
        recorder = RecordWriter(fs, duration_h=duration_h)
        print(f"[rec] Enregistrement → recordings/{recorder.base}_*  "
              f"({'durée ' + str(duration_h) + ' h' if duration_h else 'arrêt manuel'})")

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
    thr_line = ax2.axhline(config.APNEA_AMP_EPS, color="red", ls="--", lw=1.0,
                           label="seuil apnée (adaptatif)")
    warmup_text = ax2.text(0.5, 0.5, "", transform=ax2.transAxes, ha="center",
                           va="center", fontsize=14, fontweight="bold",
                           color="darkorange")
    ax2.set_ylabel("Amplitude (rad)")
    ax2.set_xlabel("Temps (s)")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left", fontsize=8)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.93, bottom=0.17, hspace=0.12)

    # --- Boutons : réinitialiser la vue / re-calibrer ---
    # reset_view : purge l'historique AFFICHÉ (onde + amplitude) pour évacuer les
    #   pics de mise en place ; n'affecte NI le rythme NI la détection.
    # recalibrate : relance les 10 s de calibration du seuil adaptatif — utile
    #   après un changement d'antenne/position (re-cale instantanément la baseline).
    def reset_view(event=None):
        wave.clear();     wave.extend([0.0] * n_plot)
        amp_hist.clear(); amp_hist.extend([0.0] * n_amp_hist)

    def recalibrate(event=None):
        adaptive.recalibrate()
        print(">>> Re-calibration du seuil demandée (10 s).")

    def on_key(e):
        if   e.key == "r": reset_view()
        elif e.key == "c": recalibrate()

    btn_reset_ax = fig.add_axes([0.30, 0.04, 0.18, 0.055])
    reset_btn = Button(btn_reset_ax, "Réinitialiser la vue (r)")
    reset_btn.on_clicked(reset_view)

    btn_recal_ax = fig.add_axes([0.52, 0.04, 0.18, 0.055])
    recal_btn = Button(btn_recal_ax, "Re-calibrer (c)")
    recal_btn.on_clicked(recalibrate)

    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.show()

    print(f">>> Calibration : {config.WARMUP_S:.0f} s pour t'installer et respirer normalement.")
    print(">>> Ensuite : surveillance active.")
    print(">>> Touches : 'r' réinitialise la vue | 'c' re-calibre le seuil | Ctrl+C arrête.\n")

    last_rate    = None
    amplitude    = 0.0
    last_draw    = 0.0
    last_eval    = 0.0
    t_prev       = time.time()
    was_warming  = True   # pour réinitialiser la vue à la fin de la calibration
    apnea_start  = None   # début de l'apnée en cours (enregistrement)
    DRAW_EVERY   = 0.16   # s
    EVAL_EVERY   = 1.0    # s — cadence alertes + journal + console

    try:
        while True:
            iq     = capture(sdr)
            iq_bb  = mixer.process(iq)
            iq_dec = decimate(iq_bb)
            phase  = tracker.process(iq_dec)
            filt   = bandpass.apply(phase)

            if recorder is not None:
                recorder.write(phase)      # signal source enregistré sur disque

            for v in filt:
                wave.append(float(v))      # onde filtrée → affichage
            for v in phase:
                raw_win.append(float(v))   # phase brute → détection d'apnée

            # amplitude d'oscillation sur la phase brute détrendée (réaction rapide)
            amplitude = oscillation_amplitude(np.asarray(raw_win))

            peak_rate.update(filt, amplitude)   # rythme AFFICHAGE (intervalle pics)

            r = estimator.push(filt)            # rythme ALERTES (FFT robuste)
            if r is not None:
                last_rate = r

            now = time.time()
            dt  = min(now - t_prev, 1.0)   # clamp anti-grand-pas au démarrage
            t_prev = now

            # Seuil adaptatif : état (warmup/active), respiration, seuil, restant
            state, breathing, threshold, remaining = adaptive.update(amplitude, dt)
            warming = (state == "warmup")

            # Fin de la calibration → on repart sur une vue propre
            if was_warming and not warming:
                reset_view()
            was_warming = warming

            # --- Alertes + journal + console (seulement hors calibration) ---
            if warming:
                alerts = []
            elif now - last_eval >= EVAL_EVERY:
                last_eval = now
                alerts = alerter.evaluate(last_rate, breathing)
                logger.log(last_rate, amplitude, alerts)
                print("  " + alerter.status_line(last_rate, amplitude, alerts, threshold))
            else:
                alerts = alerter.evaluate(last_rate, breathing)  # MAJ chrono apnée

            # --- Enregistrement : repères d'apnée + arrêt sur durée ---
            if recorder is not None:
                apnea_now = any("APNÉE" in a for a in alerts)
                if apnea_now and apnea_start is None:
                    apnea_start = recorder.signal_time()
                elif not apnea_now and apnea_start is not None:
                    recorder.log_apnea(apnea_start, recorder.signal_time())
                    apnea_start = None
                if recorder.duration_reached():
                    print("\nDurée d'enregistrement atteinte.")
                    break

            # --- Affichage (cadence rapide, découplé de la capture) ---
            if now - last_draw >= DRAW_EVERY:
                last_draw = now

                rec_str = ""
                if recorder is not None:
                    el = _fmt_hms(recorder.elapsed())
                    rec_str = (f"● REC {el}/{_fmt_hms(duration_h * 3600)}  |  "
                               if duration_h else f"● REC {el}  |  ")

                line_wave.set_ydata(np.array(wave))
                ax1.relim(); ax1.autoscale_view(scalex=False)

                if warming:
                    # Message de calibration à la place de la courbe d'amplitude
                    line_amp.set_visible(False)
                    thr_line.set_visible(False)
                    warmup_text.set_visible(True)
                    warmup_text.set_text(
                        "Prenez place et commencez à respirer normalement\n"
                        f"(calibration dans {remaining:.0f} s)")
                    line_wave.set_color("seagreen")
                    title.set_text(rec_str + "Calibration en cours…")
                    banner.set_text("⏳ Calibration")
                    banner.set_color("darkorange")
                else:
                    line_amp.set_visible(True)
                    thr_line.set_visible(True)
                    warmup_text.set_visible(False)

                    amp_hist.append(amplitude)
                    alert_on = bool(alerts)
                    line_amp.set_ydata(np.array(amp_hist))
                    thr_line.set_ydata([threshold, threshold])
                    line_wave.set_color("crimson" if alert_on else "seagreen")
                    ax2.relim(); ax2.autoscale_view(scalex=False)

                    disp_rate = peak_rate.rate()   # rythme réactif (intervalle entre pics)
                    rate_str = f"{disp_rate:.1f} resp/min" if disp_rate is not None else "— resp/min"
                    title.set_text(rec_str + f"Rythme (live) : {rate_str}    |    "
                                   f"Amplitude : {amplitude:.3f} | seuil : {threshold:.3f} rad")
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
        if recorder is not None:
            if apnea_start is not None:                 # apnée en cours à l'arrêt
                recorder.log_apnea(apnea_start, recorder.signal_time())
            recorder.close()
            print(f"\nEnregistrement terminé : recordings/{recorder.base}_phase.f32")
            print(f"  Durée : {_fmt_hms(recorder.signal_time())}  |  "
                  f"apnées repérées en direct : {recorder.n_apneas}")
            print(f"  → Analyse : python3 analyze.py")
        print(f"Journal enregistré : {logger.path}")
        print("Phase 1c terminée.")


if __name__ == "__main__":
    main()
