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
from processing.phase     import decimate, extract_phase, remove_dc, Downconverter, PhaseTracker
from processing.filters   import RespiratoryFilter, CardiacFilter
from processing.estimator import RateEstimator
from processing.alerts    import AlertSystem, CardiacAlertSystem
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
    mixer       = Downconverter()      # descend le ton IF (+100 kHz) → 0 Hz
    tracker     = PhaseTracker()       # phase continue entre buffers
    resp_filter = RespiratoryFilter()
    estimator   = RateEstimator()
    alert_sys   = AlertSystem()

    cardiac_filter    = CardiacFilter()
    cardiac_estimator = RateEstimator(
        f_low=config.CARDIAC_F_LOW,
        f_high=config.CARDIAC_F_HIGH,
        window_s=config.CARDIAC_WINDOW_S,
        smoothing_n=config.CARDIAC_SMOOTHING_N,
    )
    cardiac_alert = CardiacAlertSystem()

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

            # 2. Descente IF → 0 Hz (indispensable avant décimation)
            iq_bb  = mixer.process(iq)

            # 3. Décimation 1 MSPS → DECIMATED_FS
            iq_dec = decimate(iq_bb)

            # 4. Extraction de phase continue + suppression DC
            phase = tracker.process(iq_dec)
            phase = remove_dc(phase)

            # 5. Filtres passe-bande (resp + cardiaque sur la même phase brute)
            resp_filtered    = resp_filter.apply(phase)
            cardiac_filtered = cardiac_filter.apply(phase)

            # 6. Estimation des rythmes
            rate_rpm = estimator.push(resp_filtered)
            rate_bpm = cardiac_estimator.push(cardiac_filtered)

            # 7. Alertes
            resp_alerts    = alert_sys.evaluate(rate_rpm)
            cardiac_alerts = cardiac_alert.evaluate(rate_bpm)
            alert_sys.print_status(rate_rpm, resp_alerts)
            cardiac_alert.print_status(rate_bpm, cardiac_alerts)

            # 8. Affichage temps-réel (3 panneaux)
            plot.update(resp_filtered, cardiac_filtered, rate_rpm, rate_bpm)

    except KeyboardInterrupt:
        print("\n\nArrêt demandé.")

    finally:
        stop_tx(sdr_master)
        print("Système arrêté proprement.")


if __name__ == "__main__":
    main()
