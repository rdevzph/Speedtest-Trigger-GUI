import os
import platform
import runpy
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

APP_NAME = "Speedtest Trigger"
APP_VERSION = "v1.0.1"


def resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)


def run_bundled_speedtest_cli():
    script_path = resource_path(os.path.join("speedtest-cli", "speedtest.py"))

    if not os.path.exists(script_path):
        print("Error: bundled speedtest.py not found.", flush=True)
        sys.exit(1)

    original_argv = sys.argv[:]

    try:
        cli_args = [arg for arg in sys.argv[1:] if arg != "--run-speedtest-cli"]
        sys.argv = [script_path] + cli_args
        runpy.run_path(script_path, run_name="__main__")
    finally:
        sys.argv = original_argv


class SpeedtestGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("560x330")
        self.root.resizable(False, False)

        self.process = None
        self.running = False
        self.script_path = resource_path(os.path.join("speedtest-cli", "speedtest.py"))

        self.status_var = tk.StringVar(value="Idle")
        self.telco_var = tk.StringVar(value="-")
        self.server_var = tk.StringVar(value="-")
        self.ping_var = tk.StringVar(value="-")
        self.interval_var = tk.StringVar(value="30")

        container = ttk.Frame(root, padding=16)
        container.pack(fill="both", expand=True)

        title = ttk.Label(
            container, text=f"{APP_NAME} {APP_VERSION}", font=("Arial", 14, "bold")
        )
        title.pack(anchor="w", pady=(0, 12))

        grid = ttk.Frame(container)
        grid.pack(fill="x", pady=(0, 12))

        self.add_row(grid, 0, "Status", self.status_var)
        self.add_row(grid, 1, "Current ISP", self.telco_var)
        self.add_row(grid, 2, "Best Server", self.server_var)
        self.add_row(grid, 3, "Ping", self.ping_var)

        interval_frame = ttk.Frame(container)
        interval_frame.pack(fill="x", pady=(0, 12))

        ttk.Label(interval_frame, text="Loop every (sec):").pack(side="left")
        self.interval_entry = ttk.Entry(
            interval_frame, textvariable=self.interval_var, width=8
        )
        self.interval_entry.pack(side="left", padx=(8, 0))
        ttk.Label(interval_frame, text="Example: 30").pack(side="left", padx=(8, 0))

        btns = ttk.Frame(container)
        btns.pack(fill="x", pady=(8, 8))

        self.start_btn = ttk.Button(
            btns, text="Start Loop", command=self.start_speedtest
        )
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ttk.Button(
            btns, text="Stop", command=self.stop_speedtest, state="disabled"
        )
        self.stop_btn.pack(side="left")

        self.log = tk.Text(container, height=10, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.insert("end", "Ready.\n")
        self.log.config(state="disabled")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def add_row(self, parent, row, label, var):
        ttk.Label(parent, text=f"{label}:", width=14).grid(
            row=row, column=0, sticky="w", pady=4
        )
        ttk.Label(parent, textvariable=var).grid(row=row, column=1, sticky="w", pady=4)

    def append_log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def set_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def set_telco(self, text):
        self.root.after(0, lambda: self.telco_var.set(text))

    def set_server(self, text):
        self.root.after(0, lambda: self.server_var.set(text))

    def set_ping(self, text):
        self.root.after(0, lambda: self.ping_var.set(text))

    def log_line(self, text):
        self.root.after(0, lambda: self.append_log(text))

    def update_buttons(self, running):
        def _update():
            self.start_btn.config(state="disabled" if running else "normal")
            self.stop_btn.config(state="normal" if running else "disabled")
            self.interval_entry.config(state="disabled" if running else "normal")

        self.root.after(0, _update)

    def get_interval(self):
        try:
            value = int(self.interval_var.get().strip())
            return value if value > 0 else 30
        except Exception:
            return 30

    def build_subprocess_kwargs(self, capture_output=True):
        kwargs = {
            "text": True,
            "shell": False,
        }

        if capture_output:
            kwargs.update(
                {
                    "stdout": subprocess.PIPE,
                    "stderr": subprocess.STDOUT,
                    "bufsize": 1,
                }
            )

        if platform.system().lower() == "windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        return kwargs

    def build_speedtest_cmd(self):
        if getattr(sys, "frozen", False):
            return [sys.executable, "--run-speedtest-cli"]
        return [sys.executable, self.script_path]

    def start_speedtest(self):
        if self.running:
            return

        self.update_buttons(True)
        self.set_status("Starting...")
        threading.Thread(target=self.start_loop, daemon=True).start()

    def start_loop(self):
        if self.running:
            return

        self.running = True
        self.set_status("Starting loop...")
        self.set_telco("-")
        self.set_server("-")
        self.set_ping("-")
        self.update_buttons(True)

        threading.Thread(target=self.loop_speedtest, daemon=True).start()

    def stop_speedtest(self):
        self.running = False

        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
            except Exception:
                pass

        self.set_status("Stopped")
        self.update_buttons(False)
        self.log_line("Process stopped by user.")

    def loop_speedtest(self):
        try:
            while self.running:
                self.root.after(0, self.clear_log)
                self.log_line(f"Loop started. Interval: {self.get_interval()}s")

                result = self.run_speedtest_once()

                if not self.running:
                    break

                if result == "retry_soon":
                    wait_time = 5
                else:
                    wait_time = self.get_interval()

                for remaining in range(wait_time, 0, -1):
                    if not self.running:
                        break
                    self.set_status(f"Waiting {remaining}s...")
                    time.sleep(1)

            if self.status_var.get() != "Stopped":
                self.set_status("Stopped")
            self.update_buttons(False)

        except Exception as e:
            self.set_status("Retrying...")
            self.log_line(f"Loop error: {e}")

            while self.running:
                for remaining in range(5, 0, -1):
                    if not self.running:
                        break
                    self.set_status(f"Retrying in {remaining}s...")
                    time.sleep(1)
                break

    def run_speedtest_once(self):
        try:
            if not os.path.exists(self.script_path):
                raise FileNotFoundError("speedtest.py not found")

            self.set_status("Checking ISP and best server...")

            self.process = subprocess.Popen(
                self.build_speedtest_cmd(),
                **self.build_subprocess_kwargs(capture_output=True),
            )

            found_isp = False
            found_server = False
            found_ping = False
            output_lines = []

            for raw_line in self.process.stdout:
                if not self.running:
                    break

                line = raw_line.strip()
                if not line:
                    continue

                output_lines.append(line)
                self.log_line(line)

                if line.startswith("ISP:"):
                    value = line.replace("ISP:", "", 1).strip()
                    self.set_telco(value)
                    self.set_status("ISP detected")
                    found_isp = True

                elif line.startswith("Best Server:"):
                    value = line.replace("Best Server:", "", 1).strip()
                    self.set_server(value)
                    self.set_status("Best server detected")
                    found_server = True

                elif line.startswith("Ping:"):
                    value = line.replace("Ping:", "", 1).strip()
                    self.set_ping(value)
                    self.set_status("Ping detected")
                    found_ping = True

            if self.process:
                self.process.wait(timeout=5)

            if not self.running:
                return "stopped"

            joined_output = "\n".join(output_lines)

            if self.process and self.process.returncode not in (0, None):
                retryable_markers = [
                    "429",
                    "Too Many Requests",
                    "Failed to retrieve server list",
                    "timed out",
                    "timeout",
                    "Temporary failure",
                    "Connection reset",
                    "Connection aborted",
                    "Connection refused",
                    "Name or service not known",
                    "Network is unreachable",
                ]

                if any(
                    marker.lower() in joined_output.lower()
                    for marker in retryable_markers
                ):
                    self.set_status("Rate limited / retrying")
                    self.log_line(
                        "Temporary speedtest error detected. Retrying in 5 seconds..."
                    )
                    return "retry_soon"

                raise RuntimeError(
                    f"speedtest.py exited with code {self.process.returncode}"
                )

            if found_isp or found_server or found_ping:
                self.set_status("Updated")
                return "ok"

            self.set_status("No data")
            self.log_line(
                "No ISP/server/ping output detected. Retrying in 5 seconds..."
            )
            return "retry_soon"

        except FileNotFoundError:
            self.running = False
            self.update_buttons(False)
            self.set_status("Missing speedtest.py")
            self.log_line("Error: bundled speedtest.py not found.")
            return "fatal"

        except Exception as e:
            if self.running:
                self.set_status("Retrying...")
                self.log_line(f"Error: {e}")
                self.log_line("Retrying in 5 seconds...")
                return "retry_soon"

            self.set_status("Stopped")
            return "stopped"

    def on_close(self):
        self.stop_speedtest()
        self.root.destroy()


if __name__ == "__main__":
    if getattr(sys, "frozen", False) and "--run-speedtest-cli" in sys.argv:
        run_bundled_speedtest_cli()
        sys.exit(0)

    root = tk.Tk()

    try:
        if platform.system().lower() == "windows":
            root.iconbitmap(resource_path("icon.ico"))
        else:
            root.iconphoto(True, tk.PhotoImage(file=resource_path("icon.png")))
    except Exception as e:
        print("Icon load failed:", e)

    app = SpeedtestGUI(root)
    root.mainloop()
