"""Protect provider credentials with the current Windows user's DPAPI key."""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


_CRYPTPROTECT_UI_FORBIDDEN = 0x1
_CREDENTIAL_PURPOSE = "TheraSim provider credential v1"


class CredentialStoreError(OSError):
    """A provider credential could not be protected by the operating system."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.c_void_p),
    ]


def _transform(data: bytes, *, protect: bool) -> bytes:
    if os.name != "nt":
        raise CredentialStoreError(
            "Persistent provider credentials require a supported operating-system "
            "credential store. On this platform, configure credentials through "
            "environment variables."
        )

    input_buffer = ctypes.create_string_buffer(data)
    input_blob = _DataBlob(
        len(data),
        ctypes.cast(input_buffer, ctypes.c_void_p),
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    protect_data = crypt32.CryptProtectData
    protect_data.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    protect_data.restype = wintypes.BOOL

    unprotect_data = crypt32.CryptUnprotectData
    unprotect_data.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    unprotect_data.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    description = wintypes.LPWSTR()
    try:
        if protect:
            succeeded = protect_data(
                ctypes.byref(input_blob),
                _CREDENTIAL_PURPOSE,
                None,
                None,
                None,
                _CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )
        else:
            succeeded = unprotect_data(
                ctypes.byref(input_blob),
                ctypes.byref(description),
                None,
                None,
                None,
                _CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )

        if not succeeded or not output_blob.pbData:
            raise CredentialStoreError(
                "The Windows credential store could not protect this provider key."
            )
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    except OSError as exc:
        raise CredentialStoreError(
            "The Windows credential store could not protect this provider key."
        ) from exc
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(output_blob.pbData)
        if description:
            kernel32.LocalFree(ctypes.cast(description, ctypes.c_void_p))


def protect_provider_key(value: str) -> str:
    """Return a base64-encoded DPAPI blob; no application encryption key is stored."""

    if not value:
        return ""
    try:
        return base64.b64encode(
            _transform(value.encode("utf-8"), protect=True)
        ).decode("ascii")
    except UnicodeEncodeError as exc:
        raise CredentialStoreError(
            "The provider key contains unsupported characters."
        ) from exc


def unprotect_provider_key(value: str) -> str:
    """Decrypt a provider key for the current Windows user only."""

    if not value:
        return ""
    try:
        encrypted = base64.b64decode(value, validate=True)
        if not encrypted:
            raise ValueError("empty credential blob")
        return _transform(encrypted, protect=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise CredentialStoreError(
            "A saved provider key could not be read from the Windows credential store."
        ) from exc
