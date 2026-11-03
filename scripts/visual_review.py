"""Revisión visual local aislada; guarda capturas ficticias sin enlaces privados."""

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
SHOTS = ROOT / "docs" / "capturas"
DB = DATA / "phase5-visual.db"
PROFILE = DATA / "chrome-phase5-review"
PORT = 8767
CHROME_PORT = 9233
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def wait_url(url, timeout=15):
    for _ in range(timeout * 10):
        try:
            return json.load(urlopen(url, timeout=1))
        except Exception:
            time.sleep(.1)
    raise RuntimeError("El servidor de revisión no respondió.")


def main():
    DATA.mkdir(exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import select
    from app.database import SessionLocal
    from app.identity import new_session
    from app.models import Message, Order, OrderKind, OrderStatus, Product, User, UserRole
    from app.seed import seed_catalog

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(config, "head")
    seed_catalog()
    with SessionLocal() as db:
        student = db.scalar(select(User).where(User.alias == "luna_taller"))
        visitor = db.scalar(select(User).where(User.alias == "visitante_visual"))
        if visitor is None:
            visitor = User(alias="visitante_visual", role=UserRole.VISITOR)
            db.add(visitor)
            db.flush()
        teacher = db.scalar(select(User).where(User.alias == "docente_visual"))
        if teacher is None:
            teacher = User(alias="docente_visual", role=UserRole.TEACHER)
            db.add(teacher)
            db.flush()
        if db.scalar(select(Order).where(Order.requester_id == visitor.id)) is None:
            product = db.scalar(select(Product).where(Product.slug == "figura-personalizada-3d"))
            inquiry = Order(kind=OrderKind.PRODUCT_INQUIRY, status=OrderStatus.IN_CONVERSATION, requester_id=visitor.id, recipient_id=student.id, product_id=product.id, requester_alias="Visitante de prueba", description="¿Se puede adaptar el color de esta figura?", visitor_access_enabled=True)
            custom = Order(kind=OrderKind.CUSTOM_FIGURE, status=OrderStatus.RECEIVED, requester_id=visitor.id, recipient_id=None, requester_alias="Visitante de prueba", description="Quiero una figura de ejemplo con tonos verdes.", visitor_access_enabled=True)
            db.add_all([inquiry, custom])
            db.flush()
            db.add_all([Message(order_id=inquiry.id, author_id=visitor.id, body="Hola, ¿podemos hablar de una figura en verde?"), Message(order_id=inquiry.id, author_id=student.id, body="Claro. Cuéntame qué tonos tenías en mente."), Message(order_id=custom.id, author_id=visitor.id, body="Me gustaría una figura sencilla con chaqueta verde.")])
        db.commit()
        inquiry_id = db.scalar(select(Order.id).where(Order.kind == OrderKind.PRODUCT_INQUIRY, Order.requester_id == visitor.id))
        sessions = {"visitor": new_session(db, visitor), "student": new_session(db, student), "teacher": new_session(db, teacher)}

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT), "--no-access-log"], cwd=ROOT, env=os.environ.copy(), creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = None
    try:
        wait_url(f"http://127.0.0.1:{PORT}/health")
        chrome = subprocess.Popen([str(CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage", "--remote-allow-origins=*", f"--remote-debugging-port={CHROME_PORT}", f"--user-data-dir={PROFILE}", "about:blank"], cwd=ROOT, creationflags=flags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tabs = wait_url(f"http://127.0.0.1:{CHROME_PORT}/json")
        ws_url = next(tab["webSocketDebuggerUrl"] for tab in tabs if tab["type"] == "page")
        with connect(ws_url, origin="http://localhost") as ws:
            next_id = 0

            def command_cdp(method, params=None):
                nonlocal next_id
                next_id += 1
                ws.send(json.dumps({"id": next_id, "method": method, "params": params or {}}))
                while True:
                    message = json.loads(ws.recv())
                    if message.get("id") == next_id:
                        if "error" in message:
                            raise RuntimeError(message["error"])
                        return message.get("result", {})

            command_cdp("Page.enable")
            command_cdp("Network.enable")

            def capture(name, route, width, height, session=None, checkboxes=False):
                command_cdp("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width < 700})
                command_cdp("Network.clearBrowserCookies")
                if session:
                    command_cdp("Network.setCookie", {"name": "ta_session", "value": sessions[session], "url": f"http://127.0.0.1:{PORT}/", "httpOnly": True, "sameSite": "Lax"})
                command_cdp("Page.navigate", {"url": f"http://127.0.0.1:{PORT}{route}"})
                time.sleep(.8)
                metrics = command_cdp("Runtime.evaluate", {"expression": "({title:document.title, width:document.documentElement.scrollWidth, viewport:innerWidth, height:document.documentElement.scrollHeight, missing:[...document.images].filter(i=>!i.complete||i.naturalWidth===0).length})", "returnByValue": True})["result"]["value"]
                if metrics["width"] > metrics["viewport"] or metrics["missing"]:
                    raise AssertionError(f"Problema en {name}: {metrics}")
                if name == "portada-escritorio":
                    command_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                    command_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9})
                    audit = command_cdp("Runtime.evaluate", {"expression": """(() => {
                      const rgb = s => (s.match(/\\d+/g) || []).slice(0,3).map(Number).map(v => {v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});
                      const lum = s => rgb(s).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
                      const ratio = (a,b) => {const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
                      const body=getComputedStyle(document.body),button=getComputedStyle(document.querySelector('.hero .button'));
                      const focus=getComputedStyle(document.activeElement);
                      return {body:ratio(body.color,body.backgroundColor),button:ratio(button.color,button.backgroundColor),focusWidth:focus.outlineWidth,focusStyle:focus.outlineStyle,focused:document.activeElement.tagName};
                    })()""", "returnByValue": True})["result"]["value"]
                    if audit["body"] < 4.5 or audit["button"] < 4.5 or audit["focusStyle"] == "none" or audit["focusWidth"] == "0px":
                        raise AssertionError(f"Contraste o foco insuficiente: {audit}")
                    print(f"Contraste y foco: {audit}")
                if checkboxes:
                    checks = command_cdp("Runtime.evaluate", {"expression": "[...document.querySelectorAll('input[type=checkbox]')].map(e=>({name:e.name,checked:e.checked,width:e.getBoundingClientRect().width,visible:getComputedStyle(e).visibility}))", "returnByValue": True})["result"]["value"]
                    if len(checks) != 2 or any(c["checked"] or c["width"] < 15 or c["visible"] != "visible" for c in checks):
                        raise AssertionError(f"Casillas no visibles: {checks}")
                    print(f"{name}: casillas verificadas por Chrome: {[c['name'] for c in checks]}")
                image = command_cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
                (SHOTS / f"{name}.png").write_bytes(base64.b64decode(image))
                if name == "conversacion-movil":
                    long_text = command_cdp("Runtime.evaluate", {"expression": """(() => {
                      document.querySelector('.message p').textContent = 'palabralarga'.repeat(80);
                      return {width:document.documentElement.scrollWidth,viewport:innerWidth};
                    })()""", "returnByValue": True})["result"]["value"]
                    if long_text["width"] > long_text["viewport"]:
                        raise AssertionError(f"Texto largo desborda: {long_text}")
                    print("conversacion-movil: texto largo sin desbordamiento")
                print(f"{name}: {metrics['title']}, {width}×{height}, sin desbordamiento ni imágenes rotas")

            views = [
                ("portada-escritorio", "/", 1360, 900, None, False),
                ("portada-movil", "/", 390, 844, None, False),
                ("catalogo-escritorio", "/catalogo", 1360, 900, None, False),
                ("catalogo-movil", "/catalogo", 390, 844, None, False),
                ("producto-escritorio", "/productos/figura-personalizada-3d", 1360, 900, None, False),
                ("producto-movil", "/productos/figura-personalizada-3d", 390, 844, None, False),
                ("solicitud-movil", "/figura-personalizada", 390, 844, None, True),
                ("acceso-escritorio", "/entrar", 1360, 900, None, False),
                ("panel-docente", "/panel", 1360, 900, "teacher", False),
                ("panel-creador", "/panel", 390, 844, "student", False),
                ("panel-visitante", "/panel", 390, 844, "visitor", False),
                ("conversacion-escritorio", f"/panel/solicitudes/{inquiry_id}", 1360, 900, "student", False),
                ("conversacion-movil", f"/panel/solicitudes/{inquiry_id}", 390, 844, "visitor", False),
            ]
            for view in views:
                capture(*view)
    finally:
        if chrome is not None:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
