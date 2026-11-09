

from pathlib import Path
from html import escape
import json
import re
import unicodedata
from urllib.parse import quote, urlsplit, urlunsplit

import markdown
import yaml


# CARPETAS DEL PROYECTO

BASE = Path(__file__).resolve().parent.parent
BLOG = BASE / "blog"
HISTORIAS = BLOG / "historias"
PORTADA = BLOG / "index.html"
SALIDA = BLOG / "cumbres"

MARCADOR_INICIO = "<!-- HISTORIAS_GENERADAS_INICIO -->"
MARCADOR_FIN = "<!-- HISTORIAS_GENERADAS_FIN -->"


def texto_seguro(valor):
    return escape(str(valor or ""), quote=True)


def crear_slug(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(
        letra for letra in texto
        if not unicodedata.combining(letra)
    )
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto)
    return texto.strip("-") or "montana"


def leer_historia(archivo):
    contenido = archivo.read_text(encoding="utf-8")

    if not contenido.startswith("---"):
        return None

    partes = re.split(
        r"^---\s*$",
        contenido,
        maxsplit=2,
        flags=re.MULTILINE
    )

    if len(partes) < 3:
        return None

    datos = yaml.safe_load(partes[1]) or {}

    if not isinstance(datos, dict):
        return None

    # Solo se publican historias aprobadas.
    if str(datos.get("estado", "")).strip().lower() != "publicado":
        return None

    titulo = str(datos.get("title", "")).strip()

    try:
        numero = int(datos.get("numero"))
    except (TypeError, ValueError):
        raise ValueError(
            f"Numero de cumbre incorrecto: {archivo.name}"
        )

    if not titulo or not 1 <= numero <= 100:
        raise ValueError(
            f"Titulo o numero incorrecto: {archivo.name}"
        )

    fecha = str(datos.get("fecha", "") or "")
    imagen = str(datos.get("imagen", "") or "").strip()

    galeria = datos.get("galeria") or []
    if isinstance(galeria, str):
        galeria = [galeria]
    if not isinstance(galeria, list):
        raise ValueError(f"Galería incorrecta: {archivo.name}")
    galeria = [str(ruta).strip() for ruta in galeria if ruta]

    # La primera foto de la galería también sirve de portada.
    if not imagen and galeria:
        imagen = galeria[0]

    cuerpo = partes[2].strip()

    html_cuerpo = markdown.markdown(
        cuerpo,
        extensions=["extra", "sane_lists"]
    )

    slug = crear_slug(titulo)

    return {
        "titulo": titulo,
        "numero": numero,
        "fecha": fecha,
        "imagen": imagen,
        "galeria": galeria,
        "cuerpo": html_cuerpo,
        "slug": f"{numero:03d}-{slug}",
    }


def url_imagen(ruta, desde_articulo=False):
    if not ruta:
        return ""

    ruta = ruta.replace("\\", "/")
    if ruta.startswith(("https://", "http://")):
        return ruta
    if ruta.startswith("/"):
        destino = ruta
    elif ruta.startswith("blog/"):
        destino = "/" + ruta
    elif ruta.startswith("../"):
        destino = ruta
    else:
        # Compatible con rutas antiguas sin carpeta.
        destino = "/blog/imagenes/" + ruta.split("/")[-1]

    # Los nombres con espacios o tildes deben funcionar en las URLs.
    partes = urlsplit(destino)
    return urlunsplit((partes.scheme, partes.netloc,
                       quote(partes.path, safe="/%"),
                       partes.query, partes.fragment))


def crear_articulo(historia):
    titulo = texto_seguro(historia["titulo"])
    numero = historia["numero"]
    fecha = texto_seguro(historia["fecha"])

    imagen_html = ""

    if historia["imagen"] and historia["imagen"] not in historia["galeria"]:
        src = texto_seguro(
            url_imagen(historia["imagen"], desde_articulo=True)
        )

        imagen_html = (
            f'<img class="foto" src="{src}" '
            f'alt="{titulo}" loading="lazy">'
        )

    fotos = []
    vistas = set()
    for ruta in historia["galeria"]:
        src = url_imagen(ruta, desde_articulo=True)
        if src and src not in vistas:
            vistas.add(src)
            fotos.append(
                f'<figure><img src="{texto_seguro(src)}" '
                f'alt="{titulo} — fotografía {len(fotos) + 1}" '
                f'loading="lazy"></figure>'
            )

    galeria_html = (
        '<section class="galeria-fotos" aria-label="Fotografías de la excursión">'
        '<h2>Galería de fotografías</h2>'
        '<div class="galeria-grid">' + "\n".join(fotos) + '</div></section>'
        if fotos else ""
    )

    contenido = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport"
        content="width=device-width, initial-scale=1">
  <title>{titulo} | 100 montañas en 365 días</title>
  <meta name="description"
        content="Cumbre {numero:03d}: {titulo}. Una historia personal de montaña en Baviera.">

  <style>
    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: #faf8f2;
      color: #25382e;
      font-family: Arial, sans-serif;
      line-height: 1.8;
    }}

    .contenedor {{
      width: min(780px, 90%);
      margin: auto;
    }}

    header {{
      border-bottom: 1px solid #dfe5da;
      padding: 24px 0;
    }}

    a {{
      color: #1f4033;
      text-decoration: none;
    }}

    .marca {{
      font-family: Georgia, serif;
      font-size: 23px;
      font-weight: bold;
    }}

    main {{
      padding: 65px 0 100px;
    }}

    .numero {{
      color: #728473;
      letter-spacing: 2px;
      text-transform: uppercase;
      font-size: 12px;
    }}

    h1 {{
      font-family: Georgia, serif;
      color: #1f4033;
      font-weight: normal;
      font-size: clamp(38px, 6vw, 65px);
      line-height: 1.15;
    }}

    .fecha {{
      color: #728473;
      font-size: 14px;
      margin-bottom: 35px;
    }}

    .foto {{
      width: 100%;
      height: auto;
      border-radius: 5px;
      margin: 35px 0;
    }}

    .relato {{
      font-size: 18px;
      overflow-wrap: break-word;
    }}

    .relato img {{
      max-width: 100%;
      height: auto;
      border-radius: 5px;
    }}

    .relato h2, .relato h3 {{
      font-family: Georgia, serif;
      color: #1f4033;
    }}

    .galeria-fotos {{ margin-top: 48px; }}
    .galeria-fotos h2 {{ font-family: Georgia, serif; font-weight: normal; }}
    .galeria-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr)); gap: 16px; }}
    .galeria-grid figure {{ margin: 0; }}
    .galeria-grid img {{ display: block; width: 100%; height: auto; border-radius: 5px; }}

    .invitacion {{
      margin-top: 75px;
      border-top: 1px solid #dfe5da;
      padding-top: 35px;
    }}

    .boton {{
      display: inline-block;
      background: #1f4033;
      color: white;
      padding: 13px 24px;
      border-radius: 4px;
      margin-top: 12px;
    }}

    footer {{
      background: #1f4033;
      color: white;
      padding: 30px 0;
    }}

    footer a {{
      color: white;
    }}
  </style>
</head>

<body>

  <header>
    <div class="contenedor">
      <a class="marca" href="/blog/">
        100 montañas en 365 días
      </a>
    </div>
  </header>

  <main class="contenedor">

    <div class="numero">
      Cumbre {numero:03d} de 100
    </div>

    <h1>{titulo}</h1>

    <div class="fecha">
      Fecha de ascenso: {fecha}
    </div>

    {imagen_html}

    <article class="relato">
      {historia["cuerpo"]}
    </article>

    {galeria_html}

    <div class="invitacion">
      <h2>¿Te gustaría vivir tu propia experiencia?</h2>

      <p>
        Descubre nuestras caminatas por los
        Prealpes bávaros. Grupos pequeños,
        naturaleza y tiempo para disfrutar
        de cada paisaje.
      </p>

      <a class="boton" href="/">
        Descubrir las excursiones
      </a>

      <p>
        <a href="/blog/">
          Volver a las 100 montañas
        </a>
      </p>
    </div>

  </main>

  <footer>
    <div class="contenedor">
      Una pausa en tu viaje · Prealpes bávaros
    </div>
  </footer>

</body>
</html>"""

    destino = SALIDA / historia["slug"] / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")


def crear_tarjeta(historia):
    titulo = texto_seguro(historia["titulo"])
    numero = historia["numero"]
    fecha = texto_seguro(historia["fecha"])
    enlace = f"/blog/cumbres/{historia['slug']}/"

    imagen_html = ""

    if historia["imagen"]:
        src = texto_seguro(url_imagen(historia["imagen"]))
        imagen_html = (
            f'<img src="{src}" alt="{titulo}" loading="lazy">'
        )

    return f"""
    <article class="story-card">
      <a href="{enlace}">
        {imagen_html}
        <div class="story-content">
          <div class="story-number">
            Cumbre {numero:03d} de 100
          </div>
          <h3>{titulo}</h3>
          <p>{fecha}</p>
          <span class="story-link">
            Leer la historia
          </span>
        </div>
      </a>
    </article>
    """


def actualizar_portada(historias):
    html = PORTADA.read_text(encoding="utf-8")

    tarjetas = "\n".join(
        crear_tarjeta(historia) for historia in historias
    )

    if not tarjetas:
        tarjetas = """
        <div class="empty-state">
          <h3>Las primeras historias llegarán pronto.</h3>
          <p>
            Este diario irá reuniendo las experiencias
            y fotografías de cada cumbre.
          </p>
        </div>
        """

    inicio = html.find('<div class="stories-grid" id="stories-grid">')

    if inicio == -1:
        raise ValueError(
            "No se encontro el contenedor de historias en blog/index.html"
        )

    inicio_contenido = html.find(">", inicio) + 1
    fin_contenido = html.find("</div>", inicio_contenido)

    # Sustituimos el contenido usando marcadores propios,
    # para que futuras ejecuciones sean seguras.
    if MARCADOR_INICIO in html and MARCADOR_FIN in html:
        patron = (
            re.escape(MARCADOR_INICIO)
            + r".*?"
            + re.escape(MARCADOR_FIN)
        )
        html = re.sub(
            patron,
            lambda _: (
                MARCADOR_INICIO
                + "\n"
                + tarjetas
                + "\n"
                + MARCADOR_FIN
            ),
            html,
            flags=re.DOTALL
        )
    else:
        # Primera ejecucion: sustituir el bloque vacio
        # sin alterar el resto de la portada.
        apertura = '<div class="stories-grid" id="stories-grid">'
        comienzo = html.index(apertura) + len(apertura)

        cierre_seccion = html.find(
            "\n        </div>\n\n      </div>\n    </section>",
            comienzo
        )

        if cierre_seccion == -1:
            raise ValueError(
                "No se pudo identificar el cierre de la galeria"
            )

        html = (
            html[:comienzo]
            + "\n"
            + MARCADOR_INICIO
            + "\n"
            + tarjetas
            + "\n"
            + MARCADOR_FIN
            + html[cierre_seccion:]
        )

    cantidad = len(historias)

    html = re.sub(
        r'(<span id="summit-count">).*?(</span>)',
        lambda m: m.group(1) + str(cantidad) + m.group(2),
        html,
        count=1,
        flags=re.DOTALL
    )

    porcentaje = min(cantidad, 100)

    # Actualizar el ancho sin duplicar el atributo style en cada ejecución.
    def actualizar_progreso(m):
        etiqueta = m.group(0)
        estilo = re.search(r'\sstyle=["\']([^"\']*)["\']', etiqueta)
        if estilo:
            anterior = estilo.group(1)
            nuevo = re.sub(r'width\s*:\s*[^;]+;?', '', anterior).strip()
            nuevo = (nuevo.rstrip(';') + '; ' if nuevo else '') + f'width: {porcentaje}%'
            return etiqueta[:estilo.start()] + f' style="{nuevo}"' + etiqueta[estilo.end():]
        return etiqueta[:-1] + f' style="width: {porcentaje}%">'

    html = re.sub(
        r'<div\b(?=[^>]*\bid=["\']progress-fill["\'])[^>]*>',
        actualizar_progreso, html, count=1
    )

    PORTADA.write_text(html, encoding="utf-8")


def main():
    SALIDA.mkdir(parents=True, exist_ok=True)

    historias = []

    if HISTORIAS.exists():
        for archivo in sorted(HISTORIAS.glob("*.md")):
            historia = leer_historia(archivo)

            if historia is not None:
                historias.append(historia)

    historias.sort(key=lambda h: h["numero"])

    numeros = [h["numero"] for h in historias]

    if len(numeros) != len(set(numeros)):
        raise ValueError(
            "Hay dos historias publicadas con el mismo numero de cumbre."
        )

    # Limpiar paginas generadas anteriormente.
    # Solo se borran paginas dentro de blog/cumbres.
    import shutil

    if SALIDA.exists():
        shutil.rmtree(SALIDA)

    SALIDA.mkdir(parents=True, exist_ok=True)

    for historia in historias:
        crear_articulo(historia)

    actualizar_portada(historias)

    print(
        f"Blog generado correctamente: "
        f"{len(historias)} historias publicadas."
    )


if __name__ == "__main__":
    main()
