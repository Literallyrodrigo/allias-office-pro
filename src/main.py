import os
import sys
import hashlib
import shutil
import threading
import customtkinter as ctk
from tkinter import filedialog
from datetime import datetime
import ctypes

APP_NAME = "com.allias.officepro"

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_NAME)
except:
    pass


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =========================
# HASH
# =========================
def fast_hash(path, quick_bytes=1024 * 1024):
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            h.update(f.read(quick_bytes))
        return h.hexdigest()
    except:
        return None


def full_hash(path, chunk_size=65536):
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except:
        return None


# =========================
# FORENSIC METADATA (MELHORADO)
# =========================
def mtime(path):
    try:
        return os.path.getmtime(path)
    except:
        return float("inf")


def ctime(path):
    """
    Windows: creation time
    Linux: metadata change time (menos confiável)
    """
    try:
        return os.path.getctime(path)
    except:
        return float("inf")


def size(path):
    try:
        return os.path.getsize(path)
    except:
        return 0


def fmt_size(n):
    return f"{n/1024/1024:.2f} MB"


def fmt_time(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "unknown"


# =========================
# APP
# =========================
class AlliasOfficePRO(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("Allias Office PRO")
        self.geometry("1200x750")

        self.folder = ""
        self.duplicates = {}
        self.vars = {}

        self.after(0, lambda: self.iconbitmap(resource_path("assets/icon.ico")))

        header = ctk.CTkFrame(self, height=60, corner_radius=0)
        header.pack(fill="x")

        ctk.CTkLabel(header, text="Allias Office PRO",
                     font=("Arial", 18, "bold")).pack(pady=15)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(container, width=240, corner_radius=0)
        sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(sidebar, text="Control Panel",
                     font=("Arial", 16, "bold")).pack(pady=20)

        ctk.CTkButton(sidebar, text="📁 Select Folder",
                      command=self.select_folder).pack(pady=10, fill="x", padx=10)

        ctk.CTkButton(sidebar, text="🔍 Smart Scan",
                      command=self.scan_thread).pack(pady=10, fill="x", padx=10)

        ctk.CTkButton(sidebar, text="⚡ Auto Select Copies",
                      command=self.auto_select).pack(pady=10, fill="x", padx=10)

        ctk.CTkButton(sidebar, text="🗑 Move to Trash",
                      command=self.delete).pack(pady=10, fill="x", padx=10)

        self.main = ctk.CTkFrame(container)
        self.main.pack(side="right", fill="both", expand=True)

        self.status = ctk.CTkLabel(self.main, text="Ready",
                                   font=("Arial", 16, "bold"))
        self.status.pack(pady=10)

        self.progress = ctk.CTkProgressBar(self.main, width=500)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.scroll = ctk.CTkScrollableFrame(self.main, width=900, height=600)
        self.scroll.pack(pady=10)

    # =========================
    def select_folder(self):
        self.folder = filedialog.askdirectory()
        if self.folder:
            self.status.configure(text=self.folder)

    # =========================
    def scan_thread(self):
        threading.Thread(target=self.scan, daemon=True).start()

    # =========================
    def scan(self):

        if not self.folder:
            return

        self.status.configure(text="Scanning...")

        files = []
        scan_index = 0

        for root, _, fs in os.walk(self.folder):
            for f in fs:
                p = os.path.join(root, f)
                try:
                    files.append((p, os.path.getsize(p), scan_index))
                    scan_index += 1
                except:
                    pass

        # SIZE FILTER
        size_map = {}
        for p, s, idx in files:
            size_map.setdefault(s, []).append((p, idx))

        candidates = {k: v for k, v in size_map.items() if len(v) > 1}

        # FAST HASH
        fast_map = {}
        total = sum(len(v) for v in candidates.values())
        i = 0

        for _, group in candidates.items():
            for p, idx in group:
                h = fast_hash(p)
                if h:
                    fast_map.setdefault(h, []).append((p, idx))

                i += 1
                if total:
                    self.progress.set(i / total)

        # FULL HASH
        full_map = {}

        for _, group in fast_map.items():
            if len(group) <= 1:
                continue

            for p, idx in group:
                h = full_hash(p)
                if h:
                    full_map.setdefault(h, []).append((p, idx))

        # FINAL DECISION
        self.duplicates = {}

        for h, group in full_map.items():
            if len(group) <= 1:
                continue

            enriched = []

            for p, idx in group:
                enriched.append((
                    p,
                    idx,
                    size(p),
                    ctime(p),   # criação (IMPORTANTE)
                    mtime(p)    # modificação
                ))

            # =========================
            # 🔥 ORIGINAL MAIS PROVÁVEL
            # =========================
            enriched.sort(key=lambda x: (
                x[3],   # creation time (principal)
                x[4],   # modification time
                x[1],   # scan order
                x[0]    # path fallback
            ))

            self.duplicates[h] = [x[0] for x in enriched]

        self.render()
        self.status.configure(text="Scan complete")

    # =========================
    def render(self):

        for w in self.scroll.winfo_children():
            w.destroy()

        self.vars = {}

        if not self.duplicates:
            ctk.CTkLabel(self.scroll, text="No duplicates found").pack()
            return

        for h, files in self.duplicates.items():

            frame = ctk.CTkFrame(self.scroll, corner_radius=12)
            frame.pack(fill="x", pady=10, padx=10)

            ctk.CTkLabel(frame, text=f"Hash: {h}",
                         text_color="cyan").pack(anchor="w", padx=10)

            original = files[0]

            ctk.CTkLabel(
                frame,
                text=f"Original kept: {os.path.basename(original)}",
                text_color="green"
            ).pack(anchor="w", padx=10)

            for f in files:

                row = ctk.CTkFrame(frame)
                row.pack(fill="x", padx=10, pady=3)

                var = ctk.BooleanVar()

                cb = ctk.CTkCheckBox(row, text=os.path.basename(f), variable=var)
                cb.pack(side="left", padx=10)

                if f == original:
                    var.set(False)
                    cb.configure(state="disabled")

                meta = (
                    f"{fmt_size(size(f))} | "
                    f"C: {fmt_time(ctime(f))} | "
                    f"M: {fmt_time(mtime(f))}"
                )

                ctk.CTkLabel(
                    row,
                    text=meta,
                    text_color="gray"
                ).pack(side="right", padx=10)

                self.vars[f] = var

    # =========================
    def auto_select(self):
        for files in self.duplicates.values():
            original = files[0]
            for f in files:
                if f != original and f in self.vars:
                    self.vars[f].set(True)

    # =========================
    def delete(self):

        trash = os.path.join(self.folder, "_AlliasTrash")
        os.makedirs(trash, exist_ok=True)

        removed = set()
        saved = 0

        for f, var in self.vars.items():
            if var.get():
                try:
                    saved += size(f)
                    shutil.move(f, trash)
                    removed.add(f)
                except:
                    pass

        new_dupes = {}

        for h, files in self.duplicates.items():
            filtered = [f for f in files if f not in removed]
            if len(filtered) > 1:
                new_dupes[h] = filtered

        self.duplicates = new_dupes

        self.status.configure(text=f"Freed {fmt_size(saved)}")
        self.render()


if __name__ == "__main__":
    app = AlliasOfficePRO()
    app.mainloop()