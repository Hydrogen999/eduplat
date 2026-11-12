import httpx, hmac, hashlib
from app.core.config import settings

class Paystack:
    def __init__(self):
        self.base = settings.PAYSTACK_BASE_URL
        self.headers = {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}

    async def initialize(self, *, email: str, amount_kobo: int, reference: str,
                         callback_url: str, metadata: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{self.base}/transaction/initialize", headers=self.headers, json={
                "email": email,
                "amount": amount_kobo,
                "currency": "NGN",
                "reference": reference,
                "callback_url": callback_url,
                "metadata": metadata or {},
            })
            if r.status_code >= 400:
                raise RuntimeError(f"Paystack init failed: {r.text}")
            return r.json()["data"]

    async def verify(self, reference: str) -> dict:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{self.base}/transaction/verify/{reference}", headers=self.headers)
            if r.status_code >= 400:
                raise RuntimeError(f"Paystack verify failed: {r.text}")
            return r.json()["data"]

    @staticmethod
    def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
        if not settings.PAYSTACK_SECRET_KEY or not signature:
            return False
        expected = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

paystack = Paystack()