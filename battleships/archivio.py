"""
L'archivio: tutto quello che riguarda il salvataggio delle partite su Redis.
Gli altri file non parlano mai con Redis direttamente, ma passano da qui.

Come sono salvate le cose (le stesse strutture provate nel terminale):
  partita:<id>                 HASH  -> nome, stato, vincitore, numero di colpi
  partita:<id>:navi:<chi>      HASH  -> "riga,colonna" -> nome della nave
  partita:<id>:colpi:<chi>     SET   -> celle "riga,colonna" su cui <chi> è stato colpito
  classifica                   SORTED SET -> nome giocatore -> vittorie
<chi> vale "giocatore" oppure "computer".
"""
import os

import redis

from gioco import Griglia

# Le partite si cancellano da sole dopo 24 ore senza mosse
SCADENZA = 24 * 60 * 60

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=2,
)


def _da_testo(testo):
    """'1,4' -> (1, 4)"""
    riga, colonna = testo.split(",")
    return (int(riga), int(colonna))


def _a_testo(cella):
    """(1, 4) -> '1,4'"""
    return f"{cella[0]},{cella[1]}"


# ---------- La partita ----------

def salva_partita(id_partita, dati):
    chiave = f"partita:{id_partita}"
    r.hset(chiave, mapping=dati)
    r.expire(chiave, SCADENZA)


def carica_partita(id_partita):
    """Restituisce un dizionario con i dati della partita, vuoto se non esiste."""
    return r.hgetall(f"partita:{id_partita}")


# ---------- Le griglie ----------

def salva_griglia(id_partita, chi, griglia):
    chiave_navi = f"partita:{id_partita}:navi:{chi}"
    chiave_colpi = f"partita:{id_partita}:colpi:{chi}"

    # La "pipeline" manda tutti i comandi a Redis in un colpo solo: più veloce
    pipe = r.pipeline()
    pipe.delete(chiave_navi, chiave_colpi)
    pipe.hset(chiave_navi, mapping={
        _a_testo(cella): nome
        for nome, celle in griglia.navi.items()
        for cella in celle
    })
    if griglia.colpi_ricevuti:
        pipe.sadd(chiave_colpi, *[_a_testo(c) for c in griglia.colpi_ricevuti])
    pipe.expire(chiave_navi, SCADENZA)
    pipe.expire(chiave_colpi, SCADENZA)
    pipe.execute()


def carica_griglia(id_partita, chi):
    griglia = Griglia()
    for testo, nome in r.hgetall(f"partita:{id_partita}:navi:{chi}").items():
        griglia.navi.setdefault(nome, set()).add(_da_testo(testo))
    griglia.colpi_ricevuti = {
        _da_testo(testo) for testo in r.smembers(f"partita:{id_partita}:colpi:{chi}")
    }
    return griglia


# ---------- La classifica ----------

def aggiungi_vittoria(nome):
    r.zincrby("classifica", 1, nome)


def leggi_classifica():
    return r.zrevrange("classifica", 0, 9, withscores=True)
