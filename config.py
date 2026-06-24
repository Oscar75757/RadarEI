# =============================================================================
# Configuration centrale — Radar Doppler CW pour monitoring respiratoire
# Modifier uniquement ce fichier pour ajuster les paramètres du système.
# =============================================================================

# --- Identifiants des modules PlutoSDR (par NUMÉRO DE SÉRIE, stable) ---
# L'URI usb:bus.port.addr change à chaque branchement/reboot ; la série, non.
# Le code retrouve tout seul l'URI courant de chaque rôle (hardware/discovery.py).
# Pluto 1 = MAÎTRE : émet la CW ET reçoit (canal cohérent, LO partagé).
# Pluto 2 = récepteur SEUL : 2e point de vue, synchronisé en logiciel (phase 1d).
SERIAL_MASTER = "104473dcbc0d000b0400340077bd47a811"   # maître TX+RX (AD9364, débridé)
SERIAL_RX2    = "104473dcbc0d000b130035004db947f3a5"   # récepteur seul

# Active le 2e récepteur (diversité spatiale). False = on travaille sur le seul
# Pluto maître (recommandé pour la mise au point de la phase 1).
USE_SECOND_RX = True

# --- Paramètres RF ---
FC          = 2_400_000_000   # Fréquence porteuse : 2.4 GHz
TX_GAIN     = -10             # Gain TX en dBm (entre -89 et 0)
RX_GAIN     = 40              # Gain RX en dB  (mode manuel)
SAMPLE_RATE = 1_000_000       # Taux d'échantillonnage : 1 MSPS
RX_BW       = 500_000         # Bande passante RX : doit laisser passer le ton IF (±F_IF)
RX_BUFFER   = 1024 * 64      # Taille du buffer IQ par capture

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

# --- Fenêtre d'analyse FFT ---
WINDOW_S    = 20.0   # durée de la fenêtre glissante en secondes (résolution ~3 resp/min)
OVERLAP     = 0.9    # chevauchement (90 % → nouvelle estimation toutes les 2 s)

# --- Seuils d'alerte ---
APNEA_DELAY_S  = 15   # secondes sans détection → alerte apnée
BRADY_RPM      = 8    # resp/min minimum normal
TACHY_RPM      = 30   # resp/min maximum normal

# --- Lissage temporel ---
SMOOTHING_N = 3   # nombre d'estimations à moyenner

# --- Affichage ---
PLOT_WINDOW_S = 30   # durée visible sur le graphe temps-réel (secondes)
