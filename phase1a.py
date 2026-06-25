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

Conforts repris de la phase 1c :
  - délai d'installation au démarrage (le temps de se placer et de commencer
    à respirer) ; la vue est remise à zéro à la fin pour partir propre ;
  - bouton « Réinitialiser la vue » (touche 'r') pour recaler l'échelle d'un
    coup (évacue un pic de mouvement sans attendre qu'il sorte de la fenêtre).

Utilisation :
    source .venv/bin/activate
    python3 phase1a.py

Test de validation : respire normalement → la courbe oscille à ~0.2–0.5 Hz.
Bloque ta respiration → la courbe doit s'aplatir. Reprends → elle repart.
"""

import collections
import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

import config
from hardware.discovery import resolve_master
from hardware.tx        import init_master, start_tx, stop_tx
from hardware.rx        import config_master_rx, capture
from processing.phase   import decimate, Downconverter, ClutterCanceller, PhaseTracker

TITRE = "Phase 1a — signal de phase brut : respire devant les antennes"


def main():
    print("=== Phase 1a — visualisation du signal de phase ===\n")

    # --- Matériel : Pluto maître seul (TX + RX cohérents) ---
    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    mixer   = Downconverter()      # descend le ton IF (+100 kHz) vers 0 Hz
    clutter = ClutterCanceller()   # retire le couplage statique TX→RX (anti-inversion)
    tracker = PhaseTracker()

    # --- Fenêtre d'affichage glissante ---
    n_points = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
    buf = collections.deque([0.0] * n_points, maxlen=n_points)
    t   = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

    plt.ion()
    fig, ax = plt.subplots(figsize=(11, 4.8))
    (line,) = ax.plot(t, list(buf), color="royalblue", lw=1.5)
    ax.set_xlabel("Temps (s)")
    ax.set_ylabel("Phase (rad, centrée)")
    ax.grid(True, alpha=0.3)
    warmup_text = ax.text(0.5, 0.5, "", transform=ax.transAxes, ha="center", va="center",
                          fontsize=14, fontweight="bold", color="darkorange")
    fig.subplots_adjust(left=0.08, right=0.97, top=0.92, bottom=0.22)

    # --- Bouton de réinitialisation de la vue (+ touche 'r') ---
    # On remplit avec la VALEUR COURANTE de la phase (pas zéro) : sinon, la phase
    # brute étant fortement décalée, le saut entre l'ancien (0) et le nouveau
    # niveau formerait un créneau qui empêche l'auto-échelle de se recaler.
    def reset_view(event=None):
        last = buf[-1] if len(buf) else 0.0
        buf.clear()
        buf.extend([last] * n_points)

    # Re-calibrer = relancer la période d'installation (réarme le timer ; la vue
    # est nettoyée automatiquement à la fin du nouveau délai).
    def recalibrate(event=None):
        nonlocal t_start
        t_start = time.time()
        clutter.reset()            # ré-apprend le couplage statique (nouvelle position)
        print(">>> Nouvelle installation demandée.")

    def on_key(e):
        if   e.key == "r": reset_view()
        elif e.key == "c": recalibrate()

    btn_reset_ax = fig.add_axes([0.28, 0.04, 0.20, 0.07])
    reset_btn = Button(btn_reset_ax, "Réinitialiser la vue (r)")
    reset_btn.on_clicked(reset_view)

    btn_recal_ax = fig.add_axes([0.52, 0.04, 0.20, 0.07])
    recal_btn = Button(btn_recal_ax, "Re-calibrer (c)")
    recal_btn.on_clicked(recalibrate)

    fig.canvas.mpl_connect("key_press_event", on_key)

    plt.show()

    print(f">>> Installation : {config.WARMUP_S:.0f} s pour te placer (~1 m) et respirer normalement.")
    print(">>> Ensuite : bloque ta respiration → la courbe doit s'aplatir.")
    print(">>> Touches : 'r' réinitialise la vue | 'c' relance l'installation | Ctrl+C arrête.\n")

    t_start     = time.time()
    was_warming = True
    try:
        while True:
            iq     = capture(sdr)            # IQ brut (écho à +F_IF)
            iq_bb  = mixer.process(iq)       # descente IF → 0 Hz
            iq_dec = decimate(iq_bb)         # → 100 Hz (élimine le clutter à -F_IF)
            iq_dec = clutter.process(iq_dec) # retire le couplage statique survivant à 0 Hz
            phase  = tracker.process(iq_dec) # phase continue (rad)

            for v in phase:
                buf.append(float(v))

            warming = (time.time() - t_start) < config.WARMUP_S
            if was_warming and not warming:
                reset_view()                 # vue propre à la fin de l'installation
            was_warming = warming

            if warming:
                line.set_visible(False)
                warmup_text.set_visible(True)
                remaining = config.WARMUP_S - (time.time() - t_start)
                warmup_text.set_text(
                    "Prenez place et commencez à respirer normalement\n"
                    f"(démarrage dans {remaining:.0f} s)")
                ax.set_title("Installation en cours…")
            else:
                line.set_visible(True)
                warmup_text.set_visible(False)
                arr = np.array(buf)
                line.set_ydata(arr - arr.mean())   # centrage pour l'affichage
                ax.relim()
                ax.autoscale_view(scalex=False)
                ax.set_title(TITRE)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nArrêt demandé.")
    finally:
        stop_tx(sdr)
        print("Émission arrêtée. Phase 1a terminée.")


if __name__ == "__main__":
    main()
