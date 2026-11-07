#!/usr/bin/env python3
"""
BAS1C AI Image Renamer
GUI for renaming one image or a whole folder using a local Ollama vision model.
Requires Windows, Python 3.10+, Ollama, and minicpm-v (or another vision model).
"""

import csv
import json
import os
import re
import threading
import time
import base64
import queue
import traceback
from pathlib import Path
from io import BytesIO
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import requests
from PIL import Image, ImageOps

APP_NAME = "BAS1C AI Image Renamer"
OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "minicpm-v"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
IMAGE_MAX_SIZE = (1280, 1280)
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 600

PROMPT = """You are a precise visual asset librarian. Inspect the actual image.
Identify the main visible subject, object, scene, setting, and distinguishing details.
Create a useful filename based ONLY on what is visibly supported by the image.
Prefer specific names over generic names. Preserve recognizable brand or place names
only when clearly legible or identifiable. Do not guess text, brands, locations, or objects.
Do not copy the original filename. Do not use filler such as image, photo, picture, asset.
A filename may contain 2 to 8 meaningful words, lowercase, separated by hyphens.
Return ONLY valid JSON in this exact structure:
{"description":"brief factual visual description","filename":"descriptive-hyphenated-name"}
If the image is genuinely blank/black, say so in the description and use
"blank-black-image" or "blank-black-screen" as appropriate."""

def slugify(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"\.(png|jpe?g|webp)$", "", value, flags=re.I)
    value = value.replace("_", "-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    words = [w for w in value.split("-") if w]
    if not words:
        raise ValueError("The model returned an empty filename.")
    if len(words) > 8:
        value = "-".join(words[:8])
    return value

def image_to_base64(path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail(IMAGE_MAX_SIZE)
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=86, optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii")

def parse_response(content):
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError("Could not parse JSON from model response.")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Model response was not a JSON object.")
    return data

def ollama_model_exists(model):
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
    r.raise_for_status()
    names = [m.get("name", "") for m in r.json().get("models", [])]
    return any(n == model or n.startswith(model + ":") for n in names), names

def analyze(path, model):
    image = image_to_base64(path)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT, "images": [image]}],
        "format": "json",
        "stream": False,
        "keep_alive": "10m",
        "options": {"temperature": 0.2, "top_p": 0.85}
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload,
                      timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    r.raise_for_status()
    content = r.json().get("message", {}).get("content", "")
    if not content.strip():
        raise ValueError("Ollama returned an empty response.")
    data = parse_response(content)
    return str(data.get("description", "")).strip(), slugify(data.get("filename", ""))

def unique_filename(folder, base, ext, reserved):
    candidate = f"{base}{ext}"
    i = 1
    while candidate.casefold() in reserved or (folder / candidate).exists():
        candidate = f"{base}-{i}{ext}"
        i += 1
    reserved.add(candidate.casefold())
    return candidate

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("850x620")
        self.minsize(760, 540)
        self.configure(bg="#111318")
        self.q = queue.Queue()
        self.busy = False
        self.plan = []
        self._build()
        self.after(100, self._poll)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#111318")
        style.configure("TLabel", background="#111318", foreground="#e8eaf0")
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Sub.TLabel", foreground="#aab0bd")
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=9)
        style.configure("TEntry", padding=6)

        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="BAS1C AI IMAGE RENAMER", style="Title.TLabel").pack(anchor="w")
        ttk.Label(root, text="Local visual naming powered by Ollama + MiniCPM-V",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 16))

        modelrow = ttk.Frame(root)
        modelrow.pack(fill="x", pady=(0, 12))
        ttk.Label(modelrow, text="Vision model:").pack(side="left")
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Entry(modelrow, textvariable=self.model_var, width=24).pack(side="left", padx=8)
        ttk.Label(modelrow, text="Default: minicpm-v", style="Sub.TLabel").pack(side="left")

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=5)
        self.single_btn = ttk.Button(buttons, text="Choose one image…", command=self.choose_single)
        self.single_btn.pack(side="left", padx=(0, 8))
        self.folder_btn = ttk.Button(buttons, text="Choose a folder…", command=self.choose_folder)
        self.folder_btn.pack(side="left")

        self.target_var = tk.StringVar(value="No image or folder selected")
        ttk.Label(root, textvariable=self.target_var, style="Sub.TLabel",
                  wraplength=790).pack(anchor="w", pady=(8, 12))

        opts = ttk.Frame(root)
        opts.pack(fill="x", pady=(0, 12))
        self.recursive_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="Include subfolders (folder mode)",
                        variable=self.recursive_var).pack(side="left")
        self.preview_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Always preview before renaming",
                        variable=self.preview_var).pack(side="left", padx=18)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(0, 12))
        self.run_btn = ttk.Button(actions, text="Analyze & prepare names",
                                  style="Accent.TButton", command=self.start_analysis)
        self.run_btn.pack(side="left")
        self.rename_btn = ttk.Button(actions, text="Execute approved renames",
                                     command=self.execute_plan, state="disabled")
        self.rename_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(actions, text="Open output folder",
                                   command=self.open_output, state="disabled")
        self.open_btn.pack(side="left")

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.pack(fill="x", pady=(4, 8))
        self.status_var = tk.StringVar(value="Ready. Ollama must be running.")
        ttk.Label(root, textvariable=self.status_var, style="Sub.TLabel").pack(anchor="w")

        self.log = tk.Text(root, height=18, bg="#191d25", fg="#e7eaf0",
                           insertbackground="white", relief="flat",
                           font=("Consolas", 9), wrap="word")
        self.log.pack(fill="both", expand=True, pady=(10, 0))
        self.log.configure(state="disabled")
        self.selected_files = []
        self.output_folder = None

    def write_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def choose_single(self):
        p = filedialog.askopenfilename(
            title="Choose one image",
            filetypes=[("Supported images", "*.png *.jpg *.jpeg *.webp"),
                       ("All files", "*.*")]
        )
        if p:
            self.selected_files = [Path(p)]
            self.output_folder = Path(p).parent
            self.target_var.set(f"Single image: {p}")
            self.rename_btn.configure(state="disabled")
            self.plan = []

    def choose_folder(self):
        p = filedialog.askdirectory(title="Choose image folder")
        if p:
            folder = Path(p)
            self.output_folder = folder
            self.selected_files = self.scan(folder)
            self.target_var.set(f"Folder: {folder}  |  {len(self.selected_files)} supported images")
            self.rename_btn.configure(state="disabled")
            self.plan = []

    def scan(self, folder):
        iterator = folder.rglob("*") if self.recursive_var.get() else folder.iterdir()
        return sorted([p for p in iterator if p.is_file() and p.suffix.lower() in EXTENSIONS],
                      key=lambda p: str(p).casefold())

    def set_busy(self, value):
        self.busy = value
        state = "disabled" if value else "normal"
        self.single_btn.configure(state=state)
        self.folder_btn.configure(state=state)
        self.run_btn.configure(state=state)
        if value:
            self.rename_btn.configure(state="disabled")

    def start_analysis(self):
        if self.busy:
            return
        if not self.selected_files:
            messagebox.showinfo(APP_NAME, "Choose one image or a folder first.")
            return
        model = self.model_var.get().strip() or DEFAULT_MODEL
        self.set_busy(True)
        self.plan = []
        self.progress.configure(maximum=len(self.selected_files), value=0)
        self.write_log(f"\n--- Starting analysis: {len(self.selected_files)} image(s), model={model} ---")
        threading.Thread(target=self._analysis_worker, args=(model,), daemon=True).start()

    def _analysis_worker(self, model):
        try:
            ok, names = ollama_model_exists(model)
            if not ok:
                raise RuntimeError(f"Model '{model}' not found in Ollama. Installed: {', '.join(names) or 'none'}")
            files = self.selected_files[:]
            reserved = {p.name.casefold() for p in self.output_folder.rglob("*") if p.is_file()}
            plan = []
            for i, path in enumerate(files, 1):
                try:
                    desc, base = analyze(path, model)
                    new_name = unique_filename(path.parent, base, path.suffix, reserved)
                    plan.append({"source": str(path), "description": desc,
                                 "destination": str(path.with_name(new_name)),
                                 "status": "READY", "error": ""})
                    self.q.put(("log", f"[{i}/{len(files)}] {path.name} -> {new_name}"))
                except Exception as e:
                    plan.append({"source": str(path), "description": "",
                                 "destination": "", "status": "FAILED", "error": str(e)})
                    self.q.put(("log", f"[{i}/{len(files)}] FAILED: {path.name}: {e}"))
                self.q.put(("progress", i))
            self.plan = plan
            plan_path = self.output_folder / "bas1c_rename_plan.json"
            with open(plan_path, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            csv_path = self.output_folder / "bas1c_rename_preview.csv"
            self.save_csv(csv_path, plan)
            self.q.put(("done_analysis", (sum(x["status"] == "READY" for x in plan), len(plan),
                                          str(csv_path), str(plan_path))))
        except Exception as e:
            self.q.put(("fatal", str(e)))

    @staticmethod
    def save_csv(path, plan):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["source", "description", "destination", "status", "error"])
            writer.writeheader()
            writer.writerows(plan)

    def execute_plan(self):
        ready = [x for x in self.plan if x["status"] == "READY"]
        if not ready:
            messagebox.showinfo(APP_NAME, "There are no ready-to-rename images.")
            return
        if not messagebox.askyesno(APP_NAME,
            f"Rename {len(ready)} image(s) now?\n\nA CSV preview is saved in the selected folder.\nExisting files will never be overwritten."):
            return
        self.set_busy(True)
        threading.Thread(target=self._execute_worker, daemon=True).start()

    def _execute_worker(self):
        renamed = 0
        for i, item in enumerate(self.plan, 1):
            if item["status"] != "READY":
                continue
            src = Path(item["source"])
            dst = Path(item["destination"])
            try:
                if not src.exists():
                    raise FileNotFoundError("Source file no longer exists")
                if dst.exists():
                    raise FileExistsError("Destination already exists; refusing to overwrite")
                src.rename(dst)
                item["status"] = "RENAMED"
                renamed += 1
                self.q.put(("log", f"RENAMED: {src.name} -> {dst.name}"))
            except Exception as e:
                item["status"] = "FAILED"
                item["error"] = str(e)
                self.q.put(("log", f"FAILED: {src.name}: {e}"))
        self.save_csv(self.output_folder / "bas1c_rename_report.csv", self.plan)
        with open(self.output_folder / "bas1c_rename_plan.json", "w", encoding="utf-8") as f:
            json.dump(self.plan, f, indent=2, ensure_ascii=False)
        self.q.put(("done_execute", renamed))

    def open_output(self):
        if self.output_folder and self.output_folder.exists():
            os.startfile(str(self.output_folder))

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.write_log(data)
                elif kind == "progress":
                    self.progress.configure(value=data)
                elif kind == "done_analysis":
                    ready, total, csv_path, plan_path = data
                    self.set_busy(False)
                    self.rename_btn.configure(state="normal" if ready else "disabled")
                    self.open_btn.configure(state="normal")
                    self.status_var.set(f"Analysis complete: {ready}/{total} ready. Review bas1c_rename_preview.csv.")
                    self.write_log(f"Analysis complete. Preview: {csv_path}")
                    self.write_log(f"Plan saved: {plan_path}")
                elif kind == "done_execute":
                    self.set_busy(False)
                    self.rename_btn.configure(state="disabled")
                    self.open_btn.configure(state="normal")
                    self.status_var.set(f"Renaming complete: {data} file(s) renamed.")
                    messagebox.showinfo(APP_NAME, f"Finished. {data} file(s) renamed.\nReport saved in the selected folder.")
                elif kind == "fatal":
                    self.set_busy(False)
                    self.status_var.set("Stopped due to an error.")
                    messagebox.showerror(APP_NAME, data)
        except queue.Empty:
            pass
        self.after(100, self._poll)

if __name__ == "__main__":
    App().mainloop()
