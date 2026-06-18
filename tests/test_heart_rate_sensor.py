from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from intiface_bridge.sensors import HeartRateCollector, parse_heart_rate_measurement


class FakeBleakClient:
    def __init__(self, device, disconnected_callback=None):
        self.device = device
        self.disconnected_callback = disconnected_callback
        self.is_connected = False
        self.services = None
        self.started_notify_uuid = None
        self.stopped_notify_uuid = None

    async def connect(self):
        self.is_connected = True
        self.services = getattr(self.device, "services", None)

    async def get_services(self):
        return self.services

    async def start_notify(self, uuid, callback):
        self.started_notify_uuid = uuid
        self.callback = callback

    async def stop_notify(self, uuid):
        self.stopped_notify_uuid = uuid

    async def disconnect(self):
        self.is_connected = False


def make_characteristic(uuid: str, properties: list[str], description: str = ""):
    return SimpleNamespace(
        uuid=uuid,
        properties=properties,
        description=description,
    )


def make_service(uuid: str, characteristics: list[SimpleNamespace], description: str = ""):
    return SimpleNamespace(
        uuid=uuid,
        characteristics=characteristics,
        description=description,
    )


def test_parse_heart_rate_measurement_with_energy_and_rr_intervals():
    sample = parse_heart_rate_measurement(
        bytes.fromhex("1E48F40100020403"),
        measured_at="2026-06-18T00:00:00+00:00",
        sequence=7,
    )

    assert sample.bpm == 72
    assert sample.measured_at == "2026-06-18T00:00:00+00:00"
    assert sample.sequence == 7
    assert sample.sensor_contact_detected is True
    assert sample.energy_expended == 500
    assert sample.rr_intervals_ms == [500.0, 753.91]
    assert sample.raw_hex == "1E48F40100020403"


def test_parse_heart_rate_measurement_rejects_truncated_uint16_payload():
    with pytest.raises(ValueError, match="uint16 heart rate payload too short"):
        parse_heart_rate_measurement(bytes.fromhex("01"))


def test_collector_notification_updates_latest_sample():
    collector = HeartRateCollector(device_name="Demo Band")

    collector._handle_notification(None, bytearray.fromhex("10480002"))

    latest_sample = collector.get_latest_sample()
    assert latest_sample is not None
    assert latest_sample.bpm == 72
    assert latest_sample.sequence == 1
    assert latest_sample.rr_intervals_ms == [500.0]
    assert collector.status()["latest_bpm"] == 72


def test_scan_devices_sorts_results_and_service_uuids(monkeypatch):
    async def fake_discover(timeout=8.0, return_adv=True):
        assert timeout == 6.5
        assert return_adv is True
        return {
            "00:11:22:33:44:88": (
                SimpleNamespace(name=None, address="00:11:22:33:44:88"),
                SimpleNamespace(
                    local_name="Band B",
                    rssi=-55,
                    service_uuids=["b", "a"],
                ),
            ),
            "00:11:22:33:44:77": (
                SimpleNamespace(name="Band A", address="00:11:22:33:44:77"),
                SimpleNamespace(
                    local_name="",
                    rssi=-40,
                    service_uuids=["d", "c"],
                ),
            ),
        }

    monkeypatch.setattr(
        "intiface_bridge.sensors.heart_rate.BleakScanner.discover",
        fake_discover,
    )

    collector = HeartRateCollector(device_name="Band", scan_timeout=6.5)

    devices = asyncio.run(collector.scan_devices())

    assert devices == [
        {
            "name": "Band A",
            "address": "00:11:22:33:44:77",
            "rssi": -40,
            "service_uuids": ["c", "d"],
        },
        {
            "name": "Band B",
            "address": "00:11:22:33:44:88",
            "rssi": -55,
            "service_uuids": ["a", "b"],
        },
    ]


def test_find_device_rejects_multiple_name_matches(monkeypatch):
    async def fake_scan_devices(timeout=None):
        return [
            {"name": "Demo Band", "address": "AA"},
            {"name": "Demo Band", "address": "BB"},
        ]

    collector = HeartRateCollector(device_name="Demo Band")
    monkeypatch.setattr(collector, "scan_devices", fake_scan_devices)

    with pytest.raises(RuntimeError, match='找到多个名称包含 "Demo Band" 的 BLE 设备'):
        asyncio.run(collector._find_device())


def test_resolve_notify_uuid_prefers_standard_characteristic():
    collector = HeartRateCollector(device_name="Demo Band")
    services = [
        make_service(
            "service-1",
            [
                make_characteristic("00001234-0000-1000-8000-00805f9b34fb", ["notify"]),
                make_characteristic(
                    "00002A37-0000-1000-8000-00805F9B34FB",
                    ["notify"],
                ),
            ],
        )
    ]

    notify_uuid = collector._resolve_notify_uuid(services)

    assert notify_uuid == "00002A37-0000-1000-8000-00805F9B34FB"


def test_connect_and_disconnect_update_state(monkeypatch):
    device = SimpleNamespace(
        name="Demo Band",
        address="00:11:22:33:44:55",
        services=[
            make_service(
                "service-1",
                [
                    make_characteristic(
                        "00002A37-0000-1000-8000-00805F9B34FB",
                        ["notify"],
                    )
                ],
            )
        ],
    )

    async def fake_find_device_by_address(address, timeout=8.0):
        assert address == "00:11:22:33:44:55"
        assert timeout == 8.0
        return device

    monkeypatch.setattr("intiface_bridge.sensors.heart_rate.BleakClient", FakeBleakClient)
    monkeypatch.setattr(
        "intiface_bridge.sensors.heart_rate.BleakScanner.find_device_by_address",
        fake_find_device_by_address,
    )

    collector = HeartRateCollector(device_address="00:11:22:33:44:55")

    asyncio.run(collector.connect())

    assert collector.connected is True
    assert collector.streaming is True
    assert collector.selected_device_name == "Demo Band"
    assert collector.selected_device_address == "00:11:22:33:44:55"
    assert collector.notify_char_uuid == "00002a37-0000-1000-8000-00805f9b34fb"
    assert collector.client is not None
    assert collector.client.started_notify_uuid == "00002A37-0000-1000-8000-00805F9B34FB"

    collector._handle_notification(None, bytearray.fromhex("10480002"))
    assert collector.get_latest_sample() is not None
    assert collector.status()["latest_bpm"] == 72

    asyncio.run(collector.disconnect())

    assert collector.connected is False
    assert collector.streaming is False
    assert collector.client is None
    assert collector.selected_device_name is None
    assert collector.selected_device_address is None
    assert collector.notify_char_uuid is None
    assert collector.get_latest_sample() is None
    assert collector.status()["latest_bpm"] is None
    assert collector.status()["last_packet_at"] is None


def test_wait_for_sample_times_out_without_packets():
    collector = HeartRateCollector(device_name="Demo Band")

    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(collector.wait_for_sample(timeout=0.01))

