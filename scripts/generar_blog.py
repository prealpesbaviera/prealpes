
from pathlib import Path
from html import escape
from urllib.parse import quote
import re
import shutil
import unicodedata

import markdown
import yaml


BASE = Path(__file__).resolve().parent.parent
BLOG = BASE / "blog"
HISTORIAS = BLOG / "historias"
PORTADA = BLOG / "index.html"
SALIDA = BLOG / "cumbres"

INICIO = "<!-- HISTORIAS_GENERADAS_INICIO -->"
FIN = "<!-- HISTORIAS_GENERADAS_FIN -->"


def seguro(valor):
    return escape(str(valor or ""), quote=True)


def slug(texto):
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return re.sub(
        r"[^a-z0-9]+", "-", texto.lower()
    ).strip("-") or "montana"


def url_imagen(ruta):
    ruta = str(ruta or "").replace("\\", "/").strip()

    if not ruta:
        return ""

    if ruta.startswith(("https://", "http://")):
        return ruta

    if ruta.startswith("/"):
        destino = ruta
    elif ruta.startswith("blog/"):
        destino = "/" + ruta
    else:
        destino = "/blog/imagenes/" + ruta.split("/")[-1]

    return quote(destino, safe="/%")


def leer_historia(archivo):
    contenido = archivo.read_text(encoding="utf-8")

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

    if str(datos.get("estado", "")).lower().strip() != "publicado":
        return None

    titulo = str(datos.get("title", "")).strip()
    numero = int(datos.get("numero"))

    if not titulo or not 1 <= numero <= 100:
        raise ValueError(
            f"Titulo o numero incorrecto: {archivo.name}"
        )

    galeria = datos.get("galeria") or []

    if isinstance(galeria, str):
        galeria = [galeria]

    if not isinstance(galeria, list):
        raise ValueError(
            f"Galeria incorrecta: {archivo.name}"
        )

    galeria = [
        str(foto).strip()
        for foto in galeria
        if foto
    ]

    imagen = str(datos.get("imagen") or "").strip()

    if not imagen and galeria:
        imagen = galeria[0]

    cuerpo = partes[2].strip()

    return {
        "titulo": titulo,
        "numero": numero,
        "fecha": str(datos.get("fecha") or ""),
        "imagen": imagen,
        "galeria": galeria,
        "cuerpo": markdown.markdown(
            cuerpo,
            extensions=["extra", "sane_lists"]
        ),
        "slug": f"{numero:03d}-{slug(titulo)}"
    }


def crear_articulo(historia):
    titulo = seguro(historia["titulo"])
    numero = historia["numero"]
    fecha = seguro(historia["fecha"])
    galeria = historia["galeria"]

    utilizadas = set()

    def foto_html(indice):
        if indice < 1 or indice > len(galeria):
            return '<p>Fotografia no encontrada.</p>'

        utilizadas.add(indice)

        src = seguro(url_imagen(galeria[indice - 1]))

        return (
            f'<figure class="foto-relato">'
            f'<img src="{src}" alt="{titulo} - foto {indice}" '
            f'loading="lazy">'
            f'</figure>'
        )

    def insertar_fotos(coincidencia):
        indices = [
            int(n)
            for n in re.findall(
                r"\d+", coincidencia.group(1)
            )
        ]

        fotos = [foto_html(i) for i in indices]

        if len(fotos) == 1:
            return fotos[0]

        return (
            '<div class="grupo-fotos">'
            + "\n".join(fotos)
            + '</div>'
        )

    cuerpo = re.sub(
        r"<p>\s*\[\[(?:foto|fotos):\s*([0-9, ]+)\]\]\s*</p>",
        insertar_fotos,
        historia["cuerpo"],
        flags=re.IGNORECASE
    )

    restantes = [
        foto_html(i)
        for i in range(1, len(galeria) + 1)
        if i not in utilizadas
    ]

    galeria_final = ""

    if restantes:
        galeria_final = (
            '<section class="galeria-final">'
            '<h2>Más fotografías de esta montaña</h2>'
            '<div class="grupo-fotos">'
            + "\n".join(restantes)
            + '</div></section>'
        )

    portada = ""

    if historia["imagen"] and historia["imagen"] not in galeria:
        src = seguro(url_imagen(historia["imagen"]))
        portada = (
            f'<img class="portada" src="{src}" '
            f'alt="{titulo}">'
        )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} | 100 montañas en 365 días</title>
<meta name="description" content="Cumbre {numero:03d}: {titulo}. Relato personal de montaña en Baviera.">

<style>
* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #faf8f2;
    color: #25382e;
    font-family: Arial, sans-serif;
    line-height: 1.85;
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
    margin-bottom: 18px;
}}

.fecha {{
    color: #728473;
    font-size: 14px;
    margin-bottom: 40px;
}}

.portada {{
    display: block;
    width: 100%;
    height: auto;
    border-radius: 5px;
    margin: 35px 0;
}}

.relato {{
    font-size: 18px;
    overflow-wrap: break-word;
}}

.relato p {{
    margin: 0 0 1.55em;
}}

.relato h2,
.relato h3,
.galeria-final h2 {{
    font-family: Georgia, serif;
    color: #1f4033;
    font-weight: normal;
    line-height: 1.3;
}}

.relato h2 {{
    font-size: 30px;
    margin-top: 2.2em;
}}

.relato h3 {{
    font-size: 23px;
    margin-top: 1.8em;
}}

.relato img {{
    max-width: 100%;
    height: auto;
    border-radius: 5px;
}}

.foto-relato {{
    margin: 38px 0;
}}

.foto-relato img {{
    display: block;
    width: 100%;
    height: auto;
    border-radius: 5px;
}}

.grupo-fotos {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 14px;
    margin: 36px 0;
}}

.grupo-fotos .foto-relato {{
    margin: 0;
}}

.grupo-fotos img {{
    width: 100%;
    height: 100%;
    object-fit: cover;
}}

.galeria-final {{
    margin-top: 55px;
}}

.invitacion {{
    margin-top: 80px;
    border-top: 1px solid #dfe5da;
    padding-top: 40px;
}}

.invitacion h2 {{
    font-family: Georgia, serif;
    color: #1f4033;
    font-weight: normal;
    font-size: 30px;
    line-height: 1.3;
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

@media (max-width: 520px) {{
    main {{
        padding-top: 40px;
    }}

    .relato {{
        font-size: 17px;
    }}

    .grupo-fotos {{
        gap: 8px;
    }}
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

  {portada}

  <article class="relato">
    {cuerpo}
  </article>

  {galeria_final}

  <div class="invitacion" style="display: none;">
    <h2>Algunas montañas también podemos descubrirlas juntos.</h2>

    <p>
      Descubre nuestras caminatas por los Prealpes bávaros.
      Grupos pequeños, naturaleza y tiempo para disfrutar
      de cada paisaje.
    </p>

    <a class="boton" href="/">
      Descubrir las excursiones
    </a>

    <p>
      <a href="/blog/">Volver a las 100 montañas</a>
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
    destino.write_text(html, encoding="utf-8")


def crear_tarjeta(historia):
    titulo = seguro(historia["titulo"])
    numero = historia["numero"]
    fecha = seguro(historia["fecha"])
    enlace = f"/blog/cumbres/{historia['slug']}/"

    imagen_html = ""

    if historia["imagen"]:
        src = seguro(url_imagen(historia["imagen"]))
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
        crear_tarjeta(h) for h in historias
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

    if INICIO in html and FIN in html:
        patron = re.escape(INICIO) + r".*?" + re.escape(FIN)

        html = re.sub(
            patron,
            lambda _: INICIO + "\n" + tarjetas + "\n" + FIN,
            html,
            flags=re.DOTALL
        )
    else:
        apertura = '<div class="stories-grid" id="stories-grid">'

        if apertura not in html:
            raise ValueError(
                "No se encontro stories-grid en blog/index.html"
            )

        comienzo = html.index(apertura) + len(apertura)

        cierre = html.find(
            "\n        </div>\n\n      </div>\n    </section>",
            comienzo
        )

        if cierre == -1:
            raise ValueError(
                "No se encontro el cierre de la seccion de historias"
            )

        html = (
            html[:comienzo]
            + "\n" + INICIO + "\n"
            + tarjetas + "\n"
            + FIN
            + html[cierre:]
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

    def progreso(coincidencia):
        etiqueta = coincidencia.group(0)

        estilo = re.search(
            r'\sstyle=["\']([^"\']*)["\']',
            etiqueta
        )

        if estilo:
            anterior = estilo.group(1)
            nuevo = re.sub(
                r'width\s*:\s*[^;]+;?',
                '',
                anterior
            ).strip()

            nuevo = (
                (nuevo.rstrip(";") + "; ") if nuevo else ""
            ) + f"width: {porcentaje}%"

            return (
                etiqueta[:estilo.start()]
                + f' style="{nuevo}"'
                + etiqueta[estilo.end():]
            )

        return (
            etiqueta[:-1]
            + f' style="width: {porcentaje}%">'
        )

    html = re.sub(
        r'<div\b(?=[^>]*\bid=["\']progress-fill["\'])[^>]*>',
        progreso,
        html,
        count=1
    )

    PORTADA.write_text(html, encoding="utf-8")


def main():
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
