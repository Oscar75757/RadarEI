"""
Diagnostic TON DÉCALÉ — la liaison TX→RX est-elle vivante ?
==========================================================
L'IQ brut était au plancher de bruit (±1-3 LSB). Émettre à DC ne permet pas de
trancher : le signal se confond avec l'offset DC du récepteur.

Ici on émet un ton à F_IF = +100 kHz (porteuse à fc + 100 kHz), à PLEINE
puissance. Si la chaîne fonctionne, ce ton réapparaît **à +100 kHz** dans le
spectre du récepteur, bien séparé du DC.

Verdict :
  - gros pic à +100 kHz                 → liaison TX→RX VIVANTE. Le souci venait
                                          du choix d'émettre à DC : on adoptera
                                          une architecture à ton décalé (IF).
  - rien à +100 kHz, plancher partout   → liaison MORTE : vérifier câbles SMA,
                                          ports TX/RX, émission réelle du TX.

Utilisation :
    source .venv/bin/activate
    python3 diagnostic_tone.py
"""

import numpy as np
import matplotlib.pyplot as plt

import config
from hardware.discovery import resolve_master
from hardware.tx        import init_master, stop_tx
from hardware.rx        import config_master_rx, capture

F_IF      = 100_000      # décalage du ton (Hz) — bien séparé du DC
N_TONE    = 1000         # 100 périodes exactes dans le buffer (ton cyclique propre)
RX_BW_DIAG = 600_000     # filtre RX élargi pour voir ±100 kHz


def main():
    print("=== Diagnostic ton décalé (+100 kHz) — liaison TX→RX ===\n")

    sdr = init_master(resolve_master())
    config_master_rx(sdr)
    sdr.rx_rf_bandwidth = RX_BW_DIAG

    # --- TX : ton complexe à +100 kHz, pleine puissance ---
    sdr.tx_lo                 = config.FC
    sdr.tx_hardwaregain_chan0 = 0            # atténuation 0 dB = puissance max
    sdr.tx_rf_bandwidth       = RX_BW_DIAG
    t    = np.arange(N_TONE) / config.SAMPLE_RATE
    tone = ((2 ** 14) * np.exp(2j * np.pi * F_IF * t)).astype(np.complex64)
    sdr.tx_cyclic_buffer = True
    sdr.tx(tone)
    print(f"[TX] ton à fc + {F_IF/1e3:.0f} kHz, gain 0 dB (puissance max)")

    try:
        for _ in range(5):       # purge des buffers transitoires
            capture(sdr)
        iq = capture(sdr)
    finally:
        stop_tx(sdr)

    fs  = config.SAMPLE_RATE
    n   = len(iq)
    amp = np.abs(iq)

    win  = np.hanning(n)
    spec = np.fft.fftshift(np.fft.fft(iq * win))
    freq = np.fft.fftshift(np.fft.fftfreq(n, d=1 / fs))
    psd  = 20 * np.log10(np.abs(spec) + 1e-9)

    # niveau dans une fenêtre autour de F_IF
    band   = np.abs(freq - F_IF) < 5_000
    if_db  = psd[band].max()
    if_f   = freq[band][np.argmax(psd[band])]
    dc_db  = psd[np.abs(freq) < 2_000].max()
    floor  = np.median(psd)
    fullscale = 2 ** 11

    print(f"\n[mesures]")
    print(f"  |IQ| moyen / max      : {amp.mean():.1f} / {amp.max():.1f}   "
          f"(pleine échelle ≈ {fullscale})  {'⚠️ SATURATION' if amp.max() > 0.9*fullscale else ''}")
    print(f"  niveau @ +100 kHz     : {if_db:.1f} dB   (pic à {if_f/1e3:+.1f} kHz)")
    print(f"  niveau @ DC           : {dc_db:.1f} dB")
    print(f"  plancher (médiane)    : {floor:.1f} dB")
    print(f"  ton au-dessus du plancher : {if_db - floor:.1f} dB")
    if if_db - floor > 20:
        print("  → ✅ liaison TX→RX VIVANTE. Le ton décalé est bien reçu.")
    else:
        print("  → ❌ liaison MORTE : aucun ton reçu. Vérifier câbles SMA / ports / émission TX.")

    # --- Affichage ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    t_ms = np.arange(min(n, 4000)) / fs * 1e3
    ax1.plot(t_ms, iq.real[:len(t_ms)], lw=0.6, label="I", color="royalblue")
    ax1.plot(t_ms, iq.imag[:len(t_ms)], lw=0.6, label="Q", color="darkorange")
    ax1.set_title("1. IQ brut — si la liaison vit, on voit une sinusoïde à 100 kHz")
    ax1.set_xlabel("Temps (ms)"); ax1.set_ylabel("Amplitude (LSB)")
    ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)

    ax2.plot(freq / 1e3, psd, lw=0.7, color="seagreen")
    ax2.axvline(F_IF / 1e3, color="red", ls="--", lw=1.0, label="ton émis (+100 kHz)")
    ax2.axvline(0, color="black", ls=":", lw=0.8, label="0 Hz (DC)")
    ax2.set_title("2. Spectre RX — le ton émis réapparaît-il à +100 kHz ?")
    ax2.set_xlabel("Fréquence (kHz)"); ax2.set_ylabel("Puissance (dB)")
    ax2.legend(fontsize=8); ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    plt.show()
    print("\nDiagnostic ton terminé.")


if __name__ == "__main__":
    main()
