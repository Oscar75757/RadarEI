import json
import os
import time
from datetime import datetime

import numpy as np
import config


class RecordWriter:
    """Enregistre une séance longue durée sur disque, au fil de l'eau.

    Trois fichiers dans recordings/ (préfixe rec_AAAAMMJJ_HHMMSS) :
      - *_phase.f32  : signal de phase φ(t) décimé, float32 brut (np.fromfile pour relire).
                       C'est le signal « source » : tout se recalcule offline à partir de lui.
      - *_meta.json  : fréquence d'échantillonnage, horodatage, config RF, durée.
      - *_apnea.csv  : événements d'apnée détectés EN DIRECT (repères de confort ;
                       l'analyse de référence se fait offline avec analyze.py).

    L'écriture du signal est flushée régulièrement → une coupure de courant ne fait
    perdre que les toutes dernières secondes, jamais toute la nuit.
    """

    def __init__(self, fs: float, directory: str = "recordings",
                 duration_h: float | None = None, note: str = ""):
        os.makedirs(directory, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base = f"rec_{stamp}"
        prefix = os.path.join(directory, self.base)
        self.phase_path  = prefix + "_phase.f32"
        self.meta_path   = prefix + "_meta.json"
        self.events_path = prefix + "_apnea.csv"

        self._phase_f = open(self.phase_path, "wb")
        self._events_f = open(self.events_path, "w")
        self._events_f.write("debut_s,fin_s,duree_s\n")
        self._events_f.flush()

        self.fs = fs
        self.duration_h = duration_h
        self._n = 0
        self._t0 = time.time()
        self._last_flush = self._t0
        self.n_apneas = 0

        self._meta = {
            "debut": datetime.now().isoformat(timespec="seconds"),
            "fs_hz": fs,
            "fc_hz": config.FC,
            "f_if_hz": config.F_IF,
            "dtype": "float32",
            "signal": "phase decimee continue (rad)",
            "duree_cible_h": duration_h,
            "note": note,
        }
        self._write_meta()

    def write(self, phase_chunk) -> None:
        """Ajoute un bloc d'échantillons de phase au fichier signal."""
        a = np.asarray(phase_chunk, dtype=np.float32)
        a.tofile(self._phase_f)
        self._n += len(a)
        now = time.time()
        if now - self._last_flush >= 5.0:      # flush sur disque toutes les 5 s
            self._phase_f.flush()
            self._last_flush = now

    def log_apnea(self, start_s: float, end_s: float) -> None:
        self._events_f.write(f"{start_s:.1f},{end_s:.1f},{end_s - start_s:.1f}\n")
        self._events_f.flush()
        self.n_apneas += 1

    def signal_time(self) -> float:
        """Position courante dans le signal enregistré (s)."""
        return self._n / self.fs

    def elapsed(self) -> float:
        """Temps réel écoulé depuis le début de l'enregistrement (s)."""
        return time.time() - self._t0

    def duration_reached(self) -> bool:
        return self.duration_h is not None and self.elapsed() >= self.duration_h * 3600

    def _write_meta(self) -> None:
        m = dict(self._meta)
        m["n_samples"] = self._n
        m["duree_s"] = self._n / self.fs
        m["fin"] = datetime.now().isoformat(timespec="seconds")
        with open(self.meta_path, "w") as f:
            json.dump(m, f, indent=2, ensure_ascii=False)

    def close(self) -> None:
        self._phase_f.flush()
        self._phase_f.close()
        self._events_f.close()
        self._write_meta()
