# Light Novel Translator (Ollama)

*Read this in [Portuguese / Português](README.md) · [Spanish / Español](README.es.md).*

Desktop app for reading light novels (EPUB/PDF/TXT) in Japanese, English or
Spanish and translating them into Brazilian Portuguese or English with a local
LLM via Ollama, featuring 3 levels of "dynamization" (text condensation).

> **Responsible use and legality:** this is a translation-assistance tool for
> **personal use, exclusively with legally obtained content** — books you
> purchased (DRM-free ebooks), works published for free by their own authors
> (e.g. Syosetu, Kakuyomu) or in the public domain. **Do not use this program
> with pirated copies** downloaded from aggregators, scans or unauthorized
> repositories: besides being illegal, it directly harms the authors of the
> works you love. No book, translation or derived file (glossaries/memories)
> is distributed in this repository, and generated translations must not be
> redistributed — they are for your own reading. Support the authors by buying
> the official editions.

## Requirements

- Windows, Linux or macOS with Python 3.10+ (https://python.org — on Windows,
  check "Add to PATH")
- A translation "engine" of your choice (see Installation): **Ollama** for
  local models, or an **API key** from an OpenAI-compatible provider
- For local models: any PC with 8 GB of RAM can run the small ones (on the
  CPU, slower). With a GPU, see the model table below — from 4 GB up to 16 GB
  of VRAM. For the API, hardware doesn't matter.

## Installation

```bat
pip install -r requirements.txt
python main.py
```

Then choose **how to run the model** — both options are equivalent to the
app, and you can switch anytime with the **Via:** selector:

**Option A — Local model (Ollama):** free, private and offline. Install
Ollama (https://ollama.com), pull a model from the table below with
`ollama pull <model>` and keep the selector on **Via: Ollama**.

**Option B — API:** frontier-model quality regardless of your hardware — in
exchange for pay-per-use and sending the text to the provider. In the app,
switch to **Via: API** and enter the URL and key (details in the "Using an
API" section below).

**Option C — Subscription via CLI:** if you already subscribe to Claude
(Pro/Max), ChatGPT, or use a Google account, you can use the subscription
instead of a key: install the provider's official CLI and log in once
(`claude` + /login, `gemini`, or `codex login`); in the app, switch to
**Via: CLI** and pick the provider. Text goes to the provider as in Option B,
and your subscription's programmatic-usage limits/credits apply (Claude paid
plans include a dedicated monthly credit for this). No streaming: each block
arrives at once.

## Recommended local models (Option A — from modest PCs to the top)

Pick by your GPU's VRAM (or RAM, if running CPU-only):

| Hardware | Model | Size | What to expect |
|---|---|---|---|
| No GPU / 8 GB RAM | `gemma3:4b` | ~3.3 GB | Runs on almost any PC. Understandable but simplified translation; use the glossary to keep names straight. Slow on CPU. |
| 4 GB GPU | `gemma3:4b` or `qwen3:4b` | ~3 GB | Same as above, but fast. Good for trying the app out. |
| 6 GB GPU | `qwen3:8b` | ~5.2 GB | First tier with decent Japanese. A good entry point. |
| 8 GB GPU | `gemma3:12b` | ~8 GB | Noticeably better prose; strong multilingual. A tight fit — close other GPU apps. |
| 12 GB GPU | `qwen3:14b` | ~10 GB | Great quality/speed balance for Japanese. |
| 16 GB GPU | `gemma3:27b-it-qat` | ~14 GB | **Top of this list.** Google's QAT quantization: near-lossless 27B quality that fits in VRAM. |

Every name in the table is the exact Ollama tag — just
`ollama pull <model>` and click ⟳ in the app. They all come quantized to
4 bits with nothing extra to specify: the default tags use Q4_K_M, and
`gemma3:27b-it-qat` uses Google's QAT (quantization applied during training —
same compression, far smaller quality loss).

Rules of thumb: the smaller the model, the more the 📓 glossary and the
🎓 learning-from-existing-translations feature matter (they offset part of the
loss); below 4B, Japanese translation degrades too much — not recommended; and
a larger model quantized to Q4 almost always beats a smaller one at Q8.

> **Heads-up:** the sizes in the table are the model weights only — VRAM and
> RAM are not exclusively the model's. The translation context takes another
> ~1-2 GB of VRAM, and the OS and other programs also use memory (Windows
> takes ~0.5-1 GB of VRAM; a hardware-accelerated browser, Discord and games
> can eat several GB). If your chosen model is near your hardware's limit,
> close heavy programs before translating — otherwise the model spills over
> into RAM/disk and translation gets much slower.

## Using an API (Option B in detail)

Switch the **Via:** selector to "API" and enter the base URL and key of any
OpenAI-compatible provider (DeepSeek, OpenRouter, Gemini, Groq...). If the
provider doesn't list models, type the model name directly into the box
(e.g. `deepseek-chat`). The configuration is saved to `api.json` **on your
computer only** — the file is gitignored; never push it to GitHub, as it
contains your key.

Things to consider: APIs charge per use (a typical volume costs cents to a few
dollars depending on the model), require internet, and the book's text is sent
to the provider — read their terms. For 100% local and free usage, stick with
Ollama (Option A).

## Usage

```bat
python main.py
```

1. **📖 Open book** — select an .epub, .pdf or .txt file.
2. Choose **model**, **source language** (From: Japanese/English/Spanish),
   **target language** (To: PT-BR/English) and **dynamization**:
   - **Full** — complete translation.
   - **Low dynamization** — ~25% shorter; trims redundant descriptions, keeps all dialogue and events.
   - **Medium dynamization** — ~35-45% shorter; also shortens low-relevance internal monologue while keeping dialogue and character-revealing thoughts.
   - **High dynamization** — ~50-60% shorter; drops thoughts/monologues that don't matter to the plot.
3. **▶ Translate chapter** or **▶▶ Translate all**. The translation streams in real time in the right panel; finished chapters turn green in the list.
4. **💾 Save translation** exports everything to .txt/.md.

Translations are cached per chapter+source+target+level combination — changing
the level and translating again creates another version without losing the
previous one (within the same session).

**Executable (.exe):** run `build.bat` to produce
`dist\LightNovelTranslator.exe` via PyInstaller — distribute the app without
requiring Python (Ollama is still needed).

**Tests:** `python -m unittest discover tests` runs the full suite, no Ollama
needed — it uses fake clients.

## Features

**Dynamization:** this is the app's fast-reading feature — instead of
translating and then summarizing, the model condenses *while* translating,
rewriting the text as leaner flowing prose. The goal is cutting fat, not
story: at every level, all plot events and important dialogue are preserved;
what goes away is wordy description, repetitive narration and internal
monologue that adds nothing — that web-novel pattern where the protagonist
ponders the same thing for three paragraphs.

The levels control how aggressive the cut is:

- **Full** — complete translation, nothing cut. Recommended for a first read
  of works you want to savor.
- **Low (~25% shorter)** — light trimming only: redundant descriptions and
  repetition shrink; all dialogue, events and character moments stay.
- **Medium (~35-45%)** — also shortens low-relevance internal monologue, while
  keeping thoughts that reveal personality or affect the story.
- **High (~50-60%)** — drops musings and digressions that don't matter to the
  plot and compresses long descriptions into a sentence. Ideal for dragging
  arcs, re-reads, or catching up on a long saga.

An honest warning: at **any** dynamization level there's a risk of cutting
something that seems irrelevant now but matters later — the model judges from
the chapter's context, with no knowledge of what the author planted for the
future. In general, though, it only kills false Chekhov's guns: web novels are
full of details that never fire, and those are the first to go. If the work is
known for tying up loose ends (mysteries, heavy foreshadowing), stick to Full
or Low.

Since each level is a *rewrite* performed by the model, results vary slightly
between runs, and larger models judge what's cuttable better — on small models
(4-8B), prefer Low, as their judgment is less reliable. The cache stores each
level separately: you can translate the same chapter in Full and High and
compare, without losing either version.

**Glossary (📓):** to get names and terms right every time (kanji name
readings are ambiguous — 月森アヤメ could become "Tsukimori Ayame", "Getsumori
Ayame" or another reading, depending on the model's guess), fill the glossary
with `original = rendering`, one per line. It is saved as
`<book>.glossario.txt` next to the book file and reloaded automatically when
you open the book again. The **Import…** button inside the editor merges
entries from another `.glossario.txt` (e.g. the `saga.glossario.txt` produced
by 🎓📂) into the current book's glossary, without duplicating or overwriting
what you already have.

**Style:** PT-BR output follows community-translation conventions: dialogue
with em dashes (—), colloquial register that preserves the narrator's
humor/sarcasm, otaku terms kept untranslated (galge, eroge, senpai...) and
expressive onomatopoeia.

**Saga mode (📂 Saga…):** select a folder containing the saga's volumes
(.epub/.pdf/.txt — ordering is alphabetical, so name them `vol01`, `vol02`...).
The app translates volume by volume, chaining the memory between them, and
saves each one to `traduzidos/<volume>_traduzido.txt` inside the folder. The
saga's memory and glossary live in the folder root (`saga.memoria.txt` /
`saga.glossario.txt`). When you open a saga, any other `.glossario.txt` in the
folder (from individual volumes or from 🎓) is automatically merged into the
saga glossary — existing entries in it take priority and are never overwritten. If you stop midway (■), the in-progress volume is saved
as `_parcial` and, on the next run, completed volumes are skipped — automatic
resume.

**Learn from an existing translation (🎓):** if the series already has some
translated volumes (official or community), use them to teach the app: click
🎓 Learn…, select the original volume and then the same volume translated.
The model compares corresponding excerpts from both and extracts
`original name = translator's rendering` pairs straight into the glossary —
each pair is validated against both texts (it's only accepted if the original
exists in the source text and the rendering exists in the translated text),
preventing made-up entries. Repeat for every translated volume you have
(vol. 1, 2, 3...); known entries are not duplicated. 🎓 also builds/updates
the 🧠 saga memory by reading the translated volume — so unreleased volumes
start with the story context already loaded. Then review 📓 Glossary and
🧠 Memory and translate the unreleased volumes with everything established.

**Learn saga (🎓📂):** the batch version of 🎓. Put the original volumes and
their existing translations in one folder, marking each translation with a `t`
suffix in the name: `vol01.txt` + `vol01t.txt`, `vol02.epub` + `vol02t.txt`
(`vol02_t` also works, and extensions may differ). The app pairs the files,
shows the pairs for confirmation and processes them volume by volume, in
order: extracting the glossary from each pair (no duplicate entries) and
building the chained memory by reading the translations. Everything is saved
to `saga.glossario.txt` and `saga.memoria.txt` in the folder root. Afterwards,
drop the unreleased volumes into the same folder and use 📂 Saga… — volumes
that have a `t` pair are automatically skipped during translation, and the
unreleased ones inherit the learned glossary and memory.

Both folder tools remember what they've already done: translation skips
volumes that already have a file in `traduzidos/`, and learning records the
processed pairs in `saga.aprendido.txt` — if you later add a `vol04`/`vol04t`,
only it will be read; volumes 1-3 are not reprocessed (their glossary and
memory are already saved). To relearn from scratch, delete
`saga.aprendido.txt`.

**Saga memory (🧠):** the app keeps a story recap (characters, terms, events,
tone) that is injected as context into every translation and automatically
updated by the model after each finished chapter (turn it off with ☑ auto if
you want). It is saved as `<book>.memoria.txt` next to the book. To translate
a saga's context in a standalone volume, open the volume and use, in
🧠 Memory, **Import copy…** (copies the recap into the current book without
touching the source file) or **Link to saga…** (reads from AND writes to the
saga's `.memoria.txt` from then on, accumulating context there). You can also
edit the recap manually.

**Character names:** never translated, always output in the Latin alphabet
(Hepburn romanization, e.g. 山田太郎 → Tarou Yamada). If a translation still
comes back with Japanese script, the app detects it and automatically runs a
second correction pass on the chapter.

**Name consistency (🔍):** scans finished translations for the same name
spelled in different orders ("Ayame Tsukimori" vs "Tsukimori Ayame"), shows
occurrence counts and unifies to the majority/glossary form in one click —
directly in the cache, no retranslation.

**Audio (🔊):** generates an MP3 of the translated chapter with a free neural
voice (edge-tts, requires internet) in the target language — your light novel
becomes an audiobook.

**Review (✨):** optional checkbox that runs a second model pass over the
finished translation, improving fluency and naturalness without changing
content (blocks the revision shrinks/grows too much are discarded, keeping the
original). Doubles the time per chapter — worth it with mid-size models.

**Persistence:** each book's translations are saved automatically to
`<book>.cache.json` next to the file — close the app and resume later,
including reading position (the chapter you were on reopens by itself). Your
model, language, level and font choices are also remembered between sessions
(`settings.json`).

**Export:** 💾 now saves to **EPUB** (default — chapters preserved, readable
on Kindle/phone/readers), plus .txt and .md.

**Images preserved:** if the original EPUB or PDF has illustrations, the app
marks each one's position in the text (⟦IMGn⟧, visible in the panels), the
model preserves the markers in the translation (with a safety net: a lost
marker is restored at the end of the passage) and the EPUB export embeds the
original images in the right places. For PDFs, the with-images output is also
EPUB — rebuilding a PDF's exact layout with translated text isn't feasible;
EPUB keeps illustrations at the correct position in the reading flow. Tiny
images (icons/dividers) are ignored; in .txt export they become
"[ilustração]".

**Reading mode (👁):** hides the original panel to read the translation
full-width; click again to bring it back.

**Synced bilingual:** with both panels visible, click any paragraph (in the
translation or the original) and the corresponding paragraph on the other
side is highlighted and scrolled into view — great for studying Japanese
against the translation. In Full mode the pairing is exact (the translation
mirrors the structure); with dynamization it's proportional (approximate,
since paragraphs were merged).

The glossary editor also has **Suggest (AI)…**: the model reads the book's
opening and proposes entries (detected names + likely reading) — only names
present in the text get in, but the proposed reading is a guess: review
before saving.

## Tips

- Kindle files (DRM-free .mobi/.azw3) work if
  [Calibre](https://calibre-ebook.com) is installed — conversion to EPUB is
  automatic and invisible.
- The app quietly notes in the status bar when a newer GitHub release exists
  (network failures are silent).
- Scanned (image-based) PDFs don't work — the PDF must have selectable text.
- If the app says Ollama wasn't found, open Ollama and click ⟳.
- JP→EN quality tends to be slightly better than JP→PT-BR on local models.

## Credits

This project exists thanks to these open-source tools:

- [Ollama](https://ollama.com) — local LLM runtime, the engine behind everything
- [Gemma 3](https://ai.google.dev/gemma) (Google) and [Qwen 3](https://github.com/QwenLM/Qwen3) (Alibaba) — the recommended translation models
- [Python](https://python.org) and Tkinter — language and GUI
- [PyMuPDF](https://pymupdf.readthedocs.io) — PDF text extraction
- [EbookLib](https://github.com/aerkalov/ebooklib) — EPUB file reading
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) — EPUB HTML processing
- [Requests](https://requests.readthedocs.io) — communication with the Ollama API

Developed with the assistance of [Claude](https://claude.com) (Anthropic).
