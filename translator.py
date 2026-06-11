# -*- coding: utf-8 -*-
"""Cliente Ollama + prompts de tradução/dinamização + chunking."""

import json
import os
import re
import shutil
import subprocess

import requests

SOURCE_LANGS = {
    "Japonês": "Japanese",
    "Inglês": "English",
    "Espanhol": "Spanish",
}

LANGS = {
    "Português (BR)": "Brazilian Portuguese",
    "Inglês": "English",
    "Espanhol": "Spanish",
}

LEVELS = ["Completo", "Dinamização baixa", "Dinamização média", "Dinamização alta"]

_LEVEL_INSTRUCTIONS = {
    "Completo": "",
    "Dinamização baixa": (
        "\nAdditionally, LIGHTLY condense the translation (about 20-30% shorter than a "
        "full translation): tighten wordy or repetitive descriptions and redundant "
        "narration, but KEEP all dialogue, all plot events and all character moments."
    ),
    "Dinamização média": (
        "\nAdditionally, MODERATELY condense the translation (about 35-45% shorter than "
        "a full translation): tighten wordy descriptions, cut repetitive narration, and "
        "shorten internal monologue that adds little to the scene, but KEEP all dialogue, "
        "all plot events, and any thoughts that reveal character or affect the story. "
        "The result must still read as flowing prose."
    ),
    "Dinamização alta": (
        "\nAdditionally, HEAVILY condense the translation (about 50-60% shorter than a "
        "full translation): cut internal monologue and stray thoughts that do not matter "
        "to the story, summarize long descriptions in one short sentence, and merge "
        "redundant passages. KEEP every plot event and all dialogue that matters to the "
        "story. The result must still read as flowing prose, not as a bullet summary."
    ),
}


def build_system_prompt(lang_label, level, source_label="Japonês", glossary="",
                        memory=""):
    source = SOURCE_LANGS.get(source_label, "Japanese")
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    prompt = (
        "You are a fan translator producing high-quality community translations "
        f"(fansub style) of light novels and web novels. Translate the {source} "
        f"text sent by the user into natural, fluent {target}."
    )
    if target == "Brazilian Portuguese":
        prompt += (
            " STYLE: write like the best Brazilian fan translations: lively, "
            "colloquial PT-BR that preserves the narrator's personality — sarcasm, "
            "humor and informal voice included. Prefer expressive, natural phrasing "
            "over literal wording, as long as the meaning is fully preserved. "
            "Spoken dialogue lines start with a travessão (—), the Brazilian "
            "standard, instead of quotation marks (e.g. 「ん？」 → — Hum?  /  "
            "「おはよう」 → — Bom dia.). Keep otaku-culture terms that "
            "Brazilian fans use untranslated (otaku, light novel, galge, eroge, "
            "harém, senpai...). Render onomatopoeia expressively in the Latin "
            "alphabet (ペラ……ペラ…… → Flip… Flip…, ふわぁ…… → Fuwaaa…)."
        )
    elif target == "Spanish":
        prompt += (
            " STYLE: lively, idiomatic Spanish that preserves the narrator's "
            "personality — sarcasm, humor and informal voice included. Prefer "
            "natural phrasing over literal wording. Spoken dialogue lines "
            "start with a raya (—), the Spanish standard, instead of "
            "quotation marks (e.g. 「ん？」 → — ¿Mmm?). Use opening ¿ and ¡ "
            "correctly. Keep otaku-culture terms untranslated (otaku, light "
            "novel, galge, eroge, senpai...). Render onomatopoeia "
            "expressively in the Latin alphabet."
        )
    else:
        prompt += (
            " STYLE: lively, idiomatic prose that preserves the narrator's "
            "personality — sarcasm, humor and informal voice included. Prefer "
            "natural phrasing over literal wording."
        )
    if source == "Japanese":
        prompt += (
            " Preserve Japanese honorifics (-san, -kun, -chan, -sama, senpai...). "
            "Translate sound effects/onomatopoeia naturally."
        )
    else:
        prompt += (
            " Keep character names as they are. If the text preserves Japanese "
            "honorifics (-san, -kun...), keep them too."
        )
    if target == "Brazilian Portuguese":
        interj = ('「ん？」 → "Hum?", 「えっ！？」 → "Quê?!", 「うん」 → "Aham", '
                  '「はぁ…」 → "Haa…" (suspiro), 「ちっ」 → "Tsc"')
    elif target == "Spanish":
        interj = ('「ん？」 → "¿Mmm?", 「えっ！？」 → "¡¿Qué?!", 「うん」 → "Ajá", '
                  '「はぁ…」 → "Haa…" (suspiro), 「ちっ」 → "Tch"')
    else:
        interj = ('「ん？」 → "Hm?", 「えっ！？」 → "Huh?!", 「うん」 → "Yeah", '
                  '「はぁ…」 → "*sigh*", 「ちっ」 → "Tch"')
    prompt += (
        " CRITICAL RULE: the output must contain ZERO Japanese script — no kanji, "
        "no hiragana, no katakana. Hepburn romanization applies ONLY to proper "
        "names (people, places, technique names): do NOT translate names, write them in "
        "the Latin alphabet (e.g. 山田太郎 → Tarou Yamada, ユキ → Yuki) and use the "
        "same romanization consistently throughout the text. Everything else must "
        "be TRANSLATED, never transliterated. In particular, interjections, grunts "
        "and verbal sounds are NOT names — render them as the natural equivalent "
        f"in {target} (e.g. {interj}). Never output raw romaji like 'n?', 'e?!' "
        "or 'un'."
    )
    if level == "Completo":
        structure = (
            " STRUCTURE RULE: mirror the paragraph structure of the source, with "
            "paragraphs separated by blank lines. You may merge consecutive very "
            "short narration lines into one flowing paragraph when it reads "
            "better, but never collapse large sections into a single block."
        )
    else:
        structure = (
            " STRUCTURE RULE: keep the output divided into paragraphs separated "
            "by blank lines (when condensing you may merge adjacent paragraphs, "
            "but never collapse everything into a single block of text)."
        )
    prompt += structure
    if target != "Brazilian Portuguese":
        prompt += (
            " Convert Japanese quotation brackets 「…」 into standard "
            f"{target} quotation marks."
        )
    if glossary.strip():
        prompt += (
            "\nGLOSSARY — use these exact renderings, consistently, for names "
            "and terms. Lines may carry a note after '|' (e.g. character "
            "gender): use the notes to translate correctly, but NEVER output "
            "them:\n" + glossary.strip()
        )
    if memory.strip():
        prompt += (
            "\nSTORY CONTEXT — recap of the series so far (characters, "
            "relationships, terms, ongoing events). Use it to keep names, tone "
            "and references consistent; do NOT retell it in the output:\n"
            + memory.strip()
        )
    prompt += (
        " IMAGE MARKERS: tokens like ⟦IMG3⟧ mark where an illustration sits "
        "in the text. Copy every marker to the output EXACTLY as-is, alone on "
        "its own line, at the corresponding position. Never translate, drop "
        "or duplicate a marker."
    )
    return (
        prompt
        + _LEVEL_INSTRUCTIONS.get(level, "")
        + "\nOutput ONLY the translation. No notes and no explanations."
    )


def sanitize_source(text):
    """Doma o texto-fonte antes de enviar ao modelo.

    Sequências gigantes de pontuação repetida (………………, ーーーー etc., comuns
    em web novels) são o gatilho clássico de loop de repetição em LLMs locais.
    Encurta sem perder o efeito estilístico.
    """
    text = re.sub(r"([…。．.、・〜~ーー―\-=★☆!?！？])\1{5,}",
                  lambda m: m.group(1) * 6, text)
    text = re.sub(r"(\S)\1{14,}", lambda m: m.group(1) * 8, text)
    return text


def chunk_text(text, max_chars=1800):
    """Divide o texto em blocos respeitando parágrafos (e frases, se preciso)."""
    paras = [p for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        while len(p) > max_chars:  # parágrafo gigante: corta por frase
            cut = max(p.rfind(c, 0, max_chars)
                      for c in ("。", "！", "？", "」", ". ", "! ", "? "))
            if cut <= 0:
                cut = max_chars
            piece, p = p[: cut + 1], p[cut + 1:]
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(piece)
        if len(cur) + len(p) + 2 > max_chars and cur:
            chunks.append(cur)
            cur = p
        else:
            # linha em branco entre parágrafos: o modelo precisa VER a estrutura
            cur = (cur + "\n\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    return chunks


class OllamaClient:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def is_up(self):
        try:
            requests.get(self.base_url + "/api/version", timeout=3)
            return True
        except requests.RequestException:
            return False

    def list_models(self):
        r = requests.get(self.base_url + "/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]

    def chat_stream(self, model, system, user, num_ctx=16384, temperature=0.4):
        """Gera a resposta em streaming (yield de pedaços de texto).

        Tenta desligar o modo "thinking" (qwen3 etc.); se o modelo não
        suportar o parâmetro, refaz a chamada sem ele.
        """
        try:
            yield from self._chat_stream(model, system, user, num_ctx, temperature, think=False)
        except (RuntimeError, requests.HTTPError) as e:
            if "think" in str(e).lower():
                yield from self._chat_stream(model, system, user, num_ctx, temperature, think=None)
            else:
                raise

    def _chat_stream(self, model, system, user, num_ctx, temperature, think):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "options": {"num_ctx": num_ctx, "temperature": temperature,
                        "repeat_penalty": 1.1, "repeat_last_n": 256},
        }
        if think is not None:
            payload["think"] = think
        with requests.post(
            self.base_url + "/api/chat", json=payload, stream=True, timeout=600
        ) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"Ollama HTTP {r.status_code}: {r.text[:500]}")
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if "error" in data:
                    raise RuntimeError(data["error"])
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break


class ApiClient:
    """Backend alternativo: qualquer API compatível com OpenAI.

    Mesma interface do OllamaClient (chat_stream/list_models/is_up), então o
    resto do app não precisa saber qual backend está em uso.
    Exemplos de base_url: https://api.deepseek.com/v1,
    https://openrouter.ai/api/v1, https://generativelanguage.googleapis.com/v1beta/openai
    """

    def __init__(self, base_url, api_key=""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def is_up(self):
        try:
            requests.get(self.base_url + "/models",
                         headers=self._headers(), timeout=5)
            return True
        except requests.RequestException:
            return False

    def list_models(self):
        r = requests.get(self.base_url + "/models",
                         headers=self._headers(), timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        return sorted(m.get("id", "") for m in data if m.get("id"))

    def chat_stream(self, model, system, user, num_ctx=16384, temperature=0.4):
        # num_ctx é ignorado: APIs gerenciam o contexto sozinhas
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "temperature": temperature,
        }
        with requests.post(
            self.base_url + "/chat/completions", headers=self._headers(),
            json=payload, stream=True, timeout=600,
        ) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"API HTTP {r.status_code}: {r.text[:500]}")
            for raw in r.iter_lines():
                if not raw:
                    continue
                line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if "error" in obj:
                    raise RuntimeError(str(obj["error"])[:500])
                choices = obj.get("choices") or []
                if not choices:
                    continue
                piece = (choices[0].get("delta") or {}).get("content", "")
                if piece:
                    yield piece


class CliClient:
    """Backend via CLI oficial autenticado pela ASSINATURA (sem chave de API).

    Usa o programa de linha de comando do provedor, logado uma única vez pelo
    usuário (claude /login, gemini, codex login). Cada bloco vira uma chamada
    de processo; não há streaming token a token — a resposta chega inteira.
    """

    PROVIDERS = {
        "Claude (claude -p)": {
            "bin": "claude",
            "args": ["-p", "--output-format", "text"],
            "model_flag": "--model",
            "stdin": True,
            "models": ["sonnet", "opus", "haiku"],
        },
        "Gemini (gemini-cli)": {
            "bin": "gemini",
            "args": [],
            "model_flag": "-m",
            "stdin": True,
            "models": ["gemini-2.5-pro", "gemini-2.5-flash"],
        },
        "Codex (codex exec)": {
            "bin": "codex",
            "args": ["exec", "-"],
            "model_flag": "-m",
            "stdin": True,
            "models": [],
        },
    }

    def __init__(self, provider):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Provedor CLI desconhecido: {provider}")
        self.provider = provider
        self.spec = self.PROVIDERS[provider]

    def binary_path(self):
        """Acha o CLI mesmo quando o PATH herdado pelo app está desatualizado.

        No Windows: npm instala como <bin>.cmd em %APPDATA%\\npm; o instalador
        nativo do Claude usa %USERPROFILE%\\.local\\bin. O Explorer só propaga
        PATH novo após relogar, então procuramos nesses lugares diretamente.
        """
        p = shutil.which(self.spec["bin"])
        if p:
            return p
        if os.name == "nt":
            bases = [
                os.path.join(os.environ.get("APPDATA", ""), "npm"),
                os.path.join(os.environ.get("USERPROFILE", ""),
                             ".local", "bin"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""),
                             "Programs", "claude"),
            ]
            for base in bases:
                for ext in (".cmd", ".exe", ".bat", ".ps1", ""):
                    cand = os.path.join(base, self.spec["bin"] + ext)
                    if base and os.path.isfile(cand):
                        return cand
        return None

    def _build_cmd(self, exe, model):
        cmd = [exe] + list(self.spec["args"])
        if model and self.spec.get("model_flag"):
            cmd += [self.spec["model_flag"], model]
        low = exe.lower()
        if low.endswith((".cmd", ".bat")):
            # Python/CreateProcess não executa .cmd direto: passa pelo cmd /c
            cmd = ["cmd", "/c"] + cmd
        elif low.endswith(".ps1"):
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File"] + cmd
        return cmd

    def is_up(self):
        return self.binary_path() is not None

    def list_models(self):
        if not self.is_up():
            raise RuntimeError(
                f"CLI '{self.spec['bin']}' não encontrado no PATH.")
        return list(self.spec["models"])

    def chat_stream(self, model, system, user, num_ctx=16384,
                    temperature=0.4):
        # num_ctx/temperature são gerenciados pelo próprio CLI
        exe = self.binary_path()
        if not exe:
            raise RuntimeError(
                f"CLI '{self.spec['bin']}' não encontrado. Instale-o e faça "
                "login uma vez (ex.: claude /login). Se acabou de instalar, "
                "feche e reabra o app (o PATH novo só vale para processos "
                "novos).")
        cmd = self._build_cmd(exe, model)
        prompt = f"{system}\n\n----\n\n{user}"
        kwargs = {}
        if os.name == "nt":  # não abrir janela de console no modo .exe
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            r = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600, **kwargs)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self.spec['bin']}: tempo esgotado (10 min).")
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()[:500]
            raise RuntimeError(f"{self.spec['bin']} falhou: {err}")
        out = (r.stdout or "").strip()
        if not out:
            raise RuntimeError(f"{self.spec['bin']}: resposta vazia.")
        yield out


def strip_thinking(text):
    """Remove blocos <think>...</think> de modelos com raciocínio (ex.: qwen3)."""
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.S).strip()


IMG_MARKER_RE = re.compile(r"⟦IMG(\d+)⟧")


def restore_missing_markers(source_chunk, output):
    """Rede de segurança: se o modelo perdeu um ⟦IMGn⟧, devolve-o ao fim do
    bloco (a imagem fica um pouco deslocada, mas nunca some)."""
    src_markers = IMG_MARKER_RE.findall(source_chunk)
    out_markers = set(IMG_MARKER_RE.findall(output))
    missing = [m for m in src_markers if m not in out_markers]
    for m in missing:
        output = output.rstrip() + f"\n\n⟦IMG{m}⟧"
    return output


# kanji, hiragana, katakana (inclui半角 katakana)
JP_SCRIPT_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿ｦ-ﾝ]")


def has_japanese_script(text):
    return bool(JP_SCRIPT_RE.search(text))


# romaji solto que alguns modelos deixam escapar em falas curtas → interjeição real
_INTERJ_PT = {
    "n": "Hum", "nn": "Hum", "e": "Quê", "ee": "Quê", "eh": "Quê",
    "a": "Ah", "aa": "Ah", "ah": "Ah", "u": "Uh", "uu": "Uh",
    "un": "Aham", "unn": "Hmm", "uun": "Hmm", "ha": "Haa", "haa": "Haa",
    "he": "Hã", "hee": "Hã", "ho": "Oh", "hoo": "Oh",
    "chi": "Tsc", "tch": "Tsc", "tsk": "Tsc", "fun": "Hunf",
}
_INTERJ_EN = {
    "n": "Hm", "nn": "Hm", "e": "Huh", "ee": "Huh", "eh": "Huh",
    "a": "Ah", "aa": "Ah", "ah": "Ah", "u": "Uh", "uu": "Uh",
    "un": "Yeah", "unn": "Hmm", "uun": "Hmm", "ha": "Hah", "haa": "Hah",
    "he": "Heh", "hee": "Heh", "ho": "Oh", "hoo": "Oh",
    "chi": "Tch", "tch": "Tch", "tsk": "Tsk", "fun": "Hmph",
}
_INTERJ_ES = {
    "n": "Mmm", "nn": "Mmm", "e": "Qué", "ee": "Qué", "eh": "Qué",
    "a": "Ah", "aa": "Ah", "ah": "Ah", "u": "Uh", "uu": "Uh",
    "un": "Ajá", "unn": "Mmm", "uun": "Mmm", "ha": "Ja", "haa": "Jaa",
    "he": "Je", "hee": "Je", "ho": "Oh", "hoo": "Oh",
    "chi": "Tch", "tch": "Tch", "tsk": "Tch", "fun": "Hmph",
}


# marcadores internos de contexto que o modelo pode vazar/traduzir na saída
_LEAK_RE = re.compile(
    r"(?im)^\s*\[?\s*("
    r"(final|fim|end)\s+(do|de|of)\s+(o\s+)?context[oe]?|"
    r"previous translated context.*|contexto traduzido anterior.*|"
    r"translate the following text:?|traduza o (texto|seguinte).*"
    r")\s*\]?\s*$\n?")


def _dedupe_lines(text, max_rep=2):
    """Colapsa linhas idênticas consecutivas (sintoma de loop de repetição)."""
    out = []
    last_key, reps = None, 0
    for line in text.split("\n"):
        key = line.strip()
        if not key:
            # linha em branco não zera a contagem (loops vêm como "A\n\nA\n\nA")
            if out and out[-1].strip() == "":
                continue
            out.append(line)
            continue
        if key == last_key:
            reps += 1
            if reps > max_rep:
                continue
        else:
            last_key, reps = key, 1
        out.append(line)
    text = "\n".join(out)
    # remove linha em branco órfã no fim
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def postprocess_translation(text, lang_label):
    """Limpeza determinística: interjeições em romaji e aspas japonesas."""
    text = _LEAK_RE.sub("", text)
    text = _dedupe_lines(text)
    table = {"Inglês": _INTERJ_EN,
             "Espanhol": _INTERJ_ES}.get(lang_label, _INTERJ_PT)

    def _repl(m):
        word = table.get(m.group(2).lower())
        if word:
            return m.group(1) + word + m.group(3) + m.group(4)
        return m.group(0)

    # fala curta entre aspas (japonesas ou ocidentais): 「n?」 "e?!" “un”
    text = re.sub(r'(「|『|“|‘|")\s*([A-Za-z]{1,3})\s*([?!…~.]*)\s*(」|』|”|’|")',
                  _repl, text)
    # fala curta após travessão:  — N?
    def _repl_dash(m):
        word = table.get(m.group(2).lower())
        if word:
            return m.group(1) + word + m.group(3)
        return m.group(0)
    text = re.sub(r"(?m)(^[—–-]\s*)([A-Za-z]{1,3})([?!…~.]+)\s*$", _repl_dash, text)

    # aspas japonesas remanescentes → aspas comuns
    text = (text.replace("「", "“").replace("」", "”")
                .replace("『", "‘").replace("』", "’"))
    return re.sub(r"\n{3,}", "\n\n", text)


def fix_japanese_leftovers(client, model, text, lang_label):
    """Segunda passada: romaniza nomes/termos que sobraram em grafia japonesa."""
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    system = (
        f"You are a copy editor. The user sends a text in {target} that still "
        "contains some words in Japanese script (kanji/kana). Rewrite the text "
        "EXACTLY as it is, changing ONLY the words in Japanese script: if it is a "
        "proper name, write it in the Latin alphabet using Hepburn romanization; "
        "if it is an interjection or verbal sound (ん, えっ, うん...), replace it "
        f"with the natural equivalent in {target} (Hum?, Quê?!, Aham...); anything "
        f"else, translate it into {target}. Do not change anything else. "
        "Output ONLY the corrected text, with zero Japanese script."
    )
    buf = "".join(client.chat_stream(model, system, text, temperature=0.1))
    buf = strip_thinking(buf)
    # só aceita a correção se resolveu E não destruiu o texto nem os parágrafos
    orig_paras = max(1, len([p for p in text.split("\n\n") if p.strip()]))
    new_paras = len([p for p in buf.split("\n\n") if p.strip()])
    if (buf and not has_japanese_script(buf)
            and len(buf) > 0.5 * len(text)
            and new_paras >= 0.6 * orig_paras):
        return buf
    return text


def review_translation(client, model, text, lang_label,
                       on_progress=None, should_stop=None):
    """Passada opcional de revisão: melhora fluidez sem mudar conteúdo.

    Revisa em blocos; se a revisão de um bloco encolher/crescer demais
    (sinal de conteúdo perdido/inventado), mantém o original do bloco.
    """
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    system = (
        f"You are a literary copy editor for {target} light novel "
        "translations. The user sends a passage already translated into "
        f"{target}. Improve fluency and naturalness, fix awkward or overly "
        "literal phrasing, and keep names/honorifics consistent. Keep the "
        "dialogue punctuation style as-is. Do NOT add, remove or reorder "
        "content; do NOT change the meaning; keep the same paragraph breaks. "
        "Output ONLY the revised passage."
    )
    chunks = chunk_text(text, max_chars=3500)
    out = []
    for i, chunk in enumerate(chunks):
        if should_stop and should_stop():
            out.extend(chunks[i:])
            break
        if on_progress:
            on_progress(i + 1, len(chunks))
        try:
            buf = strip_thinking("".join(
                client.chat_stream(model, system, chunk, temperature=0.3)))
        except Exception:
            out.append(chunk)
            continue
        paras_ok = len([p for p in buf.split("\n\n") if p.strip()]) >= \
            0.6 * max(1, len([p for p in chunk.split("\n\n") if p.strip()]))
        if buf and 0.7 * len(chunk) <= len(buf) <= 1.4 * len(chunk) and paras_ok:
            out.append(buf.strip())
        else:
            out.append(chunk)  # revisão suspeita: mantém o original
    return "\n\n".join(out)


_NAME_TOKEN = r"[A-ZÀ-ÖØ-Þ][\w'’\-]+"


def find_name_inconsistencies(texts, glossary=""):
    """Acha o mesmo nome grafado em ordens diferentes nas traduções.

    Duas fontes: (1) glossário — a forma canônica vs a invertida;
    (2) genérico — pares de palavras capitalizadas que aparecem nas duas
    ordens no texto. Retorna [{"de", "para", "n_de", "n_para", "fonte"}],
    sempre sugerindo unificar para a forma majoritária/canônica.
    """
    import collections

    full = "\n".join(texts)
    findings, seen = [], set()

    # 1) guiado pelo glossário (canônico vence sempre)
    for line in glossary.splitlines():
        if "=" not in line:
            continue
        canon = line.partition("=")[2].partition("|")[0].strip()
        parts = canon.split()
        if len(parts) != 2:
            continue
        inv = f"{parts[1]} {parts[0]}"
        n_inv = full.count(inv)
        if n_inv:
            findings.append({"de": inv, "para": canon, "n_de": n_inv,
                             "n_para": full.count(canon),
                             "fonte": "glossário"})
            seen.add(frozenset((canon, inv)))

    # 2) genérico: bigramas capitalizados nas duas ordens
    bigrams = collections.Counter(
        re.findall(rf"({_NAME_TOKEN}) ({_NAME_TOKEN})", full))
    for (a, b), n_ab in bigrams.items():
        n_ba = bigrams.get((b, a), 0)
        if not n_ba:
            continue
        f1, f2 = f"{a} {b}", f"{b} {a}"
        key = frozenset((f1, f2))
        if key in seen:
            continue
        seen.add(key)
        if n_ab >= n_ba:  # maioria vence; empate mantém a primeira vista
            findings.append({"de": f2, "para": f1, "n_de": n_ba,
                             "n_para": n_ab, "fonte": "texto"})
        else:
            findings.append({"de": f1, "para": f2, "n_de": n_ab,
                             "n_para": n_ba, "fonte": "texto"})
    return findings


def apply_name_mapping(text, mapping):
    """Aplica unificações {variante: canônico} a um texto."""
    for de, para in mapping.items():
        text = text.replace(de, para)
    return text


def update_memory(client, model, memory, chapter_title, chapter_translation,
                  lang_label="Português (BR)"):
    """Atualiza a 'memória da saga' com o capítulo recém-traduzido.

    Retorna a memória atualizada (ou a antiga, se a atualização falhar).
    """
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    text = chapter_translation
    if len(text) > 12000:  # capítulo enorme: começo + fim bastam p/ o resumo
        text = text[:7000] + "\n[...]\n" + text[-5000:]
    system = (
        f"You maintain the compact 'story bible' of a light novel series, written "
        f"in {target}. The user sends the current story bible and the newest "
        "translated chapter. Output the UPDATED story bible, merging in the new "
        "information:\n"
        "- CHARACTERS: name (romanization used), role, key relationships\n"
        "- TERMS: world-specific terms/skills/places and the renderings used\n"
        "- STORY SO FAR: running summary of events (2-4 new sentences per "
        "chapter; compress older events as needed)\n"
        "- TONE: narration style notes (e.g. sarcastic first-person)\n"
        "Keep the WHOLE story bible under about 1500 words — merge or drop minor "
        "details when it grows. Output ONLY the story bible text, no comments."
    )
    user = (
        f"CURRENT STORY BIBLE:\n{memory.strip() or '(empty — first chapter)'}\n\n"
        f"NEW CHAPTER ({chapter_title}):\n{text}"
    )
    buf = strip_thinking("".join(
        client.chat_stream(model, system, user, temperature=0.2)))
    if buf and len(buf) >= 0.3 * len(memory.strip()):  # não aceita encolher demais
        return buf[:12000]
    return memory


def extract_glossary_pairs(client, model, src_seg, dst_seg, lang_label,
                           existing=""):
    """Extrai pares 'original = tradução' de um trecho fonte + trecho traduzido.

    Só aceita pares cujo original aparece no trecho fonte E cuja tradução
    aparece no trecho traduzido (anti-alucinação).
    """
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    system = (
        "You build a translation glossary for a light novel. The user sends a "
        f"source-language excerpt and the corresponding published {target} "
        "translation. Extract pairs of proper names (people, places), "
        "skills/techniques and world-specific terms that appear in BOTH "
        "excerpts, mapping the exact source form to the exact rendering the "
        "translator used. Skip generic words and common nouns. Output ONLY "
        "lines in the format:\noriginal = rendering\nNothing else."
    )
    if existing.strip():
        system += "\nSkip pairs already known:\n" + existing.strip()[:2000]
    user = f"SOURCE EXCERPT:\n{src_seg}\n\nTRANSLATION EXCERPT:\n{dst_seg}"
    buf = strip_thinking("".join(
        client.chat_stream(model, system, user, temperature=0.1)))
    pairs = []
    for line in buf.splitlines():
        # tolera enfeites comuns de modelos: numeração, negrito, crases, aspas
        line = re.sub(r"^\s*\d+[.)]\s*", "", line.strip())
        line = line.replace("**", "").replace("`", "")
        if "=" not in line:
            continue
        orig, _, dst = line.partition("=")
        orig = orig.strip(" \t-•*→「」『』\"'“”‘’")
        dst = dst.strip(" \t.「」『』\"'“”‘’")
        if not orig or not dst or len(orig) > 40 or len(dst) > 60:
            continue
        if orig not in src_seg:
            continue  # o modelo inventou o original — descarta
        pairs.append((orig, dst))
    return pairs


def _norm(s):
    return re.sub(r"\s+", " ", s).lower()


def suggest_glossary(client, model, src_text, lang_label, existing=""):
    """Lê a abertura da obra e propõe entradas de glossário para revisão.

    Diferente do learn_glossary, aqui só existe o texto-fonte: o original é
    validado contra o texto (anti-alucinação), mas a tradução proposta é um
    PALPITE do modelo — por isso o resultado vai para revisão, não direto.
    """
    target = LANGS.get(lang_label, "Brazilian Portuguese")
    system = (
        "You read the OPENING of a light novel in its source language and "
        f"build a STARTER glossary for translating it into {target}. List the "
        "proper names found in the text (characters, places, organizations, "
        "techniques/skills): for Japanese names propose the most likely "
        "Hepburn romanization; for other terms propose the rendering a fan "
        "translator would use. One per line, format:\noriginal = rendering\n"
        "Skip generic words. Output ONLY the lines."
    )
    if existing.strip():
        system += "\nSkip names already known:\n" + existing.strip()[:1500]
    user = src_text[:6000]
    buf = strip_thinking("".join(
        client.chat_stream(model, system, user, temperature=0.1)))
    known = {l.partition("=")[0].strip()
             for l in existing.splitlines() if "=" in l}
    pairs = []
    for line in buf.splitlines():
        line = re.sub(r"^\s*\d+[.)]\s*", "", line.strip())
        line = line.replace("**", "").replace("`", "")
        if "=" not in line:
            continue
        orig, _, dst = line.partition("=")
        orig = orig.strip(" \t-•*→「」『』\"'“”‘’")
        dst = dst.strip(" \t.「」『』\"'“”‘’")
        if not orig or not dst or len(orig) > 40 or len(dst) > 60:
            continue
        if orig not in user or orig in known:
            continue  # inventado ou já conhecido
        known.add(orig)
        pairs.append((orig, dst))
    return pairs


def learn_glossary(client, model, src_chapters, dst_chapters, lang_label,
                   existing="", max_calls=12, seg_chars=2200,
                   on_progress=None, should_stop=None):
    """Minera o glossário comparando um livro original com sua tradução.

    src_chapters/dst_chapters: listas (titulo, texto) de extract_book().
    Alinha capítulos proporcionalmente (não precisa ser exato: nomes se
    repetem ao longo do livro). Retorna lista de pares novos, sem duplicados.
    """
    known = {}
    for line in existing.splitlines():
        if "=" in line:
            known[line.partition("=")[0].strip()] = True

    # alinhamento proporcional GLOBAL: janelas na mesma fração do livro
    # (não precisa ser exato — nomes se repetem; a validação descarta o resto)
    src_full = "\n".join(t for _, t in src_chapters)
    dst_full = "\n".join(t for _, t in dst_chapters)
    n_samples = max(1, min(max_calls,
                           (len(src_full) + seg_chars - 1) // seg_chars))
    # janela da tradução cobre a fatia proporcional + folga p/ desalinhamento
    dst_win = int(max(seg_chars * 2.2, len(dst_full) / n_samples * 1.5))
    dst_win = min(dst_win, 9000)  # protege o limite de contexto do modelo
    found = []
    for k in range(n_samples):
        if should_stop and should_stop():
            break
        f = k / max(1, n_samples - 1) if n_samples > 1 else 0.0
        so = int(f * max(0, len(src_full) - seg_chars))
        do = int(f * max(0, len(dst_full) - dst_win))
        src_seg = src_full[so:so + seg_chars]
        dst_seg = dst_full[do:do + dst_win]
        if on_progress:
            on_progress(k + 1, n_samples)
        try:
            pairs = extract_glossary_pairs(client, model, src_seg, dst_seg,
                                           lang_label, existing)
        except Exception:
            continue
        # valida a tradução contra o LIVRO TRADUZIDO INTEIRO (não só a janela):
        # tolera desalinhamento sem abrir mão da prova de que a forma existe
        dst_full_norm = _norm(dst_full)
        for orig, dst in pairs:
            if orig not in known and _norm(dst) in dst_full_norm:
                known[orig] = True
                found.append((orig, dst))
    return found


def build_memory_from_translation(client, model, dst_chapters, title,
                                  lang_label, memory="", slice_chars=9000,
                                  max_slices=5, on_progress=None,
                                  should_stop=None):
    """Constrói/atualiza a memória da saga lendo um volume JÁ traduzido.

    Percorre fatias do livro em ordem, atualizando a memória a cada uma.
    """
    full = "\n".join(t for _, t in dst_chapters)
    n = max(1, min(max_slices, (len(full) + slice_chars - 1) // slice_chars))
    step = max(1, (len(full) - slice_chars) // max(1, n - 1)) if n > 1 else 0
    for k in range(n):
        if should_stop and should_stop():
            break
        if on_progress:
            on_progress(k + 1, n)
        start = k * step
        piece = full[start:start + slice_chars]
        try:
            memory = update_memory(client, model, memory,
                                   f"{title} (parte {k+1}/{n})",
                                   piece, lang_label)
        except Exception:
            continue
    return memory


def translate_chapter(client, model, text, lang_label, level,
                      source_label="Japonês", glossary="", memory="",
                      chunk_chars=1800, on_piece=None, should_stop=None):
    """Traduz um capítulo inteiro. Retorna o texto final.

    on_piece(str): callback chamado com cada pedaço streamado.
    should_stop(): callback que retorna True para cancelar.
    chunk_chars: tamanho do bloco — modelos locais pequenos pedem ~1800;
    backends API/CLI (modelos de ponta) aceitam 4500+, reduzindo chamadas.
    """
    system = build_system_prompt(lang_label, level, source_label, glossary,
                                 memory)
    chunks = chunk_text(sanitize_source(text), max_chars=chunk_chars)
    out_parts = []
    prev_tail = ""

    for i, chunk in enumerate(chunks):
        if should_stop and should_stop():
            break
        user = chunk
        if prev_tail:
            user = (
                "[Previous translated context, for continuity only — do NOT retranslate "
                f"or repeat it]\n{prev_tail}\n[End of context]\n\n"
                "Translate the following text:\n" + chunk
            )
        buf = ""
        for piece in client.chat_stream(model, system, user):
            if should_stop and should_stop():
                break
            buf += piece
            if on_piece:
                on_piece(piece)
        buf = strip_thinking(buf)
        # sobrou grafia japonesa (nomes em kanji/kana)? roda passada de correção
        if buf and has_japanese_script(buf) and not (should_stop and should_stop()):
            try:
                buf = fix_japanese_leftovers(client, model, buf, lang_label)
            except Exception:
                pass  # mantém a tradução original se a correção falhar
        buf = postprocess_translation(buf, lang_label)
        buf = restore_missing_markers(chunk, buf)
        out_parts.append(buf.strip())
        prev_tail = buf.strip()[-600:]
        if on_piece and i < len(chunks) - 1:
            on_piece("\n\n")

    return "\n\n".join(p for p in out_parts if p)
