"""
Le regole della battaglia navale, in Python puro.
Niente Redis, niente sito web: solo il gioco.
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
        # nome nave -> insieme delle celle che occupa
        self.navi = {}
        # insieme delle celle su cui l'avversario ha già sparato
        self.colpi_ricevuti = set()

    def posiziona_nave(self, nome, riga, colonna, orizzontale):
        """Prova a mettere una nave. Restituisce True se ci riesce."""
        if nome not in FLOTTA or nome in self.navi:
            return False

        lunghezza = FLOTTA[nome]
        if orizzontale:
            celle = {(riga, colonna + i) for i in range(lunghezza)}
        else:
            celle = {(riga + i, colonna) for i in range(lunghezza)}

        # La nave deve stare tutta dentro la griglia
        for r, c in celle:
            if not (0 <= r < DIMENSIONE and 0 <= c < DIMENSIONE):
                return False

        # Non deve sovrapporsi a un'altra nave
        for altre_celle in self.navi.values():
            if celle & altre_celle:
                return False

        self.navi[nome] = celle
        return True

    def posiziona_casuale(self):
        """Mette tutta la flotta in posizioni casuali."""
        self.navi = {}
        for nome in FLOTTA:
            while not self.posiziona_nave(
                nome,
                random.randrange(DIMENSIONE),
                random.randrange(DIMENSIONE),
                random.choice([True, False]),
            ):
                pass

    def ricevi_colpo(self, cella):
        """L'avversario spara su una cella. Restituisce (esito, nave):
        esito è 'già_sparato', 'acqua', 'colpito' oppure 'affondato'."""
        if cella in self.colpi_ricevuti:
            return "già_sparato", None
        self.colpi_ricevuti.add(cella)

        for nome, celle in self.navi.items():
            if cella in celle:
                if celle <= self.colpi_ricevuti:
                    return "affondato", nome
                return "colpito", nome

        return "acqua", None

    def tutte_affondate(self):
        """True se tutte le navi sono state affondate: partita persa."""
        tutte_le_celle = set().union(*self.navi.values())
        return tutte_le_celle <= self.colpi_ricevuti
