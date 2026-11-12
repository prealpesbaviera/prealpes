
from pathlib import Path
from html import escape
from urllib.parse import quote
import re
import json
import shutil
import unicodedata
import markdown
import yaml

BASE = Path(__file__).resolve().parent.parent
BLOG = BASE / 'blog'
HISTORIAS = BLOG / 'historias'
PORTADA = BLOG / 'index.html'
SALIDA = BLOG / 'cumbres'
INICIO = '<!-- HISTORIAS_GENERADAS_INICIO -->'
FIN = '<!-- HISTORIAS_GENERADAS_FIN -->'
MOSTRAR_EXCURSIONES = False


def seguro(valor):
    return escape(str(valor or ''), quote=True)


def crear_slug(texto):
    texto = unicodedata.normalize('NFKD', str(texto))
    texto = ''.join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return (
        re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-')
        or 'montana'
    )


def url_imagen(ruta):
    ruta = str(ruta or '').replace('\\', '/').strip()

    if not ruta:
        return ''

    if ruta.startswith(('https://', 'http://')):
        return ruta

    if ruta.startswith('/'):
        destino = ruta
    elif ruta.startswith('blog/'):
        destino = '/' + ruta
    else:
        destino = '/blog/imagenes/' + ruta.split('/')[-1]

    return quote(destino, safe='/%')


def numero_decimal(valor):
    """Convierte valores como 12,5 km, 850 m o 1.250 m."""
    if valor is None or isinstance(valor, bool):
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    encontrado = re.search(r'-?[\d.,]+', texto)

    if not encontrado:
        return None

    numero = encontrado.group(0).strip('. ,')

    if ',' in numero and '.' in numero:
        if numero.rfind(',') > numero.rfind('.'):
            numero = numero.replace('.', '').replace(',', '.')
        else:
            numero = numero.replace(',', '')
    elif ',' in numero:
        numero = numero.replace(',', '.')
    elif (
        numero.count('.') == 1
        and len(numero.split('.')[-1]) == 3
        and ('m' in texto.lower() or 'km' not in texto.lower())
    ):
        numero = numero.replace('.', '')

    try:
        return float(numero)
    except ValueError:
        return None


def leer_historia(archivo):
    contenido = archivo.read_text(encoding='utf-8')
    partes = re.split(
        r'^---\s*$',
        contenido,
        maxsplit=2,
        flags=re.MULTILINE
    )

    if len(partes) < 3:
        return None

    datos = yaml.safe_load(partes[1]) or {}

    if not isinstance(datos, dict):
        return None

    titulo = str(datos.get('title') or '').strip()

    try:
        numero = int(datos.get('numero'))
    except (ValueError, TypeError):
        raise ValueError(
            f'Número incorrecto en {archivo.name}'
        )

    if not titulo or not 1 <= numero <= 100:
        raise ValueError(
            f'Título o número incorrecto: {archivo.name}'
        )

    galeria = datos.get('galeria') or []

    if isinstance(galeria, str):
        galeria = [galeria]

    if not isinstance(galeria, list):
        raise ValueError(
            f'Galería incorrecta: {archivo.name}'
        )

    galeria = [
        str(f).strip()
        for f in galeria
        if f
    ]

    imagen = (
        str(datos.get('imagen') or '').strip()
        or (galeria[0] if galeria else '')
    )

    campos = [
        ('altitud', 'Altitud'),
        ('desnivel', 'Desnivel +'),
        ('distancia', 'Distancia'),
        ('duracion', 'Duración'),
        ('dificultad', 'Dificultad'),
        ('acceso', 'Acceso')
    ]

    ficha = [
        (etiqueta, str(datos.get(clave) or '').strip())
        for clave, etiqueta in campos
        if str(datos.get(clave) or '').strip()
    ]

    cuerpo = markdown.markdown(
        partes[2].strip(),
        extensions=['extra', 'sane_lists']
    )

    publicado = (
        str(datos.get('estado', '')).strip().lower()
        == 'publicado'
    )

    realizada = datos.get('realizada')

    if realizada is None:
        # Compatibilidad con historias publicadas anteriormente.
        realizada = publicado
    elif isinstance(realizada, str):
        realizada = realizada.strip().lower() in (
            'true', 'si', 'sí', '1', 'yes'
        )
    else:
        realizada = bool(realizada)

    return dict(
        titulo=titulo,
        numero=numero,
        fecha=str(datos.get('fecha') or ''),
        imagen=imagen,
        galeria=galeria,
        ficha=ficha,
        cuerpo=cuerpo,
        slug=f'{numero:03d}-{crear_slug(titulo)}',
        publicado=publicado,
        realizada=realizada,
        latitud=numero_decimal(datos.get('latitud')),
        longitud=numero_decimal(datos.get('longitud')),
        altitud=numero_decimal(datos.get('altitud')),
        distancia=numero_decimal(datos.get('distancia')),
        desnivel=numero_decimal(datos.get('desnivel'))
    )


def crear_ficha(historia):
    if not historia['ficha']:
        return ''

    datos = ''.join(
        f'<div class="dato">'
        f'<span>{seguro(e)}</span>'
        f'<strong>{seguro(v)}</strong>'
        f'</div>'
        for e, v in historia['ficha']
    )

    return (
        '<section class="ficha">'
        '<div class="ficha-titulo">'
        'Ficha técnica de la ruta'
        '</div>'
        f'<div class="ficha-datos">{datos}</div>'
        '</section>'
    )


def preparar_elementos_editoriales(cuerpo):
    """Convierte los códigos editoriales de Pages CMS en HTML."""

    patrones = {
        'cita': ('cita-editorial', 'blockquote'),
        'destacado': ('destacado-editorial', 'aside'),
        'entradilla': ('entradilla-editorial', 'div'),
        'nota': ('nota-editorial', 'aside'),
        'epigrafe': ('epigrafe-editorial', 'p'),
        'capitulo': ('capitulo-editorial', 'h2'),
        'centrado': ('centrado-editorial', 'p'),
    }

    def sustituir(m):
        tipo = m.group(1).lower()

        if tipo == 'separador':
            return '<hr class="separador-editorial">'

        texto = seguro(m.group(2).strip())
        clase, etiqueta = patrones[tipo]

        return (
            f'<{etiqueta} class="{clase}">'
            f'{texto}'
            f'</{etiqueta}>'
        )

    patron = (
        r'<p>\s*\[\['
        r'(cita|destacado|entradilla|nota|epigrafe|'
        r'capitulo|centrado|separador)'
        r'(?::([^\]\n]+))?'
        r'\]\]\s*</p>'
    )

    return re.sub(
        patron,
        sustituir,
        cuerpo,
        flags=re.IGNORECASE
    )


def preparar_relato(historia):
    galeria = historia['galeria']
    utilizadas = set()

    clases = {
        'foto': 'foto-mediana',
        'grande': 'foto-grande',
        'izquierda': 'foto-izquierda',
        'derecha': 'foto-derecha'
    }

    def crear_foto(indice, modo='foto'):
        if indice < 1 or indice > len(galeria):
            return '<p>Fotografía no encontrada.</p>'

        utilizadas.add(indice)

        src = seguro(
            url_imagen(galeria[indice - 1])
        )

        titulo = seguro(historia['titulo'])
        clase = clases.get(modo, 'foto-mediana')

        return (
            f'<figure class="foto-relato {clase}">'
            f'<a href="{src}" class="ampliar" '
            f'data-lightbox '
            f'aria-label="Ampliar fotografía {indice}">'
            f'<img src="{src}" '
            f'alt="{titulo} - fotografía {indice}" '
            f'loading="lazy"></a></figure>'
        )

    def reemplazar(m):
        modo = m.group(1).lower()
        indices = [
            int(n)
            for n in re.findall(r'\d+', m.group(2))
        ]

        if not indices:
            return ''

        if modo == 'fotos':
            return (
                '<div class="grupo-fotos">'
                + ''.join(crear_foto(i) for i in indices)
                + '</div>'
            )

        return crear_foto(indices[0], modo)

    patron = (
        r'<p>\s*\[\['
        r'(foto|fotos|izquierda|derecha|grande):\s*'
        r'([0-9, ]+)\]\]\s*</p>'
    )

    cuerpo = re.sub(
        patron,
        reemplazar,
        historia['cuerpo'],
        flags=re.IGNORECASE
    )

      cuerpo = preparar_elementos_editoriales(cuerpo)
    # La portada no se repite en la galería final.
    portada_url = url_imagen(historia['imagen'])

    restantes = [
        i
        for i in range(1, len(galeria) + 1)
        if i not in utilizadas
        and url_imagen(galeria[i - 1]) != portada_url
    ]

    galeria_final = ''

    if restantes:
        fotos = ''.join(
            crear_foto(i)
            for i in restantes
        )

        galeria_final = (
            '<section class="galeria-final">'
            '<h2>Más fotografías de esta montaña</h2>'
            f'<div class="grupo-fotos">{fotos}</div>'
            '</section>'
        )

    return cuerpo, galeria_final


def crear_invitacion():
    if not MOSTRAR_EXCURSIONES:
        return ''

    return '''
    <section class="invitacion">
    <h2>Algunas montañas también podemos descubrirlas juntos.</h2>
    <p>Descubre nuestras caminatas por los Prealpes bávaros.
    Grupos pequeños, naturaleza y tiempo para disfrutar
    de cada paisaje.</p>
    <a class="boton" href="/">Descubrir las excursiones</a>
    </section>
    '''


ESTILOS = '''
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: #faf8f2;
  color: #25382e;
  font-family: Georgia, serif;
  line-height: 1.8;
}

.contenedor {
  width: min(980px, 92%);
  margin: auto;
}

header {
  background: #faf8f2;
  border-bottom: 1px solid #e6e8de;
}

.cabecera {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.marca {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #1f4033;
  font-family: Georgia, serif;
  font-size: 18px;
  font-weight: 600;
  text-decoration: none;
}

.marca img {
  width: 90px;
  height: 64px;
  object-fit: contain;
}

.marca small {
  display: block;
  font: 10px Arial, sans-serif;
  letter-spacing: 2px;
  color: #627269;
  margin-top: 5px;
  text-transform: uppercase;
}

.navegacion {
  display: flex;
  flex-wrap: wrap;
  gap: 22px;
}

.navegacion a {
  color: #67776c;
  font: 13px Arial, sans-serif;
  text-decoration: none;
}

.navegacion a:hover,
.marca:hover {
  text-decoration: underline;
}

main {
  padding: 65px 0 90px;
}

.numero {
  font: 12px Arial, sans-serif;
  color: #71816f;
  letter-spacing: 3px;
  text-transform: uppercase;
}

h1 {
  font-size: clamp(38px, 6vw, 62px);
  line-height: 1.12;
  font-weight: normal;
  color: #1f4033;
  margin: 22px 0;
}

.fecha {
  font: 14px Arial, sans-serif;
  color: #728473;
  margin-bottom: 32px;
}

/* Fotografía 60 % y ficha técnica 40 %. */
.presentacion {
  display: grid;
  grid-template-columns: minmax(0, 60fr) minmax(0, 40fr);
  gap: 22px;
  align-items: stretch;
  margin: 0 0 25px;
}

.presentacion.solo-ficha {
  grid-template-columns: 1fr;
}

.presentacion.solo-foto {
  grid-template-columns: minmax(0, 1fr);
}

.portada-enlace {
  display: block;
  height: 100%;
  min-height: 280px;
  max-height: 390px;
  overflow: hidden;
  border-radius: 15px;
  cursor: zoom-in;
}

.portada {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ficha {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: auto 1fr;
  background: #eeefe3;
  border: 1px solid #d7dfd0;
  border-radius: 15px;
  overflow: hidden;
  margin: 0;
}

.ficha-titulo {
  background: #1f4033;
  color: white;
  font-size: 18px;
  line-height: 1.3;
  padding: 17px 20px;
}

.ficha-datos {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 17px 16px;
  padding: 20px;
  align-content: center;
}

.dato {
  display: flex;
  flex-direction: column;
  line-height: 1.4;
  min-width: 0;
  overflow-wrap: anywhere;
}

.dato span {
  color: #687967;
  font: 12px Arial, sans-serif;
  margin-bottom: 5px;
}

.dato strong {
  color: #1f4033;
  font-size: 16px;
}

.relato {
  font-size: 19px;
  line-height: 1.85;
  overflow-wrap: break-word;
  display: flow-root;
}

.relato p {
  margin: 0 0 1.55em;
}

.relato h2,
.relato h3,
.galeria-final h2 {
  color: #1f4033;
  font-weight: normal;
  line-height: 1.3;
}

.relato h2 {
  font-size: 31px;
  margin-top: 1.2em;
}

.relato h3 {
  font-size: 24px;
  margin-top: 1.7em;
}

.relato blockquote {
  margin: 35px 0;
  padding: 18px 30px;
  border-left: 4px solid #718a69;
  background: #eeefe3;
  font-style: italic;
}

.relato img {
  max-width: 100%;
}

.foto-relato {
  margin: 32px auto;
}

.foto-relato img {
  display: block;
  width: 100%;
  height: auto;
  border-radius: 15px;
}

.ampliar {
  display: block;
  cursor: zoom-in;
}

.foto-mediana {
  width: min(76%, 650px);
}

.foto-grande {
  width: 100%;
  clear: both;
}

.foto-izquierda {
  float: left;
  width: 39%;
  margin: 8px 27px 20px 0;
}

.foto-derecha {
  float: right;
  width: 39%;
  margin: 8px 0 20px 27px;
}

.grupo-fotos {
  clear: both;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin: 38px 0;
}

.grupo-fotos .foto-relato {
  width: 100%;
  margin: 0;
}

.grupo-fotos .foto-relato img {
  width: 100%;
  height: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
}

.galeria-final {
  margin-top: 60px;
}

.invitacion {
  margin-top: 80px;
  padding-top: 38px;
  border-top: 1px solid #dfe5da;
}

.invitacion h2 {
  font-size: 30px;
  font-weight: normal;
  color: #1f4033;
  line-height: 1.3;
}

.boton {
  display: inline-block;
  background: #1f4033;
  color: white;
  text-decoration: none;
  padding: 13px 24px;
  border-radius: 5px;
  margin-top: 12px;
}

.volver {
  margin-top: 65px;
  font-size: 15px;
}

.volver a {
  color: #1f4033;
  text-decoration: none;
}

footer {
  background: #1f4033;
  color: white;
  padding: 30px 0;
  font: 13px Arial, sans-serif;
}

.lightbox {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(8, 16, 12, .94);
  display: none;
  align-items: center;
  justify-content: center;
  padding: 52px 18px 20px;
}

.lightbox.abierto {
  display: flex;
}

.lightbox img {
  display: block;
  max-width: 96vw;
  max-height: 88vh;
  object-fit: contain;
  border-radius: 5px;
}

.lightbox-cerrar {
  position: absolute;
  top: 10px;
  right: 18px;
  color: white;
  background: transparent;
  border: 0;
  font-size: 35px;
  cursor: pointer;
}

@media (max-width: 680px) {
  main {
    padding-top: 40px;
  }

  .cabecera {
    padding: 16px 0;
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .presentacion {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .portada-enlace {
    height: 290px;
    min-height: 0;
  }

  .ficha-datos {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .relato {
    font-size: 17px;
  }

  .foto-mediana,
  .foto-izquierda,
  .foto-derecha {
    float: none;
    width: 100%;
    margin: 28px 0;
  }

  .grupo-fotos {
    gap: 8px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
  }
}

/* ELEMENTOS EDITORIALES */

.relato .entradilla-editorial {
  font-size: clamp(22px, 3vw, 28px);
  line-height: 1.55;
  color: #1f4033;
  padding: 16px 0 18px;
  border-bottom: 1px solid #b8c6b7;
  margin: 0 0 36px;
}

.relato .cita-editorial {
  clear: both;
  margin: 46px auto;
  max-width: 760px;
  padding: 28px 35px;
  background: #eeefe3;
  border-left: 5px solid #b9a47b;
  color: #1f4033;
  font-size: clamp(22px, 3vw, 30px);
  line-height: 1.5;
  font-style: italic;
}

.relato .destacado-editorial {
  clear: both;
  margin: 42px 0;
  padding: 28px 34px;
  border-radius: 12px;
  background: #1f4033;
  color: white;
  font-size: 23px;
  line-height: 1.5;
}

.relato .nota-editorial {
  clear: both;
  margin: 30px 0;
  padding: 18px 24px;
  border: 1px solid #cdd8c8;
  border-radius: 8px;
  background: #f1f3eb;
  font-size: 16px;
  font-family: Arial, sans-serif;
}

.relato .epigrafe-editorial {
  clear: both;
  margin: 20px 0 45px;
  color: #7a866f;
  text-align: center;
  font-size: 15px;
  font-style: italic;
}

.relato .capitulo-editorial {
  clear: both;
  margin: 62px 0 25px;
  padding-top: 20px;
  border-top: 1px solid #b9a47b;
  font-size: clamp(29px, 4vw, 40px);
  font-weight: normal;
}

.relato .centrado-editorial {
  clear: both;
  max-width: 700px;
  margin: 45px auto;
  text-align: center;
  font-size: 23px;
  font-style: italic;
}

.relato .separador-editorial {
  clear: both;
  border: 0;
  width: 90px;
  height: 2px;
  background: #b9a47b;
  margin: 52px auto;
}

'''


SCRIPT_LIGHTBOX = '''
<script>
(() => {
  const visor = document.getElementById('visor');
  const foto = document.getElementById('visor-foto');
  const cerrar = document.getElementById('visor-cerrar');
  let anterior = null;

  function ocultar() {
    visor.classList.remove('abierto');
    visor.setAttribute('aria-hidden', 'true');
    foto.removeAttribute('src');
    document.body.style.overflow = '';
    if (anterior) anterior.focus();
  }

  document.querySelectorAll('a[data-lightbox]').forEach(enlace => {
    enlace.addEventListener('click', evento => {
      evento.preventDefault();
      anterior = enlace;
      foto.src = enlace.href;
      foto.alt = enlace.querySelector('img')?.alt || 'Fotografía ampliada';
      visor.classList.add('abierto');
      visor.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      cerrar.focus();
    });
  });

  cerrar.addEventListener('click', ocultar);

  visor.addEventListener('click', evento => {
    if (evento.target === visor) ocultar();
  });

  document.addEventListener('keydown', evento => {
    if (
      evento.key === 'Escape'
      && visor.classList.contains('abierto')
    ) {
      ocultar();
    }
  });
})();
</script>
'''


def crear_articulo(historia):
    titulo = seguro(historia['titulo'])
    numero = historia['numero']
    fecha = seguro(historia['fecha'])

    ficha = crear_ficha(historia)
    cuerpo, galeria_final = preparar_relato(historia)
    invitacion = crear_invitacion()

    portada = ''

    if historia['imagen']:
        src = seguro(url_imagen(historia['imagen']))

        portada = (
            f'<a class="portada-enlace" href="{src}" '
            f'data-lightbox '
            f'aria-label="Ampliar fotografía principal">'
            f'<img class="portada" src="{src}" '
            f'alt="{titulo}"></a>'
        )

    clase = 'presentacion'

    if ficha and not portada:
        clase += ' solo-ficha'

    if portada and not ficha:
        clase += ' solo-foto'

    presentacion = (
        f'<div class="{clase}">{portada}{ficha}</div>'
        if portada or ficha
        else ''
    )

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo} | 100 montañas en 365 días</title>
<meta name="description" content="Cumbre {numero:03d}: {titulo}. Relato personal de montaña en Baviera.">
<style>{ESTILOS}</style>
</head>
<body>

<header>
<div class="contenedor cabecera">

<a class="marca" href="/blog/">
<img src="/logonuevo.png" alt="Montañas">
<span>Una pausa en tu camino
<small>Giovanny Barrera</small>
</span>
</a>

<nav class="navegacion" aria-label="Navegación principal">
<a href="/blog/">Inicio</a>
<a href="/blog/#historias">Historias</a>
<a href="/blog/#proyecto">El reto</a>
<a href="/blog/#mapa">Mapa de cumbres</a>
<a href="/blog/#sobre-mi">Sobre mí</a>
<a href="/">Excursiones</a>
</nav>

</div>
</header>

<main class="contenedor">

<div class="numero">Cumbre {numero:03d} de 100</div>
<h1>{titulo}</h1>
<div class="fecha">Fecha de ascenso: {fecha}</div>

{presentacion}

<article class="relato">
{cuerpo}
</article>

{galeria_final}
{invitacion}

<div class="volver">
<a href="/blog/">← Volver a las 100 montañas</a>
</div>

</main>

<footer>
<div class="contenedor">
Una pausa en tu viaje · Prealpes bávaros
</div>
</footer>

<div class="lightbox" id="visor" role="dialog"
aria-label="Fotografía ampliada"
aria-modal="true" aria-hidden="true">
<button class="lightbox-cerrar" id="visor-cerrar"
type="button" aria-label="Cerrar fotografía">×</button>
<img id="visor-foto" alt="">
</div>

{SCRIPT_LIGHTBOX}

</body>
</html>'''

    destino = SALIDA / historia['slug'] / 'index.html'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding='utf-8')



def crear_tarjeta(historia):
    titulo = seguro(historia['titulo'])
    numero = historia['numero']
    fecha = seguro(historia['fecha'])
    publicada = historia['publicado']

    imagen_html = ''

    if historia['imagen']:
        src = seguro(url_imagen(historia['imagen']))
        imagen_html = (
            f'<img src="{src}" alt="{titulo}" loading="lazy">'
        )

    contenido = f'''
<div class="story-content">
<div class="story-number">Cumbre {numero:03d} de 100</div>
<h3>{titulo}</h3>
<p>{fecha}</p>
<span class="story-link">
{"Leer la historia" if publicada else "Historia en preparación"}
</span>
</div>'''

    if publicada:
        enlace = f"/blog/cumbres/{historia['slug']}/"
        interior = (
            f'<a href="{enlace}">'
            f'{imagen_html}{contenido}'
            '</a>'
        )
    else:
        interior = imagen_html + contenido

    return f'''
<article class="story-card">
{interior}
</article>'''


def actualizar_portada(historias, cumbres):
    html = PORTADA.read_text(encoding='utf-8')

    tarjetas = '\n'.join(
        crear_tarjeta(h)
        for h in historias
    )

    if not tarjetas:
        tarjetas = (
            '<div class="empty-state">'
            '<h3>Las primeras historias llegarán pronto.</h3>'
            '<p>Este diario irá reuniendo las experiencias '
            'y fotografías de cada cumbre.</p>'
            '</div>'
        )

    if INICIO in html and FIN in html:
        patron = re.escape(INICIO) + r'.*?' + re.escape(FIN)

        html = re.sub(
            patron,
            lambda m: INICIO + '\n' + tarjetas + '\n' + FIN,
            html,
            flags=re.DOTALL
        )
    else:
        apertura = '<div class="stories-grid" id="stories-grid">'

        if apertura not in html:
            raise ValueError(
                'No se encontró stories-grid en blog/index.html'
            )

        comienzo = html.index(apertura) + len(apertura)

        cierre = html.find(
            '\n        </div>\n\n      </div>\n    </section>',
            comienzo
        )

        if cierre == -1:
            raise ValueError(
                'No se encontró el cierre de la sección'
            )

        html = (
            html[:comienzo]
            + '\n' + INICIO
            + '\n' + tarjetas
            + '\n' + FIN
            + html[cierre:]
        )

    # El progreso cuenta cumbres realizadas,
    # no solamente relatos publicados.
    cantidad = sum(
        1 for c in cumbres
        if c['realizada']
    )

    html = re.sub(
        r'(<span id="summit-count">).*?(</span>)',
        lambda m: m.group(1) + str(cantidad) + m.group(2),
        html,
        count=1,
        flags=re.DOTALL
    )

    porcentaje = min(cantidad, 100)

    def actualizar_progreso(m):
        etiqueta = m.group(0)

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

            if nuevo:
                nuevo = nuevo.rstrip(';') + '; '

            nuevo += f'width: {porcentaje}%'

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
        actualizar_progreso,
        html,
        count=1
    )

    # Preparar los datos para el mapa.
    datos_mapa = []

    for c in cumbres:
        if not c['realizada']:
            continue

        datos_mapa.append({
            'numero': c['numero'],
            'nombre': c['titulo'],
            'lat': c['latitud'],
            'lon': c['longitud'],
            'altitud': c['altitud'],
            'distancia': c['distancia'],
            'desnivel': c['desnivel'],
            'url': (
                f"/blog/cumbres/{c['slug']}/"
                if c['publicado']
                else ''
            )
        })

    # JSON seguro para insertarlo dentro de JavaScript.
    datos_json = json.dumps(
        datos_mapa,
        ensure_ascii=False
    ).replace('<', '\\u003c')

    patron_datos = (
        r'const\s+cumbres\s*=\s*\[[\s\S]*?\]\s*;'
    )

    if not re.search(patron_datos, html):
        raise ValueError(
            'No se encontró const cumbres = [...] '
            'en blog/index.html'
        )

    html = re.sub(
        patron_datos,
        lambda m: 'const cumbres = ' + datos_json + ';',
        html,
        count=1
    )

    PORTADA.write_text(
        html,
        encoding='utf-8'
    )


def main():
    registros = []

    if HISTORIAS.exists():
        for archivo in sorted(HISTORIAS.glob('*.md')):
            historia = leer_historia(archivo)

            if historia is not None:
                registros.append(historia)

    registros.sort(
        key=lambda h: h['numero']
    )

    numeros = [
        h['numero']
        for h in registros
    ]

    if len(numeros) != len(set(numeros)):
        raise ValueError(
            'Hay dos registros con el mismo número de cumbre.'
        )

    # Solamente las historias publicadas generan artículos.
    historias = [
        r for r in registros
        if r['publicado']
    ]

    if SALIDA.exists():
        shutil.rmtree(SALIDA)

    SALIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    for historia in historias:
        crear_articulo(historia)

    actualizar_portada(
        historias,
        registros
    )

    realizadas = sum(
        1 for r in registros
        if r['realizada']
    )

    print(
        f'Blog generado: {len(historias)} historias '
        f'publicadas y {realizadas} cumbres realizadas.'
    )


if __name__ == '__main__':
    main()
