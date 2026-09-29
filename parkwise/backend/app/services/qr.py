from __future__ import annotations

import base64
from io import BytesIO

import qrcode


def qr_png_bytes(value: str) -> bytes:
    image = qrcode.make(value)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def qr_png_base64(value: str) -> str:
    return base64.b64encode(qr_png_bytes(value)).decode("ascii")
