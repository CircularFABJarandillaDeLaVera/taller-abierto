"""Recorrido real en Chrome con base y perfiles ficticios aislados."""

import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUN = datetime.now().strftime("%Y%m%d-%H%M%S")
DATA = ROOT / "data" / f"phase6-browser-{RUN}"
DB = DATA / "demo.db"
SERVER_PORT = 8768
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def wait_json(url, timeout=20):
    for _ in range(timeout * 10):
        try:
            return json.load(urlopen(url, timeout=1))
        except Exception:
            time.sleep(.1)
    raise RuntimeError("El proceso local no respondió.")


class Browser:
    def __init__(self, name, port, width, height, session=None):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.process = subprocess.Popen([str(CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--remote-allow-origins=*", f"--remote-debugging-port={port}", f"--user-data-dir={DATA / name}", "about:blank"], cwd=ROOT, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tabs = wait_json(f"http://127.0.0.1:{port}/json")
        self.ws_context = connect(next(tab["webSocketDebuggerUrl"] for tab in tabs if tab["type"] == "page"), origin="http://localhost")
        self.ws = self.ws_context.__enter__()
        self.counter = 0
        self.call("Page.enable")
        self.call("Network.enable")
        self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 700})
        if session:
            self.call("Network.setCookie", {"name": "ta_session", "value": session, "url": f"http://127.0.0.1:{SERVER_PORT}/", "httpOnly": True, "sameSite": "Lax"})

    def call(self, method, params=None):
        self.counter += 1
        self.ws.send(json.dumps({"id": self.counter, "method": method, "params": params or {}}))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") == self.counter:
                if "error" in reply:
                    raise RuntimeError(reply["error"])
                return reply.get("result", {})

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError("Error en la ejecución del navegador.")
        return result["result"].get("value")

    def go(self, route):
        self.call("Page.navigate", {"url": f"http://127.0.0.1:{SERVER_PORT}{route}"})
        time.sleep(.8)

    def wait_for(self, expression, timeout=12):
        for _ in range(timeout * 5):
            if self.js(expression):
                return
            time.sleep(.2)
        raise AssertionError(f"Chrome no alcanzó la condición: {expression[:90]}")

    def close(self):
        self.ws_context.__exit__(None, None, None)
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def capture(self, name):
        encoded = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
        (DATA / f"{name}.png").write_bytes(base64.b64decode(encoded))


def main():
    DATA.mkdir(parents=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
    os.environ["POLL_SECONDS"] = "5"
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.identity import new_session
    from app.models import Order, User
    from app.seed import seed_catalog

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(config, "head")
    seed_catalog()
    with SessionLocal() as db:
        student = db.scalar(select(User).where(User.alias == "luna_taller"))
        student_session = new_session(db, student)

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    env = os.environ.copy()
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(SERVER_PORT), "--no-access-log"], cwd=ROOT, env=env, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    browsers = []
    try:
        wait_json(f"http://127.0.0.1:{SERVER_PORT}/health")
        student = Browser("creador", 9234, 1360, 900, student_session)
        visitor = Browser("visitante", 9235, 390, 844)
        browsers.extend([student, visitor])
        student.go("/panel")
        visitor.go("/productos/figura-personalizada-3d")
        visitor.js("""(() => { const f=document.querySelector('form[action$="/consulta"]'); f.querySelector('[name=alias]').value='Visitante de navegador'; f.querySelector('[name=message]').value='Consulta ficticia desde Chrome'; f.requestSubmit(); return true; })()""")
        visitor.wait_for("location.pathname === '/solicitud-recibida'")
        with SessionLocal() as db:
            order = db.scalar(select(Order).order_by(Order.id.desc()))
            order_id = order.id
        visitor.go(f"/panel/solicitudes/{order_id}")
        visitor.wait_for("document.querySelector('[data-conversation]') !== null")
        visitor.js("document.querySelector('#reply-body').value='Borrador de visitante sin enviar'; true")
        student.wait_for("document.querySelector('[data-news-count]')?.textContent === '1'", timeout=15)
        student.wait_for("document.querySelector('[data-order-id]')?.textContent.includes('Nueva para ti') && document.querySelector('[data-empty-state]')?.hidden === true")
        assert student.js("document.querySelector('[data-news-toast]')?.hidden === false")
        student.capture("creador-aviso-escritorio")
        print("Chrome: creador recibe aviso sin recargar; visitante conserva su borrador.")
        student.go(f"/panel/solicitudes/{order_id}")
        student.wait_for("document.querySelector('[data-conversation]') !== null")
        student.js("""(() => {document.querySelector('#reply-body').value='Respuesta ficticia del creador'; document.querySelector('.reply-form').requestSubmit(); return true})()""")
        student.wait_for("document.querySelector('[data-conversation]') !== null")
        visitor.wait_for("document.querySelector('[data-show-new]')?.hidden === false", timeout=15)
        assert visitor.js("document.querySelector('#reply-body').value === 'Borrador de visitante sin enviar'")
        visitor.js("""(() => { const original=window.fetch; let failed=false; window.fetch=(url,options) => { if (!failed && String(url).endsWith('/lectura')) { failed=true; return Promise.reject(new Error('Fallo simulado de lectura')); } return original(url,options); }; document.querySelector('[data-show-new]').click(); return true; })()""")
        visitor.wait_for("[...document.querySelectorAll('[data-message-id]')].some(e=>e.textContent.includes('Respuesta ficticia del creador'))")
        visitor.wait_for("document.querySelector('[data-show-new]')?.textContent === 'Reintentar lectura'")
        assert visitor.js("document.querySelector('[data-news-count]')?.textContent === '1'")
        assert visitor.js("Number(document.querySelector('[data-conversation]').dataset.receivedId) > Number(document.querySelector('[data-conversation]').dataset.confirmedId)")
        visitor.js("document.querySelector('[data-show-new]').click(); true")
        visitor.wait_for("document.querySelector('[data-news-count]')?.hidden === true")
        assert visitor.js("document.querySelector('[data-conversation]').dataset.receivedId === document.querySelector('[data-conversation]').dataset.confirmedId")
        assert visitor.js("document.querySelector('#reply-body').value === 'Borrador de visitante sin enviar'")
        assert visitor.js("document.documentElement.scrollWidth <= innerWidth")
        visitor.capture("visitante-conversacion-movil")
        print("Chrome: visitante móvil ve mensajes nuevos sin recarga ni pérdida del borrador; lectura guardada.")

        visitor.go("/figura-personalizada")
        visitor.js("document.querySelector('[name=description]').value='Descripción ficticia sin enviar'; true")
        time.sleep(6)
        assert visitor.js("document.querySelector('input[type=file]') === null && document.querySelector('input[type=checkbox]') === null && document.querySelector('[name=description]').value === 'Descripción ficticia sin enviar'")
        assert visitor.js("document.documentElement.scrollWidth <= innerWidth")
        visitor.capture("figura-sin-fotos-movil")
        print("Chrome: figura sin fotos; descripción móvil permanece tras el sondeo.")
        print(f"Capturas ficticias aisladas: {DATA}")
    finally:
        for browser in browsers:
            browser.close()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
