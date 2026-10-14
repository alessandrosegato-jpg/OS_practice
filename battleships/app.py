import secrets
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import archivio
from gioco import Griglia, cella_a_testo, testo_a_cella

app = FastAPI(title="Battaglia Navale")

AVVERSARIO = {"g1": "g2", "g2": "g1"}


# ---------- Cosa ci aspettiamo di ricevere dal browser ----------

class Giocatore(BaseModel):
    nome: str          # es. {"nome": "mario"}


class Colpo(BaseModel):
    codice: str        # il codice segreto del giocatore
    cella: str         # es. "B5"


# ---------- Funzioni di aiuto ----------

def carica_o_404(id_partita):
    partita = archivio.carica_partita(id_partita)
    if not partita:
        raise HTTPException(status_code=404, detail="Partita non trovata o scaduta")
    return partita


def chi_sono(partita, codice):
    """Dal codice segreto capisce se sei il giocatore 1 o 2.
    È così che nessuno può sparare al posto tuo, anche se ha il link."""
    for chi in ("g1", "g2"):
        if codice and partita.get(f"codice_{chi}") == codice:
            return chi
    raise HTTPException(status_code=403, detail="Non fai parte di questa partita")


def esiti_colpi(griglia):
    """Per ogni colpo ricevuto dice se era acqua o colpito, es. {"B5": "acqua"}"""
    celle_navi = set().union(*griglia.navi.values())
    return {
        cella_a_testo(c): ("colpito" if c in celle_navi else "acqua")
        for c in griglia.colpi_ricevuti
    }


def navi_affondate(griglia):
    return [nome for nome, celle in griglia.navi.items() if celle <= griglia.colpi_ricevuti]


def descrivi_partita(id_partita, partita, io):
    """Lo stato della partita visto da UN giocatore.
    Delle navi dell'avversario diciamo solo dove sono già state colpite!"""
    lui = AVVERSARIO[io]
    mia = archivio.carica_griglia(id_partita, io)
    sua = archivio.carica_griglia(id_partita, lui)

    vincitore = partita.get("vincitore", "")
    return {
        "id": id_partita,
        "stato": partita["stato"],                 # in_attesa, in_corso, finita
        "mio_nome": partita[f"nome_{io}"],
        "nome_avversario": partita.get(f"nome_{lui}", ""),
        "tocca_a_me": partita["stato"] == "in_corso" and partita["turno"] == io,
        "ho_vinto": vincitore == io,
        "colpi_sparati": len(sua.colpi_ricevuti),
        "mia_griglia": {
            "navi": {nome: sorted(cella_a_testo(c) for c in celle) for nome, celle in mia.navi.items()},
            "colpi_ricevuti": esiti_colpi(mia),
        },
        "griglia_nemica": {
            "colpi": esiti_colpi(sua),
            "navi_affondate": navi_affondate(sua),
        },
    }


def nuova_flotta(id_partita, chi):
    griglia = Griglia()
    griglia.posiziona_casuale()
    archivio.salva_griglia(id_partita, chi, griglia)


# ---------- Le "porte" dell'API ----------

@app.post("/api/partite")
def crea_partita(dati: Giocatore):
    """Crea una partita e restituisce il codice segreto del giocatore 1."""
    id_partita = uuid.uuid4().hex[:8]
    codice = secrets.token_hex(16)

    nuova_flotta(id_partita, "g1")
    archivio.salva_partita(id_partita, {
        "stato": "in_attesa",
        "nome_g1": dati.nome.strip()[:20] or "anonimo",
        "codice_g1": codice,
        "turno": "g1",
        "vincitore": "",
    })
    return {"id": id_partita, "codice": codice}


@app.get("/api/partite/{id_partita}/info")
def info_partita(id_partita: str):
    """Informazioni pubbliche, per chi apre il link: chi ti ha sfidato e se c'è posto."""
    partita = carica_o_404(id_partita)
    return {"sfidante": partita["nome_g1"], "posto_libero": "codice_g2" not in partita}


@app.post("/api/partite/{id_partita}/unisciti")
def unisciti(id_partita: str, dati: Giocatore):
    """Chi ha ricevuto il link entra come giocatore 2 e la partita comincia."""
    carica_o_404(id_partita)
    codice = secrets.token_hex(16)
    if not archivio.occupa_posto_sfidante(id_partita, codice):
        raise HTTPException(status_code=409, detail="Questa partita ha già due giocatori")

    nuova_flotta(id_partita, "g2")
    archivio.salva_partita(id_partita, {
        "nome_g2": dati.nome.strip()[:20] or "anonimo",
        "stato": "in_corso",
    })
    return {"id": id_partita, "codice": codice}


@app.get("/api/partite/{id_partita}")
def leggi_partita(id_partita: str, codice: str = ""):
    """Com'è la situazione? Il browser lo chiede ogni secondo e mezzo."""
    partita = carica_o_404(id_partita)
    io = chi_sono(partita, codice)
    return descrivi_partita(id_partita, partita, io)


@app.post("/api/partite/{id_partita}/spara")
def spara(id_partita: str, colpo: Colpo):
    partita = carica_o_404(id_partita)
    io = chi_sono(partita, colpo.codice)
    lui = AVVERSARIO[io]

    if partita["stato"] == "in_attesa":
        raise HTTPException(status_code=409, detail="Aspetta che arrivi il tuo avversario")
    if partita["stato"] == "finita":
        raise HTTPException(status_code=409, detail="La partita è finita")
    if partita["turno"] != io:
        raise HTTPException(status_code=409, detail="Non è il tuo turno")

    cella = testo_a_cella(colpo.cella)
    if cella is None:
        raise HTTPException(status_code=400, detail="Cella non valida")

    sua = archivio.carica_griglia(id_partita, lui)
    esito, nave = sua.ricevi_colpo(cella)
    if esito == "già_sparato":
        raise HTTPException(status_code=409, detail="Hai già sparato lì")
    archivio.salva_griglia(id_partita, lui, sua)

    if sua.tutte_affondate():
        aggiornamenti = {"stato": "finita", "vincitore": io}
        archivio.aggiungi_vittoria(partita[f"nome_{io}"])
    else:
        aggiornamenti = {"turno": lui}   # passa la mano all'avversario
    archivio.salva_partita(id_partita, aggiornamenti)

    partita.update(aggiornamenti)
    return {
        "colpo": {"cella": cella_a_testo(cella), "esito": esito, "nave": nave},
        "partita": descrivi_partita(id_partita, partita, io),
    }


@app.get("/api/classifica")
def classifica():
    return [{"nome": nome, "vittorie": int(punti)} for nome, punti in archivio.leggi_classifica()]


# ---------- La pagina del gioco ----------

PAGINA = Path(__file__).parent / "index.html"


@app.get("/")
def home():
    return FileResponse(PAGINA)


@app.get("/health")
def health():
    # OpenShift userà questo indirizzo per controllare che l'app sia viva
    return {"status": "ok"}


if __name__ == "__main__":
    # OpenShift si aspetta che l'app ascolti sulla porta 8080
    uvicorn.run(app, host="0.0.0.0", port=8080)
