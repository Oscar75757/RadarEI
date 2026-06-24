"""
Phase 1c — Validation du signal cardiaque
==========================================
Objectif : visualiser côte à côte le signal respiratoire et le signal cardiaque.

Principes d'affichage (identiques à phase1a pour la resp) :
  - Panneau resp    : phase brute accumulée dans buffer glissant 30s, centrée
                      par arr - arr.mean() — AUCUN filtre IIR sur l'affichage.
                      Identique à phase1a → même qualité visuelle.
  - Panneau cardiac : sortie du CardiacFilter (0.8–2.5 Hz) accumulée dans son
                      propre buffer glissant 30s, centrée par la même méthode.
                      Le filtre IIR est nécessaire ici pour ôter la respiration
                      (20–50× plus forte) et rendre le signal cardiaque visible.

Les filtres IIR (RespiratoryFilter, CardiacFilter) sont utilisés UNIQUEMENT
pour l'estimation du rythme (FFT), pas pour l'affichage.

Test de validation :
  1. Respire → panneau resp oscille à ~0.2–0.5 Hz (identique à phase1a).
  2. Panneau cardiac montre une oscillation ~10× plus rapide, visible après
     autoscale (amplitude typ. 0.01–0.05 rad contre ~0.5 rad pour la resp).
  3. Bloque ta respiration → panneau resp s'aplatit, panneau cardiac continue.

Utilisation :
    source .venv/bin/activate
    python3 phase1c.py
"""

import collections
import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery   import resolve_master
from hardware.tx          import init_master, start_tx, stop_tx
from hardware.rx          import config_master_rx, capture
from processing.phase     import decimate, Downconverter, PhaseTracker
from processing.filters   import RespiratoryFilter, CardiacFilter
from processing.estimator import RateEstimator


def main():
    print("=== Phase 1c — validation du signal cardiaque ===\n")
    print("1er rythme respiratoire fiable après ~20 s.")
    print("1er rythme cardiaque fiable après ~15 s.")
    print("Ctrl+C pour arrêter.\n")

    # --- Matériel ---
    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    # --- Traitement ---
    mixer          = Downconverter()
    tracker        = PhaseTracker()
    # Filtres IIR — uniquement pour l'estimation du rythme, pas pour l'affichage
    resp_filter    = RespiratoryFilter()
    cardiac_filter = CardiacFilter()
    resp_est       = RateEstimator()
    cardiac_est    = RateEstimator(
        f_low=config.CARDIAC_F_LOW,
        f_high=config.CARDIAC_F_HIGH,
        window_s=config.CARDIAC_WINDOW_S,
        smoothing_n=config.CARDIAC_SMOOTHING_N,
    )

    # --- Buffers d'affichage glissants (même mécanisme que phase1a) ---
    n_points    = int(config.PLOT_WINDOW_S * config.DECIMATED_FS)
    resp_buf    = collections.deque([0.0] * n_points, maxlen=n_points)
    cardiac_buf = collections.deque([0.0] * n_points, maxlen=n_points)
    t = np.linspace(-config.PLOT_WINDOW_S, 0, n_points)

    # --- Affichage 2 panneaux ---
    plt.ion()
    fig, (ax_resp, ax_cardiac) = plt.subplots(
        2, 1,
        figsize=(12, 8),
        gridspec_kw={"height_ratios": [1, 1]},
    )
    fig.suptitle("Phase 1c — Respiration & Cardiaque")

    # Panneau 1 : phase brute centrée sur buffer 30s — identique à phase1a
    (line_resp,) = ax_resp.plot(t, list(resp_buf), color="royalblue", lw=1.5)
    ax_resp.set_ylabel("Phase (rad, centrée)")
    ax_resp.set_title(
        f"Respiration — phase brute (comme phase1a) | "
        f"en cours d'estimation…"
    )
    ax_resp.grid(True, alpha=0.3)
    ax_resp.set_xticklabels([])

    # Panneau 2 : sortie CardiacFilter centrée sur buffer 30s
    (line_cardiac,) = ax_cardiac.plot(t, list(cardiac_buf), color="crimson", lw=1.0)
    ax_cardiac.set_ylabel("Phase cardiaque (rad)")
    ax_cardiac.set_title(
        f"Cardiaque — {config.CARDIAC_F_LOW}–{config.CARDIAC_F_HIGH} Hz "
        f"(amplitude typ. 0.01–0.05 rad) | en cours d'estimation…"
    )
    ax_cardiac.set_xlabel("Temps (s)")
    ax_cardiac.grid(True, alpha=0.3)

    fig.tight_layout()
    plt.show()

    last_resp_rate    = None
    last_cardiac_rate = None

    try:
        while True:
            iq     = capture(sdr)
            iq_bb  = mixer.process(iq)
            iq_dec = decimate(iq_bb)
            phase  = tracker.process(iq_dec)   # phase continue, pas de remove_dc

            # --- Affichage resp : buffer glissant + centrage global (= phase1a) ---
            for v in phase:
                resp_buf.append(float(v))
            arr_resp = np.array(resp_buf)
            line_resp.set_ydata(arr_resp - arr_resp.mean())
            ax_resp.relim()
            ax_resp.autoscale_view(scalex=False)

            # --- Affichage cardiac : filtre IIR + buffer glissant + centrage ---
            cardiac_filt = cardiac_filter.apply(phase)
            for v in cardiac_filt:
                cardiac_buf.append(float(v))
            arr_cardiac = np.array(cardiac_buf)
            line_cardiac.set_ydata(arr_cardiac - arr_cardiac.mean())
            ax_cardiac.relim()
            ax_cardiac.autoscale_view(scalex=False)

            # --- Estimation des rythmes (filtres IIR séparés) ---
            resp_filt = resp_filter.apply(phase)
            resp_rate    = resp_est.push(resp_filt)
            cardiac_rate = cardiac_est.push(cardiac_filt)
            if resp_rate    is not None: last_resp_rate    = resp_rate
            if cardiac_rate is not None: last_cardiac_rate = cardiac_rate

            # Mise à jour des titres
            r_str = f"{last_resp_rate:.1f} rpm" if last_resp_rate else "en cours…"
            c_str = f"{last_cardiac_rate:.0f} bpm" if last_cardiac_rate else "en cours…"
            ax_resp.set_title(f"Respiration — phase brute (comme phase1a) | {r_str}")
            ax_cardiac.set_title(
                f"Cardiaque — {config.CARDIAC_F_LOW}–{config.CARDIAC_F_HIGH} Hz "
                f"(amplitude typ. 0.01–0.05 rad) | {c_str}"
            )

            if last_resp_rate is not None or last_cardiac_rate is not None:
                print(f"  Resp: {r_str}  |  Cardiaque: {c_str}", end="\r")

            fig.canvas.draw_idle()
            fig.canvas.flush_events()
            plt.pause(0.001)

    except KeyboardInterrupt:
        print("\n\nArrêt demandé.")
    finally:
        stop_tx(sdr)
        print("Émission arrêtée. Phase 1c terminée.")


if __name__ == "__main__":
    main()
