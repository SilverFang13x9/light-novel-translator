# Light Novel Translator (Ollama)

*Read this in [English](README.en.md) · Léelo en [español](README.es.md).*

App desktop para ler light novels (EPUB/PDF/TXT) em japonês, inglês ou
espanhol, traduzi-las para Português (BR) ou Inglês com uma LLM local via
Ollama, com 3 níveis de "dinamização" (condensação do texto).

> **Uso responsável e legalidade:** esta é uma ferramenta de tradução
> assistida para **uso pessoal, exclusivamente com conteúdo obtido de forma
> legal** — livros que você comprou (ebooks sem DRM), obras publicadas
> gratuitamente pelos próprios autores (ex.: Syosetu, Kakuyomu) ou em domínio
> público. **Não use este programa com cópias piratas** baixadas de
> agregadores, scans ou repositórios não autorizados: além de ilegal,
> prejudica diretamente os autores das obras que você gosta. Nenhuma obra,
> tradução ou arquivo derivado (glossários/memórias) é distribuído neste
> repositório, e as traduções geradas não devem ser redistribuídas — são para
> a sua leitura. Apoie os autores comprando as edições oficiais.

## Requisitos

- Windows, Linux ou macOS com Python 3.10+ (https://python.org — no Windows,
  marque "Add to PATH")
- Um "motor" de tradução, à sua escolha (veja Instalação): **Ollama** para
  rodar modelos locais, ou uma **chave de API** de provedor compatível com
  OpenAI
- Para modelos locais: qualquer PC com 8 GB de RAM já roda os pequenos (na
  CPU, mais devagar). Com GPU, veja a tabela de modelos abaixo — de 4 GB até
  16 GB de VRAM. Para API, o hardware não importa.

## Instalação

```bat
pip install -r requirements.txt
python main.py
```

Depois escolha **como rodar o modelo** — as duas opções são equivalentes para
o app, e dá para alternar a qualquer momento no seletor **Via:**

**Opção A — Modelo local (Ollama):** gratuito, privado e offline. Instale o
Ollama (https://ollama.com), baixe um modelo da tabela abaixo com
`ollama pull <modelo>` e deixe o seletor em **Via: Ollama**.

**Opção B — API:** qualidade dos modelos de ponta, sem depender do seu
hardware — em troca de custo por uso e de enviar o texto ao provedor. No app,
mude para **Via: API** e informe a URL e a chave (detalhes na seção "Usando
uma API" abaixo).

**Opção C — Assinatura via CLI:** se você já assina Claude (Pro/Max), ChatGPT
ou usa conta Google, dá para usar a assinatura em vez de chave: instale o CLI
oficial do provedor e faça login uma vez (`claude` + /login, `gemini`, ou
`codex login`); no app, mude para **Via: CLI** e escolha o provedor. O texto
vai ao provedor como na Opção B, e os limites/créditos de uso programático da
sua assinatura se aplicam (no Claude, há um crédito mensal dedicado para isso
nos planos pagos). Sem streaming: cada bloco chega de uma vez.

## Modelos locais recomendados (Opção A — do PC modesto ao topo)

Escolha pela VRAM da sua GPU (ou RAM, se for rodar só na CPU):

| Hardware | Modelo | Tamanho | O que esperar |
|---|---|---|---|
| Sem GPU / 8 GB RAM | `gemma3:4b` | ~3,3 GB | Roda em quase qualquer PC. Tradução compreensível, mas simplificada; use o glossário para segurar os nomes. Lento na CPU. |
| GPU 4 GB | `gemma3:4b` ou `qwen3:4b` | ~3 GB | Igual acima, porém rápido. Bom para testar o app. |
| GPU 6 GB | `qwen3:8b` | ~5,2 GB | Primeiro nível com japonês decente. Boa porta de entrada. |
| GPU 8 GB | `gemma3:12b` | ~8 GB | Prosa visivelmente melhor; multilíngue forte. Fica justo — feche outros apps de GPU. |
| GPU 12 GB | `qwen3:14b` | ~10 GB | Ótimo equilíbrio qualidade/velocidade em japonês. |
| GPU 16 GB | `gemma3:27b-it-qat` | ~14 GB | **Topo desta lista.** Quantização QAT da Google: qualidade de 27B quase sem perda, cabendo na VRAM. |

Todos os nomes da tabela são as tags exatas do Ollama — basta
`ollama pull <modelo>` e clicar em ⟳ no app. Todas já vêm quantizadas em
4 bits, sem precisar especificar nada: as tags padrão usam Q4_K_M, e a
`gemma3:27b-it-qat` usa QAT da Google (quantização aplicada durante o
treinamento — mesma compressão, perda de qualidade bem menor).

Regras gerais: quanto menor o modelo, mais importante ficam o 📓 glossário e a
🎓 aprendizagem com traduções existentes (eles compensam parte da perda);
abaixo de 4B a tradução de japonês degrada demais — não recomendado; e um
modelo maior quantizado em Q4 quase sempre supera um menor em Q8.

> **Atenção:** os tamanhos da tabela são só os pesos do modelo — a VRAM e a
> RAM não são exclusivas dele. O contexto da tradução consome mais ~1-2 GB de
> VRAM, e o sistema e outros programas também ocupam memória (Windows usa
> ~0,5-1 GB de VRAM; navegador com aceleração de hardware, Discord e jogos
> podem consumir vários GB). Se o modelo escolhido fica no limite do seu
> hardware, feche os programas pesados antes de traduzir — caso contrário, o
> modelo transborda para a RAM/disco e a tradução fica bem mais lenta.

## Usando uma API (Opção B em detalhes)

Troque o seletor **Via:** para "API" e informe a URL base e a chave de
qualquer provedor compatível com OpenAI (DeepSeek, OpenRouter, Gemini,
Groq...). Se o provedor não listar os modelos, digite o nome do modelo direto
na caixa (ex.: `deepseek-chat`). A configuração fica salva em `api.json`
**somente no seu computador** — o arquivo está no `.gitignore`; nunca o suba
para o GitHub, pois contém sua chave.

Pontos a considerar: APIs cobram por uso (um volume típico custa de centavos a
poucos dólares, conforme o modelo), exigem internet, e o texto da obra é
enviado ao provedor — leia os termos dele. Para uso 100% local e gratuito,
fique no Ollama (Opção A).

## Uso

```bat
python main.py
```

1. **📖 Abrir livro** — selecione um .epub, .pdf ou .txt.
2. Escolha **modelo**, **idioma de origem** (De: Japonês/Inglês/Espanhol),
   **idioma de destino** (Para: PT-BR/Inglês) e **dinamização**:
   - **Completo** — tradução integral.
   - **Dinamização baixa** — ~25% mais curto; corta descrições redundantes, mantém todos os diálogos e eventos.
   - **Dinamização média** — ~35-45% mais curto; encurta também monólogos internos pouco relevantes, mantendo diálogos e pensamentos que revelam personagem.
   - **Dinamização alta** — ~50-60% mais curto; ignora pensamentos/monólogos sem importância para a trama.
3. **▶ Traduzir capítulo** ou **▶▶ Traduzir tudo**. A tradução aparece em tempo real no painel direito; capítulos prontos ficam verdes na lista.
4. **💾 Salvar tradução** exporta tudo para .txt/.md.

Traduções ficam em cache por combinação capítulo+origem+destino+nível — trocar o nível e traduzir de novo gera outra versão sem perder a anterior (na mesma sessão).

**Executável (.exe):** rode `build.bat` para gerar
`dist\LightNovelTranslator.exe` via PyInstaller — distribua o app sem exigir
Python instalado (o Ollama continua necessário).

**Testes:** `python -m unittest discover tests` roda a suíte completa, sem
precisar de Ollama — usa clientes simulados.

## Funcionalidades

**Dinamização:** é o recurso de leitura dinâmica do app — em vez de traduzir e
depois resumir, o modelo condensa *durante* a tradução, reescrevendo o texto
como prosa fluida mais enxuta. A ideia é cortar gordura, não história: em
qualquer nível, todos os eventos da trama e os diálogos importantes são
preservados; o que sai são descrições prolixas, narração repetitiva e
monólogos internos que não acrescentam nada — aquele padrão de web novel em
que o protagonista pondera a mesma coisa por três parágrafos.

Os níveis controlam a agressividade do corte:

- **Completo** — tradução integral, nada é cortado. Recomendado para a
  primeira leitura de obras que você quer saborear.
- **Baixa (~25% mais curto)** — só aparas: descrições redundantes e repetições
  encolhem; todos os diálogos, eventos e momentos de personagem ficam.
- **Média (~35-45%)** — também encurta monólogos internos pouco relevantes,
  mas mantém pensamentos que revelam personalidade ou afetam a história.
- **Alta (~50-60%)** — ignora pensamentos e divagações sem importância para a
  trama e resume descrições longas em uma frase. Ideal para arcos arrastados,
  releituras ou para "colocar a leitura em dia" numa saga longa.

Um aviso honesto: em **qualquer** nível de dinamização existe o risco de
cortar algo que pareça irrelevante agora mas importe mais adiante — o modelo
decide pelo contexto do capítulo, sem saber o que o autor plantou para o
futuro. No geral, porém, ela só mata as falsas armas de Chekhov: as web novels
são cheias de detalhes que nunca disparam, e são esses que caem primeiro. Se a
obra é famosa por amarrar pontas (mistério, foreshadowing pesado), prefira
Completo ou Baixa.

Como cada nível é uma *reescrita* feita pelo modelo, o resultado varia um
pouco a cada tradução, e modelos maiores julgam melhor o que pode ser cortado
— em modelos pequenos (4-8B), prefira Baixa, pois o critério deles é menos
confiável. O cache guarda cada nível separadamente: dá para traduzir o mesmo
capítulo em Completo e em Alta e comparar, sem perder nenhuma das versões.

**Glossário (📓):** para nomes e termos saírem sempre certos (a leitura de
kanji de nomes é ambígua — 月森アヤメ pode virar "Tsukimori Ayame", "Getsumori
Ayame" ou outra leitura, dependendo do palpite do modelo), preencha o
glossário com `original = tradução`, um por linha. Ele é salvo como
`<livro>.glossario.txt` ao lado do arquivo do livro e recarregado
automaticamente quando você abre o livro de novo. O botão **Importar…** dentro
do editor mescla as entradas de outro `.glossario.txt` (ex.: o
`saga.glossario.txt` gerado pelo 🎓📂) no glossário do livro atual, sem
duplicar nem sobrescrever o que você já tem. E o **Sugerir (IA)…** faz o
modelo ler a abertura da obra e propor entradas (nomes detectados + leitura
provável) — só nomes que existem no texto entram, mas a leitura proposta é um
palpite: revise antes de Salvar.

**Estilo:** a tradução PT-BR segue o padrão das traduções de comunidade:
diálogos com travessão (—), registro coloquial preservando o humor/sarcasmo do
narrador, termos otaku mantidos (galge, eroge, senpai...) e onomatopeias
expressivas.

**Modo saga (📂 Saga…):** selecione uma pasta com os volumes da saga
(.epub/.pdf/.txt — a ordem é alfabética, então nomeie como `vol01`, `vol02`...).
O app traduz volume por volume, encadeando a memória entre eles, e salva cada
um em `traduzidos/<volume>_traduzido.txt` dentro da pasta. A memória e o
glossário da saga ficam na raiz da pasta (`saga.memoria.txt` /
`saga.glossario.txt`). Ao abrir a saga, qualquer outro `.glossario.txt` na
pasta (de volumes individuais ou do 🎓) é fundido automaticamente no glossário
da saga — entradas já existentes nele têm prioridade e não são sobrescritas. Se você parar no meio (■), o volume em andamento é salvo
como `_parcial` e, ao rodar de novo, volumes já concluídos são pulados —
retomada automática.

**Aprender com tradução existente (🎓):** se a obra já tem alguns volumes
traduzidos (oficial ou de comunidade), use-os para ensinar o app: clique em
🎓 Aprender…, selecione o volume original e depois o mesmo volume traduzido.
O modelo compara trechos correspondentes dos dois e extrai os pares
`nome original = forma usada pelo tradutor` direto para o glossário — cada par
é validado contra os dois textos (só entra se o original existe no texto-fonte
e a tradução existe no texto traduzido), evitando invenções. Repita para cada
volume traduzido que você tiver (vol. 1, 2, 3...); entradas repetidas não são
duplicadas. O 🎓 também gera/atualiza a 🧠 memória da saga lendo o volume
traduzido — assim os volumes inéditos começam com o contexto da história já
carregado. Depois revise em 📓 Glossário e 🧠 Memória e traduza os volumes
inéditos com tudo consolidado.

**Aprender saga (🎓📂):** a versão em lote do 🎓. Monte uma pasta com os
volumes originais e suas traduções existentes, marcando a tradução com o
sufixo `t` no nome: `vol01.txt` + `vol01t.txt`, `vol02.epub` + `vol02t.txt`
(`vol02_t` também funciona, e as extensões podem ser diferentes). O app pareia
os arquivos, mostra os pares para confirmação e processa volume a volume, em
ordem: extrai o glossário de cada par (sem duplicar entradas) e constrói a
memória encadeada lendo as traduções. Tudo é salvo em `saga.glossario.txt` e
`saga.memoria.txt` na raiz da pasta. Depois, basta colocar os volumes inéditos
na mesma pasta e usar o 📂 Saga… — volumes que têm par `t` são pulados na
tradução automaticamente, e os inéditos herdam o glossário e a memória
aprendidos.

Ambas as ferramentas de pasta lembram o que já fizeram: a tradução pula
volumes que já têm arquivo em `traduzidos/`, e o aprendizado registra os pares
processados em `saga.aprendido.txt` — se você adicionar um `vol04`/`vol04t`
depois, só ele será lido; os volumes 1-3 não são reprocessados (o glossário e
a memória deles já estão salvos). Para reaprender tudo do zero, apague o
`saga.aprendido.txt`.

**Memória da saga (🧠):** o app mantém um resumo da história (personagens,
termos, eventos, tom) que é injetado como contexto em toda tradução e
atualizado automaticamente pelo modelo a cada capítulo concluído (desligue no
☑ auto se quiser). Fica salvo em `<livro>.memoria.txt` ao lado do livro. Para
usar o contexto de uma saga num volume avulso, abra o volume e use, em
🧠 Memória, **Importar cópia…** (copia o resumo para o livro atual, sem mexer
no arquivo de origem) ou **Vincular à saga…** (passa a ler E gravar no
`.memoria.txt` da saga, acumulando o contexto nela). Você também pode editar
o resumo manualmente.

**Nomes de personagens:** nunca são traduzidos, mas sempre saem em alfabeto
latino (romanização Hepburn, ex.: 山田太郎 → Tarou Yamada). Se a tradução ainda
vier com grafia japonesa, o app detecta e roda automaticamente uma segunda
passada de correção no capítulo.

**Consistência de nomes (🔍):** varre as traduções prontas procurando o mesmo
nome grafado em ordens diferentes ("Ayame Tsukimori" vs "Tsukimori Ayame"),
mostra as ocorrências e unifica para a forma majoritária/do glossário em um
clique — direto no cache, sem retraduzir.

**Áudio (🔊):** gera um MP3 do capítulo traduzido com voz neural gratuita
(edge-tts, requer internet), no idioma de destino — sua light novel vira
audiolivro.

**Revisão (✨):** checkbox opcional que faz uma segunda passada do modelo na
tradução pronta, melhorando fluidez e naturalidade sem mudar conteúdo (blocos
em que a revisão encurta/alonga demais são descartados, mantendo o original).
Dobra o tempo por capítulo — vale com modelos médios.

**Persistência:** as traduções de cada livro ficam salvas automaticamente em
`<livro>.cache.json` ao lado do arquivo — pode fechar o app e retomar depois,
inclusive a posição de leitura (o capítulo onde você estava reabre sozinho).
Suas escolhas de modelo, idiomas, nível e fonte também são lembradas entre
sessões (`settings.json`).

**Exportar:** 💾 agora salva em **EPUB** (padrão — capítulos preservados,
legível em Kindle/celular/leitores), além de .txt e .md.

**Imagens preservadas:** se o EPUB ou PDF original tem ilustrações, o app
marca a posição de cada uma no texto (⟦IMGn⟧, visível nos painéis), o modelo
preserva os marcadores na tradução (com rede de segurança: marcador perdido é
restaurado ao fim do trecho) e a exportação EPUB embute as imagens originais
nos lugares certos. Para PDFs, a saída com imagens também é EPUB — reconstruir
o layout exato de um PDF com texto traduzido não é viável; o EPUB mantém as
ilustrações na posição correta do fluxo da leitura. Imagens minúsculas
(ícones/divisores) são ignoradas; na exportação .txt viram "[ilustração]".

**Modo leitura (👁):** oculta o painel do original para ler a tradução em
tela cheia; clique de novo para voltar.

**Bilíngue sincronizado:** com os dois painéis visíveis, clique em qualquer
parágrafo (da tradução ou do original) e o parágrafo correspondente do outro
lado é destacado e rolado até a vista — ótimo para estudar japonês comparando
com a tradução. No modo Completo o pareamento é exato (a tradução espelha a
estrutura); com dinamização ele é proporcional (aproximado, já que parágrafos
foram fundidos).

## Dicas

- Arquivos Kindle (.mobi/.azw3 sem DRM) funcionam se o
  [Calibre](https://calibre-ebook.com) estiver instalado — a conversão para
  EPUB é automática e invisível.
- O app avisa discretamente na barra de status quando há versão nova no
  GitHub (via releases; falhas de rede são silenciosas).
- PDFs escaneados (imagem) não funcionam — é preciso PDF com texto selecionável.
- Se o app disser que o Ollama não foi encontrado, abra o Ollama e clique em ⟳.
- A qualidade JP→EN costuma ser levemente superior a JP→PT-BR nos modelos locais.

## Créditos

Este projeto existe graças a estas ferramentas de código aberto:

- [Ollama](https://ollama.com) — execução local de LLMs, o motor de tudo
- [Gemma 3](https://ai.google.dev/gemma) (Google) e [Qwen 3](https://github.com/QwenLM/Qwen3) (Alibaba) — os modelos de tradução recomendados
- [Python](https://python.org) e Tkinter — linguagem e interface gráfica
- [PyMuPDF](https://pymupdf.readthedocs.io) — extração de texto de PDFs
- [EbookLib](https://github.com/aerkalov/ebooklib) — leitura de arquivos EPUB
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) — processamento do HTML dos EPUBs
- [Requests](https://requests.readthedocs.io) — comunicação com a API do Ollama

Desenvolvido com o auxílio do [Claude](https://claude.com) (Anthropic).
