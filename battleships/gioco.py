"""
Le regole della battaglia navale, in Python puro.
Niente Redis, niente sito web: solo il gioco.

Puoi provarlo nel terminale con:  python gioco.py
"""
import random

# Dimensione della griglia: 10 x 10
DIMENSIONE = 10

# Le righe si chiamano A..J, le colonne 1..10 (come nel gioco da tavolo)
LETTERE = "ABCDEFGHIJ"

# Le navi della flotta: nome -> lunghezza
FLOTTA = {
    "portaerei": 5,
    "corazzata": 4,
    "incrociatore": 3,
    "sottomarino": 3,
    "cacciatorpediniere": 2,
}


def testo_a_cella(testo):
    """Trasforma 'B5' in (1, 4): riga e colonna partendo da 0.
    Restituisce None se il testo non è valido."""
    testo = testo.strip().upper()
    if len(testo) < 2 or testo[0] not in LETTERE:
        return None
    try:
        colonna = int(testo[1:]) - 1
    except ValueError:
        return None
    if not 0 <= colonna < DIMENSIONE:
        return None
    return (LETTERE.index(testo[0]), colonna)


def cella_a_testo(cella):
    """Trasforma (1, 4) in 'B5'."""
    riga, colonna = cella
    return f"{LETTERE[riga]}{colonna + 1}"


class Griglia:
    """La griglia di UN giocatore: le sue navi e i colpi ricevuti."""

    def __init__(self):
        # nome nave -> insieme delle celle che occupa, es. {"sottomarino": {(0,0), (0,1), (0,2)}}
        self.navi = {}
        # insieme delle celle su cui l'avversario ha già sparato
        self.colpi_ricevuti = set()

    # ---------- Posizionamento delle navi ----------

    def posiziona_nave(self, nome, riga, colonna, orizzontale):
        """Prova a mettere una nave. Restituisce True se ci riesce, False se non è valida."""
        if nome not in FLOTTA or nome in self.navi:
            return False

        lunghezza = FLOTTA[nome]
        if orizzontale:
            celle = {(riga, colonna + i) for i in range(lunghezza)}
        else:
            celle = {(riga + i, colonna) for i in range(lunghezza)}

        # Controllo 1: la nave deve stare tutta dentro la griglia
        for r, c in celle:
            if not (0 <= r < DIMENSIONE and 0 <= c < DIMENSIONE):
                return False

        # Controllo 2: non deve sovrapporsi a un'altra nave
        for altre_celle in self.navi.values():
            if celle & altre_celle:   # "&" = celle in comune tra i due insiemi
                return False

        self.navi[nome] = celle
        return True

    def posiziona_casuale(self):
        """Mette tutta la flotta in posizioni casuali (usato dal computer)."""
        self.navi = {}
        for nome in FLOTTA:
            # Riprova finché non trova una posizione valida
            while not self.posiziona_nave(
                nome,
                random.randrange(DIMENSIONE),
                random.randrange(DIMENSIONE),
                random.choice([True, False]),
            ):
                pass

    # ---------- Il colpo ----------

    def ricevi_colpo(self, cella):
        """L'avversario spara su una cella. Restituisce una di queste risposte:
        'già_sparato', 'acqua', 'colpito', 'affondato'"""
        if cella in self.colpi_ricevuti:
            return "già_sparato", None
        self.colpi_ricevuti.add(cella)

        for nome, celle in self.navi.items():
            if cella in celle:
                # La nave è affondata se TUTTE le sue celle sono state colpite
                if celle <= self.colpi_ricevuti:   # "<=" = "è contenuto in"
                    return "affondato", nome
                return "colpito", nome

        return "acqua", None

    def tutte_affondate(self):
        """True se tutte le navi sono state affondate: partita persa."""
        tutte_le_celle = set().union(*self.navi.values())
        return tutte_le_celle <= self.colpi_ricevuti

    # ---------- Disegno nel terminale ----------

    def disegna(self, mostra_navi):
        """Disegna la griglia come testo.
        mostra_navi=False -> vista dell'avversario (le navi non colpite restano nascoste)."""
        celle_navi = set().union(*self.navi.values()) if self.navi else set()
        righe = ["   " + " ".join(f"{c + 1:>2}" for c in range(DIMENSIONE))]
        for r in range(DIMENSIONE):
            simboli = []
            for c in range(DIMENSIONE):
                cella = (r, c)
                if cella in self.colpi_ricevuti:
                    simboli.append(" X" if cella in celle_navi else " ~")
                elif mostra_navi and cella in celle_navi:
                    simboli.append(" #")
                else:
                    simboli.append(" .")
            righe.append(f" {LETTERE[r]} " + " ".join(simboli))
        return "\n".join(righe)


# ---------- Partita di prova nel terminale ----------
if __name__ == "__main__":
    nemico = Griglia()
    nemico.posiziona_casuale()

    print("⚓ Battaglia navale - prova nel terminale")
    print("Spara scrivendo una cella, es. B5. Scrivi 'esci' per smettere, 'trucco' per vedere le navi.\n")
    colpi = 0

    while not nemico.tutte_affondate():
        print(nemico.disegna(mostra_navi=False))
        scelta = input("\nDove spari? ")

        if scelta.lower() == "esci":
            break
        if scelta.lower() == "trucco":
            print(nemico.disegna(mostra_navi=True), "\n")
            continue

        cella = testo_a_cella(scelta)
        if cella is None:
            print("❗ Cella non valida, usa il formato A1 ... J10\n")
            continue

        risultato, nave = nemico.ricevi_colpo(cella)
        if risultato == "già_sparato":
            print("❗ Hai già sparato lì\n")
            continue

        colpi += 1
        messaggi = {
            "acqua": "🌊 Acqua",
            "colpito": f"💥 Colpito! ({nave})",
            "affondato": f"🔥 Colpito e affondato: {nave}!",
        }
        print(f"{cella_a_testo(cella)}: {messaggi[risultato]}\n")
    else:
        print(nemico.disegna(mostra_navi=True))
        print(f"\n🏆 Hai vinto in {colpi} colpi!")
