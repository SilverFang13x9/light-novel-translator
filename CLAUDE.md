# CLAUDE.md — Contexto do projeto para assistentes de IA

> Documento de handoff escrito pelo Claude Fable 5 para futuras sessões
> (Claude Sonnet/Opus ou outro assistente). Leia ANTES de mexer no código.
> Última atualização: 10/junho/2026 (inclui backend API, importação de
> glossário/memória e correção do tema das comboboxes).

## O que é este projeto

**Light Novel Translator** — app desktop (Python + Tkinter, arquivo único de
interface) que traduz light novels japonesas (e EN/ES) para PT-BR ou inglês
usando LLM local via Ollama OU API compatível com OpenAI. Criado em par com o
autor (leitor de light novels; ver LICENSE), em hardware de referência:
**GPU 16GB VRAM + 32GB RAM, Windows**.

Objetivo central: tradução com cara de **tradução de fã brasileira** (fansub),
não de máquina — incluindo leitura "dinamizada" (condensada) opcional.

## Arquitetura (3 arquivos, ~1200 linhas)

### `extractor.py` — entrada de livros
- `extract_book(path)` → lista de `(titulo, texto)` por capítulo.
- EPUB: ebooklib + BeautifulSoup; remove `<rt>` (furigana); título de h1-h3;
  evita duplicar texto de divs aninhadas; filtra itens <50 chars (capas etc.).
- PDF: PyMuPDF (`fitz`); usa o sumário (TOC níveis 1-2) se houver ≥2 entradas,
  senão agrupa de 10 em 10 páginas; junta linhas quebradas no meio de frases
  japonesas (regex que olha pontuação 。！？」).
- TXT: tenta UTF-8 → Shift-JIS → CP932 → Latin-1; divide capítulos por regex
  `第N章/話/巻`, `Chapter N`, `Capítulo N`; senão, capítulo único.

### `translator.py` — todo o trabalho com o modelo
Classes/funções principais (em ordem no arquivo):
- `SOURCE_LANGS` (Japonês/Inglês/Espanhol), `LANGS` (PT-BR/Inglês/Espanhol),
  `LEVELS` (Completo, Dinamização baixa/média/alta). Espanhol como destino
  tem ramo de estilo próprio (raya — para diálogo, ¿¡), tabela _INTERJ_ES e
  código de idioma "es" no EPUB. READMEs em PT/EN/ES com links cruzados.
- `build_system_prompt(lang_label, level, source_label, glossary, memory)` —
  monta o system prompt. Componentes, nesta ordem:
  1. Persona: "fan translator producing high-quality community translations".
  2. STYLE (se PT-BR): coloquial, sarcasmo preservado, **diálogos com
     travessão —** (padrão BR, não aspas), termos otaku não traduzidos
     (galge, eroge, senpai...), onomatopeias expressivas em romaji
     (ペラ……ペラ…… → Flip… Flip…). Exemplos few-shot embutidos com obra
     FICTÍCIA (月森アヤメ — NUNCA usar obras reais em exemplos, pedido do
     usuário).
  3. CRITICAL RULE: saída com ZERO kanji/kana; Hepburn SÓ para nomes próprios;
     interjeições têm tabela de exemplos por idioma alvo (ん？→Hum?/Hm?) —
     isto existe porque modelos romanizavam ん？ como "n?" (bug real).
  4. STRUCTURE RULE: espelhar parágrafos com linha em branco (Completo) ou
     permitir fusão ao condensar — existe porque o modelo fundia tudo num
     blocão (bug real).
  5. GLOSSARY (se houver): pares `original = tradução` obrigatórios.
  6. STORY CONTEXT (se houver): memória da saga.
  7. Instrução do nível de dinamização + "Output ONLY the translation".
- `sanitize_source(text)` — colapsa runs de pontuação repetida (………×300 → ×6).
  Existe porque runs gigantes causavam **loop de repetição degenerativo**
  (bug real: modelo repetiu a mesma frase 90×).
- `chunk_text(text, max_chars=1800)` — divide por parágrafos (separados com
  `\n\n` para o modelo VER a estrutura), corta frases por 。！？」 e ". ".
- `OllamaClient` — `/api/chat` streaming; `num_ctx=16384` (8192 estourava com
  glossário+memória e o Ollama TRUNCA SILENCIOSAMENTE o início do prompt);
  `repeat_penalty=1.1, repeat_last_n=256` (anti-loop); `think: false` com
  retry sem o parâmetro se o modelo não suportar (qwen3 tem modo thinking).
- `CliClient` — backend via CLI oficial autenticado por ASSINATURA (sem
  chave): claude -p / gemini / codex exec por subprocesso (stdin, timeout
  600s, sem streaming — resposta inteira num yield). PROVIDERS dict com
  bin/args/model_flag/models; shutil.which valida PATH. Via: CLI na UI;
  modelo vazio = padrão do CLI (guardas "if not model" têm exceção p/ CLI).
- `ApiClient` — backend alternativo: qualquer API compatível com OpenAI
  (DeepSeek/OpenRouter/Gemini/Groq). MESMA interface do OllamaClient
  (is_up/list_models/chat_stream), então o resto do app não sabe qual backend
  está em uso. SSE (`data: {...}`/`[DONE]`), Bearer auth, num_ctx ignorado.
  Testado contra servidor HTTP fake no sandbox.
- `strip_thinking()` — remove `<think>...</think>`.
- `JP_SCRIPT_RE`/`has_japanese_script()` — detecta kanji/hiragana/katakana
  (inclui katakana half-width).
- `fix_japanese_leftovers()` — 2ª passada LLM se sobrou grafia japonesa;
  SÓ aceita a correção se: sem JP script, ≥50% do tamanho, e ≥60% dos
  parágrafos originais (proteção contra correção destrutiva).
- `_INTERJ_PT/_INTERJ_EN` + `postprocess_translation()` — pós-processamento
  DETERMINÍSTICO (não confiar só em prompt!): remove vazamento de marcadores
  internos (`_LEAK_RE` pega "[Final do contexto]" etc. — o modelo traduzia o
  marcador de contexto, bug real); `_dedupe_lines()` colapsa linhas idênticas
  consecutivas a máx. 2 (anti-loop); converte romaji-interjeição entre aspas
  (「n?」→"Hum?") via tabela; converte 「」『』 para aspas ocidentais.
- `update_memory()` — atualiza a "story bible" (≤~1500 palavras) com o
  capítulo recém-traduzido; trunca capítulo >12k chars (começo+fim); rejeita
  resposta <30% do tamanho da memória atual.
- `extract_glossary_pairs()` — extrai pares nome=tradução de trecho fonte +
  trecho traduzido. Limpa enfeites de modelo (numeração, **negrito**, crases,
  aspas). VALIDAÇÃO ANTI-ALUCINAÇÃO: original tem que existir no trecho
  fonte (a validação da tradução fica em learn_glossary).
- `learn_glossary()` — amostragem proporcional GLOBAL (janelas na mesma
  fração do livro fonte/traduzido; janela da tradução escala
  `max(seg*2.2, len/n*1.5)` cap 9000); valida tradução contra o LIVRO
  TRADUZIDO INTEIRO normalizado (`_norm` = espaços+lowercase) — janela só não
  bastava (bug real: rejeitava tudo).
- `build_memory_from_translation()` — gera memória lendo volume já traduzido
  em ≤5 fatias de 9k chars sequenciais.
- `translate_chapter()` — orquestra: sanitize → chunk → para cada chunk:
  contexto dos 600 chars finais da tradução anterior (com marcador
  "[Previous translated context...]") → stream → strip_thinking →
  fix_japanese_leftovers (se preciso) → postprocess → acumula.

### `main.py` — interface Tkinter (tema preto #000000 + creme #FDFBD4)
Paleta em constantes no topo: BG/PANEL/FG/ACCENT/MUTED/OK_COLOR — mudar tema
= mudar só ali. Botões flat invertem p/ creme no hover; seleção = creme com
texto preto em listas/textos/comboboxes.
- Toolbar compactada em menus (Menubutton): 📖 Abrir ▾ (livro/saga) /
  ⚙ Motor ▾ (radio Ollama|API|CLI + cascata Modelo + Digitar modelo… + ⟳) /
  🌐 Idiomas ▾ (cascatas De/Para) / Dinamização / ▶ / ▶▶ / ■ / 💾 /
  🎓 Aprender ▾ (par avulso / saga) / 🛠 Ferramentas ▾ (📓 glossário,
  🧠 memória, checkbutton memória automática, 🔍 nomes, 🔊 áudio) /
  ✨ revisão / 👁 Leitura / A−A+.
  A combobox de modelo NÃO existe mais — lista vem de _set_model_choices()
  (radiobuttons no submenu); digitação manual via _type_model (simpledialog).
- **Backend**: `switch_backend()` troca self.client entre OllamaClient e
  ApiClient. `configure_api()` = diálogo URL base + chave, persistido em
  `api.json` ao lado do main.py (no .gitignore — CONTÉM SEGREDO). Se a API
  não lista modelos, a combobox de modelo vira state="normal" (digitável).
- **Tema dos combobox**: no Windows, estado "readonly" ignora
  style.configure — precisa de style.map(fieldbackground/foreground por
  estado) + option_add("*TCombobox*Listbox...") para a lista suspensa
  (bug real: caixas brancas com letra clara, ilegíveis).
- Painéis: lista de capítulos | original | tradução (streaming ao vivo).
- Threading: worker em `threading.Thread`, comunicação UI via `queue.Queue`
  + `after(80, _poll_queue)`. Tipos de msg: models, models_err, start_chapter,
  piece, done_chapter, load_volume, select_chapter, memory, glossary_set,
  status, error, finished.
- Cache: `self.translations[(idx, origem, destino, nível)]` — versões
  coexistem.
- **Arquivos satélites** (persistência, todos UTF-8 ao lado do livro/pasta):
  - `<livro>.glossario.txt` — pares `original = tradução` (1/linha).
  - `<livro>.memoria.txt` — story bible.
  - Saga: `saga.glossario.txt`, `saga.memoria.txt`, `saga.aprendido.txt`
    (basenames dos pares já aprendidos), `traduzidos/<vol>_traduzido.txt`.
- **Modo saga (📂)**: pasta com volumes em ordem alfabética; pula volumes com
  saída existente em `traduzidos/` (retomada); salva `_parcial` se
  interrompido; funde TODOS os `.glossario.txt` da pasta no da saga
  (`_merge_folder_glossaries`, saga tem prioridade, nunca sobrescreve); pula
  volumes que têm par `t` (tradução de comunidade presente).
- **🎓 Aprender**: par original+traduzido → glossário + memória.
- **Importação de contexto** (volume avulso herdando saga): editor 📓 tem
  "Importar…" (mescla outro .glossario.txt sem duplicar/sobrescrever, salva
  no glossário do livro atual); editor 🧠 tem "Importar cópia…" (copia o
  resumo sem mudar memory_path) e "Vincular à saga…" (repointa memory_path —
  passa a ler E GRAVAR no .memoria.txt da saga). Regra: mesma história em
  andamento → vincular; spin-off/teste → copiar.
- **🎓📂 Aprender saga**: pasta com `vol01`+`vol01t` (sufixo t = traduzido;
  aceita `_t`, `-t`, case-insensitive, extensões diferentes;
  `_pair_learning_files`); processa em ordem, acumula glossário sem duplicar,
  encadeia memória; registra progresso em `saga.aprendido.txt`.

## Decisões de design e PORQUÊS (não regredir!)

1. **Pós-processamento determinístico > prompt**: prompts não bastam em
   modelos 14B. Toda garantia crítica (interjeições, dedupe, vazamentos,
   aspas) tem código determinístico de backup.
2. **Validação anti-alucinação no 🎓**: par só entra se original ∈ fonte E
   tradução ∈ livro traduzido (normalizado). Sem isso o glossário enche de
   invenção.
3. **Proteções de "não piorar"**: fix_japanese_leftovers e update_memory
   rejeitam respostas destrutivas e mantêm a versão anterior. Tradução nunca
   aborta por falha de memória/correção (try/except com pass).
4. **Estilo fansub PT-BR**: foi calibrado comparando uma tradução de
   comunidade real com a saída da IA (usuário forneceu os textos). Traços:
   travessão, coloquial, jargão otaku, onomatopeia, nomes via glossário.
5. **Nomes**: leitura de kanji é ambígua — glossário é a ÚNICA solução
   confiável; prompt sozinho gera erros (caso real observado: modelo
   alucinou outra leitura para o nome em kanji do protagonista).
6. **Exemplos no código/README usam obra fictícia** (月森アヤメ/星霜剣記) —
   o usuário pediu para não citar obras reais.
7. **Licença/legal**: MIT, em nome do autor (ver LICENSE). README tem
   aviso forte: só conteúdo legal, sem pirataria, sem redistribuir traduções.
   `.gitignore` bloqueia livros/glossários/memórias/traduzidos/api.json
   (derivados de obras protegidas e segredos NÃO vão ao GitHub).
8. **README bilíngue**: README.md (PT) + README.en.md (EN) com links
   cruzados no topo — manter os DOIS sincronizados a cada mudança. Estrutura:
   Requisitos → Instalação → Modelos (tabela por VRAM + aviso de que
   VRAM/RAM são compartilhadas com outros processos) → API opcional → Uso →
   Funcionalidades (Dinamização explicada em detalhe, incl. nota das "falsas
   armas de Chekhov") → Dicas → Créditos.

## Modelos recomendados (junho/2026)

- Padrão: `qwen3:14b` (~10GB). Topo p/ 16GB: `gemma3:27b-it-qat` (~14GB, QAT
  da Google — qualidade quase sem perda). Escada completa no README.
- Tags padrão do Ollama = Q4_K_M; a `-it-qat` é q4_0 com QAT.
- Regra: maior em Q4 > menor em Q8. Nunca Q3/Q2 (nomes/kanji degradam).

## Bugs históricos já corrigidos (regressões a vigiar)

| Sintoma | Causa | Correção |
|---|---|---|
| 「ん？」 → "n?" | regra de romanização ampla demais | Hepburn só p/ nomes + tabela de interjeições + pós-proc |
| Parágrafos fundidos em blocão | chunks com \n simples entre parágrafos | \n\n nos chunks + STRUCTURE RULE + rejeição no fix pass |
| Frase repetida 90× + "[Final do contexto]" na saída | run de ……… no fonte + marcador traduzido | sanitize_source + repeat_penalty + _dedupe_lines + _LEAK_RE |
| 🎓 sem resultados | validação rígida (formatação de modelo, janela desalinhada) | limpeza de enfeites + validação contra livro inteiro normalizado |
| Nome de protagonista alucinado | leitura de kanji ambígua | glossário + 🎓 |
| Comboboxes brancas/ilegíveis no Windows | estado readonly ignora style.configure | style.map por estado + option_add p/ Listbox interna |

## Adições da última leva (jun/2026, fim da sessão Fable 5)

- `review_translation()` em translator.py: passada ✨ opcional de revisão por
  blocos (3500 chars), com rejeição de blocos destrutivos (0.7-1.4x tamanho +
  contagem de parágrafos). Checkbox "✨ revisão" integrado aos dois workers.
- Glossário aceita notas: `original = tradução | nota` (prompt instrui a usar
  e nunca exibir).
- Persistência: `<livro>.cache.json` (todas as traduções + capítulo atual,
  salvo a cada done_chapter e no fechar); `settings.json` (modelo, idiomas,
  nível, fonte, checkboxes). _on_close() salva tudo.
- 💾 exporta EPUB (default) via `_export_epub()` (ebooklib: EpubHtml por
  capítulo, toc/spine/nav) — NUNCA foi testado de verdade (ebooklib não
  instala no sandbox): primeira coisa a validar com o usuário.
- 👁 Modo leitura: toggle que esconde o painel do original
  (PanedWindow.forget/add).
- `build.bat` (PyInstaller --onefile --windowed); build/dist/spec no
  .gitignore, junto com settings.json e *.cache.json.
- `tests/` formalizada: 20 testes unittest (translator + extractor txt) —
  `python -m unittest discover tests`, sem rede.

- Imagens preservadas: extractor agora tem `extract_book_images()` →
  (capítulos com marcadores ⟦IMGn⟧, dict de imagens); `extract_book()`
  continua sem marcadores (usado por saga/🎓 — não poluir aprendizado).
  EPUB: imagens via ITEM_IMAGE resolvidas por basename; páginas só-imagem
  viram "Ilustração N". PDF: `get_text("dict")`, blocos tipo 1 = imagem na
  ordem do layout (filtro: <4KB ou <64px = decoração, ignora). Prompt tem
  regra IMAGE MARKERS; `restore_missing_markers()` re-anexa marcador que o
  modelo perder. `_export_epub` embute como EpubItem + <img> no lugar do
  marcador; .txt vira "[ilustração]". PDF com imagens exporta EPUB (layout
  de PDF é irrecuperável). Extração EPUB/PDF de imagens NÃO testada no
  sandbox (libs indisponíveis) — validar com livro real.

- Jun/2026 (fim de sessão): 🔍 consistência de nomes
  (find_name_inconsistencies: glossário + bigramas capitalizados nas duas
  ordens, maioria vence; apply_name_mapping no cache) e 🔊 TTS via edge-tts
  (TTS_VOICES por idioma alvo; import guardado — dependência em
  requirements). Tradução paralela foi implementada e DESIMPLEMENTADA a
  pedido do usuário: só beneficiava API/CLI e o foco do app é modelo local
  (além de conflitar com o encadeamento da memória). Não reintroduzir sem
  pedido explícito.

- Bilíngue sincronizado: clique em qualquer painel destaca (tag "sync",
  bg #34301a) e rola até o parágrafo equivalente no outro.
  _paragraph_spans conta por LINHA NÃO-VAZIA (não por \n\n!) — é como o
  chunk_text divide o fonte para o modelo; .txt de web novel tem linhas em
  branco múltiplas que criavam unidades vazias e desalinhavam tudo (bug
  real: parágrafo caía no anterior). _map_paragraph: 1:1 quando contagens
  iguais; proporcional quando dinamização fundiu. Painel do original tem o
  TÍTULO como 1ª unidade (skip compensa; clique no título é ignorado).
  Opera sobre o conteúdo exibido nos widgets (robusto a parciais).

- suggest_glossary(): IA lê abertura (6k chars) e propõe entradas — original
  validado contra o texto, leitura proposta é PALPITE (vai p/ revisão no
  editor 📓, botão "Sugerir (IA)…"; resultado via fila "glossary_suggest"
  com self._gloss_txt + winfo_exists). MOBI/AZW3: convert_kindle_to_epub()
  no extractor via ebook-convert do Calibre (which + hints de path Windows;
  erro orienta instalar). Update check: APP_VERSION + version_newer()
  (tuplas de ints) contra releases/latest do GitHub_REPO, silencioso em
  falha, aviso só na status bar. Lembrete: criar releases com tag vX.Y.Z no
  GitHub e subir APP_VERSION a cada release, senão a checagem nunca avisa.

## Ideias discutidas e NÃO implementadas (backlog)

- ~~Backend via API~~ — IMPLEMENTADO: `ApiClient` em translator.py
  (OpenAI-compatible, SSE), seletor "Via:" na toolbar, diálogo de URL/chave,
  config persistida em `api.json` (gitignored — contém segredo!). Quando a
  API não lista modelos, a combobox de modelo fica editável.
- Busca de nomes em wikis (Fandom) para semear glossário — decidido que
  glossário manual + 🎓 bastam; internet só agregaria nesse ponto.
- Fontes adaptativas para Linux (DejaVu) — funciona sem, cosmético.

## Ambiente de desenvolvimento (notas para o assistente)

- Comunique mudanças em PT-BR claro, sem jargão não explicado, e de forma
  concisa — o projeto é mantido por entusiasta, não por equipe de devs.
- Testes: o sandbox Linux do Cowork NÃO tem ebooklib/pymupdf instaláveis
  (proxy bloqueia pip) e o espelho de arquivos às vezes TRUNCA arquivos
  grandes — valide compilação/funções copiando o código para /tmp e
  reconstruindo o final conhecido se necessário. Os arquivos reais no Windows
  do usuário são a fonte da verdade (Write/Edit confirmam sucesso).
- Sempre testar com cliente fake (classe com chat_stream que faz yield) —
  todo o pipeline é testável sem Ollama real.
- Arquivos de teste do usuário (upload): capítulo 1 de uma obra em JP
  (Livro.txt), tradução de comunidade e tradução de IA — usados para calibrar
  estilo e testar o 🎓. Não redistribuir.
