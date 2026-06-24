"""
Radar Doppler CW — Monitoring respiratoire sans contact
========================================================
Architecture :
    - Pluto 1 (MAÎTRE) : émet la CW et reçoit → canal cohérent (LO partagé)
    - Pluto 2 (optionnel) : récepteur seul → 2e point de vue (diversité spatiale)

Utilisation :
    source .venv/bin/activate
    python3 main.py

Prérequis :
    - URI des deux Plutos renseignés dans config.py (USE_SECOND_RX pour activer le 2e)
    - Antennes papillon (TX + RX maître) pointées vers le thorax du patient
"""

import config
from hardware.discovery   import resolve_master, resolve_rx2
from hardware.tx          import init_master, start_tx, stop_tx
from hardware.rx          import config_master_rx, init_second_rx, capture
from processing.phase     import decimate, extract_phase, remove_dc
from processing.filters   import RespiratoryFilter
from processing.estimator import RateEstimator
from processing.alerts    import AlertSystem
from display.plot_live    import LivePlot


def main():
    print("=== Démarrage du système de monitoring respiratoire ===\n")

    # --- Résolution des URI par numéro de série (stable entre sessions) ---
    uri_master = resolve_master()

    # --- Initialisation matérielle ---
    sdr_master = init_master(uri_master)          # crée l'objet TX+RX
    config_master_rx(sdr_master)                  # configure son RX (canal cohérent)
    start_tx(sdr_master)                          # configure son TX et démarre la CW

    if config.USE_SECOND_RX:
        sdr_rx2 = init_second_rx(resolve_rx2())
    else:
        sdr_rx2 = None
        print("[RX2] 2e récepteur désactivé (USE_SECOND_RX = False)")

    # --- Initialisation traitement ---
    resp_filter = RespiratoryFilter()
    estimator   = RateEstimator()
    alert_sys   = AlertSystem()

    # --- Affichage ---
    plot = LivePlot()
    plot.show()

    print("\nCapture en cours — Ctrl+C pour arrêter.\n")

    try:
        while True:
            # 1. Capture IQ du canal cohérent (maître)
            iq = capture(sdr_master)

            # 1bis. Capture du 2e canal si activé.
            #       Synchronisation + fusion à venir en phase 1d (processing/sync.py).
            if sdr_rx2 is not None:
                _iq2 = capture(sdr_rx2)   # noqa: F841 — réservé pour la fusion

            # 2. Décimation 1 MSPS → DECIMATED_FS
            iq_dec = decimate(iq)

            # 3. Extraction de phase + suppression DC
            phase = extract_phase(iq_dec)
            phase = remove_dc(phase)

            # 4. Filtre passe-bande respiratoire
            phase_filtered = resp_filter.apply(phase)

            # 5. Estimation du rythme (None tant que la fenêtre n'est pas pleine)
            rate_rpm = estimator.push(phase_filtered)

            # 6. Alertes
            alerts = alert_sys.evaluate(rate_rpm)
            alert_sys.print_status(rate_rpm, alerts)

            # 7. Affichage temps-réel
            plot.update(phase_filtered, rate_rpm)

    except KeyboardInterrupt:
        print("\n\nArrêt demandé.")

    finally:
        stop_tx(sdr_master)
        print("Système arrêté proprement.")


if __name__ == "__main__":
    main()
