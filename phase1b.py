"""
Phase 1b — Rythme respiratoire chiffré
======================================
La phase 1a a validé le signal de phase (architecture IF + descente numérique).
Ici on le transforme en **rythme respiratoire en resp/min**, affiché en continu.

Chaîne complète :
    capture → descente IF → décimation → phase → FILTRE passe-bande 0.1–0.8 Hz
            → FFT sur fenêtre glissante → pic → resp/min (lissé)

Le filtre passe-bande fait deux choses essentielles :
  - il coupe < 0.1 Hz   → élimine la dérive lente du corps (le « verrou » P1) ;
  - il coupe > 0.8 Hz   → élimine le bruit haute fréquence.

Montage : 1 Pluto MAÎTRE seul, 2 antennes ESLP (TX + RX) pointées vers le thorax.

Utilisation :
    source .venv/bin/activate
    python3 phase1b.py

Note : le filtre (coupure basse 0.1 Hz) et la fenêtre FFT (20 s) ont un régime
transitoire ; le 1er rythme fiable apparaît après ~20 s. Le test du blocage
respiratoire reste valable : pendant l'apnée, l'onde filtrée s'aplatit.
"""

import collections
import time
import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery import resolve_master
from hardware.tx        import init_master, start_tx, stop_tx
from hardware.rx        import config_master_rx, capture
from processing.phase   import decimate, Downconverter, PhaseTracker
from processing.filters import RespiratoryFilter
from processing.estimator import RateEstimator


def main():
    print("=== Phase 1b — rythme respiratoire (resp/min) ===\n")

    # --- Matériel ---
    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    # --- Traitement ---
    mixer     = Downconverter()      # ton IF (+100 kHz) → 0 Hz
    tracker   = PhaseTracker()       # phase continue entre buffers
    bandpass  = RespiratoryFilter()  # passe-bande 0.1–0.8 Hz (état persistant)
    estimator = RateEstimator()      # FFT glissante → resp/min

    # --- Affichage : onde filtrée + rythme courant ---
    n_points = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
    buf = collections.deque([0.0] * n_points, maxlen=n_points)
    t   = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    (line,) = ax.plot(t, list(buf), color="seagreen", lw=1.6)
    ax.set_xlabel("Temps (s)")
    ax.set_ylabel("Onde respiratoire filtrée (rad)")
    ax.grid(True, alpha=0.3)
    rate_text = ax.set_title("Rythme : — resp/min   (acquisition en cours…)")
    fig.tight_layout()
    plt.show()

    print(">>> Respire normalement devant les antennes (~1 m).")
    print(">>> 1er rythme fiable après ~20 s. Ctrl+C pour arrêter.\n")

    last_rate  = None
    last_draw  = 0.0
    DRAW_EVERY = 0.16   # s — redessine ~6 fois/s (découplé de la capture)
    try:
        while True:
            # --- Capture + traitement à CHAQUE tour (continuité de la descente IF) ---
            iq     = capture(sdr)
            iq_bb  = mixer.process(iq)        # descente IF
            iq_dec = decimate(iq_bb)          # → 100 Hz
            phase  = tracker.process(iq_dec)  # phase continue
            filt   = bandpass.apply(phase)    # passe-bande respiratoire

            for v in filt:
                buf.append(float(v))

            rate = estimator.push(filt)       # None tant que la fenêtre n'est pas pleine
            if rate is not None:
                last_rate = rate
                print(f"  Rythme respiratoire : {rate:5.1f} resp/min")

            # --- Affichage throttlé : la boucle reste plus rapide que le temps réel
            #     et vide la file de buffers → pas de retard qui s'accumule. ---
            now = time.time()
            if now - last_draw >= DRAW_EVERY:
                last_draw = now
                line.set_ydata(np.array(buf))
                ax.relim()
                ax.autoscale_view(scalex=False)
                if last_rate is None:
                    rate_text.set_text("Rythme : — resp/min   (acquisition en cours…)")
                else:
                    rate_text.set_text(f"Rythme : {last_rate:.1f} resp/min")
                fig.canvas.draw_idle()
                fig.canvas.flush_events()
                plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        stop_tx(sdr)
        print("Émission arrêtée. Phase 1b terminée.")


if __name__ == "__main__":
    main()
