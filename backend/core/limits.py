from fastapi import HTTPException, Request


async def read_body_limited(request: Request, max_bytes: int) -> bytes:
    """`Content-Length` header'ına güvenmeden (istemci bu header'ı hiç
    göndermeyebilir veya yalan söyleyebilir — chunked transfer encoding'de
    header zaten yok) gövdeyi parça parça okur; `max_bytes` aşılırsa devasa
    gövde tamamen belleğe alınmadan hemen 413 ile kesilir."""
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="Request body too large")
    return bytes(body)
