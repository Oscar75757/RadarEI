"""
Diagnostic IQ BRUT — où est le signal ?
=======================================
Le diagnostic décimé montrait |IQ| ≈ 0. Deux causes possibles, indiscernables
après décimation :

  (A) lien mort : rien n'arrive au récepteur.
  (B) signal présent mais à une fréquence Δf ≠ 0 → la décimation (moyenne
      complexe de 10 000 points) l'annule.

Ce script regarde l'IQ AVANT toute décimation :
  1. amplitude brute |IQ| dans un buffer       → y a-t-il de la puissance ?
  2. spectre bande de base (FFT du buffer)      → où est l'énergie : à 0 Hz, ou à Δf ?

Verdict :
  - spectre plat, amplitude minuscule        → (A) problème de lien matériel.
  - gros pic à 0 Hz                          → signal à DC : la décimation devrait
                                               le garder, chercher le bug ailleurs.
  - gros pic décalé à Δf ≠ 0                 → (B) il faut ramener le signal à 0 Hz
                                               (mélange par e^{-j2πΔf t}) avant de décimer.

Utilisation :
    source .venv/bin/activate
    python3 diagnostic_raw.py
"""

import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery import resolve_master
from hardware.tx        import init_master, start_tx, stop_tx
from hardware.rx        import config_master_rx, capture


def main():
    print("=== Diagnostic IQ BRUT (non décimé) ===\n")

    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    start_tx(sdr)

    try:
        for _ in range(3):       # on jette les premiers buffers (régime transitoire)
            capture(sdr)
        iq = capture(sdr)        # un buffer brut complet
    finally:
        stop_tx(sdr)

    fs = config.SAMPLE_RATE
    n  = len(iq)
    amp = np.abs(iq)

    # --- Spectre bande de base (centré sur 0 Hz) ---
    win  = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(iq * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1 / fs))   # Hz
    psd  = 20 * np.log10(np.abs(spec) + 1e-9)

    k_peak   = np.argmax(np.abs(spec))
    f_peak   = freq[k_peak]
    peak_db  = psd[k_peak]
    noise_db = np.median(psd)

    print(f"[mesures IQ brut]")
    print(f"  N samples         : {n}")
    print(f"  |IQ| moyen        : {amp.mean():.1f}   (pleine échelle ≈ 2048)")
    print(f"  |IQ| max          : {amp.max():.1f}")
    print(f"  pic spectral à    : {f_peak:+.0f} Hz   ({f_peak/1e3:+.2f} kHz)")
    print(f"  niveau du pic     : {peak_db:.1f} dB")
    print(f"  plancher (médiane): {noise_db:.1f} dB")
    print(f"  pic au-dessus du plancher : {peak_db - noise_db:.1f} dB")
    if abs(f_peak) < fs / n * 3:
        print("  → signal essentiellement à 0 Hz (DC).")
    else:
        print(f"  → ⚠️ signal DÉCALÉ de {f_peak:+.0f} Hz : la décimation par moyenne le détruit.")

    # --- Affichage ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    t_ms = np.arange(min(n, 4000)) / fs * 1e3
    ax1.plot(t_ms, iq.real[:len(t_ms)], lw=0.6, label="I", color="royalblue")
    ax1.plot(t_ms, iq.imag[:len(t_ms)], lw=0.6, label="Q", color="darkorange")
    ax1.set_title("1. IQ brut (4000 premiers samples) — y a-t-il de la puissance ?")
    ax1.set_xlabel("Temps (ms)"); ax1.set_ylabel("Amplitude (LSB)")
    ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)

    ax2.plot(freq / 1e3, psd, lw=0.7, color="seagreen")
    ax2.axvline(f_peak / 1e3, color="red", ls="--", lw=0.9,
                label=f"pic @ {f_peak/1e3:+.2f} kHz")
    ax2.axvline(0, color="black", ls=":", lw=0.8, label="0 Hz (DC)")
    ax2.set_title("2. Spectre bande de base — où est l'énergie ?")
    ax2.set_xlabel("Fréquence (kHz)"); ax2.set_ylabel("Puissance (dB)")
    ax2.set_xlim(-fs / 2e3, fs / 2e3)
    ax2.legend(fontsize=8); ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    plt.show()
    print("\nDiagnostic brut terminé.")


if __name__ == "__main__":
    main()
