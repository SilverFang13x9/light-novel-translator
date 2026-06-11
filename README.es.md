# Light Novel Translator (Ollama)

*Lee esto en [portugués](README.md) o en [inglés](README.en.md).*

Aplicación de escritorio para leer light novels (EPUB/PDF/TXT) en japonés,
inglés o español y traducirlas al portugués brasileño, inglés o español con un
LLM local vía Ollama o una API, con 3 niveles de "dinamización" (condensación
del texto).

> **Uso responsable y legalidad:** esta es una herramienta de traducción
> asistida para **uso personal, exclusivamente con contenido obtenido
> legalmente** — libros que compraste (ebooks sin DRM), obras publicadas
> gratuitamente por sus propios autores (p. ej. Syosetu, Kakuyomu) o de
> dominio público. **No uses este programa con copias piratas** descargadas de
> agregadores, scans o repositorios no autorizados: además de ilegal,
> perjudica directamente a los autores de las obras que amas. Ningún libro,
> traducción o archivo derivado (glosarios/memorias) se distribuye en este
> repositorio, y las traducciones generadas no deben redistribuirse — son para
> tu propia lectura. Apoya a los autores comprando las ediciones oficiales.

## Requisitos

- Windows, Linux o macOS con Python 3.10+ (https://python.org — en Windows,
  marca "Add to PATH")
- Un "motor" de traducción a tu elección (ver Instalación): **Ollama** para
  modelos locales, o una **clave de API** de un proveedor compatible con
  OpenAI
- Para modelos locales: cualquier PC con 8 GB de RAM ejecuta los pequeños (en
  CPU, más lento). Con GPU, mira la tabla de modelos — de 4 GB a 16 GB de
  VRAM. Para la API, el hardware no importa.

## Instalación

```bat
pip install -r requirements.txt
python main.py
```

Luego elige **cómo ejecutar el modelo** — ambas opciones son equivalentes
para la app, y puedes alternar en cualquier momento con el selector **Via:**

**Opción A — Modelo local (Ollama):** gratuito, privado y offline. Instala
Ollama (https://ollama.com), descarga un modelo de la tabla con
`ollama pull <modelo>` y deja el selector en **Via: Ollama**.

**Opción B — API:** calidad de modelos punteros sin depender de tu hardware —
a cambio de pago por uso y de enviar el texto al proveedor. En la app, cambia
a **Via: API** e introduce la URL y la clave (detalles más abajo).

**Opción C — Suscripción vía CLI:** si ya pagas Claude (Pro/Max), ChatGPT o
usas cuenta de Google, puedes usar la suscripción en vez de una clave: instala
el CLI oficial del proveedor e inicia sesión una vez (`claude` + /login,
`gemini`, o `codex login`); en la app, cambia a **Via: CLI** y elige el
proveedor. Aplican los límites/créditos de uso programático de tu suscripción.
Sin streaming: cada bloque llega de una vez.

## Modelos locales recomendados (Opción A)

Elige según la VRAM de tu GPU (o RAM, si vas a usar solo CPU):

| Hardware | Modelo | Tamaño | Qué esperar |
|---|---|---|---|
| Sin GPU / 8 GB RAM | `gemma3:4b` | ~3,3 GB | Funciona en casi cualquier PC. Traducción comprensible pero simplificada; usa el glosario para los nombres. Lento en CPU. |
| GPU 4 GB | `gemma3:4b` o `qwen3:4b` | ~3 GB | Igual que arriba, pero rápido. Bueno para probar la app. |
| GPU 6 GB | `qwen3:8b` | ~5,2 GB | Primer nivel con japonés decente. Buena puerta de entrada. |
| GPU 8 GB | `gemma3:12b` | ~8 GB | Prosa visiblemente mejor; multilingüe fuerte. Ajustado — cierra otras apps de GPU. |
| GPU 12 GB | `qwen3:14b` | ~10 GB | Gran equilibrio calidad/velocidad en japonés. |
| GPU 16 GB | `gemma3:27b-it-qat` | ~14 GB | **Tope de esta lista.** Cuantización QAT de Google: calidad de 27B casi sin pérdida, cabiendo en la VRAM. |

Todos los nombres son las etiquetas exactas de Ollama — basta
`ollama pull <modelo>` y pulsar ⟳ en la app. Todas vienen cuantizadas a
4 bits: las etiquetas estándar usan Q4_K_M y la `gemma3:27b-it-qat` usa QAT de
Google (cuantización aplicada durante el entrenamiento — misma compresión,
pérdida mucho menor).

Reglas generales: cuanto más pequeño el modelo, más importan el 📓 glosario y
el 🎓 aprendizaje con traducciones existentes; por debajo de 4B la traducción
de japonés se degrada demasiado; y un modelo mayor en Q4 casi siempre supera a
uno menor en Q8.

> **Atención:** los tamaños de la tabla son solo los pesos del modelo — la
> VRAM y la RAM no son exclusivas de él. El contexto consume ~1-2 GB más de
> VRAM, y el sistema y otros programas también ocupan memoria (navegador,
> Discord, juegos). Si tu modelo queda al límite, cierra los programas pesados
> antes de traducir — si no, el modelo se desborda a la RAM/disco y todo se
> vuelve mucho más lento.

## Usando una API (Opción B en detalle)

Cambia el selector **Via:** a "API" e introduce la URL base y la clave de
cualquier proveedor compatible con OpenAI (DeepSeek, OpenRouter, Gemini,
Groq...). Si el proveedor no lista modelos, escribe el nombre del modelo
directamente en la caja (p. ej. `deepseek-chat`). La configuración se guarda
en `api.json` **solo en tu equipo** — el archivo está en el `.gitignore`;
nunca lo subas a GitHub, contiene tu clave.

A considerar: las APIs cobran por uso (un volumen típico cuesta de céntimos a
unos pocos dólares), requieren internet, y el texto de la obra se envía al
proveedor — lee sus términos. Para uso 100% local y gratuito, quédate con
Ollama (Opción A).

## Uso

```bat
python main.py
```

1. **📖 Abrir livro** — selecciona un .epub, .pdf o .txt.
2. Elige **modelo**, **idioma de origen** (De: japonés/inglés/español),
   **idioma de destino** (Para: PT-BR/inglés/español) y **dinamización**:
   - **Completo** — traducción íntegra.
   - **Baja** — ~25% más corto; recorta descripciones redundantes, mantiene todos los diálogos y eventos.
   - **Media** — ~35-45% más corto; acorta también monólogos internos poco relevantes.
   - **Alta** — ~50-60% más corto; ignora pensamientos sin importancia para la trama.
3. **▶ Traduzir capítulo** o **▶▶ Traduzir tudo**. La traducción aparece en tiempo real; los capítulos listos se marcan en verde.
4. **💾 Salvar tradução** exporta a EPUB (predeterminado), .txt o .md.

Las traducciones se guardan en caché por combinación
capítulo+origen+destino+nivel.

**Ejecutable (.exe):** ejecuta `build.bat` para generar
`dist\LightNovelTranslator.exe` con PyInstaller — distribuye la app sin exigir
Python (Ollama sigue siendo necesario para la opción local).

**Pruebas:** `python -m unittest discover tests` ejecuta la suite completa sin
necesitar Ollama — usa clientes simulados.

## Funcionalidades

La interfaz está en portugués; las funciones principales:

**Dinamización:** el modelo condensa *durante* la traducción, reescribiendo
como prosa fluida más compacta. Corta grasa, no historia: eventos y diálogos
importantes siempre se conservan. Aviso honesto: en cualquier nivel existe el
riesgo de cortar algo que importe más adelante — en general solo mata los
falsos fusiles de Chéjov, los mil detalles de web novel que nunca disparan.
Para obras de misterio/foreshadowing pesado, usa Completo o Baja.

**Glosario (📓):** fija nombres y términos con `original = traducción`
(opcionalmente `| nota`, p. ej. el género del personaje). Se guarda junto al
libro y se recarga solo. **Importar…** mezcla otro glosario sin duplicar.

**Memoria de saga (🧠):** resumen de la historia (personajes, términos,
eventos, tono) inyectado como contexto y actualizado a cada capítulo. Para
volúmenes sueltos: **Importar cópia…** (copia) o **Vincular à saga…** (lee y
escribe en la memoria de la saga).

**Modo saga (📂):** traduce una carpeta entera volumen a volumen, encadenando
la memoria, guardando en `traduzidos/` y reanudando donde paró.

**Aprender (🎓 / 🎓📂):** dale un volumen original + su traducción existente
(o una carpeta con pares `vol01`/`vol01t`) y la app extrae el glosario y
construye la memoria a partir de ellos, con validación anti-alucinación.

**Imágenes preservadas:** las ilustraciones de EPUB/PDF se mantienen en su
posición vía marcadores ⟦IMGn⟧ y se incrustan en el EPUB exportado.

**Consistencia de nombres (🔍):** busca el mismo nombre escrito en órdenes
distintos en las traducciones y lo unifica a la forma mayoritaria/del glosario
en un clic. **Audio (🔊):** genera un MP3 del capítulo con voz neural gratuita
(edge-tts).

**Revisión (✨):** segunda pasada opcional del modelo para mejorar fluidez sin
cambiar contenido.

**Persistencia:** traducciones, posición de lectura y preferencias se guardan
automáticamente entre sesiones.

**Bilingüe sincronizado:** haz clic en cualquier párrafo y el párrafo
correspondiente del otro panel se resalta y desplaza a la vista — ideal para
estudiar japonés comparando con la traducción.

## Consejos

- Archivos Kindle (.mobi/.azw3 sin DRM) funcionan si
  [Calibre](https://calibre-ebook.com) está instalado (conversión automática).
- La app avisa en la barra de estado cuando hay versión nueva en GitHub.
- El editor de glosario tiene **Sugerir (IA)…**: el modelo lee la apertura y
  propone nombres — revisa las lecturas antes de guardar.
- Los PDF escaneados (imagen) no funcionan — hace falta texto seleccionable.
- Si la app dice que no encontró Ollama, ábrelo y pulsa ⟳.
- La calidad JA→EN suele ser algo superior a JA→ES/PT en modelos locales.

## Créditos

Este proyecto existe gracias a estas herramientas de código abierto:

- [Ollama](https://ollama.com) — ejecución local de LLMs
- [Gemma 3](https://ai.google.dev/gemma) (Google) y [Qwen 3](https://github.com/QwenLM/Qwen3) (Alibaba) — los modelos recomendados
- [Python](https://python.org) y Tkinter — lenguaje e interfaz gráfica
- [PyMuPDF](https://pymupdf.readthedocs.io) — extracción de texto de PDFs
- [EbookLib](https://github.com/aerkalov/ebooklib) — lectura de archivos EPUB
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) — procesamiento del HTML de los EPUB
- [Requests](https://requests.readthedocs.io) — comunicación con las APIs

Desarrollado con la asistencia de [Claude](https://claude.com) (Anthropic).
