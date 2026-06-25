"""
record.py — Enregistrement longue durée (étude de sommeil)
==========================================================
Lance la surveillance temps-réel (vue identique à phase1c) ET enregistre le
signal de phase sur disque, pour analyse offline ultérieure (analyze.py).

Sert par exemple à dépister l'apnée du sommeil sur une nuit entière.

Utilisation :
    source .venv/bin/activate
    python3 record.py                 # enregistre jusqu'à Ctrl+C
    python3 record.py --duree 8       # s'arrête seul après 8 h (Ctrl+C marche aussi)
    python3 record.py --minutes 3     # test court : s'arrête seul après 3 min

Sortie (dans recordings/) :
    rec_*_phase.f32  : signal de phase (source pour l'analyse)
    rec_*_meta.json  : métadonnées (fréquence, horodatage, config)
    rec_*_apnea.csv  : apnées repérées en direct (repères ; l'analyse fait foi)

Puis :  python3 analyze.py            # analyse le dernier enregistrement
"""

import argparse
import phase1c


def main():
    p = argparse.ArgumentParser(description="Enregistrement respiratoire longue durée.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--duree", type=float, default=None, metavar="HEURES",
                   help="durée maximale en heures (sinon : arrêt manuel par Ctrl+C)")
    g.add_argument("--minutes", type=float, default=None, metavar="MIN",
                   help="durée maximale en minutes (test court)")
    args = p.parse_args()

    duration_h = args.duree
    if args.minutes is not None:
        duration_h = args.minutes / 60.0

    print("=== Enregistrement longue durée ===")
    if duration_h:
        mins = duration_h * 60
        label = f"{mins:.0f} min" if mins < 60 else f"{duration_h:g} h"
        print(f"    Arrêt automatique après {label} (ou Ctrl+C).\n")
    else:
        print("    Arrêt par Ctrl+C.\n")

    phase1c.main(record=True, duration_h=duration_h)


if __name__ == "__main__":
    main()
