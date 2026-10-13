"""
URL shortener - backend API
Salva i link su Redis e conta i click.
Ogni risposta indica quale pod l'ha servita (utile per vedere il load balancing).
"""
import os
import secrets
import socket
import string

import redis
from flask import Flask, abort, jsonify, redirect, request

app = Flask(__name__)

POD_NAME = socket.gethostname()
ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = int(os.environ.get("CODE_LENGTH", "6"))

# Connessione a Redis: host e password arrivano da variabili d'ambiente
# (in OpenShift: il nome del Service e un Secret)
r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    password=os.environ.get("REDIS_PASSWORD") or None,
    decode_responses=True,
    socket_connect_timeout=2,
)


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


@app.post("/api/shorten")
def shorten():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(error="Il link deve iniziare con http:// o https://", pod=POD_NAME), 400

    # Genera un codice libero (SET NX = scrivi solo se non esiste già)
    for _ in range(5):
        code = new_code()
        if r.set(f"url:{code}", url, nx=True):
            r.zadd("clicks", {code: 0})
            r.incr("stats:links_total")
            return jsonify(code=code, url=url, pod=POD_NAME), 201
    return jsonify(error="Impossibile generare un codice, riprova", pod=POD_NAME), 500


@app.get("/r/<code>")
def follow(code):
    url = r.get(f"url:{code}")
    if url is None:
        abort(404)
    r.zincrby("clicks", 1, code)
    r.incr("stats:clicks_total")
    return redirect(url, code=302)


@app.get("/api/stats")
def stats():
    top = r.zrevrange("clicks", 0, 9, withscores=True)
    links = []
    for code, clicks in top:
        links.append({"code": code, "url": r.get(f"url:{code}"), "clicks": int(clicks)})
    return jsonify(
        pod=POD_NAME,
        links_total=int(r.get("stats:links_total") or 0),
        clicks_total=int(r.get("stats:clicks_total") or 0),
        top=links,
    )


@app.get("/api/info")
def info():
    return jsonify(pod=POD_NAME)


# Liveness: il processo è vivo?
@app.get("/livez")
def livez():
    return "ok", 200


# Readiness: il pod è pronto a ricevere traffico? (solo se Redis risponde)
@app.get("/readyz")
def readyz():
    try:
        r.ping()
        return "ok", 200
    except redis.RedisError:
        return "redis non raggiungibile", 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
