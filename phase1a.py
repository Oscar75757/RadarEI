"""
Phase 1a — Validation du signal respiratoire
============================================
Objectif : VOIR la respiration à l'écran sur le signal de phase BRUT,
avant d'ajouter filtrage, FFT et alertes. C'est le premier point de
vérification physique : si la courbe oscille avec la respiration, toute
la chaîne matérielle (émission CW → réflexion thorax → réception →
extraction de phase) fonctionne.

Montage : 1 Pluto MAÎTRE seul, 2 antennes papillon (TX + RX) pointées
vers le thorax. (Le 2e récepteur n'intervient pas à ce stade.)

Utilisation :
    source .venv/bin/activate
    python3 phase1a.py

Test de validation : respire normalement → la courbe oscille à ~0.2–0.5 Hz.
Bloque ta respiration → la courbe doit s'aplatir. Reprends → elle repart.
"""

import collections
import numpy as np
import matplotlib.pyplot as plt

import config
from mqtt_publisher     import MQTTPublisher
from hardware.discovery import resolve_master
from hardware.tx        import init_master, start_tx, stop_tx
from hardware.rx        import config_master_rx, capture
from processing.phase   import decimate, Downconverter, PhaseTracker


def main():
    print("=== Phase 1a — visualisation du signal de phase ===\n")

    # --- Matériel : Pluto maître seul (TX + RX cohérents) ---
    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    mixer   = Downconverter()   # descend le ton IF (+100 kHz) vers 0 Hz
    tracker = PhaseTracker()
    mqtt    = MQTTPublisher()

    # --- Fenêtre d'affichage glissante ---
    n_points = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
    buf = collections.deque([0.0] * n_points, maxlen=n_points)
    t   = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 4))
    (line,) = ax.plot(t, list(buf), color="royalblue", lw=1.5)
    ax.set_xlabel("Temps (s)")
    ax.set_ylabel("Phase (rad, centrée)")
    ax.set_title("Phase 1a — signal de phase brut : respire devant les antennes")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    plt.show()

    print(">>> Respire normalement devant les antennes (~1 m).")
    print(">>> Validation : bloque ta respiration → la courbe doit s'aplatir.")
    print(">>> Ctrl+C pour arrêter.\n")

    try:
        while True:
            iq     = capture(sdr)            # ~65 ms d'IQ brut (écho à +F_IF)
            iq_bb  = mixer.process(iq)       # descente IF → 0 Hz
            iq_dec = decimate(iq_bb)         # 1 MSPS → 100 Hz (élimine le clutter à -F_IF)
            phase  = tracker.process(iq_dec) # phase continue (rad)

            for v in phase:
                buf.append(float(v))

            arr      = np.array(buf)
            centered = arr - arr.mean()
            line.set_ydata(centered)
            ax.relim()
            ax.autoscale_view(scalex=False)
            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(0.001)
            mqtt.publish_live(None, 0.0, [], centered.tolist(), mode="phase1a")

    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        stop_tx(sdr)
        mqtt.close()
        print("Émission arrêtée. Phase 1a terminée.")


if __name__ == "__main__":
    main()
