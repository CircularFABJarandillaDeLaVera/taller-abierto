"""Corta cargas multipart antes de que el parser acumule toda la petición."""
from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse

MAX_REQUEST_BYTES = 16 * 1024 * 1024


class MultipartSizeLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not Headers(scope=scope).get("content-type", "").startswith("multipart/form-data"):
            return await self.app(scope, receive, send)
        length = Headers(scope=scope).get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_REQUEST_BYTES):
            return await PlainTextResponse("La petición supera 16 MB.", status_code=413)(scope, receive, send)
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    # El servidor cierra la petición en lugar de procesar un cuerpo excesivo.
                    raise RequestTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLarge:
            await PlainTextResponse("La petición supera 16 MB.", status_code=413)(scope, receive, send)


class RequestTooLarge(Exception):
    pass
