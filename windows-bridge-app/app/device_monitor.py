import time
import threading
import logging

logger = logging.getLogger(__name__)


class DetectedDevice:
    """Info about a detected device."""

    def __init__(self, ip: str = "", mac: str = "", method: str = ""):
        self.ip = ip
        self.mac = mac
        self.method = method  # detection method that found it

    def __repr__(self):
        return f"DetectedDevice(ip={self.ip!r}, mac={self.mac!r}, method={self.method!r})"


class DeviceMonitor:
    """Polls WMI for target device presence and fires callbacks on state changes."""

    def __init__(self, config, on_device_connected, on_device_disconnected):
        self._config = config
        self._on_connected = on_device_connected
        self._on_disconnected = on_device_disconnected
        self._device_present = False
        self._detected_device = None  # DetectedDevice when connected
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

    @property
    def detected_device(self):
        """Returns DetectedDevice info (ip, mac) if device is present, else None."""
        return self._detected_device

    def _poll_loop(self):
        # WMI uses COM; must initialize COM on this thread
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import wmi
            w = wmi.WMI()
            while self._running:
                try:
                    device_info = self._check_device(w)
                    found = device_info is not None
                    if found and not self._device_present:
                        self._device_present = True
                        self._detected_device = device_info
                        logger.info("Target device CONNECTED: %s", device_info)
                        self._on_connected(device_info)
                    elif not found and self._device_present:
                        self._device_present = False
                        self._detected_device = None
                        logger.info("Target device DISCONNECTED")
                        self._on_disconnected()
                except Exception:
                    logger.exception("Error during device polling")
                time.sleep(self._config.app.poll_interval_seconds)
        finally:
            pythoncom.CoUninitialize()

    def _check_device(self, w):
        """Check for target device. Returns DetectedDevice if found, None otherwise."""
        device_cfg = self._config.target_device

        if device_cfg.detection_method == "hardware_id":
            query = (
                f"SELECT * FROM Win32_PnPEntity "
                f"WHERE PNPDeviceID LIKE '%{device_cfg.hardware_id}%'"
            )
            results = w.query(query)
            if results:
                return DetectedDevice(method="hardware_id")
            return None

        elif device_cfg.detection_method == "friendly_name":
            query = (
                f"SELECT * FROM Win32_PnPEntity "
                f"WHERE Name LIKE '%{device_cfg.friendly_name}%'"
            )
            results = w.query(query)
            if results:
                return DetectedDevice(method="friendly_name")
            return None

        elif device_cfg.detection_method == "mac_address":
            return self._check_mac_address(w, device_cfg.mac_prefix)

        elif device_cfg.detection_method == "ethernet_link":
            if self._check_ethernet_link(w):
                return DetectedDevice(method="ethernet_link")
            return None

        return None

    def _check_mac_address(self, w, mac_prefix: str):
        """Check if a device with matching MAC prefix is on the ethernet link.

        Returns DetectedDevice(ip, mac) if found, None otherwise.

        Steps:
        1. Check ethernet link is up (no point scanning if cable is disconnected)
        2. Send a subnet broadcast ping to populate the ARP table
        3. Also try Get-NetNeighbor via PowerShell for reliable neighbor discovery
        4. Search ARP/neighbor table for MAC prefix match → return IP + full MAC
        """
        import subprocess

        # First, check if ethernet link is even up
        if not self._check_ethernet_link(w):
            return None

        # Normalize prefix: accept "78:E9:80", "78-E9-80", "78E980"
        raw = mac_prefix.upper().replace(":", "").replace("-", "")
        if len(raw) < 6:
            logger.warning("MAC prefix too short: %s", mac_prefix)
            return None
        prefix_dash = f"{raw[0:2]}-{raw[2:4]}-{raw[4:6]}"

        # Trigger ARP population: ping the subnet broadcast or common gateway
        ethernet_cfg = self._config.ethernet_adapter
        self._populate_arp_table(ethernet_cfg.static_ip, ethernet_cfg.subnet_mask)

        # Method 1: Check ARP table via 'arp -a'
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.split("\n"):
                line = line.strip()
                parts = line.split()
                if len(parts) >= 2:
                    mac = parts[1].upper()
                    if mac.startswith(prefix_dash):
                        device_ip = parts[0]
                        full_mac = mac
                        logger.info("Found target device: MAC=%s IP=%s", full_mac, device_ip)
                        return DetectedDevice(ip=device_ip, mac=full_mac, method="mac_address")
        except Exception:
            logger.exception("ARP table query failed")

        # Method 2: Check via PowerShell Get-NetNeighbor (more reliable on Win10+)
        try:
            ps_cmd = "Get-NetNeighbor | Where-Object { $_.State -ne 'Unreachable' } | Select-Object -Property IPAddress,LinkLayerAddress | Format-Table -HideTableHeaders"
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15,
            )
            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    mac_clean = parts[1].upper().replace("-", "").replace(":", "")
                    if mac_clean.startswith(raw[:6]):
                        device_ip = parts[0]
                        full_mac = parts[1].upper()
                        logger.info("Found target device (NetNeighbor): MAC=%s IP=%s", full_mac, device_ip)
                        return DetectedDevice(ip=device_ip, mac=full_mac, method="mac_address")
        except Exception:
            logger.exception("Get-NetNeighbor query failed")

        return None

    @staticmethod
    def _populate_arp_table(local_ip: str, subnet_mask: str):
        """Send broadcast ping to populate ARP table for the local subnet."""
        import subprocess

        # Calculate broadcast address from IP and mask
        try:
            ip_parts = [int(x) for x in local_ip.split(".")]
            mask_parts = [int(x) for x in subnet_mask.split(".")]
            broadcast_parts = [(ip_parts[i] | (~mask_parts[i] & 0xFF)) for i in range(4)]
            broadcast = ".".join(str(x) for x in broadcast_parts)

            # Ping broadcast (will timeout quickly, but populates ARP)
            subprocess.run(
                ["ping", "-n", "1", "-w", "500", broadcast],
                capture_output=True, timeout=5,
            )

            # Also ping a few common addresses in the subnet
            base = [ip_parts[i] & mask_parts[i] for i in range(4)]
            for host in [1, 2, 254]:
                target = base.copy()
                target[3] = host
                target_ip = ".".join(str(x) for x in target)
                if target_ip != local_ip:
                    subprocess.run(
                        ["ping", "-n", "1", "-w", "300", target_ip],
                        capture_output=True, timeout=3,
                    )
        except Exception:
            pass  # Best-effort; ARP table may already have entries

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
