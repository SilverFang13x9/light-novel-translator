# -*- coding: utf-8 -*-
"""Light Novel Translator — leitor/tradutor de light novels via Ollama.

Uso:  python main.py
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from extractor import IMG_RE, extract_book, extract_book_images
import json
import re

import requests

from translator import (LANGS, LEVELS, SOURCE_LANGS, ApiClient, CliClient,
                        OllamaClient, apply_name_mapping,
                        build_memory_from_translation,
                        find_name_inconsistencies, learn_glossary,
                        review_translation, suggest_glossary,
                        translate_chapter, update_memory)

APP_VERSION = "1.0.0"
GITHUB_REPO = "SilverFang13x9/light-novel-translator"


def version_newer(remote, local):
    """True se a tag remota (ex.: v1.2.0) é mais nova que a local."""
    def parse(v):
        nums = re.findall(r"\d+", v or "")
        return tuple(int(n) for n in nums[:3]) or (0,)
    return parse(remote) > parse(local)

_APPDIR = os.path.dirname(os.path.abspath(__file__))
API_CONFIG = os.path.join(_APPDIR, "api.json")
SETTINGS = os.path.join(_APPDIR, "settings.json")

# Paleta: preto puro + creme
BG = "#000000"        # fundo principal
PANEL = "#121210"     # painéis/campos (preto aquecido, dá profundidade)
FG = "#FDFBD4"        # texto principal (creme)
ACCENT = "#FDFBD4"    # destaques/seleção (creme sobre preto invertido)
MUTED = "#8a8870"     # texto secundário (creme apagado)
OK_COLOR = "#c9e4a5"  # capítulos concluídos (verde-creme)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Light Novel Translator (Ollama)")
        self.geometry("1280x800")
        self.configure(bg=BG)

        self.client = OllamaClient()
        self.chapters = []           # [(titulo, texto_original)]
        self.translations = {}       # {(idx, lang, level): texto}
        self.current = None          # índice do capítulo atual
        self.glossary = ""           # nomes/termos fixos passados ao modelo
        self.glossary_path = None
        self.memory = ""             # memória da saga (resumo p/ o modelo)
        self.memory_path = None
        self.font_size = 13
        self._stop = threading.Event()
        self._busy = False
        self._q = queue.Queue()

        self.cache_path = None       # traduções persistidas do livro atual
        self.images = {}             # imagens do livro (n -> dados)
        self._build_ui()
        self._load_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll_queue)
        self.after(200, self.refresh_models)
        self.after(1500, self._check_updates)

    def _check_updates(self):
        """Aviso discreto se houver release mais novo no GitHub (silencioso
        em qualquer falha: sem releases, sem internet, etc.)."""
        def work():
            try:
                r = requests.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}"
                    "/releases/latest", timeout=6)
                if r.status_code != 200:
                    return
                tag = r.json().get("tag_name", "")
                if version_newer(tag, APP_VERSION):
                    self._q.put(("status",
                                 f"⬆ Versão {tag} disponível em "
                                 f"github.com/{GITHUB_REPO}"))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------- settings

    def _load_settings(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        self.src_var.set(s.get("src", self.src_var.get()))
        self.lang_var.set(s.get("lang", self.lang_var.get()))
        self.level_var.set(s.get("level", self.level_var.get()))
        self.auto_mem_var.set(s.get("auto_mem", True))
        self.review_var.set(s.get("review", False))
        self._saved_model = s.get("model", "")
        fs = s.get("font_size")
        if fs:
            self.font_size = fs
            self.set_font(0)

    def _save_settings(self):
        try:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({
                    "src": self.src_var.get(),
                    "lang": self.lang_var.get(),
                    "level": self.level_var.get(),
                    "auto_mem": self.auto_mem_var.get(),
                    "review": self.review_var.get(),
                    "model": self.model_var.get(),
                    "font_size": self.font_size,
                }, f, indent=2)
        except OSError:
            pass

    def _on_close(self):
        self._stop.set()
        self._save_settings()
        self._save_reading_position()
        self.destroy()

    # ------------------------------------------------------------- UI

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=FG,
                        fieldbackground=PANEL, bordercolor="#2a2a20",
                        lightcolor=PANEL, darkcolor=BG, focuscolor=ACCENT)
        style.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                        foreground=FG, arrowcolor=FG, borderwidth=0,
                        padding=4)
        # comboboxes "readonly" ignoram o configure no Windows: mapear estado
        style.map("TCombobox",
                  fieldbackground=[("readonly", PANEL), ("disabled", PANEL)],
                  foreground=[("readonly", FG), ("disabled", MUTED)],
                  selectbackground=[("readonly", PANEL)],
                  selectforeground=[("readonly", FG)])
        # a lista suspensa é um Listbox interno, fora do sistema de estilos ttk
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "#000000")
        # botões flat: invertem para creme no hover
        style.configure("TButton", background=PANEL, foreground=FG,
                        padding=(10, 6), borderwidth=0, relief="flat",
                        font=("Segoe UI", 9))
        style.map("TButton",
                  background=[("active", ACCENT), ("pressed", "#d6d4ae"),
                              ("disabled", "#0a0a08")],
                  foreground=[("active", "#000000"), ("pressed", "#000000"),
                              ("disabled", MUTED)])
        style.configure("Horizontal.TProgressbar", background=ACCENT,
                        troughcolor=PANEL, borderwidth=0, thickness=6)
        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(sb, background=PANEL, troughcolor=BG,
                            arrowcolor=MUTED, borderwidth=0, relief="flat")
            style.map(sb, background=[("active", "#2a2a20")])

        # --- barra superior -------------------------------------------------
        top = tk.Frame(self, bg=BG, padx=8, pady=6)
        top.pack(fill="x")

        def menubutton(text):
            """Botão de menu no tema (creme no hover, como os TButton)."""
            mb = tk.Menubutton(top, text=text, bg=PANEL, fg=FG,
                               activebackground=ACCENT,
                               activeforeground="#000000", relief="flat",
                               padx=10, pady=5, font=("Segoe UI", 9))
            menu = tk.Menu(mb, tearoff=0, bg=PANEL, fg=FG,
                           activebackground=ACCENT,
                           activeforeground="#000000", bd=0)
            mb.config(menu=menu)
            mb.pack(side="left", padx=(0, 4))
            return menu

        # --- 📖 Abrir: livro avulso ou saga -----------------------------
        m_open = menubutton("📖 Abrir ▾")
        m_open.add_command(label="Livro (.epub / .pdf / .txt)…",
                           command=self.open_book)
        m_open.add_command(label="Saga (pasta de volumes)…",
                           command=self.open_saga)

        # Marcador de seleção desenhado NO TEXTO do item: herda a cor do
        # rótulo (creme no fundo escuro, preto quando em highlight creme) —
        # o indicador nativo (selectcolor) é de cor única e sumiria num dos
        # dois estados. Menus reconstroem ao abrir (postcommand).
        def mark(on):
            return "●  " if on else "    "

        def submenu(parent):
            return tk.Menu(parent, tearoff=0, bg=PANEL, fg=FG,
                           activebackground=ACCENT,
                           activeforeground="#000000", bd=0)

        # --- ⚙ Motor: backend + modelo + atualizar ----------------------
        self.backend_var = tk.StringVar(value="Ollama")
        self.model_var = tk.StringVar()
        self._models_cache = []
        m_motor = menubutton("⚙ Motor ▾")
        self.model_menu = submenu(m_motor)

        def set_backend(b):
            self.backend_var.set(b)
            self.switch_backend()

        def rebuild_motor():
            m_motor.delete(0, "end")
            for b in ("Ollama", "API", "CLI"):
                m_motor.add_command(
                    label=mark(self.backend_var.get() == b) + b,
                    command=lambda b=b: set_backend(b))
            m_motor.add_separator()
            m_motor.add_cascade(label="Modelo", menu=self.model_menu)
            m_motor.add_command(label="Digitar modelo…",
                                command=self._type_model)
            m_motor.add_command(label="⟳ Atualizar modelos",
                                command=self.refresh_models)

        def rebuild_models():
            self.model_menu.delete(0, "end")
            if not self._models_cache:
                self.model_menu.add_command(
                    label="(nenhum — use Digitar modelo…)", state="disabled")
            for m in self._models_cache:
                self.model_menu.add_command(
                    label=mark(self.model_var.get() == m) + m,
                    command=lambda m=m: self.model_var.set(m))

        m_motor.config(postcommand=rebuild_motor)
        self.model_menu.config(postcommand=rebuild_models)
        rebuild_motor()

        # --- 🌐 Idiomas: origem e destino --------------------------------
        self.src_var = tk.StringVar(value=list(SOURCE_LANGS)[0])
        self.lang_var = tk.StringVar(value=list(LANGS)[0])
        m_lang = menubutton("🌐 Idiomas ▾")
        m_de, m_para = submenu(m_lang), submenu(m_lang)

        def rebuild_lang_menu(menu, options, var):
            menu.delete(0, "end")
            for s in options:
                menu.add_command(label=mark(var.get() == s) + s,
                                 command=lambda s=s, v=var: v.set(s))

        m_de.config(postcommand=lambda: rebuild_lang_menu(
            m_de, list(SOURCE_LANGS), self.src_var))
        m_para.config(postcommand=lambda: rebuild_lang_menu(
            m_para, list(LANGS), self.lang_var))
        m_lang.add_cascade(label="De (origem)", menu=m_de)
        m_lang.add_cascade(label="Para (destino)", menu=m_para)

        tk.Label(top, text="Dinamização:", bg=BG, fg=FG).pack(side="left")
        self.level_var = tk.StringVar(value=LEVELS[0])
        ttk.Combobox(top, textvariable=self.level_var, values=LEVELS,
                     width=18, state="readonly").pack(side="left", padx=(2, 8))

        self.btn_tr = ttk.Button(top, text="▶ Traduzir capítulo",
                                 command=self.translate_current)
        self.btn_tr.pack(side="left", padx=2)
        self.btn_all = ttk.Button(top, text="▶▶ Traduzir tudo",
                                  command=self.translate_all)
        self.btn_all.pack(side="left", padx=2)
        self.btn_stop = ttk.Button(top, text="■ Parar", command=self.stop,
                                   state="disabled")
        self.btn_stop.pack(side="left", padx=2)
        ttk.Button(top, text="💾 Salvar tradução",
                   command=self.save_translation).pack(side="left", padx=2)
        m_learn = menubutton("🎓 Aprender ▾")
        m_learn.add_command(label="Com um par original + tradução…",
                            command=self.learn_from_translation)
        m_learn.add_command(label="Com uma saga (vol01 + vol01t…)…",
                            command=self.learn_saga)

        self.auto_mem_var = tk.BooleanVar(value=True)
        m_tools = menubutton("🛠 Ferramentas ▾")

        def rebuild_tools():
            m_tools.delete(0, "end")
            m_tools.add_command(label="📓 Glossário…",
                                command=self.edit_glossary)
            m_tools.add_command(label="🧠 Memória da saga…",
                                command=self.edit_memory)
            m_tools.add_command(
                label=mark(self.auto_mem_var.get())
                + "Memória automática (a cada capítulo)",
                command=lambda: self.auto_mem_var.set(
                    not self.auto_mem_var.get()))
            m_tools.add_separator()
            m_tools.add_command(label="🔍 Consistência de nomes…",
                                command=self.check_names)
            m_tools.add_command(label="🔊 Gerar áudio do capítulo…",
                                command=self.export_audio)

        m_tools.config(postcommand=rebuild_tools)
        rebuild_tools()
        self.review_var = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text="✨ revisão", variable=self.review_var,
                       bg=BG, fg=FG, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG
                       ).pack(side="left")
        ttk.Button(top, text="👁 Leitura",
                   command=self.toggle_reading_mode).pack(side="left", padx=4)

        tk.Label(top, text="  A⁻/A⁺", bg=BG, fg=FG).pack(side="left", padx=(10, 0))
        ttk.Button(top, text="−", width=3,
                   command=lambda: self.set_font(-1)).pack(side="left")
        ttk.Button(top, text="+", width=3,
                   command=lambda: self.set_font(+1)).pack(side="left")

        # --- corpo -----------------------------------------------------------
        body = tk.PanedWindow(self, orient="horizontal", bg=BG,
                              sashwidth=3, bd=0,
                              sashrelief="flat")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        left = tk.Frame(body, bg=PANEL)
        tk.Label(left, text="Capítulos", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=6, pady=4)
        self.chap_list = tk.Listbox(left, bg=PANEL, fg=FG, bd=0,
                                    highlightthickness=0,
                                    selectbackground=ACCENT,
                                    selectforeground="#000",
                                    font=("Segoe UI", 10), activestyle="none")
        self.chap_list.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.chap_list.bind("<<ListboxSelect>>", self.on_select_chapter)
        body.add(left, width=260)

        right = tk.PanedWindow(body, orient="horizontal", bg=BG,
                               sashwidth=3, bd=0,
                              sashrelief="flat")
        body.add(right)

        self._right_pane = right
        self.txt_src = self._make_text(right, "Original")
        self.txt_dst = self._make_text(right, "Tradução")
        self._reading_mode = False
        # modo bilíngue sincronizado: clique destaca o parágrafo equivalente
        self.txt_src.bind("<Button-1>",
                          lambda e: self._sync_paragraph(e, src=True))
        self.txt_dst.bind("<Button-1>",
                          lambda e: self._sync_paragraph(e, src=False))

        # --- rodapé ----------------------------------------------------------
        bottom = tk.Frame(self, bg=BG, padx=8, pady=4)
        bottom.pack(fill="x")
        self.progress = ttk.Progressbar(bottom, mode="determinate", length=220)
        self.progress.pack(side="left")
        self.status = tk.Label(bottom, text="Abra um livro (.epub / .pdf / .txt)",
                               bg=BG, fg=MUTED, anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=8)

    def _make_text(self, parent, title):
        frame = tk.Frame(parent, bg=PANEL)
        tk.Label(frame, text=title, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=4)
        txt = tk.Text(frame, wrap="word", bg=PANEL, fg=FG, bd=0,
                      insertbackground=FG, padx=16, pady=10,
                      selectbackground=ACCENT, selectforeground="#000000",
                      font=("Georgia", self.font_size), spacing3=8,
                      highlightthickness=0)
        # destaque do modo bilíngue sincronizado (parágrafo correspondente)
        txt.tag_configure("sync", background="#34301a")
        sb = ttk.Scrollbar(frame, command=txt.yview)
        txt.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        txt.pack(fill="both", expand=True)
        parent.add(frame)
        return txt

    @staticmethod
    def _paragraph_spans(text):
        """Offsets (início, fim) de cada unidade de parágrafo do texto.

        Unidade = LINHA não-vazia — exatamente como o tradutor divide o
        texto-fonte (chunk_text quebra em cada \\n). Isso ignora linhas em
        branco múltiplas dos .txt de web novel (que criavam "parágrafos
        vazios" e desalinhavam a sincronização) e casa 1:1 com a estrutura
        que o modelo espelha na tradução.
        """
        spans, pos = [], 0
        for line in text.split("\n"):
            if line.strip():
                spans.append((pos, pos + len(line)))
            pos += len(line) + 1
        return spans

    @staticmethod
    def _map_paragraph(rel, n_from, n_to):
        """Mapeia o parágrafo `rel` entre textos com contagens diferentes.

        Contagens iguais (tradução Completa espelha a estrutura) → 1:1.
        Diferentes (dinamização fundiu parágrafos) → proporcional.
        """
        if n_to == n_from:
            j = rel
        else:
            j = round(rel * (n_to - 1) / max(1, n_from - 1))
        return max(0, min(n_to - 1, j))

    def _sync_paragraph(self, event, src):
        """Clique num painel destaca o parágrafo correspondente no outro."""
        w_from = self.txt_src if src else self.txt_dst
        w_to = self.txt_dst if src else self.txt_src
        for w in (self.txt_src, self.txt_dst):
            w.tag_remove("sync", "1.0", "end")
        if self._reading_mode:  # original oculto: nada a sincronizar
            return
        t_from = w_from.get("1.0", "end-1c")
        t_to = w_to.get("1.0", "end-1c")
        if not t_from.strip() or not t_to.strip() or \
                t_to.startswith("(ainda não traduzido"):
            return
        sp_from = self._paragraph_spans(t_from)
        sp_to = self._paragraph_spans(t_to)
        # o painel do original tem o título como primeiro parágrafo
        skip_from = 1 if src else 0
        skip_to = 0 if src else 1
        n_from = len(sp_from) - skip_from
        n_to = len(sp_to) - skip_to
        if n_from <= 0 or n_to <= 0:
            return
        clicked = w_from.count(
            "1.0", w_from.index(f"@{event.x},{event.y}"), "chars")
        offset = clicked[0] if clicked else 0
        k = next((i for i, (a, b) in enumerate(sp_from)
                  if a <= offset <= b), None)
        if k is None or k < skip_from:
            return
        j = self._map_paragraph(k - skip_from, n_from, n_to) + skip_to
        for w, (a, b) in ((w_from, sp_from[k]), (w_to, sp_to[j])):
            w.tag_add("sync", f"1.0+{a}c", f"1.0+{b}c")
        w_to.see(f"1.0+{sp_to[j][0]}c")

    def toggle_reading_mode(self):
        """Oculta/mostra o painel do original para leitura confortável."""
        src_frame = self.txt_src.master
        if self._reading_mode:
            self._right_pane.add(src_frame, before=self.txt_dst.master)
        else:
            self._right_pane.forget(src_frame)
        self._reading_mode = not self._reading_mode

    def set_font(self, delta):
        self.font_size = max(9, min(28, self.font_size + delta))
        for t in (self.txt_src, self.txt_dst):
            t.configure(font=("Georgia", self.font_size))

    def _set_text(self, widget, content):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _append_text(self, widget, content):
        widget.configure(state="normal")
        widget.insert("end", content)
        widget.see("end")
        widget.configure(state="disabled")

    # ------------------------------------------------------------- ações

    # ------------------------------------------------------------- backend

    def switch_backend(self, _ev=None):
        sel = self.backend_var.get()
        if sel == "API":
            self.configure_api()
        elif sel == "CLI":
            self.configure_cli()
        else:
            self.client = OllamaClient()
            self.model_var.set("")
            self.refresh_models()

    def _type_model(self):
        m = simpledialog.askstring(
            "Modelo", "Nome do modelo (vazio = padrão do backend):",
            initialvalue=self.model_var.get(), parent=self)
        if m is not None:
            self.model_var.set(m.strip())

    def _set_model_choices(self, models):
        # o submenu Modelo reconstrói ao abrir (postcommand) a partir daqui
        self._models_cache = list(models)

    def configure_cli(self):
        win = tk.Toplevel(self)
        win.title("Usar assinatura via CLI")
        win.geometry("560x300")
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", anchor="w", wraplength=530,
                 text=("Usa o CLI oficial do provedor, autenticado pela sua "
                       "ASSINATURA — sem chave de API.\n"
                       "Pré-requisito: instale o CLI e faça login UMA vez "
                       "fora do app:\n"
                       "  • Claude: npm i -g @anthropic-ai/claude-code, "
                       "depois 'claude' e /login\n"
                       "  • Gemini: npm i -g @google/gemini-cli, depois "
                       "'gemini' (login Google)\n"
                       "  • Codex: npm i -g @openai/codex, depois "
                       "'codex login'\n"
                       "Sem streaming: cada bloco chega de uma vez (mais "
                       "lento por chamada).")
                 ).pack(fill="x", padx=10, pady=(8, 4))
        frm = tk.Frame(win, bg=BG)
        frm.pack(fill="x", padx=10)
        tk.Label(frm, text="Provedor:", bg=BG, fg=FG).grid(row=0, column=0,
                                                           sticky="w")
        providers = list(CliClient.PROVIDERS)
        prov_var = tk.StringVar(
            value=getattr(self, "_cli_provider", providers[0]))
        ttk.Combobox(frm, textvariable=prov_var, values=providers,
                     width=30, state="readonly").grid(row=0, column=1,
                                                      padx=4, pady=3)

        def save():
            client = CliClient(prov_var.get())
            if not client.is_up():
                messagebox.showwarning(
                    "CLI não encontrado",
                    f"O comando '{client.spec['bin']}' não está no PATH.\n"
                    "Instale o CLI (instruções acima) e tente de novo.",
                    parent=win)
                return
            self._cli_provider = prov_var.get()
            self.client = client
            self.model_var.set("")
            win.destroy()
            self.refresh_models()
            self.status.config(
                text=f"CLI OK: {prov_var.get()} — deixe o modelo vazio para "
                     "o padrão do CLI, ou digite/escolha um")

        def cancel():
            win.destroy()
            self.backend_var.set("Ollama")
            self.switch_backend()

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=10)
        ttk.Button(btns, text="Usar", command=save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=cancel).pack(side="left",
                                                               padx=4)
        win.protocol("WM_DELETE_WINDOW", cancel)

    def configure_api(self):
        cfg = {}
        if os.path.exists(API_CONFIG):
            try:
                with open(API_CONFIG, encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        win = tk.Toplevel(self)
        win.title("Configurar API")
        win.geometry("560x240")
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", anchor="w", wraplength=530,
                 text=("Qualquer API compatível com OpenAI. Exemplos de URL "
                       "base:\n  https://api.deepseek.com/v1\n"
                       "  https://openrouter.ai/api/v1\n"
                       "A chave fica salva em api.json, só no seu computador.")
                 ).pack(fill="x", padx=10, pady=(8, 4))
        frm = tk.Frame(win, bg=BG)
        frm.pack(fill="x", padx=10)
        tk.Label(frm, text="URL base:", bg=BG, fg=FG).grid(row=0, column=0,
                                                           sticky="w")
        url_var = tk.StringVar(value=cfg.get("base_url", ""))
        tk.Entry(frm, textvariable=url_var, width=52, bg=PANEL, fg=FG,
                 insertbackground=FG).grid(row=0, column=1, padx=4, pady=3)
        tk.Label(frm, text="Chave (key):", bg=BG, fg=FG).grid(row=1, column=0,
                                                              sticky="w")
        key_var = tk.StringVar(value=cfg.get("api_key", ""))
        tk.Entry(frm, textvariable=key_var, width=52, bg=PANEL, fg=FG,
                 insertbackground=FG, show="•").grid(row=1, column=1,
                                                     padx=4, pady=3)

        def save():
            url = url_var.get().strip()
            if not url:
                messagebox.showwarning("URL vazia", "Informe a URL base.",
                                       parent=win)
                return
            try:
                with open(API_CONFIG, "w", encoding="utf-8") as f:
                    json.dump({"base_url": url,
                               "api_key": key_var.get().strip()}, f, indent=2)
            except OSError:
                pass
            self.client = ApiClient(url, key_var.get().strip())
            self.model_var.set(cfg.get("last_model", ""))
            win.destroy()
            self.refresh_models()

        def cancel():
            win.destroy()
            self.backend_var.set("Ollama")
            self.switch_backend()

        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=10)
        ttk.Button(btns, text="Salvar e usar", command=save).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=cancel).pack(
            side="left", padx=4)
        win.protocol("WM_DELETE_WINDOW", cancel)

    def refresh_models(self):
        def work():
            try:
                models = self.client.list_models()
                self._q.put(("models", models))
            except Exception:
                self._q.put(("models_err", None))
        threading.Thread(target=work, daemon=True).start()

    def open_book(self):
        path = filedialog.askopenfilename(
            title="Abrir light novel",
            filetypes=[("Livros", "*.epub *.pdf *.txt *.mobi *.azw3 *.azw"),
                       ("EPUB", "*.epub"), ("PDF", "*.pdf"),
                       ("Texto", "*.txt"),
                       ("Kindle (requer Calibre)", "*.mobi *.azw3 *.azw")])
        if not path:
            return
        try:
            self.chapters, self.images = extract_book_images(path)
        except Exception as e:
            messagebox.showerror("Erro ao abrir", str(e))
            return
        self.translations.clear()
        self.chap_list.delete(0, "end")
        for i, (title, _) in enumerate(self.chapters):
            self.chap_list.insert("end", f" {i+1}. {title[:48]}")
        self.book_name = os.path.splitext(os.path.basename(path))[0]
        # glossário persistente ao lado do livro
        self.glossary_path = os.path.splitext(path)[0] + ".glossario.txt"
        self.glossary = self._load_aux(self.glossary_path)
        self.memory_path = os.path.splitext(path)[0] + ".memoria.txt"
        self.memory = self._load_aux(self.memory_path)
        # cache de traduções + posição de leitura persistentes
        self.cache_path = os.path.splitext(path)[0] + ".cache.json"
        start = self._load_cache()
        start = min(start, len(self.chapters) - 1)
        self.chap_list.selection_set(start)
        self.show_chapter(start)
        n_cached = len(self.translations)
        extra = f" ({n_cached} cap. já traduzidos no cache)" if n_cached else ""
        self.status.config(
            text=f"{len(self.chapters)} capítulos carregados — "
                 f"{self.book_name}{extra}")

    def _load_cache(self):
        """Carrega traduções salvas; retorna o capítulo onde parou."""
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, TypeError):
            return 0
        for key, text in data.get("traducoes", {}).items():
            try:
                idx, src, lang, level = key.split("|", 3)
                self.translations[(int(idx), src, lang, level)] = text
            except ValueError:
                continue
        # marca de verde os capítulos com tradução na combinação atual
        for k in self.translations:
            if k[1:] == self._key(0)[1:]:
                self.chap_list.itemconfig(k[0], fg=OK_COLOR)
        return int(data.get("capitulo", 0))

    def _save_cache(self):
        if not self.cache_path:
            return
        data = {
            "capitulo": self.current or 0,
            "traducoes": {f"{k[0]}|{k[1]}|{k[2]}|{k[3]}": v
                          for k, v in self.translations.items()},
        }
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def _save_reading_position(self):
        self._save_cache()

    @staticmethod
    def _load_aux(path):
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    return f.read()
            except OSError:
                pass
        return ""

    @staticmethod
    def _save_aux(path, content):
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError:
                pass

    def learn_from_translation(self):
        """Minera o glossário comparando um volume original com sua tradução."""
        if self._busy:
            return
        model = self.model_var.get()
        if not model and self.backend_var.get() != "CLI":
            messagebox.showwarning("Sem modelo", "O Ollama está rodando?")
            return
        messagebox.showinfo(
            "Aprender com tradução existente",
            "Selecione primeiro o volume ORIGINAL (idioma de origem) e, em "
            "seguida, o MESMO volume já traduzido (tradução oficial ou de "
            "comunidade). O app vai extrair nomes e termos para o glossário.")
        src_path = filedialog.askopenfilename(
            title="1/2 — Volume ORIGINAL",
            filetypes=[("Livros", "*.epub *.pdf *.txt *.mobi *.azw3")])
        if not src_path:
            return
        dst_path = filedialog.askopenfilename(
            title="2/2 — Mesmo volume TRADUZIDO",
            filetypes=[("Livros", "*.epub *.pdf *.txt *.mobi *.azw3")])
        if not dst_path:
            return
        if not self.glossary_path:  # nenhum livro aberto: salva ao lado do original
            self.glossary_path = os.path.splitext(src_path)[0] + ".glossario.txt"
            self.glossary = self._load_aux(self.glossary_path)
        if not self.memory_path:
            self.memory_path = os.path.splitext(src_path)[0] + ".memoria.txt"
            self.memory = self._load_aux(self.memory_path)
        lang = self.lang_var.get()
        self._set_busy(True)
        self._stop.clear()

        def work():
            try:
                src_ch = extract_book(src_path)
                dst_ch = extract_book(dst_path)
            except Exception as e:
                self._q.put(("error", f"Erro ao abrir: {e}"))
                self._q.put(("finished",))
                return
            self._q.put(("status", "🎓 Analisando trechos…"))
            pairs = learn_glossary(
                self.client, model, src_ch, dst_ch, lang,
                existing=self.glossary,
                on_progress=lambda k, n: self._q.put(
                    ("status", f"🎓 Aprendendo… trecho {k}/{n}")),
                should_stop=self._stop.is_set)
            if pairs:
                novo = self.glossary.rstrip()
                if novo:
                    novo += "\n"
                novo += "\n".join(f"{o} = {d}" for o, d in pairs)
                self._save_aux(self.glossary_path, novo)
                self._q.put(("glossary_set", novo))
            # constrói a memória da saga a partir do volume traduzido
            title = os.path.splitext(os.path.basename(dst_path))[0]
            mem = build_memory_from_translation(
                self.client, model, dst_ch, title, lang,
                memory=self.memory,
                on_progress=lambda k, n: self._q.put(
                    ("status", f"🧠 Gerando memória… parte {k}/{n}")),
                should_stop=self._stop.is_set)
            if mem.strip():
                self._save_aux(self.memory_path, mem)
                self._q.put(("memory", mem))
            self._q.put(("status",
                         f"🎓 Concluído: {len(pairs)} entradas novas no "
                         "glossário + memória atualizada — revise em 📓 e 🧠"))
            self._q.put(("finished",))

        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _pair_learning_files(paths):
        """Pareia originais com traduzidos pelo sufixo 't' no nome.

        vol01.txt + vol01t.txt  /  vol02.epub + vol02_t.txt  → pares.
        Retorna (pares, sobras): pares = [(original, traduzido)].
        """
        stems = {}
        for p in paths:
            stems[os.path.splitext(os.path.basename(p))[0].lower()] = p
        pairs, used = [], set()
        for stem in sorted(stems):
            if not stem.endswith("t"):
                continue
            base = stem[:-1].rstrip("_-")
            if base in stems and base != stem:
                pairs.append((stems[base], stems[stem]))
                used.add(base)
                used.add(stem)
        unmatched = [stems[s] for s in sorted(stems) if s not in used]
        return pairs, unmatched

    def learn_saga(self):
        """Aprendizado em lote: pasta com vol01, vol01t, vol02, vol02t…"""
        if self._busy:
            return
        model = self.model_var.get()
        if not model and self.backend_var.get() != "CLI":
            messagebox.showwarning("Sem modelo", "O Ollama está rodando?")
            return
        folder = filedialog.askdirectory(
            title="Pasta com pares original/traduzido (vol01 + vol01t…)")
        if not folder:
            return
        files = []
        for f in sorted(os.listdir(folder)):
            low = f.lower()
            if not low.endswith((".epub", ".pdf", ".txt",
                                 ".mobi", ".azw3", ".azw")):
                continue
            if low.endswith((".glossario.txt", ".memoria.txt",
                             ".aprendido.txt")) or \
               "_traduzido" in low:
                continue
            files.append(os.path.join(folder, f))
        pairs, unmatched = self._pair_learning_files(files)
        if not pairs:
            messagebox.showinfo(
                "Nenhum par encontrado",
                "Nomeie os arquivos como vol01 (original) e vol01t "
                "(traduzido) — o sufixo 't' marca a tradução.")
            return
        # pula pares já aprendidos em execuções anteriores
        done_path = os.path.join(folder, "saga.aprendido.txt")
        done = {l.strip().lower()
                for l in self._load_aux(done_path).splitlines() if l.strip()}
        learned = [(o, t) for o, t in pairs
                   if os.path.basename(o).lower() in done]
        pairs = [(o, t) for o, t in pairs
                 if os.path.basename(o).lower() not in done]
        if not pairs:
            messagebox.showinfo(
                "Tudo já aprendido",
                "Todos os pares desta pasta já foram aprendidos "
                "(saga.aprendido.txt). Adicione volumes novos ou apague esse "
                "arquivo para reaprender.")
            return
        txt = "\n".join(
            f"  {os.path.basename(o)}  ↔  {os.path.basename(t)}"
            for o, t in pairs)
        if learned:
            txt += "\n\nJá aprendidos (pulados):\n" + "\n".join(
                f"  {os.path.basename(o)}" for o, _ in learned)
        if unmatched:
            txt += "\n\nSem par (ignorados):\n" + "\n".join(
                f"  {os.path.basename(u)}" for u in unmatched)
        if not messagebox.askokcancel(
                "Aprender com a saga",
                f"Pares a aprender:\n\n{txt}\n\nO glossário e a memória da "
                "saga serão gerados em saga.glossario.txt / saga.memoria.txt. "
                "Continuar?"):
            return
        lang = self.lang_var.get()
        self.glossary_path = os.path.join(folder, "saga.glossario.txt")
        self.glossary = self._load_aux(self.glossary_path)
        self.memory_path = os.path.join(folder, "saga.memoria.txt")
        self.memory = self._load_aux(self.memory_path)
        self._set_busy(True)
        self._stop.clear()

        def work():
            glossary, memory = self.glossary, self.memory
            total_new = 0
            for vi, (src_p, dst_p) in enumerate(pairs):
                if self._stop.is_set():
                    break
                base = os.path.basename(src_p)
                try:
                    src_ch = extract_book(src_p)
                    dst_ch = extract_book(dst_p)
                except Exception as e:
                    self._q.put(("status", f"⚠ {base}: {e}"))
                    continue
                found = learn_glossary(
                    self.client, model, src_ch, dst_ch, lang,
                    existing=glossary,
                    on_progress=lambda k, n, b=base, v=vi: self._q.put(
                        ("status", f"🎓 [{v+1}/{len(pairs)}] {b} — "
                                   f"glossário {k}/{n}")),
                    should_stop=self._stop.is_set)
                if found:
                    glossary = glossary.rstrip()
                    if glossary:
                        glossary += "\n"
                    glossary += "\n".join(f"{o} = {d}" for o, d in found)
                    total_new += len(found)
                    self._save_aux(self.glossary_path, glossary)
                    self._q.put(("glossary_set", glossary))
                title = os.path.splitext(os.path.basename(dst_p))[0]
                memory = build_memory_from_translation(
                    self.client, model, dst_ch, title, lang, memory=memory,
                    on_progress=lambda k, n, b=base, v=vi: self._q.put(
                        ("status", f"🧠 [{v+1}/{len(pairs)}] {b} — "
                                   f"memória {k}/{n}")),
                    should_stop=self._stop.is_set)
                if memory.strip():
                    self._save_aux(self.memory_path, memory)
                    self._q.put(("memory", memory))
                if not self._stop.is_set():
                    # registra o par como aprendido (pulado na próxima vez)
                    done.add(os.path.basename(src_p).lower())
                    self._save_aux(done_path, "\n".join(sorted(done)))
            self._q.put(("status",
                         f"🎓📂 Saga aprendida: {total_new} entradas de "
                         "glossário + memória encadeada de "
                         f"{len(pairs)} volume(s)."))
            self._q.put(("finished",))

        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------- consistência / TTS

    def check_names(self):
        """Procura nomes grafados em ordens diferentes nas traduções prontas."""
        done = {k: v for k, v in self.translations.items()
                if k[1:] == self._key(0)[1:]}
        if not done:
            messagebox.showinfo("Nada para verificar",
                                "Traduza alguns capítulos primeiro.")
            return
        findings = find_name_inconsistencies(list(done.values()),
                                             self.glossary)
        if not findings:
            self.status.config(text="🔍 Nenhuma inconsistência de nome.")
            return
        win = tk.Toplevel(self)
        win.title("Consistência de nomes")
        win.geometry("560x380")
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", anchor="w", wraplength=530,
                 text=("Mesmo nome em ordens/grafias diferentes. Marque o que "
                       "unificar (sugestão: forma majoritária/do glossário).")
                 ).pack(fill="x", padx=10, pady=(8, 4))
        btns = tk.Frame(win, bg=BG)
        btns.pack(side="bottom", pady=8)
        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=10)
        vars_ = []
        for f in findings[:20]:
            v = tk.BooleanVar(value=True)
            tk.Checkbutton(
                frame, variable=v, bg=BG, fg=FG, selectcolor=PANEL,
                activebackground=BG, activeforeground=FG, anchor="w",
                text=(f'"{f["de"]}" ({f["n_de"]}×) → "{f["para"]}" '
                      f'({f["n_para"]}×) [{f["fonte"]}]')
            ).pack(fill="x")
            vars_.append((v, f))

        def aplicar():
            mapping = {f["de"]: f["para"] for v, f in vars_ if v.get()}
            if mapping:
                for k in list(done):
                    novo = apply_name_mapping(self.translations[k], mapping)
                    self.translations[k] = novo
                self._save_cache()
                if self.current is not None:
                    self.show_chapter(self.current)
                self.status.config(
                    text=f"🔍 {len(mapping)} unificação(ões) aplicada(s).")
            win.destroy()

        ttk.Button(btns, text="Aplicar", command=aplicar).pack(side="left",
                                                               padx=4)
        ttk.Button(btns, text="Cancelar",
                   command=win.destroy).pack(side="left", padx=4)

    TTS_VOICES = {"Português (BR)": "pt-BR-FranciscaNeural",
                  "Inglês": "en-US-JennyNeural",
                  "Espanhol": "es-ES-ElviraNeural"}

    def export_audio(self):
        """Gera MP3 do capítulo atual traduzido (voz neural via edge-tts)."""
        if self.current is None:
            return
        text = self.translations.get(self._key(self.current))
        if not text:
            messagebox.showinfo("Sem tradução",
                                "Traduza este capítulo primeiro.")
            return
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            messagebox.showinfo(
                "Falta o edge-tts",
                "Instale com:  pip install edge-tts\n"
                "(vozes neurais gratuitas da Microsoft; requer internet)")
            return
        title = self.chapters[self.current][0]
        path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            initialfile=f"{getattr(self, 'book_name', 'livro')}_"
                        f"{self.current+1:03d}.mp3",
            filetypes=[("Áudio MP3", "*.mp3")])
        if not path:
            return
        voice = self.TTS_VOICES.get(self.lang_var.get(),
                                    "pt-BR-FranciscaNeural")
        clean = IMG_RE.sub("", text)

        def work():
            try:
                import asyncio

                import edge_tts
                self._q.put(("status", f"🔊 Gerando áudio: {title[:40]}…"))
                asyncio.run(
                    edge_tts.Communicate(clean, voice).save(path))
                self._q.put(("status", f"🔊 Áudio salvo: {path}"))
            except Exception as e:
                self._q.put(("error", f"TTS falhou: {e}"))
            self._q.put(("finished",))

        self._set_busy(True)
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------- modo saga

    def open_saga(self):
        if self._busy:
            return
        folder = filedialog.askdirectory(title="Pasta da saga (volumes em ordem)")
        if not folder:
            return
        files = []
        for f in sorted(os.listdir(folder)):
            low = f.lower()
            if not low.endswith((".epub", ".pdf", ".txt",
                                 ".mobi", ".azw3", ".azw")):
                continue
            if low.endswith((".glossario.txt", ".memoria.txt",
                             ".aprendido.txt")) or \
               "_traduzido" in low:
                continue
            files.append(os.path.join(folder, f))
        # volumes com tradução da comunidade (par vol01/vol01t) não precisam
        # de tradução automática — ficam só para o 🎓📂 Aprender saga
        pairs, files = self._pair_learning_files(files)
        if not files:
            messagebox.showinfo(
                "Nada para traduzir",
                "Nenhum volume sem tradução encontrado na pasta." if pairs
                else "Nenhum .epub/.pdf/.txt encontrado na pasta.")
            return
        names = "\n".join(f"  {i+1}. {os.path.basename(p)}"
                          for i, p in enumerate(files))
        if pairs:
            names += ("\n\nJá têm tradução (pulados — use 🎓📂 para "
                      "aprender com eles):\n" + "\n".join(
                          f"  {os.path.basename(o)}" for o, _ in pairs))
        if not messagebox.askokcancel(
                "Traduzir saga",
                f"Volumes a traduzir (ordem alfabética):\n\n{names}\n\n"
                "Cada volume traduzido será salvo em 'traduzidos/' dentro da "
                "pasta. Volumes já traduzidos serão pulados. Continuar?"):
            return
        model = self.model_var.get()
        if not model and self.backend_var.get() != "CLI":
            messagebox.showwarning("Sem modelo",
                                   "Nenhum modelo encontrado. O Ollama está rodando?")
            return
        # memória e glossário únicos da saga, na raiz da pasta
        self.glossary_path = os.path.join(folder, "saga.glossario.txt")
        self.glossary = self._load_aux(self.glossary_path)
        # funde glossários avulsos da pasta (de volumes individuais / 🎓)
        merged = self._merge_folder_glossaries(folder, self.glossary)
        if merged != self.glossary:
            self.glossary = merged
            self._save_aux(self.glossary_path, merged)
        self.memory_path = os.path.join(folder, "saga.memoria.txt")
        self.memory = self._load_aux(self.memory_path)
        self._run_saga(folder, files, model)

    def _merge_folder_glossaries(self, folder, base):
        """Mescla todos os .glossario.txt da pasta no glossário da saga."""
        known = {}
        lines = []
        for line in base.splitlines():
            lines.append(line)
            if "=" in line:
                known[line.partition("=")[0].strip()] = True
        for f in sorted(os.listdir(folder)):
            if not f.lower().endswith(".glossario.txt") or \
               f.lower() == "saga.glossario.txt":
                continue
            for line in self._load_aux(os.path.join(folder, f)).splitlines():
                if "=" not in line:
                    continue
                key = line.partition("=")[0].strip()
                if key and key not in known:
                    known[key] = True
                    lines.append(line.strip())
        return "\n".join(l for l in lines if l.strip())

    def _run_saga(self, folder, files, model):
        src = self.src_var.get()
        lang, level = self.lang_var.get(), self.level_var.get()
        auto_mem = self.auto_mem_var.get()
        review = self.review_var.get()
        # backends de ponta (API/CLI) aceitam blocos maiores: menos chamadas
        chunk_chars = 1800 if self.backend_var.get() == "Ollama" else 4500
        out_dir = os.path.join(folder, "traduzidos")
        os.makedirs(out_dir, exist_ok=True)
        self._stop.clear()
        self._set_busy(True)

        def work():
            memory = self.memory
            for vi, path in enumerate(files):
                if self._stop.is_set():
                    break
                base = os.path.splitext(os.path.basename(path))[0]
                out_path = os.path.join(out_dir, base + "_traduzido.txt")
                if os.path.exists(out_path):
                    self._q.put(("status", f"✓ {base} já traduzido — pulando"))
                    continue
                try:
                    chapters = extract_book(path)
                except Exception as e:
                    self._q.put(("status", f"⚠ {base}: {e}"))
                    continue
                self._q.put(("load_volume", base, chapters, vi + 1, len(files)))
                results = []
                for ci, (title, text) in enumerate(chapters):
                    if self._stop.is_set():
                        break
                    self._q.put(("select_chapter", ci))
                    self._q.put(("start_chapter", ci,
                                 f"[{vi+1}/{len(files)}] {title}",
                                 ci, len(chapters)))
                    try:
                        result = translate_chapter(
                            self.client, model, text, lang, level,
                            source_label=src, glossary=self.glossary,
                            memory=memory, chunk_chars=chunk_chars,
                            on_piece=lambda s, i=ci: self._q.put(("piece", i, s)),
                            should_stop=self._stop.is_set)
                    except Exception as e:
                        self._q.put(("error", str(e)))
                        self._q.put(("finished",))
                        return
                    if self._stop.is_set() or not result:
                        break
                    if review:
                        result = review_translation(
                            self.client, model, result, lang,
                            on_progress=lambda k, t: self._q.put(
                                ("status", f"✨ Revisando… {k}/{t}")),
                            should_stop=self._stop.is_set)
                    results.append((title, result))
                    self._q.put(("done_chapter", ci,
                                 (ci, src, lang, level), result, ci + 1))
                    if auto_mem:
                        self._q.put(("status", "🧠 Atualizando memória da saga…"))
                        try:
                            memory = update_memory(self.client, model, memory,
                                                   title, result, lang)
                            self._save_aux(self.memory_path, memory)
                            self._q.put(("memory", memory))
                        except Exception:
                            pass
                # salva o volume (mesmo parcial, se foi interrompido no meio)
                if results:
                    suffix = "" if len(results) == len(chapters) else "_parcial"
                    final = out_path if not suffix else \
                        os.path.join(out_dir, base + "_traduzido_parcial.txt")
                    try:
                        with open(final, "w", encoding="utf-8") as f:
                            for title, body in results:
                                f.write(f"{'=' * 60}\n{title}\n{'=' * 60}\n\n")
                                f.write(body + "\n\n")
                        self._q.put(("status", f"💾 Volume salvo: {final}"))
                    except OSError as e:
                        self._q.put(("status", f"⚠ Erro ao salvar {base}: {e}"))
            self._q.put(("finished",))

        threading.Thread(target=work, daemon=True).start()

    def edit_memory(self):
        win = tk.Toplevel(self)
        win.title("Memória da saga")
        win.geometry("620x480")
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", anchor="w", wraplength=590,
                 text=("Resumo que o modelo usa como contexto (personagens, "
                       "termos, eventos). É atualizado automaticamente a cada "
                       "capítulo traduzido (☑ auto). Para continuar uma saga em "
                       "outro volume, use 'Abrir memória da saga…' e aponte para "
                       "o .memoria.txt do volume anterior.")
                 ).pack(fill="x", padx=10, pady=(8, 4))
        # botões no rodapé ANTES do texto: senão o Text (que pede ~24 linhas)
        # espreme os botões para fora da janela
        btns = tk.Frame(win, bg=BG)
        btns.pack(side="bottom", pady=8)
        txt = tk.Text(win, bg=PANEL, fg=FG, insertbackground=FG, wrap="word",
                      font=("Segoe UI", 10), padx=8, pady=6, height=10)
        txt.pack(fill="both", expand=True, padx=10)
        txt.insert("1.0", self.memory)

        def save():
            self.memory = txt.get("1.0", "end").strip()
            self._save_aux(self.memory_path, self.memory)
            win.destroy()
            self.status.config(text="Memória salva.")

        def load_other():
            p = filedialog.askopenfilename(
                title="Abrir memória da saga",
                filetypes=[("Memória", "*.memoria.txt"), ("Texto", "*.txt")])
            if p:
                self.memory_path = p
                self.memory = self._load_aux(p)
                txt.delete("1.0", "end")
                txt.insert("1.0", self.memory)

        def importar_copia():
            p = filedialog.askopenfilename(
                title="Importar cópia de memória (ex.: saga.memoria.txt)",
                filetypes=[("Memória", "*.memoria.txt"), ("Texto", "*.txt")],
                parent=win)
            if p:
                # copia o conteúdo SEM mudar onde este livro salva a memória
                txt.delete("1.0", "end")
                txt.insert("1.0", self._load_aux(p))
                self.status.config(
                    text="🧠 Memória copiada — clique em Salvar para "
                         "confirmar (o arquivo de origem não será alterado).")

        ttk.Button(btns, text="Salvar", command=save).pack(side="left", padx=4)
        ttk.Button(btns, text="Importar cópia…",
                   command=importar_copia).pack(side="left", padx=4)
        ttk.Button(btns, text="Vincular à saga…",
                   command=load_other).pack(side="left", padx=4)

    def edit_glossary(self):
        win = tk.Toplevel(self)
        win.title("Glossário de nomes e termos")
        win.geometry("520x420")
        win.configure(bg=BG)
        tk.Label(win, bg=BG, fg=FG, justify="left", anchor="w",
                 text=("Um por linha, no formato:  original = tradução\n"
                       "Ex.:  月森アヤメ = Ayame Tsukimori\n"
                       "      星霜剣記 = Crônicas da Espada Estelar")
                 ).pack(fill="x", padx=10, pady=(8, 4))
        # rodapé reservado antes do texto (ver comentário em edit_memory)
        gbtns = tk.Frame(win, bg=BG)
        gbtns.pack(side="bottom", pady=8)
        txt = tk.Text(win, bg=PANEL, fg=FG, insertbackground=FG,
                      font=("Consolas", 11), padx=8, pady=6, height=10)
        txt.pack(fill="both", expand=True, padx=10)
        txt.insert("1.0", self.glossary)

        def save():
            self.glossary = txt.get("1.0", "end").strip()
            self._save_aux(self.glossary_path, self.glossary)
            win.destroy()
            self.status.config(text="Glossário salvo — vale para as próximas traduções.")

        def importar():
            p = filedialog.askopenfilename(
                title="Importar glossário (ex.: saga.glossario.txt)",
                filetypes=[("Glossário", "*.glossario.txt"),
                           ("Texto", "*.txt")], parent=win)
            if not p:
                return
            base = txt.get("1.0", "end")
            known = {l.partition("=")[0].strip()
                     for l in base.splitlines() if "=" in l}
            extra = [l.strip() for l in self._load_aux(p).splitlines()
                     if "=" in l and l.partition("=")[0].strip() not in known]
            if extra:
                if base.strip() and not base.endswith("\n"):
                    txt.insert("end", "\n")
                txt.insert("end", "\n".join(extra) + "\n")
            self.status.config(
                text=f"📓 {len(extra)} entradas importadas — clique em Salvar "
                     "para confirmar.")

        def sugerir():
            if not self.chapters:
                messagebox.showinfo("Sem livro", "Abra um livro primeiro.",
                                    parent=win)
                return
            model = self.model_var.get()
            sample = IMG_RE.sub("", self.chapters[0][1])
            existing = txt.get("1.0", "end")
            self.status.config(text="📓 IA sugerindo nomes (lendo a abertura)…")
            self._gloss_txt = txt  # destino das sugestões (se ainda aberto)

            def work():
                try:
                    pairs = suggest_glossary(self.client, model, sample,
                                             self.lang_var.get(), existing)
                    self._q.put(("glossary_suggest", pairs))
                except Exception as e:
                    self._q.put(("error", f"Sugestão falhou: {e}"))

            threading.Thread(target=work, daemon=True).start()

        ttk.Button(gbtns, text="Salvar", command=save).pack(side="left", padx=4)
        ttk.Button(gbtns, text="Importar…",
                   command=importar).pack(side="left", padx=4)
        ttk.Button(gbtns, text="Sugerir (IA)…",
                   command=sugerir).pack(side="left", padx=4)

    def on_select_chapter(self, _ev=None):
        sel = self.chap_list.curselection()
        if sel:
            self.show_chapter(sel[0])

    def _key(self, idx):
        return (idx, self.src_var.get(), self.lang_var.get(),
                self.level_var.get())

    def show_chapter(self, idx):
        self.current = idx
        title, text = self.chapters[idx]
        self._set_text(self.txt_src, f"{title}\n\n{text}")
        cached = self.translations.get(self._key(idx))
        self._set_text(self.txt_dst, cached or "(ainda não traduzido)")

    def translate_current(self):
        if self.current is None or self._busy:
            return
        self._run_translation([self.current])

    def translate_all(self):
        if not self.chapters or self._busy:
            return
        pending = [i for i in range(len(self.chapters))
                   if self._key(i) not in self.translations]
        if pending:
            self._run_translation(pending)

    def stop(self):
        self._stop.set()
        self.status.config(text="Parando…")

    def _set_busy(self, busy):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_tr.config(state=state)
        self.btn_all.config(state=state)
        self.btn_stop.config(state="normal" if busy else "disabled")

    def _run_translation(self, indices):
        model = self.model_var.get()
        if not model and self.backend_var.get() != "CLI":
            messagebox.showwarning(
                "Sem modelo",
                "Nenhum modelo encontrado. O Ollama está rodando?\n"
                "Instale um modelo com:  ollama pull qwen3:14b")
            return
        src = self.src_var.get()
        lang, level = self.lang_var.get(), self.level_var.get()
        auto_mem = self.auto_mem_var.get()
        review = self.review_var.get()
        # backends de ponta (API/CLI) aceitam blocos maiores: menos chamadas
        chunk_chars = 1800 if self.backend_var.get() == "Ollama" else 4500
        self._stop.clear()
        self._set_busy(True)
        self.progress.config(maximum=len(indices), value=0)

        def work():
            memory = self.memory
            for n, idx in enumerate(indices):
                if self._stop.is_set():
                    break
                title, text = self.chapters[idx]
                self._q.put(("start_chapter", idx, title, n, len(indices)))
                try:
                    result = translate_chapter(
                        self.client, model, text, lang, level,
                        source_label=src, glossary=self.glossary,
                        memory=memory, chunk_chars=chunk_chars,
                        on_piece=lambda s, i=idx: self._q.put(("piece", i, s)),
                        should_stop=self._stop.is_set)
                    if review and result and not self._stop.is_set():
                        result = review_translation(
                            self.client, model, result, lang,
                            on_progress=lambda k, t: self._q.put(
                                ("status", f"✨ Revisando… {k}/{t}")),
                            should_stop=self._stop.is_set)
                    if not self._stop.is_set() and result:
                        self._q.put(("done_chapter", idx,
                                     (idx, src, lang, level), result, n + 1))
                        if auto_mem:
                            self._q.put(("status", f"🧠 Atualizando memória "
                                                   f"({title[:30]})…"))
                            try:
                                memory = update_memory(
                                    self.client, model, memory, title,
                                    result, lang)
                                self._save_aux(self.memory_path, memory)
                                self._q.put(("memory", memory))
                            except Exception:
                                pass  # memória é opcional, não aborta
                except Exception as e:
                    self._q.put(("error", str(e)))
                    break
            self._q.put(("finished",))

        threading.Thread(target=work, daemon=True).start()

    def save_translation(self):
        done = {k: v for k, v in self.translations.items()
                if k[1:] == self._key(0)[1:]}
        if not done:
            messagebox.showinfo("Nada para salvar",
                                "Nenhum capítulo traduzido nessa combinação de "
                                "idioma/dinamização.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".epub",
            initialfile=f"{getattr(self, 'book_name', 'livro')}_traduzido.epub",
            filetypes=[("EPUB", "*.epub"), ("Texto", "*.txt"),
                       ("Markdown", "*.md")])
        if not path:
            return
        ordered = [(self.chapters[idx][0], done[self._key(idx)])
                   for idx in sorted(k[0] for k in done)]
        try:
            if path.lower().endswith(".epub"):
                self._export_epub(path, ordered)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    for title, body in ordered:
                        body = IMG_RE.sub("[ilustração]", body)
                        f.write(f"{'=' * 60}\n{title}\n{'=' * 60}\n\n")
                        f.write(body + "\n\n")
        except Exception as e:
            messagebox.showerror("Erro ao salvar", str(e))
            return
        self.status.config(text=f"Salvo em {path}")

    def _export_epub(self, path, ordered):
        """Gera um EPUB com um capítulo por arquivo, legível em qualquer leitor."""
        import html as _html

        from ebooklib import epub
        book = epub.EpubBook()
        title = getattr(self, "book_name", "Livro") + " (tradução)"
        book.set_identifier(f"lnt-{abs(hash(title))}")
        book.set_title(title)
        book.set_language({"Inglês": "en", "Espanhol": "es"}.get(
            self.lang_var.get(), "pt-BR"))
        # embute as imagens do livro original, nas posições dos marcadores
        used = set()
        for body in (b for _, b in ordered):
            used.update(int(m) for m in IMG_RE.findall(body))
        for n in sorted(used):
            info = self.images.get(n)
            if info:
                book.add_item(epub.EpubItem(
                    uid=f"img{n}", file_name=f"images/img{n}.{info['ext']}",
                    media_type=info["media_type"], content=info["data"]))

        def para_html(p):
            m = IMG_RE.fullmatch(p.strip())
            if m:
                info = self.images.get(int(m.group(1)))
                if info:
                    return (f'<p style="text-align:center"><img '
                            f'src="images/img{m.group(1)}.{info["ext"]}" '
                            f'alt="ilustração"/></p>\n')
                return ""
            return f"<p>{_html.escape(p.strip())}</p>\n"

        items = []
        for i, (ch_title, body) in enumerate(ordered):
            paras = "".join(para_html(p)
                            for p in body.split("\n\n") if p.strip())
            c = epub.EpubHtml(title=ch_title, file_name=f"cap{i+1:03d}.xhtml",
                              lang=book.language)
            c.content = (f"<h2>{_html.escape(ch_title)}</h2>\n{paras}")
            book.add_item(c)
            items.append(c)
        book.toc = items
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + items
        epub.write_epub(path, book)

    # ------------------------------------------------------------- fila UI

    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                kind = msg[0]
                if kind == "models":
                    models = msg[1]
                    self._set_model_choices(models)
                    if models and not self.model_var.get():
                        saved = getattr(self, "_saved_model", "")
                        default = saved if saved in models else next(
                            (m for m in models if "qwen3" in m), models[0])
                        self.model_var.set(default)
                    via = self.backend_var.get()
                    self.status.config(text=f"{via} OK — {len(models)} modelo(s)")
                elif kind == "models_err":
                    if self.backend_var.get() == "CLI":
                        self.status.config(
                            text="⚠ CLI não encontrado no PATH — instale e "
                                 "faça login (veja Via: CLI)")
                    elif self.backend_var.get() == "API":
                        self.status.config(
                            text="⚠ API não listou modelos — digite o nome "
                                 "do modelo na caixa (ex.: deepseek-chat)")
                    else:
                        self.status.config(
                            text="⚠ Ollama não encontrado em localhost:11434 "
                                 "— abra o Ollama e clique em ⟳")
                elif kind == "start_chapter":
                    _, idx, title, n, total = msg
                    if idx == self.current:
                        self._set_text(self.txt_dst, "")
                    self.status.config(
                        text=f"Traduzindo {n+1}/{total}: {title[:40]}…")
                elif kind == "piece":
                    _, idx, s = msg
                    if idx == self.current:
                        self._append_text(self.txt_dst, s)
                elif kind == "done_chapter":
                    _, idx, key, result, count = msg
                    self.translations[key] = result
                    if idx == self.current:
                        # garante que a versão final (pós-correções) é exibida
                        self._set_text(self.txt_dst, result)
                    self.progress.config(value=count)
                    self.chap_list.itemconfig(idx, fg=OK_COLOR)
                    self._save_cache()  # persiste em disco a cada capítulo
                elif kind == "load_volume":
                    _, base, chapters, vn, vt = msg
                    self.chapters = chapters
                    self.translations.clear()
                    self.book_name = base
                    self.chap_list.delete(0, "end")
                    for i, (t, _txt) in enumerate(chapters):
                        self.chap_list.insert("end", f" {i+1}. {t[:48]}")
                    self.progress.config(maximum=len(chapters), value=0)
                    self.status.config(
                        text=f"📂 Volume {vn}/{vt}: {base} "
                             f"({len(chapters)} capítulos)")
                elif kind == "select_chapter":
                    idx = msg[1]
                    self.chap_list.selection_clear(0, "end")
                    self.chap_list.selection_set(idx)
                    self.chap_list.see(idx)
                    self.show_chapter(idx)
                elif kind == "memory":
                    self.memory = msg[1]
                elif kind == "glossary_set":
                    self.glossary = msg[1]
                elif kind == "glossary_suggest":
                    pairs = msg[1]
                    w = getattr(self, "_gloss_txt", None)
                    if pairs and w is not None and w.winfo_exists():
                        base = w.get("1.0", "end")
                        if base.strip() and not base.endswith("\n"):
                            w.insert("end", "\n")
                        w.insert("end", "\n".join(
                            f"{o} = {d}" for o, d in pairs) + "\n")
                        self.status.config(
                            text=f"📓 {len(pairs)} sugestões adicionadas — "
                                 "revise as leituras e clique em Salvar")
                    else:
                        self.status.config(
                            text="📓 Nenhum nome novo encontrado na abertura.")
                elif kind == "status":
                    self.status.config(text=msg[1])
                elif kind == "error":
                    messagebox.showerror("Erro na tradução", msg[1])
                elif kind == "finished":
                    self._set_busy(False)
                    self.status.config(text="Concluído.")
        except queue.Empty:
            pass
        self.after(80, self._poll_queue)


if __name__ == "__main__":
    App().mainloop()
