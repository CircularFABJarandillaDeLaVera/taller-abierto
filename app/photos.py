"""Validación, almacenamiento privado y aceptación por lote de fotografías."""
import io
import secrets
import warnings
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Attachment, AttachmentSource, Order, OrderKind, PhotoConsent, User, UserRole

MAX_FILE = 5 * 1024 * 1024
MAX_DIMENSION = 6000
MAX_PIXELS = 20_000_000
CONSENT_VERSION = "fotografias-v1-2026-11"
RIGHTS_TEXT = "Tengo los derechos o la autorización necesarios para utilizar las fotografías que adjunto"
PERSON_TEXT = "Si aparece otra persona, tengo su permiso expreso para utilizar su imagen como referencia y crear una figura personalizada. Si aparezco yo, autorizo ese uso de mi imagen"
MINOR_TEXT = "Si la persona representada es menor de edad, debe intervenir su representante legal y aportar la autorización correspondiente"
USE_TEXT = "Las fotografías se utilizarán únicamente para preparar este encargo. Publicarlas en el catálogo o en redes requerirá una autorización independiente"


class PhotoError(ValueError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


@dataclass
class PreparedPhoto:
    name: str
    mime: str
    data: bytes


def storage_root() -> Path:
    root = Path(get_settings().attachments_dir).resolve()
    static = (Path(__file__).resolve().parent / "static").resolve()
    if root == static or static in root.parents or root == Path.cwd().resolve():
        raise RuntimeError("Directorio privado de adjuntos no válido.")
    root.mkdir(parents=True, exist_ok=True)
    return root


async def prepare(files: list[UploadFile], rights: str, person: str) -> list[PreparedPhoto]:
    files = [f for f in files if f.filename]
    if len(files) > 3:
        raise PhotoError("Puedes adjuntar como máximo tres fotografías.")
    if not files:
        return []
    if rights != "on":
        raise PhotoError("Confirma que tienes los derechos o la autorización para utilizar las fotografías.", "rights_confirmed")
    if person != "on":
        raise PhotoError("Confirma el permiso expreso de la persona representada o tu autorización si apareces tú.", "person_confirmed")
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ModuleNotFoundError as exc:
        raise PhotoError("El procesamiento de fotografías no está disponible; instala las dependencias del proyecto.") from exc
    prepared = []
    for upload in files:
        suffix = Path(upload.filename).suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png"):
            raise PhotoError("Solo se admiten fotografías JPG o PNG.")
        chunks = bytearray()
        while chunk := await upload.read(min(1024 * 1024, MAX_FILE + 1 - len(chunks))):
            chunks.extend(chunk)
            if len(chunks) > MAX_FILE:
                raise PhotoError("Cada fotografía puede ocupar como máximo 5 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(chunks)) as image:
                    if image.format not in ("JPEG", "PNG") or (suffix == ".png") != (image.format == "PNG"):
                        raise PhotoError("El contenido no coincide con JPG o PNG.")
                    if max(image.size) > MAX_DIMENSION or image.width * image.height > MAX_PIXELS:
                        raise PhotoError("La fotografía supera las dimensiones permitidas.")
                    image.load()
                    clean = ImageOps.exif_transpose(image).convert("RGB") if image.format == "JPEG" else ImageOps.exif_transpose(image).convert("RGBA" if "A" in image.getbands() else "RGB")
                    pixels_only = Image.new(clean.mode, clean.size)
                    pixels_only.paste(clean)
                    output = io.BytesIO()
                    if image.format == "JPEG":
                        pixels_only.save(output, format="JPEG", quality=90)
                    else:
                        pixels_only.save(output, format="PNG")
                    data = output.getvalue()
                    if len(data) > MAX_FILE:
                        raise PhotoError("La fotografía normalizada supera 5 MB.")
                    prepared.append(PreparedPhoto(name=Path(upload.filename).name[:255], mime="image/jpeg" if image.format == "JPEG" else "image/png", data=data))
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise PhotoError("La fotografía está dañada o no es una imagen JPG/PNG válida.") from exc
    return prepared


def save_batch(db: Session, order: Order, actor: User, photos: list[PreparedPhoto], written: list[Path]) -> None:
    if not photos:
        return
    if order.kind != OrderKind.CUSTOM_FIGURE:
        raise PhotoError("Solo las figuras personalizadas admiten fotografías.")
    count = db.scalar(select(func.count()).select_from(Attachment).where(Attachment.order_id == order.id)) or 0
    if count + len(photos) > 3:
        raise PhotoError("El encargo admite un máximo de tres fotografías activas.")
    consent = PhotoConsent(order_id=order.id, accepted_by_id=actor.id, text_version=CONSENT_VERSION)
    db.add(consent)
    db.flush()
    root = storage_root()
    source = AttachmentSource.REQUESTER if actor.role == UserRole.VISITOR else AttachmentSource.STAFF if actor.role == UserRole.TEACHER else AttachmentSource.RECIPIENT
    for photo in photos:
        filename = secrets.token_hex(24) + (".jpg" if photo.mime == "image/jpeg" else ".png")
        path = root / filename
        with path.open("xb") as output:
            written.append(path)
            output.write(photo.data)
        db.add(Attachment(order_id=order.id, uploaded_by_id=actor.id, consent_id=consent.id, source=source, stored_name=filename, original_name=photo.name, mime_type=photo.mime, size_bytes=len(photo.data)))


def clean_written(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)
