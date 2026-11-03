"""Regresión del formulario renderizado y del recorrido real con PNG."""
import io
from html.parser import HTMLParser

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.models import Attachment, Message, Order, OrderKind, PhotoConsent, User
from tests.test_photos import setup, token, login


class FormInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form = None
        self.inputs = []
        self.labels = {}
        self.active_label = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("action") == "/figura-personalizada":
            self.form = attrs
        elif tag == "input" and self.form is not None:
            self.inputs.append(attrs)
        elif tag == "label" and self.form is not None:
            self.active_label = attrs.get("for")
            if self.active_label:
                self.labels[self.active_label] = ""

    def handle_data(self, data):
        if self.active_label:
            self.labels[self.active_label] += data

    def handle_endtag(self, tag):
        if tag == "label":
            self.active_label = None
        elif tag == "form" and self.form is not None:
            self.form = None


def png():
    output = io.BytesIO()
    Image.new("RGB", (40, 40), "green").save(output, format="PNG")
    return output.getvalue()


def test_rendered_consent_form_and_private_flow(setup):
    Sessions, root = setup
    visitor = TestClient(__import__("app.main", fromlist=["app"]).app, follow_redirects=False)
    creator = TestClient(__import__("app.main", fromlist=["app"]).app, follow_redirects=False)
    teacher = TestClient(__import__("app.main", fromlist=["app"]).app, follow_redirects=False)
    page = visitor.get("/figura-personalizada")
    parsed = FormInspector()
    parsed.feed(page.text)
    checkboxes = {item["name"]: item for item in parsed.inputs if item.get("type") == "checkbox"}
    assert set(checkboxes) == {"rights_confirmed", "person_confirmed"}
    for name, field in checkboxes.items():
        assert field["id"] == name and field["value"] == "on"
        assert "checked" not in field
        assert parsed.labels[name].strip()
    assert 'action="/figura-personalizada" enctype="multipart/form-data"' in page.text
    upload = next(item for item in parsed.inputs if item.get("type") == "file")
    assert upload["name"] == "photos" and upload["id"] in parsed.labels
    csrf_name = next(item["name"] for item in parsed.inputs if item.get("type") == "hidden")
    fields = {"alias": "Prueba", "description": "Figura para probar la carga"}

    def submit(accept):
        return visitor.post("/figura-personalizada", data={**fields, csrf_name: token(visitor, "/figura-personalizada"), **{checkboxes[name]["name"]: checkboxes[name]["value"] for name in accept}}, files={upload["name"]: ("foto.png", png(), "image/png")})

    for chosen, missing in ((["rights_confirmed"], "person_confirmed"), (["person_confirmed"], "rights_confirmed")):
        response = submit(chosen)
        assert response.status_code == 422
        assert f'id="{missing}"' in response.text
        assert f'aria-describedby="{missing.split("_")[0]}_error"' in response.text
        assert "Prueba" in response.text and fields["description"] in response.text
        assert "seleccionarla de nuevo" in response.text
        with Sessions() as db:
            assert db.scalar(select(func.count()).select_from(Order)) == 0

    response = submit(checkboxes)
    assert response.status_code == 303 and response.headers["location"] == "/solicitud-recibida"
    assert "Tu idea ya está en el taller" in visitor.get("/solicitud-recibida").text
    with Sessions() as db:
        order = db.scalar(select(Order))
        assert order.kind == OrderKind.CUSTOM_FIGURE and order.recipient_id is None
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        photo = db.scalar(select(Attachment))
        assert photo.consent.accepted_by_id == order.requester_id
        assert db.scalar(select(func.count()).select_from(PhotoConsent)) == 1
        assert (root / photo.stored_name).is_file()
        order_id, photo_id = order.id, photo.id
        student_id = db.scalar(select(User.id).where(User.alias == "luna_taller"))

    assert login(teacher, "docente_fotos", "Clave docente fotos").status_code == 303
    assert "Sin asignar" in teacher.get(f"/panel/solicitudes/{order_id}").text
    image_url = f"/panel/solicitudes/{order_id}/fotos/{photo_id}"
    assert teacher.get(image_url).status_code == 200
    assert "/fotos\" enctype=" not in teacher.get(f"/panel/solicitudes/{order_id}").text
    assert teacher.post(f"/panel/solicitudes/{order_id}/fotos", data={"csrf_token": token(teacher, f"/panel/solicitudes/{order_id}"), "rights_confirmed": "on", "person_confirmed": "on"}, files={"photos": ("otra.png", png(), "image/png")}).status_code == 403
    assert teacher.post(f"/panel/solicitudes/{order_id}/asignar", data={"student_id": student_id, "csrf_token": token(teacher, f"/panel/solicitudes/{order_id}")}).status_code == 303
    assert login(creator, "luna_taller", "Clave creador fotos").status_code == 303
    assert creator.get(image_url).status_code == 200
    assert "Añadir fotografías" not in creator.get(f"/panel/solicitudes/{order_id}").text
    assert creator.post(f"/panel/solicitudes/{order_id}/fotos", data={"csrf_token": token(creator, f"/panel/solicitudes/{order_id}"), "rights_confirmed": "on", "person_confirmed": "on"}, files={"photos": ("otra.png", png(), "image/png")}).status_code == 403
    assert "Añadir fotografías" in visitor.get(f"/panel/solicitudes/{order_id}").text
    assert visitor.post(f"/panel/solicitudes/{order_id}/fotos", data={"csrf_token": token(visitor, f"/panel/solicitudes/{order_id}"), "rights_confirmed": "on", "person_confirmed": "on"}, files={"photos": ("otra.png", png(), "image/png")}).status_code == 303
    with Sessions() as db:
        assert db.scalar(select(func.count()).select_from(Attachment)) == 2
        assert db.scalar(select(func.count()).select_from(PhotoConsent)) == 2
