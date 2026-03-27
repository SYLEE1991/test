import tkinter as tk
from tkinter import ttk
import threading
import subprocess
import logging

logger = logging.getLogger(__name__)


class ScanWindow:
    """Startup scan window that scans the ethernet subnet and shows detected devices."""

    def __init__(self, config):
        self._config = config
        self._root = None
        self._found_devices = []
        self._scanning = False

    def run(self):
        """Show scan window. Blocks until closed. Returns list of found devices."""
        self._root = tk.Tk()
        self._root.title("Gateway Device Scanner")
        self._root.geometry("500x400")
        self._root.resizable(False, False)

        # Center window on screen
        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        x = (self._root.winfo_screenwidth() // 2) - (w // 2)
        y = (self._root.winfo_screenheight() // 2) - (h // 2)
        self._root.geometry(f"+{x}+{y}")

        # --- Header ---
        header = ttk.Frame(self._root)
        header.pack(fill="x", padx=15, pady=(15, 5))

        ttk.Label(header, text="Gateway Device Scanner", font=("Segoe UI", 14, "bold")).pack(anchor="w")

        info_text = f"Subnet: {self._config.ethernet_adapter.static_ip} / {self._config.ethernet_adapter.subnet_mask}"
        info_text += f"    MAC Filter: {self._config.target_device.mac_prefix}"
        ttk.Label(header, text=info_text, foreground="gray").pack(anchor="w", pady=(2, 0))

        # --- Status ---
        status_frame = ttk.Frame(self._root)
        status_frame.pack(fill="x", padx=15, pady=(10, 5))

        self._status_label = ttk.Label(status_frame, text="Preparing to scan...", font=("Segoe UI", 10))
        self._status_label.pack(side="left")

        self._count_label = ttk.Label(status_frame, text="", font=("Segoe UI", 10, "bold"))
        self._count_label.pack(side="right")

        # --- Progress Bar ---
        self._progress = ttk.Progressbar(self._root, mode="indeterminate", length=470)
        self._progress.pack(padx=15, pady=(0, 10))

        # --- Device List ---
        list_frame = ttk.Frame(self._root)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        columns = ("ip", "mac")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        self._tree.heading("ip", text="IP Address")
        self._tree.heading("mac", text="MAC Address")
        self._tree.column("ip", width=180, anchor="center")
        self._tree.column("mac", width=280, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Buttons ---
        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill="x", padx=15, pady=(5, 15))

        self._rescan_btn = ttk.Button(btn_frame, text="Re-Scan", command=self._start_scan, state="disabled")
        self._rescan_btn.pack(side="left")

        ttk.Button(btn_frame, text="Close", command=self._root.destroy).pack(side="right")

        # Start scanning automatically
        self._start_scan()

        self._root.mainloop()
        return self._found_devices

    def _start_scan(self):
        if self._scanning:
            return

        self._scanning = True
        self._tree.delete(*self._tree.get_children())
        self._found_devices = []
        self._rescan_btn.config(state="disabled")
        self._status_label.config(text="Scanning...")
        self._count_label.config(text="")
        self._progress.start(15)

        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        import concurrent.futures

        ethernet_cfg = self._config.ethernet_adapter
        mac_prefix = self._config.target_device.mac_prefix.upper().replace(":", "").replace("-", "")
        prefix_dash = f"{mac_prefix[0:2]}-{mac_prefix[2:4]}-{mac_prefix[4:6]}"

        local_ip = ethernet_cfg.static_ip
        ip_parts = [int(x) for x in local_ip.split(".")]
        mask_parts = [int(x) for x in ethernet_cfg.subnet_mask.split(".")]
        base = [ip_parts[i] & mask_parts[i] for i in range(4)]

        total = 254
        scanned = [0]

        # Phase 1: Priority IP
        priority_ip = self._config.target_device.priority_ip
        if priority_ip:
            self._update_status(f"Checking priority IP: {priority_ip}...")
            try:
                subprocess.run(
                    ["ping", "-n", "1", "-w", "500", priority_ip],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass
            self._check_arp_and_add(prefix_dash, mac_prefix)

        # Phase 2: Full subnet ping sweep
        self._update_status("Scanning full subnet...")

        def ping_host(host_id):
            target = base.copy()
            target[3] = host_id
            target_ip = ".".join(str(x) for x in target)
            if target_ip != local_ip:
                try:
                    subprocess.run(
                        ["ping", "-n", "1", "-w", "200", target_ip],
                        capture_output=True, timeout=3,
                    )
                except Exception:
                    pass
            scanned[0] += 1
            if scanned[0] % 25 == 0:
                pct = int(scanned[0] / total * 100)
                self._update_status(f"Scanning... {pct}% ({scanned[0]}/{total})")

        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            pool.map(ping_host, range(1, 255))

        # After all pings, check ARP table for matches
        self._update_status("Analyzing results...")
        self._check_arp_and_add(prefix_dash, mac_prefix)

        # Also check Get-NetNeighbor
        self._check_netneighbor_and_add(mac_prefix)

        # Done
        count = len(self._found_devices)
        self._root.after(0, self._scan_complete)

    def _check_arp_and_add(self, prefix_dash: str, raw_prefix: str):
        """Check ARP table and add new matching devices to the list."""
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10,
            )
            seen_ips = {d["ip"] for d in self._found_devices}
            for line in result.stdout.split("\n"):
                line = line.strip()
                parts = line.split()
                if len(parts) >= 2:
                    mac = parts[1].upper()
                    if mac.startswith(prefix_dash) and parts[0] not in seen_ips:
                        device = {"ip": parts[0], "mac": mac}
                        self._found_devices.append(device)
                        seen_ips.add(parts[0])
                        self._root.after(0, lambda d=device: self._add_device_to_tree(d))
        except Exception:
            logger.exception("ARP check failed")

    def _check_netneighbor_and_add(self, raw_prefix: str):
        """Check Get-NetNeighbor and add new matching devices."""
        try:
            ps_cmd = (
                "Get-NetNeighbor | Where-Object { $_.State -ne 'Unreachable' } | "
                "Select-Object -Property IPAddress,LinkLayerAddress | "
                "Format-Table -HideTableHeaders"
            )
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=15,
            )
            seen_ips = {d["ip"] for d in self._found_devices}
            for line in result.stdout.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    mac_clean = parts[1].upper().replace("-", "").replace(":", "")
                    if mac_clean.startswith(raw_prefix[:6]) and parts[0] not in seen_ips:
                        device = {"ip": parts[0], "mac": parts[1].upper()}
                        self._found_devices.append(device)
                        seen_ips.add(parts[0])
                        self._root.after(0, lambda d=device: self._add_device_to_tree(d))
        except Exception:
            logger.exception("Get-NetNeighbor check failed")

    def _add_device_to_tree(self, device):
        """Add a device row to the treeview (called on main thread)."""
        self._tree.insert("", "end", values=(device["ip"], device["mac"]))
        count = len(self._found_devices)
        self._count_label.config(text=f"{count} device(s)")

    def _update_status(self, text: str):
        self._root.after(0, lambda: self._status_label.config(text=text))

    def _scan_complete(self):
        self._scanning = False
        self._progress.stop()
        self._rescan_btn.config(state="normal")

        count = len(self._found_devices)
        if count == 0:
            self._status_label.config(text="Scan complete - No devices found")
            self._progress.config(mode="determinate", value=0)
        else:
            self._status_label.config(text="Scan complete")
            self._progress.config(mode="determinate", value=100)
        self._count_label.config(text=f"{count} device(s) found")
