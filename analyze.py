"""
analyze.py — Analyse offline d'un enregistrement (dépistage apnée du sommeil)
=============================================================================
Charge un enregistrement produit par record.py et en extrait :
  - l'enveloppe d'amplitude respiratoire et le rythme au fil du temps ;
  - les ÉVÉNEMENTS D'APNÉE (amplitude effondrée ≥ MIN_APNEE_S) ;
  - l'INDICE d'apnées (apnées/heure) et la sévérité.

Atout de l'offline : la baseline de référence est NON-CAUSALE (médiane glissante
centrée) — bien plus robuste que l'EMA temps-réel, et insensible aux changements
de position pendant la nuit.

Utilisation :
    source .venv/bin/activate
    python3 analyze.py                          # dernier enregistrement
    python3 analyze.py recordings/rec_XXXX       # un enregistrement précis (préfixe)

Sorties : un rapport console, un CSV d'événements et un graphe PNG (dans recordings/).
"""

import argparse
import glob
import json
import os

import numpy as np
from scipy.signal import butter, sosfiltfilt, hilbert
from scipy.ndimage import median_filter, uniform_filter1d
import matplotlib.pyplot as plt

import config

# --- Paramètres d'analyse ---
ENV_HOP_S       = 1.0    # pas d'échantillonnage de l'enveloppe d'amplitude (s)
BASELINE_HALF_S = 120.0  # demi-fenêtre de la baseline non-causale (médiane ±2 min)
MIN_APNEE_S     = 10.0   # durée minimale d'un événement d'apnée (définition clinique)
RATE_HOP_S      = 5.0    # pas de calcul du rythme (s)


def find_recording(arg: str | None) -> str:
    """Retourne le préfixe (…/rec_XXXX) d'un enregistrement."""
    if arg:
        base = arg[:-len("_phase.f32")] if arg.endswith("_phase.f32") else arg
        if not os.path.exists(base + "_meta.json"):
            raise SystemExit(f"Introuvable : {base}_meta.json")
        return base
    metas = sorted(glob.glob("recordings/*_meta.json"), key=os.path.getmtime)
    if not metas:
        raise SystemExit("Aucun enregistrement dans recordings/ (lance record.py d'abord).")
    return metas[-1][:-len("_meta.json")]


def rate_at(window: np.ndarray, fs: float) -> float:
    """Rythme (resp/min) par FFT + interpolation parabolique sur une fenêtre."""
    x = np.arange(len(window))
    slope, intercept = np.polyfit(x, window, 1)
    w = (window - (slope * x + intercept)) * np.hanning(len(window))
    spec  = np.abs(np.fft.rfft(w))
    freqs = np.fft.rfftfreq(len(w), d=1.0 / fs)
    df    = freqs[1] - freqs[0]
    band  = np.where((freqs >= config.F_LOW) & (freqs <= config.F_HIGH))[0]
    if band.size == 0:
        return np.nan
    k = band[np.argmax(spec[band])]
    if 0 < k < len(spec) - 1:
        a, b, c = spec[k - 1], spec[k], spec[k + 1]
        denom = a - 2 * b + c
        delta = float(np.clip(0.5 * (a - c) / denom, -0.5, 0.5)) if denom != 0 else 0.0
    else:
        delta = 0.0
    return (freqs[k] + delta * df) * 60.0


def find_events(below: np.ndarray, hop_s: float, min_s: float):
    """Repère les plages contiguës `below` durant ≥ min_s. Retourne [(i0, i1), ...]."""
    events = []
    i = 0
    n = len(below)
    while i < n:
        if below[i]:
            j = i
            while j < n and below[j]:
                j += 1
            if (j - i) * hop_s >= min_s:
                events.append((i, j))
            i = j
        else:
            i += 1
    return events


def main():
    p = argparse.ArgumentParser(description="Analyse d'un enregistrement respiratoire.")
    p.add_argument("recording", nargs="?", default=None,
                   help="préfixe de l'enregistrement (défaut : le plus récent)")
    args = p.parse_args()

    base = find_recording(args.recording)
    with open(base + "_meta.json", encoding="utf-8") as f:
        meta = json.load(f)
    fs = float(meta["fs_hz"])
    phase = np.fromfile(base + "_phase.f32", dtype=np.float32)
    total_s = len(phase) / fs
    print(f"=== Analyse de {os.path.basename(base)} ===")
    print(f"  Début : {meta.get('debut', '?')}  |  durée : {total_s/3600:.2f} h "
          f"({len(phase)} échantillons @ {fs:.0f} Hz)\n")

    if total_s < config.WARMUP_S + 2 * MIN_APNEE_S:
        raise SystemExit("Enregistrement trop court pour une analyse.")

    # --- Enveloppe d'amplitude par transformée de Hilbert (offline, non-causale) ---
    # Amplitude INSTANTANÉE : chute en ~1 cycle, sans la sous-estimation d'une
    # fenêtre glissante (qui ratait les apnées courtes). On filtre d'abord en
    # bande respiratoire (zéro-phase), puis enveloppe = |signal analytique|, lissée.
    sos  = butter(config.FILTER_ORDER,
                  [config.FILTER_LOW / (fs / 2), config.FILTER_HIGH / (fs / 2)],
                  btype="band", output="sos")
    filt = sosfiltfilt(sos, phase)
    env  = np.abs(hilbert(filt))
    env  = uniform_filter1d(env, max(1, int(2.0 * fs)))   # lisse le résiduel à 2f

    hop = int(ENV_HOP_S * fs)
    t_env   = np.arange(0, len(phase), hop) / fs
    amp_env = env[::hop]

    # --- Baseline NON-CAUSALE : médiane glissante centrée (robuste à la nuit) ---
    k = int(2 * BASELINE_HALF_S / ENV_HOP_S) | 1          # taille impaire
    baseline = median_filter(amp_env, size=k, mode="nearest")
    threshold = config.APNEA_FRAC_ENTER * baseline

    # --- Détection des apnées ---
    below = amp_env < threshold
    events_idx = find_events(below, ENV_HOP_S, MIN_APNEE_S)
    events = [(t_env[i0], t_env[min(i1, len(t_env) - 1)]) for i0, i1 in events_idx]

    # --- Rythme au fil du temps (masqué hors respiration : non significatif) ---
    rwin = int(config.WINDOW_S * fs)
    rhop = int(RATE_HOP_S * fs)
    ridx = np.arange(rwin, len(phase) + 1, rhop)
    t_rate = ridx / fs
    rate = np.array([rate_at(phase[i - rwin:i], fs) for i in ridx])
    # Pendant l'apnée, la FFT accroche le cœur → rythme faux. On masque (NaN) tout
    # rythme dont la fenêtre FFT (WINDOW_S) CHEVAUCHE une apnée — sinon un pic
    # parasite subsiste à la reprise, tant que la fenêtre contient encore l'apnée.
    below_env = amp_env < threshold
    wlen = int(config.WINDOW_S / ENV_HOP_S)
    kk = np.clip((t_rate / ENV_HOP_S).astype(int), 0, len(below_env) - 1)
    valid = np.array([not below_env[max(0, k - wlen):k + 1].any() for k in kk])
    rate = np.where(valid, rate, np.nan)

    # --- Statistiques ---
    hours = total_s / 3600.0
    durations = np.array([e1 - e0 for e0, e1 in events])
    n_apnees = len(events)
    ai = n_apnees / hours if hours > 0 else 0.0
    mean_rate = float(np.nanmean(rate)) if np.any(~np.isnan(rate)) else float("nan")

    sev = ("normal" if ai < 5 else "léger" if ai < 15
           else "modéré" if ai < 30 else "sévère")

    print("--- RAPPORT ---")
    print(f"  Apnées (≥ {MIN_APNEE_S:.0f} s)      : {n_apnees}")
    print(f"  Indice d'apnées (IA)      : {ai:.1f} /h   → {sev}")
    if n_apnees:
        print(f"  Apnée la plus longue      : {durations.max():.0f} s")
        print(f"  Durée totale en apnée     : {durations.sum():.0f} s "
              f"({100*durations.sum()/total_s:.1f} % de la nuit)")
    print(f"  Rythme respiratoire moyen : {mean_rate:.1f} resp/min")
    print("  (IA = apnées seules ; l'IAH clinique inclut aussi les hypopnées.)\n")

    # --- Export CSV des événements ---
    evt_csv = base + "_evenements.csv"
    with open(evt_csv, "w") as f:
        f.write("debut_s,fin_s,duree_s,debut_hms\n")
        for e0, e1 in events:
            hms = f"{int(e0)//3600:02d}:{(int(e0)%3600)//60:02d}:{int(e0)%60:02d}"
            f.write(f"{e0:.1f},{e1:.1f},{e1-e0:.1f},{hms}\n")
    print(f"  Événements → {evt_csv}")

    # --- Graphes ---
    fig, (axA, axR, axH) = plt.subplots(3, 1, figsize=(13, 9))
    th = t_env / 3600.0
    axA.plot(th, amp_env, color="steelblue", lw=0.8, label="amplitude")
    axA.plot(th, baseline, color="green", lw=1.0, label="baseline (médiane glissante)")
    axA.plot(th, threshold, color="red", ls="--", lw=0.9, label="seuil apnée")
    for e0, e1 in events:
        axA.axvspan(e0 / 3600, e1 / 3600, color="red", alpha=0.25)
    axA.set_ylabel("Amplitude (rad)"); axA.set_xlabel("Temps (h)")
    axA.set_title(f"{os.path.basename(base)} — {n_apnees} apnées, IA = {ai:.1f}/h ({sev})")
    axA.legend(fontsize=8, loc="upper right"); axA.grid(True, alpha=0.3)

    axR.plot(t_rate / 3600.0, rate, color="darkorange", lw=0.8)
    axR.axhline(config.BRADY_RPM, color="gray", ls=":", lw=0.8)
    axR.axhline(config.TACHY_RPM, color="gray", ls=":", lw=0.8)
    axR.set_ylabel("Rythme (resp/min)"); axR.set_xlabel("Temps (h)")
    axR.grid(True, alpha=0.3)

    if n_apnees:
        axH.hist(durations, bins=20, color="crimson", alpha=0.8)
    axH.set_xlabel("Durée des apnées (s)"); axH.set_ylabel("Nombre")
    axH.grid(True, alpha=0.3)

    fig.tight_layout()
    png = base + "_analyse.png"
    fig.savefig(png, dpi=110)
    print(f"  Graphe     → {png}")
    plt.show()


if __name__ == "__main__":
    main()
