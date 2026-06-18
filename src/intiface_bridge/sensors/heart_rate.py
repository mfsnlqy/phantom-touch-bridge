from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

try:
    from bleak import BleakClient, BleakScanner
except ModuleNotFoundError as error:
    _BLEAK_IMPORT_ERROR = error

    class BleakClient:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "bleak is required to use the heart rate BLE collector."
            ) from _BLEAK_IMPORT_ERROR

    class BleakScanner:  # type: ignore[no-redef]
        @staticmethod
        async def discover(*_args: Any, **_kwargs: Any) -> Any:
            raise ModuleNotFoundError(
                "bleak is required to scan heart rate BLE devices."
            ) from _BLEAK_IMPORT_ERROR

        @staticmethod
        async def find_device_by_address(*_args: Any, **_kwargs: Any) -> Any:
            raise ModuleNotFoundError(
                "bleak is required to connect heart rate BLE devices."
            ) from _BLEAK_IMPORT_ERROR

HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"


def normalize_uuid(value: str) -> str:
    return value.strip().lower()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class HeartRateSample:
    bpm: int
    measured_at: str
    sequence: int
    rr_intervals_ms: list[float]
    sensor_contact_detected: bool | None
    energy_expended: int | None
    raw_hex: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_heart_rate_measurement(
    data: bytes,
    *,
    measured_at: str | None = None,
    sequence: int = 0,
) -> HeartRateSample:
    if not data:
        raise ValueError("empty payload")

    flags = data[0]
    offset = 1

    if flags & 0x01:
        if len(data) < offset + 2:
            raise ValueError("uint16 heart rate payload too short")
        bpm = int.from_bytes(data[offset : offset + 2], byteorder="little")
        offset += 2
    else:
        if len(data) < offset + 1:
            raise ValueError("uint8 heart rate payload too short")
        bpm = data[offset]
        offset += 1

    sensor_contact_supported = bool(flags & 0x04)
    sensor_contact_detected = bool(flags & 0x02) if sensor_contact_supported else None

    energy_expended: int | None = None
    if flags & 0x08:
        if len(data) < offset + 2:
            raise ValueError("energy expended payload too short")
        energy_expended = int.from_bytes(data[offset : offset + 2], byteorder="little")
        offset += 2

    rr_intervals_ms: list[float] = []
    if flags & 0x10:
        while offset + 1 < len(data):
            rr_value = int.from_bytes(data[offset : offset + 2], byteorder="little")
            rr_intervals_ms.append(round(rr_value * 1000 / 1024, 2))
            offset += 2

    return HeartRateSample(
        bpm=bpm,
        measured_at=measured_at or utc_now_iso(),
        sequence=sequence,
        rr_intervals_ms=rr_intervals_ms,
        sensor_contact_detected=sensor_contact_detected,
        energy_expended=energy_expended,
        raw_hex=data.hex().upper(),
    )


class HeartRateCollector:
    def __init__(
        self,
        *,
        device_name: str | None = None,
        device_address: str | None = None,
        notify_char_uuid: str | None = None,
        scan_timeout: float = 8.0,
    ) -> None:
        self.device_name = (device_name or "").strip() or None
        self.device_address = (device_address or "").strip() or None
        self.target_notify_char_uuid = (
            normalize_uuid(notify_char_uuid) if notify_char_uuid else None
        )
        self.scan_timeout = scan_timeout

        self.client: BleakClient | None = None
        self.connected = False
        self.streaming = False
        self.notify_char_uuid: str | None = None
        self.latest_sample: HeartRateSample | None = None
        self.last_error: str | None = None
        self.last_packet_at: str | None = None
        self.selected_device_name: str | None = None
        self.selected_device_address: str | None = None
        self.discovered_services: list[dict[str, Any]] = []
        self.sample_queue: asyncio.Queue[HeartRateSample] | None = None

        self._lock: asyncio.Lock | None = None
        self._sequence = 0

    async def scan_devices(self, timeout: float | None = None) -> list[dict[str, Any]]:
        resolved_timeout = timeout if timeout is not None else self.scan_timeout
        devices = await BleakScanner.discover(timeout=resolved_timeout, return_adv=True)
        results: list[dict[str, Any]] = []

        for address, (device, adv) in sorted(devices.items()):
            local_name = (adv.local_name or "").strip()
            name = (device.name or local_name or f"Unknown Device ({address})").strip()
            results.append(
                {
                    "name": name,
                    "address": address,
                    "rssi": adv.rssi,
                    "service_uuids": sorted(adv.service_uuids or []),
                }
            )

        return results

    async def connect(self) -> None:
        async with self._ensure_lock():
            if self.client and self.client.is_connected and self.streaming:
                return

            device = await self._find_device()
            client = BleakClient(device, disconnected_callback=self._handle_disconnect)
            try:
                await client.connect()
                if not client.is_connected:
                    raise RuntimeError("BLE 连接未建立。")

                services = client.services
                if services is None:
                    services = await client.get_services()
                self.discovered_services = self._serialize_services(services)

                notify_uuid = self._resolve_notify_uuid(services)
                await client.start_notify(notify_uuid, self._handle_notification)
            except Exception as error:
                self.last_error = str(error)
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception:
                    pass
                raise

            self.client = client
            self.connected = True
            self.streaming = True
            self.last_error = None
            self.selected_device_name = device.name or self.device_name
            self.selected_device_address = device.address
            self.notify_char_uuid = normalize_uuid(notify_uuid)

    async def disconnect(self) -> None:
        async with self._ensure_lock():
            if self.client is not None:
                try:
                    if self.notify_char_uuid and self.client.is_connected:
                        await self.client.stop_notify(self.notify_char_uuid)
                except Exception:
                    pass
                try:
                    if self.client.is_connected:
                        await self.client.disconnect()
                finally:
                    self.client = None

            self._reset_connection_state()

    async def start(self) -> None:
        await self.connect()

    async def stop(self) -> None:
        await self.disconnect()

    async def describe_services(self) -> list[dict[str, Any]]:
        if self.discovered_services:
            return self.discovered_services

        async with self._ensure_lock():
            if self.discovered_services:
                return self.discovered_services

            device = await self._find_device()
            client = BleakClient(device)
            try:
                await client.connect()
                services = client.services
                if services is None:
                    services = await client.get_services()
                self.discovered_services = self._serialize_services(services)
            finally:
                if client.is_connected:
                    await client.disconnect()

        return self.discovered_services

    async def wait_for_sample(self, timeout: float = 15.0) -> HeartRateSample:
        sample_queue = self._ensure_sample_queue()
        return await asyncio.wait_for(sample_queue.get(), timeout=timeout)

    def get_latest_sample(self) -> HeartRateSample | None:
        return self.latest_sample

    def status(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "streaming": self.streaming,
            "target_device_name": self.device_name,
            "target_device_address": self.device_address,
            "selected_device_name": self.selected_device_name,
            "selected_device_address": self.selected_device_address,
            "notify_char_uuid": self.notify_char_uuid,
            "last_packet_at": self.last_packet_at,
            "last_error": self.last_error,
            "latest_bpm": self.latest_sample.bpm if self.latest_sample else None,
        }

    async def _find_device(self):
        if self.device_address:
            device = await BleakScanner.find_device_by_address(
                self.device_address,
                timeout=self.scan_timeout,
            )
            if device is None:
                raise RuntimeError(
                    f'未找到地址为 "{self.device_address}" 的 BLE 设备。'
                )
            return device

        if self.device_name:
            devices = await self.scan_devices()
            matches = [
                item
                for item in devices
                if self.device_name.lower() in item["name"].lower()
            ]
            if not matches:
                raise RuntimeError(
                    f'未找到名称包含 "{self.device_name}" 的 BLE 设备。'
                )
            if len(matches) > 1:
                names = ", ".join(f'{item["name"]} ({item["address"]})' for item in matches)
                raise RuntimeError(
                    f'找到多个名称包含 "{self.device_name}" 的 BLE 设备：{names}'
                )
            device = await BleakScanner.find_device_by_address(
                matches[0]["address"],
                timeout=self.scan_timeout,
            )
            if device is None:
                raise RuntimeError(
                    f'BLE 设备 "{matches[0]["name"]}" 在连接前消失。'
                )
            return device

        raise RuntimeError("请提供设备地址或设备名称。")

    def _resolve_notify_uuid(self, services: Any) -> str:
        if self.target_notify_char_uuid:
            for service in services:
                for char in service.characteristics:
                    if normalize_uuid(char.uuid) == self.target_notify_char_uuid:
                        return char.uuid
            raise RuntimeError(
                f'未找到通知特征 "{self.target_notify_char_uuid}"。'
            )

        for service in services:
            for char in service.characteristics:
                if normalize_uuid(char.uuid) == HEART_RATE_MEASUREMENT_UUID:
                    return char.uuid

        candidates: list[str] = []
        for service in services:
            for char in service.characteristics:
                props = {prop.lower() for prop in char.properties}
                if "notify" in props or "indicate" in props:
                    candidates.append(char.uuid)

        joined = ", ".join(candidates) if candidates else "none"
        raise RuntimeError(
            "未找到标准 Heart Rate Measurement 特征。"
            f" 可用通知特征：{joined}。请手动指定 notify UUID。"
        )

    def _handle_disconnect(self, _: BleakClient) -> None:
        self._reset_connection_state()
        self.last_error = "BLE 设备已断开。"

    def _handle_notification(self, _: Any, data: bytearray) -> None:
        raw = bytes(data)
        self.last_packet_at = utc_now_iso()
        try:
            self._sequence += 1
            sample = parse_heart_rate_measurement(
                raw,
                measured_at=self.last_packet_at,
                sequence=self._sequence,
            )
        except Exception as error:
            self.last_error = f"解析心率数据包失败：{error}"
            return

        self.latest_sample = sample
        self.last_error = None
        sample_queue = self._ensure_sample_queue()
        if sample_queue is None:
            return
        try:
            sample_queue.put_nowait(sample)
        except asyncio.QueueFull:
            pass

    def _serialize_services(self, services: Any) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for service in services:
            service_entry = {
                "uuid": service.uuid,
                "description": getattr(service, "description", ""),
                "characteristics": [],
            }
            for char in service.characteristics:
                service_entry["characteristics"].append(
                    {
                        "uuid": char.uuid,
                        "description": getattr(char, "description", ""),
                        "properties": list(char.properties),
                    }
                )
            serialized.append(service_entry)
        return serialized

    def _ensure_sample_queue(self) -> asyncio.Queue[HeartRateSample] | None:
        if self.sample_queue is not None:
            return self.sample_queue

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return None

        self.sample_queue = asyncio.Queue()
        return self.sample_queue

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _reset_connection_state(self) -> None:
        self.client = None
        self.connected = False
        self.streaming = False
        self.notify_char_uuid = None
        self.latest_sample = None
        self.last_packet_at = None
        self.selected_device_name = None
        self.selected_device_address = None
        self.discovered_services = []
        self.sample_queue = None
