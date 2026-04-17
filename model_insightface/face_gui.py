#!/usr/bin/env python3
"""
🧠 Motor Biométrico Facial - Interfaz Gráfica Premium (Tkinter)
Diseño moderno con palette oscura, efectos hover, gradientes,
animación de estado y layout tipo dashboard profesional.

Lanza face_engine.py como subproceso para las operaciones de cámara.
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import json
import os
import sys
import threading
import math
from datetime import datetime

# ===================== CONFIGURACIÓN =====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
ENGINE_PATH = os.path.join(BASE_DIR, "face_engine.py")
PYTHON_EXE = sys.executable

# ===================== PALETA =====================
C = {
    "bg":           "#0f0f1a",
    "surface":      "#181830",
    "surface2":     "#1e1e3a",
    "border":       "#2a2a50",
    "accent":       "#6c63ff",
    "accent_h":     "#8b83ff",
    "accent_d":     "#4a42cc",
    "danger":       "#ff4757",
    "danger_h":     "#ff6b7a",
    "success":      "#2ed573",
    "success_d":    "#1ea85a",
    "warning":      "#ffa502",
    "text":         "#e8e8f0",
    "text2":        "#9090b0",
    "text3":        "#606080",
    "input_bg":     "#12122a",
    "log_bg":       "#0a0a18",
    "log_fg":       "#70e090",
    "grad1":        "#6c63ff",
    "grad2":        "#e94580",
}


# ===================== WIDGETS =====================

class GradientBar(tk.Canvas):
    """Barra gradiente horizontal decorativa."""

    def __init__(self, parent, height=3, c1=None, c2=None, **kw):
        self.c1, self.c2 = c1 or C["grad1"], c2 or C["grad2"]
        bg = kw.pop("bg", None) or parent.cget("bg")
        super().__init__(parent, height=height, highlightthickness=0, bg=bg, **kw)
        self.bind("<Configure>", self._draw)

    def _draw(self, e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return
        r1, g1, b1 = self._h2r(self.c1)
        r2, g2, b2 = self._h2r(self.c2)
        for i in range(w):
            t = i / max(w - 1, 1)
            c = f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"
            self.create_line(i, 0, i, h, fill=c)

    @staticmethod
    def _h2r(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class PulsingDot(tk.Canvas):
    """Indicador de estado con animación pulsante."""

    def __init__(self, parent, size=10, color=None, **kw):
        bg = kw.pop("bg", None) or parent.cget("bg")
        super().__init__(parent, width=size + 10, height=size + 10,
                         highlightthickness=0, bg=bg, **kw)
        self._s = size
        self._c = color or C["success"]
        self._run = False
        self._step = 0
        self._draw_static()

    def _draw_static(self):
        self.delete("all")
        m = (self._s + 10) // 2
        r = self._s // 2
        self.create_oval(m-r, m-r, m+r, m+r, fill=self._c, outline="")

    def set_color(self, c):
        self._c = c
        self._draw_static()

    def start_pulse(self, c=None):
        if c:
            self._c = c
        self._run = True
        self._step = 0
        self._tick()

    def stop_pulse(self, c=None):
        self._run = False
        if c:
            self._c = c
        self._draw_static()

    def _tick(self):
        if not self._run:
            return
        self.delete("all")
        m = (self._s + 10) // 2
        r = self._s // 2
        self._step = (self._step + 1) % 24
        s = 1.0 + 0.6 * math.sin(self._step * math.pi / 12)
        pr = int(r * s)
        self.create_oval(m-pr, m-pr, m+pr, m+pr, fill="", outline=self._c, width=1)
        self.create_oval(m-r, m-r, m+r, m+r, fill=self._c, outline="")
        self.after(70, self._tick)


class StyledButton(tk.Frame):
    """Botón con hover effect usando Frame+Label (más robusto que Canvas)."""

    def __init__(self, parent, text="", icon="", command=None,
                 bg_color=None, hover_color=None, press_color=None,
                 fg="#ffffff", width=22, height=2, font_size=12,
                 font_weight="bold", padx=0, pady=0):
        super().__init__(parent, bg=parent.cget("bg"))
        self._bg = bg_color or C["accent"]
        self._hover = hover_color or C["accent_h"]
        self._press = press_color or C["accent_d"]
        self._fg = fg
        self._cmd = command
        self._ok = True

        display = f"{icon}  {text}" if icon else text

        # Outer glow frame
        self._glow = tk.Frame(self, bg=self._bg, padx=1, pady=1)
        self._glow.pack(fill=tk.BOTH, expand=True, padx=padx, pady=pady)

        # Inner label acts as button
        self._lbl = tk.Label(
            self._glow, text=display,
            font=("Segoe UI", font_size, font_weight),
            fg=fg, bg=self._bg, cursor="hand2",
            width=width, height=height,
            pady=6, padx=12
        )
        self._lbl.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        for w in (self._glow, self._lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, e):
        if not self._ok:
            return
        self._lbl.config(bg=self._hover)
        self._glow.config(bg=self._hover)

    def _on_leave(self, e):
        if not self._ok:
            return
        self._lbl.config(bg=self._bg)
        self._glow.config(bg=self._bg)

    def _on_press(self, e):
        if not self._ok:
            return
        self._lbl.config(bg=self._press)
        self._glow.config(bg=self._press)

    def _on_release(self, e):
        if not self._ok:
            return
        self._lbl.config(bg=self._hover)
        self._glow.config(bg=self._hover)
        if self._cmd:
            self._cmd()

    def set_enabled(self, v):
        self._ok = v
        c = self._bg if v else C["text3"]
        cur = "hand2" if v else "arrow"
        self._lbl.config(bg=c, cursor=cur)
        self._glow.config(bg=c)


class MiniButton(tk.Label):
    """Botón mini para acciones secundarias, basado en Label."""

    def __init__(self, parent, text="", command=None,
                 bg_color=None, hover_color=None, fg_color=None,
                 font_size=8, padx_inner=8, **kw):
        self._bg = bg_color or C["surface2"]
        self._hover = hover_color or C["border"]
        self._fg = fg_color or C["text2"]
        self._fg_h = C["text"]
        self._cmd = command
        super().__init__(parent, text=text, font=("Segoe UI", font_size),
                         bg=self._bg, fg=self._fg, cursor="hand2",
                         padx=padx_inner, pady=3, relief=tk.FLAT, **kw)
        self.bind("<Enter>", lambda e: self.config(bg=self._hover, fg=self._fg_h))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg, fg=self._fg))
        self.bind("<ButtonRelease-1>", lambda e: self._cmd() if self._cmd else None)


# ===================== APP PRINCIPAL =====================
class FaceAuthApp:

    def __init__(self, root):
        self.root = root
        self.root.title("  Autenticación Facial · InsightFace")
        self.root.configure(bg=C["bg"])
        self.is_running = False
        self._build_ui()
        self._refresh_profiles()

    def _build_ui(self):
        wrap = tk.Frame(self.root, bg=C["bg"])
        wrap.pack(fill=tk.BOTH, expand=True)

        # ═══════════════ HEADER ═══════════════
        hdr = tk.Frame(wrap, bg=C["bg"])
        hdr.pack(fill=tk.X, padx=30, pady=(26, 0))

        # ── Logo ──
        logo = tk.Canvas(hdr, width=52, height=52, highlightthickness=0,
                         bg=C["bg"])
        logo.pack(side=tk.LEFT, padx=(0, 16))
        # Outer ring
        logo.create_oval(2, 2, 50, 50, outline=C["accent"], width=2.5, fill="")
        # Inner circle
        logo.create_oval(8, 8, 44, 44, fill=C["accent"], outline="")
        # Face icon (head + body silhouette)
        logo.create_oval(19, 12, 33, 27, fill="#ffffff", outline="")
        logo.create_arc(13, 24, 39, 48, start=0, extent=180,
                        fill="#ffffff", outline="")

        # ── Titles ──
        txt = tk.Frame(hdr, bg=C["bg"])
        txt.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(txt, text="Autenticación Facial",
                 font=("Segoe UI", 22, "bold"), fg=C["text"],
                 bg=C["bg"]).pack(anchor=tk.W)
        tk.Label(txt, text="InsightFace ArcFace  ·  Multiusuario  ·  Offline",
                 font=("Segoe UI", 9), fg=C["text3"],
                 bg=C["bg"]).pack(anchor=tk.W, pady=(2, 0))

        # ── Status dot ──
        self.dot = PulsingDot(hdr, size=10, color=C["success"])
        self.dot.pack(side=tk.RIGHT, pady=12)

        # ── Gradient line ──
        GradientBar(wrap, height=2).pack(fill=tk.X, padx=30, pady=(16, 22))

        # ═══════════════ USUARIO ═══════════════
        sec = tk.Frame(wrap, bg=C["bg"])
        sec.pack(fill=tk.X, padx=30)

        self._section_lbl(sec, "USUARIO")

        # Input with glow border
        self._inp_border = tk.Frame(sec, bg=C["border"], padx=2, pady=2)
        self._inp_border.pack(fill=tk.X, pady=(0, 2))

        inp_inner = tk.Frame(self._inp_border, bg=C["input_bg"])
        inp_inner.pack(fill=tk.X)

        tk.Label(inp_inner, text="  👤 ", font=("Segoe UI", 14),
                 bg=C["input_bg"], fg=C["text3"]).pack(side=tk.LEFT, padx=(8, 0))

        self.uname = tk.StringVar()
        self.entry = tk.Entry(inp_inner, textvariable=self.uname,
                              font=("Segoe UI", 14), bg=C["input_bg"],
                              fg=C["text"], insertbackground=C["accent"],
                              relief=tk.FLAT, highlightthickness=0, bd=0)
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True,
                        padx=(6, 14), pady=11, ipady=2)
        self.entry.focus_set()

        # Placeholder logic
        self._ph = True
        self._set_placeholder()
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)
        self.entry.bind("<Return>", lambda e: self._on_login())

        tk.Label(sec, text="Escribe un nombre  ·  Enter = login rápido",
                 font=("Segoe UI", 8), fg=C["text3"],
                 bg=C["bg"]).pack(anchor=tk.W, pady=(4, 0))

        # ═══════════════ ACCIONES ═══════════════
        sec2 = tk.Frame(wrap, bg=C["bg"])
        sec2.pack(fill=tk.X, padx=30, pady=(18, 0))

        self._section_lbl(sec2, "ACCIONES")

        row = tk.Frame(sec2, bg=C["bg"])
        row.pack(fill=tk.X)

        self.btn_reg = StyledButton(
            row, text="Registrar Rostro", icon="📷",
            command=self._on_register,
            bg_color=C["accent"], hover_color=C["accent_h"],
            press_color=C["accent_d"],
            width=18, font_size=12
        )
        self.btn_reg.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.btn_login = StyledButton(
            row, text="Iniciar Sesión", icon="🔐",
            command=self._on_login,
            bg_color=C["success_d"], hover_color=C["success"],
            press_color="#178a47",
            width=18, font_size=12
        )
        self.btn_login.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # ═══════════════ PERFILES ═══════════════
        sec3 = tk.Frame(wrap, bg=C["bg"])
        sec3.pack(fill=tk.X, padx=30, pady=(20, 0))

        prof_hdr = tk.Frame(sec3, bg=C["bg"])
        prof_hdr.pack(fill=tk.X, pady=(0, 8))

        self._section_lbl(prof_hdr, "PERFILES REGISTRADOS", side=tk.LEFT)

        util = tk.Frame(prof_hdr, bg=C["bg"])
        util.pack(side=tk.RIGHT)

        MiniButton(util, text=" ⟳ Refresh ", command=self._refresh_profiles
                   ).pack(side=tk.LEFT, padx=2)
        MiniButton(util, text=" ℹ Info ", command=self._on_info
                   ).pack(side=tk.LEFT, padx=2)
        MiniButton(util, text=" ✕ Eliminar ", command=self._on_delete,
                   bg_color="#2a1525", hover_color="#3d1a30",
                   fg_color=C["danger"]).pack(side=tk.LEFT, padx=2)

        # List
        lb_border = tk.Frame(sec3, bg=C["border"], padx=1, pady=1)
        lb_border.pack(fill=tk.X)
        lb_inner = tk.Frame(lb_border, bg=C["surface"])
        lb_inner.pack(fill=tk.X)

        self.lb = tk.Listbox(
            lb_inner, height=4, font=("Segoe UI", 11),
            bg=C["surface"], fg=C["text2"],
            selectbackground=C["accent"], selectforeground="#ffffff",
            relief=tk.FLAT, highlightthickness=0, activestyle="none",
            bd=0, selectborderwidth=0
        )
        self.lb.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=10, pady=8)
        self.lb.bind("<<ListboxSelect>>", self._on_sel)

        sb = tk.Scrollbar(lb_inner, command=self.lb.yview,
                          troughcolor=C["surface"], bg=C["border"])
        sb.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 4), pady=8)
        self.lb.config(yscrollcommand=sb.set)

        # ═══════════════ LOG ═══════════════
        sec4 = tk.Frame(wrap, bg=C["bg"])
        sec4.pack(fill=tk.BOTH, expand=True, padx=30, pady=(18, 0))

        self._section_lbl(sec4, "ACTIVIDAD")

        log_border = tk.Frame(sec4, bg=C["border"], padx=1, pady=1)
        log_border.pack(fill=tk.BOTH, expand=True)
        log_inner = tk.Frame(log_border, bg=C["log_bg"])
        log_inner.pack(fill=tk.BOTH, expand=True)

        self.log = tk.Text(
            log_inner, height=7, font=("JetBrains Mono", 9),
            bg=C["log_bg"], fg=C["log_fg"],
            insertbackground=C["accent"], relief=tk.FLAT,
            wrap=tk.WORD, state=tk.DISABLED, bd=0,
            padx=14, pady=10, spacing1=3
        )
        self.log.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        lsb = tk.Scrollbar(log_inner, command=self.log.yview,
                            troughcolor=C["log_bg"], bg=C["border"])
        lsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=lsb.set)

        self.log.tag_configure("ok", foreground=C["success"])
        self.log.tag_configure("err", foreground=C["danger"])
        self.log.tag_configure("warn", foreground=C["warning"])
        self.log.tag_configure("info", foreground=C["accent"])
        self.log.tag_configure("dim", foreground=C["text3"])

        # ═══════════════ STATUS BAR ═══════════════
        bar = tk.Frame(self.root, bg=C["surface"], height=30)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        GradientBar(bar, height=1, bg=C["surface"]).pack(fill=tk.X, side=tk.TOP)

        self.status_var = tk.StringVar(value="  ● Listo")
        tk.Label(bar, textvariable=self.status_var,
                 font=("Segoe UI", 8), bg=C["surface"],
                 fg=C["text3"], anchor=tk.W).pack(fill=tk.X, padx=14, pady=3)

        # Init messages
        self._wlog("Sistema biométrico iniciado", "info")
        self._wlog("Motor: InsightFace ArcFace · buffalo_l", "dim")
        self._wlog(f"Perfiles: {PROFILES_DIR}", "dim")

    # ─────────────── UI HELPERS ───────────────
    @staticmethod
    def _section_lbl(parent, text, side=None):
        l = tk.Label(parent, text=text, font=("Segoe UI", 9, "bold"),
                     fg=C["accent"], bg=parent.cget("bg"))
        if side:
            l.pack(side=side)
        else:
            l.pack(anchor=tk.W, pady=(0, 8))

    def _set_placeholder(self):
        if not self.uname.get().strip() or self._ph:
            self._ph = True
            self.entry.config(fg=C["text3"])
            self.uname.set("nombre de usuario...")

    def _focus_in(self, e):
        self._inp_border.config(bg=C["accent"])
        if self._ph:
            self.uname.set("")
            self.entry.config(fg=C["text"])
            self._ph = False

    def _focus_out(self, e):
        self._inp_border.config(bg=C["border"])
        if not self.uname.get().strip():
            self._set_placeholder()

    def _get_uname(self):
        v = self.uname.get().strip()
        return "" if self._ph or v == "nombre de usuario..." else v

    # ─────────────── ENGINE ───────────────
    def _run_engine(self, action, user=None):
        cmd = [PYTHON_EXE, ENGINE_PATH, action]
        if user:
            cmd.append(user)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE_DIR)
        return p.stdout, p.stderr

    def _run_async(self, action, user, cb):
        def work():
            self.is_running = True
            self.root.after(0, lambda: self._set_btns(False))
            self.root.after(0, lambda: self.dot.start_pulse(C["warning"]))
            self.root.after(0, lambda: self._stat(
                f"  ◉ Ejecutando {action}... (cámara abierta)"))

            out, err = self._run_engine(action, user)

            res, lines = None, []
            for ln in out.strip().split('\n'):
                if ln.startswith("__RESULT_JSON__:"):
                    try:
                        res = json.loads(ln.replace("__RESULT_JSON__:", ""))
                    except json.JSONDecodeError:
                        pass
                elif ln.strip():
                    lines.append(ln)

            self.is_running = False
            self.root.after(0, lambda: self._set_btns(True))
            self.root.after(0, lambda: self.dot.stop_pulse(C["success"]))
            self.root.after(0, lambda: cb(res, lines, err))

        threading.Thread(target=work, daemon=True).start()

    # ─────────────── ACTIONS ───────────────
    def _on_register(self):
        u = self._get_uname()
        if not u:
            messagebox.showwarning("Nombre requerido",
                                   "Ingresa un nombre de usuario.")
            self.entry.focus_set()
            return
        if not u.replace("_", "").isalnum():
            messagebox.showwarning("Nombre inválido",
                                   "Solo letras, números y guión bajo.")
            return
        if self.is_running:
            return
        self._wlog(f"Iniciando registro para '{u}'...", "info")
        self._run_async("register", u, self._cb_reg)

    def _cb_reg(self, res, lines, err):
        for ln in lines:
            self._wlog(f"  {ln}", "dim")
        if res and res.get("success"):
            u = res['username']
            c, d, t = res['num_captures'], res['embedding_dim'], res['processing_time_s']
            self._wlog(f"✓ Registrado: {u}  ({c} capturas, {d}D, {t}s)", "ok")
            self._stat(f"  ● Perfil '{u}' registrado")
            messagebox.showinfo("Registro Exitoso",
                                f"Perfil de '{u}' creado.\n\n"
                                f"  Capturas: {c}\n  Embedding: {d}D\n  Tiempo: {t}s")
        else:
            msg = res.get("message", "Error") if res else "Sin respuesta"
            self._wlog(f"✗ Registro fallido: {msg}", "err")
            self._stat("  ● Error en registro")
            messagebox.showerror("Registro Fallido", msg)
        self._refresh_profiles()

    def _on_login(self):
        u = self._get_uname()
        if not u:
            messagebox.showwarning("Nombre requerido", "Ingresa el nombre.")
            self.entry.focus_set()
            return
        if self.is_running:
            return
        if u not in self._get_profiles():
            messagebox.showwarning("No encontrado",
                                   f"No existe perfil para '{u}'.\nRegístralo primero.")
            return
        self._wlog(f"Verificando identidad de '{u}'...", "info")
        self._run_async("login", u, self._cb_login)

    def _cb_login(self, res, lines, err):
        for ln in lines:
            self._wlog(f"  {ln}", "dim")
        if res and res.get("match"):
            sc = res.get("score", 0)
            conf = res.get("confidence_level", "N/A")
            ms = res.get("processing_time_ms", 0)
            self._wlog(f"✓ ACCESO CONCEDIDO  score={sc:.3f}  ({conf})", "ok")
            self._stat(f"  ● Login exitoso · {sc:.3f}")
            messagebox.showinfo("Acceso Concedido",
                                f"Identidad verificada.\n\n"
                                f"  Score: {sc:.3f}\n  Confianza: {conf}\n  Tiempo: {ms}ms")
        else:
            sc = res.get("score", 0) if res else 0
            msg = res.get("message", "No match") if res else "Sin respuesta"
            self._wlog(f"✗ ACCESO DENEGADO  score={sc:.3f}", "err")
            self._stat(f"  ● Login fallido · {sc:.3f}")
            messagebox.showerror("Acceso Denegado",
                                 f"Identidad no verificada.\n\n"
                                 f"  Score: {sc:.3f}\n  {msg}")

    def _on_info(self):
        u = self._get_sel()
        if not u:
            messagebox.showinfo("Info", "Selecciona un perfil de la lista.")
            return
        out, _ = self._run_engine("info", u)
        try:
            i = json.loads(out.strip())
            if "error" in i:
                messagebox.showerror("Error", i["error"])
                return
            ll = i.get('last_login', 'Nunca')
            if ll != 'Nunca':
                ll = ll[:19]
            messagebox.showinfo(f"Perfil: {u}",
                f"  Usuario:        {i['username']}\n"
                f"  Creado:          {i['created'][:19]}\n"
                f"  Capturas:      {i['num_captures']}\n"
                f"  Logins:           {i['login_count']}\n"
                f"  Último login:  {ll}\n"
                f"  Embedding:   {i['embedding_shape']}  {i['embedding_dtype']}")
            self._wlog(f"ℹ {u}: {i['num_captures']} capturas, "
                       f"{i['login_count']} logins", "info")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        u = self._get_sel()
        if not u:
            messagebox.showinfo("Eliminar", "Selecciona un perfil.")
            return
        if not messagebox.askyesno("Confirmar",
                                    f"¿Eliminar perfil '{u}'?\n\nNo se puede deshacer."):
            return
        out, _ = self._run_engine("delete", u)
        try:
            r = json.loads(out.strip())
            if r.get("deleted"):
                self._wlog(f"✓ '{u}' eliminado", "warn")
                self._stat(f"  ● '{u}' eliminado")
                messagebox.showinfo("Eliminado", f"Perfil '{u}' eliminado.")
            else:
                messagebox.showerror("Error", r.get("message", "Error"))
        except Exception as e:
            messagebox.showerror("Error", str(e))
        self._refresh_profiles()

    def _on_sel(self, e):
        u = self._get_sel()
        if u:
            self._ph = False
            self.entry.config(fg=C["text"])
            self.uname.set(u)

    # ─────────────── HELPERS ───────────────
    def _get_profiles(self):
        try:
            out, _ = self._run_engine("list")
            return json.loads(out.strip()).get("profiles", [])
        except:
            return []

    def _refresh_profiles(self):
        profs = self._get_profiles()
        self.lb.delete(0, tk.END)
        if profs:
            for p in sorted(profs):
                self.lb.insert(tk.END, f"    ●  {p}")
            self._stat(f"  ● {len(profs)} perfil(es) registrado(s)")
        else:
            self.lb.insert(tk.END, "     Sin perfiles registrados")
            self._stat("  ○ Sin perfiles — Registra un usuario")

    def _get_sel(self):
        sel = self.lb.curselection()
        if not sel:
            return None
        t = self.lb.get(sel[0]).strip()
        return t.replace("●", "").strip() if "●" in t else None

    def _set_btns(self, ok):
        self.btn_reg.set_enabled(ok)
        self.btn_login.set_enabled(ok)

    def _wlog(self, msg, tag=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, f"[{ts}]  ", "dim")
        self.log.insert(tk.END, f"{msg}\n", tag)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def _stat(self, msg):
        self.status_var.set(msg)


# ===================== MAIN =====================
def main():
    root = tk.Tk()
    root.update_idletasks()
    w, h = 660, 800
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")
    root.minsize(600, 720)
    FaceAuthApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
