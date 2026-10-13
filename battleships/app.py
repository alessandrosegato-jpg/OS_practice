import os
import html

import redis
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

# Collegamento a Redis.
# Su OpenShift l'indirizzo è "redis" (il nome del Service)
# e la password arriva dal Secret "redis-secret".
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=6379,
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=2,
)


@app.get("/", response_class=HTMLResponse)
def home():
    try:
        r.ping()
        stato = "✅ Collegato a Redis"
        classifica = r.zrevrange("classifica", 0, -1, withscores=True)
        righe = "".join(
            f"<li>{html.escape(nome)}: {int(punti)} punti</li>"
            for nome, punti in classifica
        )
        if not righe:
            righe = "<li>Classifica vuota</li>"
    except redis.RedisError as errore:
        stato = f"❌ Redis non raggiungibile ({html.escape(str(errore))})"
        righe = ""

    return f"""
    <html>
      <head><meta charset="utf-8"><title>Battaglia Navale</title></head>
      <body style="font-family: sans-serif; padding: 2rem;">
        <h1>⚓ Battaglia Navale</h1>
        <p>{stato}</p>
        <h2>Classifica</h2>
        <ul>{righe}</ul>
      </body>
    </html>
    """


@app.get("/health")
def health():
    # OpenShift userà questo indirizzo per controllare che l'app sia viva
    return {"status": "ok"}


if __name__ == "__main__":
    # OpenShift si aspetta che l'app ascolti sulla porta 8080
    uvicorn.run(app, host="0.0.0.0", port=8080)
