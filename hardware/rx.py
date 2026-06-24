import adi
import numpy as np
import config


def _config_rx_chain(sdr: adi.Pluto) -> None:
    """Réglages RX communs (maître et 2e récepteur)."""
    sdr.rx_lo                   = config.FC
    sdr.rx_rf_bandwidth         = config.RX_BW
    sdr.gain_control_mode_chan0 = "manual"
    sdr.rx_hardwaregain_chan0   = config.RX_GAIN
    sdr.rx_buffer_size          = config.RX_BUFFER


def config_master_rx(sdr: adi.Pluto) -> None:
    """Configure le port RX du Pluto MAÎTRE (cohérent avec son propre TX)."""
    _config_rx_chain(sdr)
    print(f"[RX1] Récepteur maître configuré à {config.FC / 1e9:.3f} GHz "
          f"— gain {config.RX_GAIN} dB (canal cohérent)")


def init_second_rx(uri: str) -> adi.Pluto:
    """Crée et configure le 2e Pluto en RÉCEPTEUR SEUL.

    Son oscillateur est indépendant de celui du maître → dérive Δf à corriger
    en logiciel via le trajet direct (voir processing/sync.py, phase 1d).
    """
    sdr = adi.Pluto(uri=uri)
    sdr.sample_rate = config.SAMPLE_RATE
    _config_rx_chain(sdr)
    print(f"[RX2] 2e récepteur configuré à {config.FC / 1e9:.3f} GHz "
          f"— gain {config.RX_GAIN} dB (canal bistatique, à synchroniser)")
    return sdr


def capture(sdr: adi.Pluto) -> np.ndarray:
    """Retourne un buffer de samples IQ complexes (complex64)."""
    return sdr.rx().astype(np.complex64)
