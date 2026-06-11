# -*- coding: utf-8 -*-
"""Extração de texto de EPUB e PDF, dividido em capítulos.

Imagens são extraídas com a posição preservada no fluxo do texto, via
marcadores ⟦IMGn⟧ (parágrafo próprio). A tradução preserva os marcadores e a
exportação EPUB os converte de volta em imagens embutidas.
"""

import os
import re
import shutil
import subprocess
import tempfile

IMG_RE = re.compile(r"⟦IMG(\d+)⟧")

# locais comuns do Calibre no Windows (PATH herdado pode estar desatualizado)
_CALIBRE_HINTS = (
    r"C:\Program Files\Calibre2",
    r"C:\Program Files (x86)\Calibre2",
)


def _find_calibre():
    p = shutil.which("ebook-convert")
    if p:
        return p
    for base in _CALIBRE_HINTS:
        cand = os.path.join(base, "ebook-convert.exe")
        if os.path.isfile(cand):
            return cand
    return None


def convert_kindle_to_epub(path):
    """Converte .mobi/.azw3/.azw em EPUB temporário via Calibre."""
    exe = _find_calibre()
    if not exe:
        raise ValueError(
            "Formatos Kindle (.mobi/.azw3) requerem o Calibre instalado "
            "(https://calibre-ebook.com) — ele fornece o conversor "
            "'ebook-convert'. Instale e tente de novo.")
    out = os.path.join(tempfile.gettempdir(),
                       os.path.splitext(os.path.basename(path))[0]
                       + "_lnt.epub")
    r = subprocess.run([exe, path, out], capture_output=True, text=True,
                       timeout=300)
    if r.returncode != 0 or not os.path.isfile(out):
        raise ValueError("Conversão Kindle→EPUB falhou: "
                         + (r.stderr or r.stdout or "?")[:300])
    return out

# imagens menores que isso são decoração (ícones, divisores) — ignoradas
_MIN_IMG_BYTES = 4096
_MIN_IMG_PX = 64


def strip_image_markers(text):
    text = IMG_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_book(path):
    """Retorna lista de (titulo, texto) por capítulo, SEM marcadores."""
    chapters, _ = extract_book_images(path)
    return [(t, strip_image_markers(x)) for t, x in chapters]


def extract_book_images(path):
    """Retorna (capitulos, imagens).

    capitulos: [(titulo, texto_com_marcadores)]
    imagens:   {n: {"data": bytes, "ext": "jpg", "media_type": "image/jpeg"}}
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".epub":
        return extract_epub(path)
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".txt":
        return extract_txt(path), {}
    if ext in (".mobi", ".azw3", ".azw"):
        return extract_epub(convert_kindle_to_epub(path))
    raise ValueError(f"Formato não suportado: {ext}")


# ---------------------------------------------------------------- EPUB

def extract_epub(path):
    from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE, epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(path, options={"ignore_ncx": True})

    # mapa basename -> (bytes, media_type) das imagens do pacote
    img_items = {}
    for item in book.get_items_of_type(ITEM_IMAGE):
        img_items[os.path.basename(item.get_name())] = (
            item.get_content(), item.media_type or "image/jpeg")

    images = {}
    counter = [0]

    def register_image(src):
        if not src:
            return None
        data = img_items.get(os.path.basename(src.split("?")[0]))
        if not data or len(data[0]) < _MIN_IMG_BYTES:
            return None
        counter[0] += 1
        ext = os.path.splitext(src)[1].lstrip(".").lower() or "jpg"
        images[counter[0]] = {"data": data[0], "ext": ext,
                              "media_type": data[1]}
        return f"⟦IMG{counter[0]}⟧"

    chapters = []
    n = 0
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for tag in soup(["script", "style", "rt"]):  # rt = furigana
            tag.decompose()

        title = None
        for h in ("h1", "h2", "h3"):
            el = soup.find(h)
            if el and el.get_text(strip=True):
                title = el.get_text(strip=True)
                break

        paras = []
        body = soup.body or soup
        for el in body.find_all(["p", "div", "h1", "h2", "h3", "img",
                                 "image"]):
            if el.name in ("img", "image"):
                src = el.get("src") or el.get("xlink:href") or el.get("href")
                marker = register_image(src)
                if marker:
                    paras.append(marker)
                continue
            # evita duplicar texto de divs que contêm <p>
            if el.name == "div" and el.find(["p", "div"]):
                continue
            t = el.get_text(" ", strip=True)
            if t:
                paras.append(t)
        text = "\n\n".join(paras).strip()
        if not text:
            text = body.get_text("\n", strip=True)

        if len(strip_image_markers(text)) < 50 and IMG_RE.search(text or ""):
            # página só de imagem (capa, ilustração de abertura): vira
            # "capítulo" curto para a imagem não se perder
            n += 1
            chapters.append((title or f"Ilustração {n}", text))
            continue
        if len(text) < 50:  # capa/sumário/créditos sem nada útil
            continue
        n += 1
        chapters.append((title or f"Capítulo {n}", text))

    if not chapters:
        raise ValueError("Nenhum conteúdo de texto encontrado no EPUB.")
    return chapters, images


# ---------------------------------------------------------------- PDF

def extract_pdf(path, pages_per_chapter=10):
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    try:
        images = {}
        counter = [0]
        toc = [t for t in (doc.get_toc() or []) if t[0] <= 2]
        chapters = []

        if len(toc) >= 2:
            for i, (_lvl, title, page) in enumerate(toc):
                start = max(page - 1, 0)
                end = (toc[i + 1][2] - 1) if i + 1 < len(toc) else doc.page_count
                text = _pdf_pages_text(doc, start, end, images, counter)
                if len(strip_image_markers(text)) >= 50 or IMG_RE.search(text):
                    chapters.append((title.strip() or f"Capítulo {i+1}", text))
        if not chapters:
            i = 0
            while i < doc.page_count:
                end = min(i + pages_per_chapter, doc.page_count)
                text = _pdf_pages_text(doc, i, end, images, counter)
                if len(strip_image_markers(text)) >= 50 or IMG_RE.search(text):
                    chapters.append((f"Páginas {i+1}–{end}", text))
                i += pages_per_chapter

        if not chapters:
            raise ValueError(
                "Não foi possível extrair texto do PDF (pode ser escaneado).")
        return chapters, images
    finally:
        doc.close()


def _pdf_pages_text(doc, start, end, images, counter):
    """Texto das páginas com imagens intercaladas na posição do fluxo."""
    parts = []
    for p in range(start, end):
        page = doc[p]
        d = page.get_text("dict")
        blocks = sorted(d.get("blocks", []),
                        key=lambda b: (b["bbox"][1], b["bbox"][0]))
        page_parts = []
        for b in blocks:
            if b.get("type") == 1:  # bloco de imagem
                data = b.get("image")
                w, h = b.get("width", 0), b.get("height", 0)
                if (not data or len(data) < _MIN_IMG_BYTES
                        or w < _MIN_IMG_PX or h < _MIN_IMG_PX):
                    continue
                counter[0] += 1
                ext = (b.get("ext") or "jpg").lower()
                mt = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                      "png": "image/png", "gif": "image/gif",
                      "webp": "image/webp"}.get(ext, "image/jpeg")
                images[counter[0]] = {"data": data, "ext": ext,
                                      "media_type": mt}
                page_parts.append(f"⟦IMG{counter[0]}⟧")
            elif b.get("type") == 0:  # bloco de texto
                lines = []
                for line in b.get("lines", []):
                    lines.append("".join(s.get("text", "")
                                         for s in line.get("spans", [])))
                t = "\n".join(lines).strip()
                if t:
                    page_parts.append(t)
        if page_parts:
            parts.append("\n".join(page_parts))
    text = "\n".join(parts)
    # junta linhas quebradas no meio de frases japonesas (não toca marcadores)
    text = re.sub(r"(?<![。！？」』⟧\n])\n(?!\n|⟦)", "", text)
    # marcadores sempre em parágrafo próprio
    text = re.sub(r"\s*(⟦IMG\d+⟧)\s*", r"\n\n\1\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------- TXT

def extract_txt(path):
    text = ""
    for enc in ("utf-8", "utf-8-sig", "shift_jis", "cp932", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                text = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    text = text.strip()
    if not text:
        raise ValueError("Arquivo de texto vazio.")

    # tenta dividir por marcadores comuns de capítulo
    pattern = re.compile(
        r"^(第[0-9０-９一二三四五六七八九十百]+[章話巻]\s*.*|Chapter\s+\d+.*|Capítulo\s+\d+.*)$",
        re.M,
    )
    marks = list(pattern.finditer(text))
    if len(marks) >= 2:
        chapters = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[m.end():end].strip()
            if len(body) >= 50:
                chapters.append((m.group(1).strip(), body))
        if chapters:
            return chapters
    return [("Texto completo", text)]
