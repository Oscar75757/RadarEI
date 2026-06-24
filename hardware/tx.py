import adi
import numpy as np
import config


def init_master(uri: str) -> adi.Pluto:
    """Crée l'objet Pluto MAÎTRE (un seul objet pilote ses ports TX ET RX).

    Le TX et le RX de ce module partagent le même oscillateur 40 MHz interne :
    leur cohérence de phase est garantie (Δf = 0). C'est ce qui rend ce canal
    exploitable pour la mesure Doppler respiratoire.
    """
    sdr = adi.Pluto(uri=uri)
    sdr.sample_rate = config.SAMPLE_RATE
    return sdr


def start_tx(sdr: adi.Pluto) -> None:
    """Configure le port TX du maître et démarre l'émission du ton à fréquence
    intermédiaire (porteuse à fc + F_IF, pas à DC — voir config.F_IF).

    Émettre à DC ne marche pas : le récepteur du Pluto annule activement le 0 Hz
    (DC offset tracking). On décale donc l'émission de F_IF ; l'écho revient à
    +F_IF, hors du notch, et on le redescend à 0 Hz en numérique côté RX.
    """
    sdr.tx_lo                  = config.FC
    sdr.tx_hardwaregain_chan0  = config.TX_GAIN
    sdr.tx_rf_bandwidth        = config.RX_BW

    # Ton complexe à F_IF en bande de base → sortie RF à fc + F_IF.
    # N choisi pour contenir un nombre ENTIER de périodes (ton cyclique propre,
    # sans discontinuité à la jonction du buffer répété).
    n_samples = config.SAMPLE_RATE // 1000          # 1000 échantillons
    t = np.arange(n_samples) / config.SAMPLE_RATE
    tone = ((2 ** 14) * np.exp(2j * np.pi * config.F_IF * t)).astype(np.complex64)

    sdr.tx_cyclic_buffer = True   # répète le buffer indéfiniment
    sdr.tx(tone)

    print(f"[TX] Émission à {(config.FC + config.F_IF) / 1e9:.6f} GHz "
          f"(fc + {config.F_IF/1e3:.0f} kHz) — gain {config.TX_GAIN} dBm")


def stop_tx(sdr: adi.Pluto) -> None:
    sdr.tx_destroy_buffer()
    print("[TX] Émission arrêtée.")
