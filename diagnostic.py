"""
Diagnostic — qualité du signal CW avant filtrage
================================================
Objectif : comprendre POURQUOI la phase brute part en vrille (excursions de
plusieurs dizaines de radians, incohérentes avec un vrai déplacement).

Hypothèse testée : l'écho respiratoire (petit) est noyé sous un gros vecteur
quasi-statique = fuite directe TX→RX + offset DC du récepteur + échos statiques
(murs, mobilier). Tout est à 0 Hz (TX et RX partagent le LO), donc indissociable
en fréquence. Quand l'amplitude résultante est faible, l'angle devient
hyper-sensible au bruit → l'unwrap fabrique de fausses excursions.

Ce script ENREGISTRE l'IQ (décimé, complexe) sur une durée fixe, puis affiche :
  1. |IQ| dans le temps        → niveau de signal, saturation / plancher de bruit
  2. la constellation I/Q      → gros blob hors origine = clutter/DC dominant
  3. phase brute vs phase APRÈS retrait du vecteur statique (clutter cancellation)

Aucune décision de design n'est prise ici : on regarde, on mesure, on conclut.

Utilisation :
    source .venv/bin/activate
    python3 diagnostic.py [duree_s]      # défaut : 30 s
"""

import sys
import time
import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery import resolve_master
from hardware.tx        import init_master, start_tx, stop_tx
from hardware.rx        import config_master_rx, capture
from processing.phase   import decimate


def acquire(sdr, duree_s: float) -> np.ndarray:
    """Capture l'IQ décimé (COMPLEXE) pendant `duree_s`, renvoie un vecteur complex."""
    chunks = []
    t0 = time.time()
    while time.time() - t0 < duree_s:
        iq = capture(sdr)                 # buffer brut ~65 ms
        chunks.append(decimate(iq))       # décimé mais on GARDE le complexe
    return np.concatenate(chunks)


def main():
    duree = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
    print(f"=== Diagnostic signal CW — acquisition {duree:.0f} s ===\n")

    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    print(f">>> Reste immobile et respire normalement pendant {duree:.0f} s...")
    try:
        iq = acquire(sdr, duree)
    finally:
        stop_tx(sdr)

    fs = config.DECIMATED_FS
    t  = np.arange(len(iq)) / fs

    # --- Mesures clés ---
    amp        = np.abs(iq)
    dc_vector  = iq.mean()                     # vecteur quasi-statique (clutter + DC)
    iq_clean   = iq - dc_vector                # retrait du clutter dans le plan complexe
    phase_raw  = np.unwrap(np.angle(iq))
    phase_clean = np.unwrap(np.angle(iq_clean))

    ratio = np.abs(dc_vector) / (amp.std() + 1e-12)
    fullscale = 2 ** 11                         # ADC 12 bits Pluto (~±2048)
    print(f"\n[mesures]")
    print(f"  |IQ| moyen        : {amp.mean():.1f}   (pleine échelle ADC ≈ {fullscale})")
    print(f"  |IQ| max          : {amp.max():.1f}   {'⚠️ SATURATION' if amp.max() > 0.9*fullscale else 'ok'}")
    print(f"  |vecteur statique|: {np.abs(dc_vector):.1f}")
    print(f"  écart-type |IQ|   : {amp.std():.1f}")
    print(f"  ratio clutter/var : {ratio:.1f}   (élevé = écho noyé sous le clutter)")

    # Sauvegarde pour ré-analyse hors-ligne
    np.save("logs/diagnostic_iq.npy", iq)
    print(f"\n  IQ décimé complexe sauvegardé → logs/diagnostic_iq.npy")

    # --- Affichage : 3 panneaux ---
    fig = plt.figure(figsize=(13, 8))

    ax1 = fig.add_subplot(2, 2, 1)
    ax1.plot(t, amp, color="darkorange", lw=0.8)
    ax1.axhline(fullscale, color="red", ls="--", lw=0.8, label="pleine échelle")
    ax1.set_title("1. Amplitude |IQ| dans le temps")
    ax1.set_xlabel("Temps (s)"); ax1.set_ylabel("|IQ|")
    ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)

    ax2 = fig.add_subplot(2, 2, 2)
    ax2.scatter(iq.real, iq.imag, s=3, alpha=0.3, color="royalblue")
    ax2.scatter([dc_vector.real], [dc_vector.imag], s=80, color="red",
                marker="x", label="vecteur statique (clutter+DC)")
    ax2.scatter([0], [0], s=40, color="black", marker="+", label="origine")
    ax2.set_title("2. Constellation I/Q")
    ax2.set_xlabel("I"); ax2.set_ylabel("Q")
    ax2.axis("equal"); ax2.legend(fontsize=8); ax2.grid(True, alpha=0.3)

    ax3 = fig.add_subplot(2, 1, 2)
    ax3.plot(t, phase_raw - phase_raw.mean(),   color="crimson", lw=1.0,
             label="phase BRUTE (angle de IQ)")
    ax3.plot(t, phase_clean - phase_clean.mean(), color="seagreen", lw=1.0,
             label="phase APRÈS retrait du clutter (angle de IQ − vecteur statique)")
    ax3.set_title("3. Phase : brute vs. clutter retiré")
    ax3.set_xlabel("Temps (s)"); ax3.set_ylabel("Phase (rad, centrée)")
    ax3.legend(fontsize=9); ax3.grid(True, alpha=0.3)

    fig.tight_layout()
    plt.show()
    print("\nDiagnostic terminé.")


if __name__ == "__main__":
    main()
