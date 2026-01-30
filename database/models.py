"""
MIT License

Copyright (c) 2026 EvieePy <evieepy@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from typing import TYPE_CHECKING, Any, Self

import asyncpg


if TYPE_CHECKING:
    from cryptography.fernet import Fernet


__all__ = ("BaseModel", "BroadcasterModel", "DecryptedTokenModel", "TokenModel")


class BaseModel(asyncpg.Record):
    def __getattr__(self, attr: str) -> Any:
        return self[attr]


class BroadcasterModel(BaseModel):
    uid: str
    overlay_id: str


class TokenModel(BaseModel):
    uid: str
    token: str
    refresh: str


class DecryptedTokenModel:
    def __init__(self, *, uid: str, token: str, refresh: str) -> None:
        self.uid = uid
        self.token = token
        self.refresh = refresh

    @classmethod
    def from_model(cls, *, data: TokenModel, fernet: Fernet) -> Self:
        decrypted_t = fernet.decrypt(data.token).decode()
        decrypted_r = fernet.decrypt(data.refresh).decode()

        return cls(uid=data.uid, token=decrypted_t, refresh=decrypted_r)
