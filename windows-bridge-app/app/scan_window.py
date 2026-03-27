import tkinter as tk
from tkinter import ttk
import threading
import subprocess
import logging

logger = logging.getLogger(__name__)


class ScanWindow:
    """Startup window with scan mode selection and device results."""

    def __init__(self, config):
        self._config = config
        self._root = None
        self._found_devices = []
        self._scanning = False
        self._scan_mode = None  # "all" or "direct"

    def run(self):
        """Show scan window. Blocks until closed. Returns list of found devices."""
        self._root = tk.Tk()
        self._root.title("Gateway Device Scanner")
        self._root.geometry("520x480")
        self._root.resizable(False, False)
        self._center_window()

        # --- Header ---
        header = ttk.Frame(self._root)
        header.pack(fill="x", padx=15, pady=(15, 5))
        ttk.Label(header, text="Gateway Device Scanner", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        info_text = f"MAC Filter: {self._config.target_device.mac_prefix}"
        ttk.Label(header, text=info_text, foreground="gray").pack(anchor="w", pady=(2, 0))

        # --- Scan Mode Selection ---
        self._mode_frame = ttk.LabelFrame(self._root, text="Scan Mode", padding=10)
        self._mode_frame.pack(fill="x", padx=15, pady=10)

        btn_all = ttk.Button(
            self._mode_frame,
            text="Network Scan\n(All interfaces)",
            command=lambda: self._start_scan("all"),
        )
        btn_all.pack(side="left", expand=True, fill="both", padx=(0, 5), ipady=15)

        btn_direct = ttk.Button(
            self._mode_frame,
            text="Direct Connection Scan\n(Ethernet only)",
            command=lambda: self._start_scan("direct"),
        )
        btn_direct.pack(side="left", expand=True, fill="both", padx=(5, 0), ipady=15)

        # --- Status ---
        status_frame = ttk.Frame(self._root)
        status_frame.pack(fill="x", padx=15, pady=(5, 3))

        self._status_label = ttk.Label(status_frame, text="Select scan mode to start.", font=("Segoe UI", 10))
        self._status_label.pack(side="left")

        self._count_label = ttk.Label(status_frame, text="", font=("Segoe UI", 10, "bold"))
        self._count_label.pack(side="right")

        # --- Progress Bar ---
        self._progress = ttk.Progressbar(self._root, mode="determinate", length=490, value=0)
        self._progress.pack(padx=15, pady=(0, 5))

        # --- Device List ---
        list_frame = ttk.Frame(self._root)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        columns = ("ip", "mac")
        self._tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self._tree.heading("ip", text="IP Address")
        self._tree.heading("mac", text="MAC Address")
        self._tree.column("ip", width=190, anchor="center")
        self._tree.column("mac", width=280, anchor="center")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Bottom Buttons ---
        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill="x", padx=15, pady=(5, 15))

        self._rescan_btn = ttk.Button(btn_frame, text="Re-Scan", command=self._rescan, state="disabled")
        self._rescan_btn.pack(side="left")

        ttk.Button(btn_frame, text="Close", command=self._root.destroy).pack(side="right")

        self._mode_label = ttk.Label(btn_frame, text="", foreground="gray")
        self._mode_label.pack(side="left", padx=15)

        self._root.mainloop()
        return self._found_devices

    # ---- Scan Control ----

    def _start_scan(self, mode: str):
        if self._scanning:
            return

        self._scan_mode = mode
        self._scanning = True
        self._tree.delete(*self._tree.get_children())
        self._found_devices = []
        self._rescan_btn.config(state="disabled")
        self._count_label.config(text="")
        self._progress.config(mode="indeterminate")
        self._progress.start(15)

        if mode == "all":
            self._status_label.config(text="Scanning all networks...")
            self._mode_label.config(text="Mode: Network Scan")
        else:
            self._status_label.config(text="Scanning ethernet direct connection...")
            self._mode_label.config(text="Mode: Direct Connection")

        threading.Thread(target=self._do_scan, args=(mode,), daemon=True).start()

    def _rescan(self):
        if self._scan_mode:
            self._start_scan(self._scan_mode)

    # ---- Scan Logic ----

    def _do_scan(self, mode: str):
        import concurrent.futures

        ethernet_cfg = self._config.ethernet_adapter
        mac_prefix = self._config.target_device.mac_prefix.upper().replace(":", "").replace("-", "")
        prefix_dash = f"{mac_prefix[0:2]}-{mac_prefix[2:4]}-{mac_prefix[4:6]}"

        local_ip = ethernet_cfg.static_ip
        ip_parts = [int(x) for x in local_ip.split(".")]
        mask_parts = [int(x) for x in ethernet_cfg.subnet_mask.split(".")]
        base = [ip_parts[i] & mask_parts[i] for i in range(4)]

        ethernet_name = ethernet_cfg.name

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
            self._collect_devices(prefix_dash, mac_prefix, mode, ethernet_name, local_ip)

        # Phase 2: Subnet scan
        if mode == "direct":
            # Direct connection: only ping priority IP + gateway + a few common IPs
            # No need to scan 254 hosts for a single cable-connected device
            candidate_ips = set()
            if priority_ip:
                candidate_ips.add(priority_ip)
            # Add gateway
            gw = self._config.ethernet_adapter.gateway
            if gw:
                candidate_ips.add(gw)
            # Add common device IPs (.1, .2, .100, .200, .206, .254)
            for host in [1, 2, 100, 200, 206, 254]:
                target = base.copy()
                target[3] = host
                candidate_ips.add(".".join(str(x) for x in target))
            candidate_ips.discard(local_ip)

            total = len(candidate_ips)
            scanned = [0]
            self._update_status(f"Checking direct connection ({total} IPs)...")

            for ip in candidate_ips:
                try:
                    subprocess.run(
                        ["ping", "-n", "1", "-w", "500", ip],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass
                scanned[0] += 1
                self._update_status(f"Checking... {scanned[0]}/{total}")

            # If no match yet, also try a quick broadcast ping
            self._update_status("Checking broadcast...")
            broadcast_parts = [(ip_parts[i] | (~mask_parts[i] & 0xFF)) for i in range(4)]
            broadcast = ".".join(str(x) for x in broadcast_parts)
            try:
                subprocess.run(
                    ["ping", "-n", "2", "-w", "500", broadcast],
                    capture_output=True, timeout=5,
                )
            except Exception:
                pass

        else:
            # Network scan: full /24 sweep
            total = 254
            scanned = [0]
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

        # Collect final results
        self._update_status("Analyzing results...")
        self._collect_devices(prefix_dash, mac_prefix, mode, ethernet_name, local_ip)

        self._root.after(0, self._scan_complete)

    def _collect_devices(self, prefix_dash, raw_prefix, mode, ethernet_name, ethernet_ip):
        """Collect matching devices from ARP/Neighbor table.

        mode="all"    -> search all interfaces
        mode="direct" -> search ethernet adapter only
        """
        seen_ips = {d["ip"] for d in self._found_devices}

        # --- Get-NetNeighbor ---
        try:
            if mode == "direct":
                ps_cmd = (
                    f"Get-NetNeighbor -InterfaceAlias '{ethernet_name}' -ErrorAction SilentlyContinue | "
                    f"Where-Object {{ $_.State -ne 'Unreachable' }} | "
                    f"Select-Object -Property IPAddress,LinkLayerAddress | "
                    f"Format-Table -HideTableHeaders"
                )
            else:
                ps_cmd = (
                    "Get-NetNeighbor | Where-Object { $_.State -ne 'Unreachable' } | "
                    "Select-Object -Property IPAddress,LinkLayerAddress | "
                    "Format-Table -HideTableHeaders"
                )

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
                    if mac_clean.startswith(raw_prefix[:6]) and parts[0] not in seen_ips:
                        device = {"ip": parts[0], "mac": parts[1].upper()}
                        self._found_devices.append(device)
                        seen_ips.add(parts[0])
                        self._root.after(0, lambda d=device: self._add_device_to_tree(d))
        except Exception:
            logger.exception("Get-NetNeighbor failed")

        # --- arp fallback ---
        try:
            if mode == "direct":
                cmd = ["arp", "-a", "-N", ethernet_ip]
            else:
                cmd = ["arp", "-a"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
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

    # ---- UI Helpers ----

    def _add_device_to_tree(self, device):
        self._tree.insert("", "end", values=(device["ip"], device["mac"]))
        self._count_label.config(text=f"{len(self._found_devices)} device(s)")

    def _update_status(self, text: str):
        self._root.after(0, lambda: self._status_label.config(text=text))

    def _scan_complete(self):
        self._scanning = False
        self._progress.stop()
        self._progress.config(mode="determinate", value=100 if self._found_devices else 0)
        self._rescan_btn.config(state="normal")

        count = len(self._found_devices)
        mode_str = "Network" if self._scan_mode == "all" else "Direct Connection"
        if count == 0:
            self._status_label.config(text=f"{mode_str} scan complete - No devices found")
        else:
            self._status_label.config(text=f"{mode_str} scan complete")
        self._count_label.config(text=f"{count} device(s) found")

    def _center_window(self):
        self._root.update_idletasks()
        w = self._root.winfo_width()
        h = self._root.winfo_height()
        x = (self._root.winfo_screenwidth() // 2) - (w // 2)
        y = (self._root.winfo_screenheight() // 2) - (h // 2)
        self._root.geometry(f"+{x}+{y}")
