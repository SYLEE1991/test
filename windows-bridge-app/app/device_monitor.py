import time
import threading
import logging

logger = logging.getLogger(__name__)


class DeviceMonitor:
    """Polls WMI for target device presence and fires callbacks on state changes."""

    def __init__(self, config, on_device_connected, on_device_disconnected):
        self._config = config
        self._on_connected = on_device_connected
        self._on_disconnected = on_device_disconnected
        self._device_present = False
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Device monitor started (polling every %ds)", self._config.app.poll_interval_seconds)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Device monitor stopped")

    @property
    def is_device_present(self):
        return self._device_present

    def _poll_loop(self):
        # WMI uses COM; must initialize COM on this thread
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import wmi
            w = wmi.WMI()
            while self._running:
                try:
                    found = self._check_device(w)
                    if found and not self._device_present:
                        self._device_present = True
                        logger.info("Target device CONNECTED")
                        self._on_connected()
                    elif not found and self._device_present:
                        self._device_present = False
                        logger.info("Target device DISCONNECTED")
                        self._on_disconnected()
                except Exception:
                    logger.exception("Error during device polling")
                time.sleep(self._config.app.poll_interval_seconds)
        finally:
            pythoncom.CoUninitialize()

    def _check_device(self, w) -> bool:
        device_cfg = self._config.target_device

        if device_cfg.detection_method == "hardware_id":
            # Match by PNP Device ID (partial match via LIKE)
            query = (
                f"SELECT * FROM Win32_PnPEntity "
                f"WHERE PNPDeviceID LIKE '%{device_cfg.hardware_id}%'"
            )
            results = w.query(query)
            return len(results) > 0

        elif device_cfg.detection_method == "friendly_name":
            query = (
                f"SELECT * FROM Win32_PnPEntity "
                f"WHERE Name LIKE '%{device_cfg.friendly_name}%'"
            )
            results = w.query(query)
            return len(results) > 0

        elif device_cfg.detection_method == "mac_address":
            # Detect by MAC address prefix (OUI) on the ethernet adapter
            return self._check_mac_address(w, device_cfg.mac_prefix)

        elif device_cfg.detection_method == "ethernet_link":
            # Simply detect if the ethernet adapter has link up
            return self._check_ethernet_link(w)

        return False

    def _check_mac_address(self, w, mac_prefix: str) -> bool:
        """Check if any connected network adapter's peer has a matching MAC prefix.

        For directly-connected devices (e.g. via ethernet cable), we check
        the ARP table for entries on the ethernet adapter's subnet that
        match the target MAC OUI prefix.
        """
        import subprocess

        # Normalize prefix: accept "00:1A:2B", "00-1A-2B", "001A2B"
        prefix = mac_prefix.upper().replace(":", "-")
        if "-" not in prefix and len(prefix) >= 6:
            prefix = f"{prefix[0:2]}-{prefix[2:4]}-{prefix[4:6]}"

        # Query ARP table for the ethernet adapter's subnet
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.split("\n"):
                # ARP output format: "  192.168.1.1    00-1a-2b-3c-4d-5e   dynamic"
                line = line.strip()
                parts = line.split()
                if len(parts) >= 2:
                    mac = parts[1].upper()
                    if mac.startswith(prefix):
                        logger.debug("Found matching MAC: %s (IP: %s)", mac, parts[0])
                        return True
        except Exception:
            logger.exception("ARP table query failed")

        # Fallback: also check directly connected adapters via WMI
        ethernet_name = self._config.ethernet_adapter.name
        adapters = w.Win32_NetworkAdapter(NetConnectionID=ethernet_name)
        for adapter in adapters:
            if adapter.MACAddress:
                peer_mac = adapter.MACAddress.upper().replace(":", "-")
                if peer_mac.startswith(prefix):
                    return True

        return False

    def _check_ethernet_link(self, w) -> bool:
        """Check if the configured ethernet adapter has an active link."""
        ethernet_name = self._config.ethernet_adapter.name
        adapters = w.Win32_NetworkAdapter(NetConnectionID=ethernet_name)
        for adapter in adapters:
            # NetConnectionStatus: 2 = Connected
            if adapter.NetConnectionStatus == 2:
                return True
        return False

    @staticmethod
    def list_usb_devices():
        """Utility: list all USB PnP devices (for settings GUI)."""
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import wmi
            w = wmi.WMI()
            devices = w.Win32_PnPEntity()
            result = []
            for d in devices:
                if d.PNPDeviceID and "USB" in d.PNPDeviceID:
                    result.append({
                        "name": d.Name or "(unknown)",
                        "hardware_id": d.PNPDeviceID,
                        "status": d.Status,
                    })
            return result
        finally:
            pythoncom.CoUninitialize()
