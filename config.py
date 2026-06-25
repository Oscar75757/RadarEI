# =============================================================================
# Configuration centrale — Radar Doppler CW pour monitoring respiratoire
# Modifier uniquement ce fichier pour ajuster les paramètres du système.
# =============================================================================

# --- Identifiants des modules PlutoSDR (par NUMÉRO DE SÉRIE, stable) ---
# L'URI usb:bus.port.addr change à chaque branchement/reboot ; la série, non.
# Le code retrouve tout seul l'URI courant de chaque rôle (hardware/discovery.py).
# Pluto 1 = MAÎTRE : émet la CW ET reçoit (canal cohérent, LO partagé).
# Pluto 2 = récepteur SEUL : 2e point de vue, synchronisé en logiciel (phase 1d).
SERIAL_MASTER = "104473b80a160002ebff25003058be8bb8"   # maître TX+RX (AD9364, débridé)
SERIAL_RX2    = "104473b80a160002ebff25003058be8bb8"   # récepteur seul

# Active le 2e récepteur (diversité spatiale). False = on travaille sur le seul
# Pluto maître (recommandé pour la mise au point de la phase 1).
USE_SECOND_RX = True

# --- Paramètres RF ---
FC          = 2_400_000_000   # Fréquence porteuse : 2.4 GHz
TX_GAIN     = -10             # Gain TX en dBm (entre -89 et 0)
RX_GAIN     = 40              # Gain RX en dB  (mode manuel)
SAMPLE_RATE = 1_000_000       # Taux d'échantillonnage : 1 MSPS
RX_BW       = 500_000         # Bande passante RX : doit laisser passer le ton IF (±F_IF)
RX_BUFFER   = 100_000        # Taille du buffer IQ par capture — MULTIPLE de DECIMATION
                             # (10 000) → décimation sans reste, base de temps EXACTE.
                             # Indispensable pour mesurer durées/rythmes et l'IAH d'une
                             # nuit (sinon ~8.5 % du signal jeté = temps comprimé). 0.1 s.

# --- Fréquence intermédiaire (architecture à ton décalé) ---
# On émet à fc + F_IF (pas à DC) pour échapper au "DC offset tracking" du Pluto,
# qui annule activement tout signal à 0 Hz (c'est ce qui tuait l'écho à DC).
# Côté réception, on redescend numériquement le signal à 0 Hz (Downconverter) :
# l'offset DC, la fuite LO et le clutter statique se retrouvent à -F_IF et sont
# éliminés par la décimation (moyenne = passe-bas à ~100 Hz).
F_IF        = 100_000         # 100 kHz — bien au-delà du notch DC du récepteur

# --- Décimation ---
# Le signal respiratoire est < 1 Hz.
# On décime 1 MSPS → DECIMATED_FS pour alléger le traitement.
DECIMATION    = 10_000        # facteur de décimation
DECIMATED_FS  = SAMPLE_RATE // DECIMATION   # = 100 Hz effectifs

# --- Filtre d'AFFICHAGE (suppression de dérive, faible latence) ---
# Coupure basse volontairement plus basse que la bande respiratoire : une
# respiration lente (~0.1-0.13 Hz) tombe sinon sur le bord du filtre, où le
# retard de groupe explose (jusqu'à ~5 s à 6-7 resp/min). À 0.05 Hz + ordre 2,
# le retard reste sous la seconde. La dérive du corps (< 0.05 Hz) est éliminée.
FILTER_LOW   = 0.05   # Hz — passe-haut du filtre d'affichage
FILTER_HIGH  = 0.8    # Hz — passe-bas (anti-jitter)
FILTER_ORDER = 2      # ordre du filtre Butterworth

# --- Bande de DÉTECTION du rythme (recherche du pic FFT) ---
# C'est la FFT qui restreint à la vraie gamme respiratoire : la mesure du
# rythme reste juste même si le filtre laisse passer un peu de dérive lente.
F_LOW   = 0.1     # Hz — 6 resp/min  (seuil bas pathologique)
F_HIGH  = 0.8     # Hz — 48 resp/min (seuil haut pathologique)

# --- Fenêtre d'analyse FFT (CALCULS + ALERTES) ---
# Fenêtre raccourcie pour réduire la latence ; la résolution plus grossière
# (~4 resp/min) est récupérée par interpolation parabolique du pic FFT, qui
# estime la fréquence ENTRE les points de la FFT. Lissage réduit à 2.
WINDOW_S    = 14.0   # durée de la fenêtre glissante (s)
OVERLAP     = 0.9    # chevauchement (90 % → nouvelle estimation toutes les ~1.4 s)

# --- Rythme temps-réel pour AFFICHAGE (méthode temporelle, levier 4) ---
# Mesure le rythme par l'intervalle entre pics d'inspiration successifs : se met
# à jour à CHAQUE respiration (quasi temps-réel), moyenné sur les derniers pics
# pour limiter les fluctuations. Réservé à l'affichage (bruité si irrégulier).
PEAK_RATE_NPEAKS     = 3      # nombre de pics d'inspiration moyennés
PEAK_HYSTERESIS_FRAC = 0.2    # seuil de confirmation d'un pic = frac × amplitude
                              # (amplitude = crête-à-crête ≈ pleine oscillation)
PEAK_MIN_DELTA       = 0.02   # seuil mini absolu (rad) — anti-bruit
PEAK_REFRACTORY_S    = 1.2    # intervalle mini entre 2 pics (≈ 50 resp/min max)
PEAK_STALE_S         = 12.0   # sans pic depuis ce délai → rythme affiché = —

# --- Seuils d'alerte ---
# APNEA_DELAY_S = temps de CONFIRMATION sous le seuil d'amplitude avant l'alarme.
# La fenêtre d'amplitude (AMP_WINDOW_S = 8 s) absorbe déjà ~8 s avant de passer
# sous le seuil ; l'alarme tombe donc ~8 s + APNEA_DELAY_S après l'arrêt réel.
APNEA_DELAY_S  = 0    # secondes sous le seuil → alerte apnée
BRADY_RPM      = 8    # resp/min minimum normal
TACHY_RPM      = 30   # resp/min maximum normal

# --- Détection d'apnée par ABSENCE d'oscillation ---
# L'apnée ne se voit pas au niveau absolu (le passe-haut fait retomber un
# signal figé vers zéro), mais à la CHUTE D'AMPLITUDE. On mesure l'amplitude
# CRÊTE-À-CRÊTE (p95−p5) de la PHASE BRUTE détrendée sur une fenêtre glissante ;
# sous le seuil = plus de respiration. Crête-à-crête (et non écart-type) car
# celui-ci ondule quand la fenêtre ne couvre pas un nombre entier de périodes.
AMP_WINDOW_S     = 8.0    # fenêtre glissante de mesure d'amplitude (s) — mesurée
                          # sur la phase BRUTE détrendée. Doit couvrir CONFORTABLEMENT
                          # une période respiratoire, sinon l'amplitude crête-à-crête
                          # ondule (instable < 1 période). 8 s → stable dès ~10/min ;
                          # réaction à l'apnée ~8 s + APNEA_DELAY_S (≈ seuil clinique 10 s).
APNEA_AMP_EPS    = 1e-4   # epsilon anti-division-par-zéro (PAS un seuil de détection :
                          # le seuil est purement RELATIF, donc indépendant de
                          # l'antenne/distance/gain — voir le seuil adaptatif ci-dessous).

# --- Seuil d'apnée ADAPTATIF (auto-calibré sur le patient, PUREMENT RELATIF) ---
# seuil = fraction × baseline, baseline = amplitude respiratoire « habituelle »
# suivie par EMA LENTE qui s'adapte EN PERMANENCE (pas de gel). Conséquences :
#  - indépendant de l'antenne : seuil relatif à la respiration courante ;
#  - jamais bloqué : une calibration ratée se corrige toute seule (~τ), ou
#    instantanément via la re-calibration manuelle (touche « c ») ;
#  - l'apnée reste détectée car l'amplitude s'effondre bien sous le seuil
#    pendant ~70 s avant que la baseline ait assez décru (>> seuil clinique).
# Hystérésis (enter/exit) anti-flicker.
WARMUP_S            = 10.0   # délai de calibration au démarrage (patient s'installe)
APNEA_BASELINE_TAU_S = 35.0  # constante de temps de l'EMA de baseline (s)
APNEA_FRAC_ENTER    = 0.25   # entrée en apnée si amplitude < 0.25 × baseline
APNEA_FRAC_EXIT     = 0.40   # sortie d'apnée si amplitude > 0.40 × baseline

# --- Lissage temporel ---
SMOOTHING_N = 2   # nombre d'estimations FFT à moyenner

# --- Affichage ---
PLOT_WINDOW_S = 30   # durée visible sur le graphe temps-réel (secondes)

# --- MQTT (monitoring web) ---
MQTT_BROKER      = "broker.hivemq.com"   # broker public gratuit, sans compte
MQTT_PORT        = 1883
MQTT_PREFIX      = "radar/louis"         # préfixe topic — à personnaliser
MQTT_WAVE_POINTS = 150                   # points de courbe envoyés par message
