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

IDIOMAS = ('es', 'de', 'en')

ETIQUETAS = {
    'es': {
        'ficha': 'Ficha técnica de la ruta',
        'galeria': 'Más fotografías de esta montaña',
        'volver': '← Volver a las 100 montañas',
        'fecha': 'Fecha de ascenso',
        'cumbre': 'Cumbre',
        'de': 'de',
        'leer': 'Leer la historia',
        'inicio': 'Inicio',
        'historias': 'Historias',
        'reto': 'El reto',
        'mapa': 'Mapa de cumbres',
        'sobre': 'Sobre mí',
        'excursiones': 'Excursiones',
        'ampliar': 'Ampliar fotografía',
        'cerrar': 'Cerrar fotografía'
    },
    'de': {
        'ficha': 'Tourendaten',
        'galeria': 'Weitere Fotos von diesem Berg',
        'volver': '← Zurück zu den 100 Bergen',
        'fecha': 'Datum der Wanderung',
        'cumbre': 'Gipfel',
        'de': 'von',
        'leer': 'Geschichte lesen',
        'inicio': 'Startseite',
        'historias': 'Geschichten',
        'reto': 'Die Herausforderung',
        'mapa': 'Gipfelkarte',
        'sobre': 'Über mich',
        'excursiones': 'Wanderungen',
        'ampliar': 'Foto vergrößern',
        'cerrar': 'Foto schließen'
    },
    'en': {
        'ficha': 'Hike details',
        'galeria': 'More photographs of this mountain',
        'volver': '← Back to the 100 mountains',
        'fecha': 'Date of ascent',
        'cumbre': 'Summit',
        'de': 'of',
        'leer': 'Read the story',
        'inicio': 'Home',
        'historias': 'Stories',
        'reto': 'The challenge',
        'mapa': 'Summit map',
        'sobre': 'About me',
        'excursiones': 'Guided hikes',
        'ampliar': 'Enlarge photograph',
        'cerrar': 'Close photograph'
    }
}


def ruta_articulo(historia, idioma='es'):
    prefijo = (
        '/blog/cumbres/'
        if idioma == 'es'
        else f'/blog/{idioma}/cumbres/'
    )

    return f"{prefijo}{historia['slug']}/"


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


def texto_traduccion(datos, clave):
    """Obtiene un campo de traducción sin alterar su contenido."""
    valor = datos.get(clave)

    if valor is None:
        return ''

    return str(valor).strip()


def traducciones_historia(datos, cuerpo_original):
    """
    Organiza el contenido de una historia en tres idiomas.

    El español procede del cuerpo principal del archivo Markdown.

    Las traducciones se guardan en los campos:
        title_de
        contenido_de
        title_en
        contenido_en

    Una traducción se considera disponible cuando
    tiene contenido y título.
    """

    traducciones = {
        'es': {
            'titulo': str(datos.get('title') or '').strip(),
            'markdown': cuerpo_original.strip(),
            'disponible': True
        }
    }

    for idioma in ('de', 'en'):
        titulo = texto_traduccion(
            datos,
            f'title_{idioma}'
        )

        contenido = texto_traduccion(
            datos,
            f'contenido_{idioma}'
        )

        traducciones[idioma] = {
            'titulo': titulo,
            'markdown': contenido,
            'disponible': bool(titulo and contenido)
        }

    return traducciones

def normalizar_estructura_narrativa(contenido):
    """Separa párrafos narrativos y códigos editoriales."""

    patron = re.compile(
        r'\[\[[^\[\]\n]+\]\]|\[[^\[\]\n]+\]'
    )

    resultado = []

    for linea in contenido.split('\n'):
        coincidencias = list(patron.finditer(linea))

        if not coincidencias:
            resultado.append(linea)
            continue

        resto = patron.sub('', linea)

        if resto.strip():
            resultado.append(linea)
            continue

        bloques = []

        for coincidencia in coincidencias:
            pieza = coincidencia.group(0)

            if pieza.startswith('[['):
                bloques.append(pieza)
            else:
                bloques.append(pieza[1:-1].strip())

        resultado.append('\n\n'.join(bloques))

    return '\n'.join(resultado)


def separar_codigos_editoriales(contenido):
    """Coloca los códigos editoriales en párrafos independientes."""

    patron = re.compile(
        r'(\[\[(?:foto|fotos|mediana|grande|izquierda|derecha|'
        r'cita|destacado|entradilla|nota|epigrafe|capitulo|'
        r'centrado|separador)(?::[^\]\n]*)?\]\])',
        flags=re.IGNORECASE
    )

    return patron.sub(r'\n\n\1\n\n', contenido)
    
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

    cuerpo_original = partes[2].strip()

    traducciones = traducciones_historia(
        datos,
        cuerpo_original
    )

    for idioma, traduccion in traducciones.items():
        if traduccion['disponible']:
            traduccion['cuerpo'] = markdown.markdown(
                normalizar_estructura_narrativa(traduccion['markdown']),
                extensions=['extra', 'sane_lists']
            )
        else:
            traduccion['cuerpo'] = ''

    cuerpo = traducciones['es']['cuerpo']

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
        desnivel=numero_decimal(datos.get('desnivel')),
        traducciones=traducciones
    )
def crear_ficha(historia, idioma='es'):
    """Genera la ficha técnica en el idioma seleccionado."""

    if not historia['ficha']:
        return ''

    etiquetas_ficha = {
        'es': {
            'Altitud': 'Altitud',
            'Desnivel +': 'Desnivel +',
            'Distancia': 'Distancia',
            'Duración': 'Duración',
            'Dificultad': 'Dificultad',
            'Acceso': 'Acceso'
        },
        'de': {
            'Altitud': 'Höhe',
            'Desnivel +': 'Höhenmeter +',
            'Distancia': 'Strecke',
            'Duración': 'Dauer',
            'Dificultad': 'Schwierigkeit',
            'Acceso': 'Anreise'
        },
        'en': {
            'Altitud': 'Elevation',
            'Desnivel +': 'Elevation gain',
            'Distancia': 'Distance',
            'Duración': 'Duration',
            'Dificultad': 'Difficulty',
            'Acceso': 'Getting there'
        }
    }

    traducciones = etiquetas_ficha.get(
        idioma,
        etiquetas_ficha['es']
    )

    datos = ''.join(
        f'<div class="dato">'
        f'<span>{seguro(traducciones.get(e, e))}</span>'
        f'<strong>{seguro(v)}</strong>'
        f'</div>'
        for e, v in historia['ficha']
    )

    titulo = ETIQUETAS[idioma]['ficha']

    return (
        '<section class="ficha">'
        '<div class="ficha-titulo">'
        f'{seguro(titulo)}'
        '</div>'
        f'<div class="ficha-datos">{datos}</div>'
        '</section>'
    )


def preparar_elementos_editoriales(cuerpo):
    """
    Convierte los códigos editoriales de Pages CMS en HTML.

    Los códigos funcionan igual en los tres idiomas:

    [[cita:Texto]]
    [[destacado:Texto]]
    [[entradilla:Texto]]
    [[nota:Texto]]
    [[epigrafe:Texto]]
    [[capitulo:Texto]]
    [[centrado:Texto]]
    [[separador]]
    """

    patrones = {
        'cita': ('cita-editorial', 'blockquote'),
        'destacado': ('destacado-editorial', 'aside'),
        'entradilla': ('entradilla-editorial', 'div'),
        'nota': ('nota-editorial', 'aside'),
        'epigrafe': ('epigrafe-editorial', 'p'),
        'capitulo': ('capitulo-editorial', 'h2'),
        'centrado': ('centrado-editorial', 'p')
    }

    def sustituir(m):
        tipo = m.group(1).lower()

        if tipo == 'separador':
            return '<hr class="separador-editorial">'

        texto = seguro((m.group(2) or '').strip())
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


def preparar_relato(historia, idioma='es'):
    """
    Prepara el relato y sus fotografías.

    Las imágenes y la galería se comparten entre idiomas.

    Cada traducción conserva sus propios códigos
    editoriales y puede colocar las fotografías
    en posiciones diferentes dentro del texto.
    """

    galeria = historia['galeria']
    utilizadas = set()

    traduccion = historia['traducciones'].get(idioma)

    if not traduccion or not traduccion['disponible']:
        return '', ''

    cuerpo_original = traduccion['cuerpo']

    titulo = traduccion['titulo']

    clases = {
        'foto': 'foto-mediana',
        'mediana': 'foto-mediana',
        'grande': 'foto-grande',
        'izquierda': 'foto-izquierda',
        'derecha': 'foto-derecha'
    }

    def crear_foto(indice, modo='foto'):
        if indice < 1 or indice > len(galeria):
            mensajes = {
                'es': 'Fotografía no encontrada.',
                'de': 'Foto nicht gefunden.',
                'en': 'Photograph not found.'
            }

            return (
                '<p>'
                + mensajes.get(idioma, mensajes['es'])
                + '</p>'
            )

        utilizadas.add(indice)

        src = seguro(
            url_imagen(galeria[indice - 1])
        )

        titulo_seguro = seguro(titulo)
        clase = clases.get(modo, 'foto-mediana')

        ampliar = seguro(
            ETIQUETAS[idioma]['ampliar']
        )

        return (
            f'<figure class="foto-relato {clase}">'
            f'<a href="{src}" class="ampliar" '
            f'data-lightbox '
            f'aria-label="{ampliar} {indice}">'
            f'<img src="{src}" '
            f'alt="{titulo_seguro} - {indice}" '
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
                + ''.join(
                    crear_foto(i)
                    for i in indices
                )
                + '</div>'
            )

        return crear_foto(indices[0], modo)

    patron = (
        r'<p>\s*\[\['
        r'(foto|fotos|mediana|izquierda|derecha|grande):\s*'
        r'([0-9, ]+)\]\]\s*</p>'
    )

    cuerpo = re.sub(
        patron,
        reemplazar,
        cuerpo_original,
        flags=re.IGNORECASE
    )

    cuerpo = preparar_elementos_editoriales(cuerpo)

    # La fotografía principal no se repite
    # automáticamente en la galería final.

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

        titulo_galeria = seguro(
            ETIQUETAS[idioma]['galeria']
        )

        galeria_final = (
            '<section class="galeria-final">'
            f'<h2>{titulo_galeria}</h2>'
            f'<div class="grupo-fotos">{fotos}</div>'
            '</section>'
        )

    return cuerpo, galeria_final


def crear_invitacion(idioma='es'):
    """Invitación opcional a las excursiones guiadas."""

    if not MOSTRAR_EXCURSIONES:
        return ''

    textos = {
        'es': {
            'titulo': (
                'Algunas montañas también podemos '
                'descubrirlas juntos.'
            ),
            'descripcion': (
                'Descubre nuestras caminatas por los '
                'Prealpes bávaros. Grupos pequeños, '
                'naturaleza y tiempo para disfrutar '
                'de cada paisaje.'
            ),
            'boton': 'Descubrir las excursiones'
        },
        'de': {
            'titulo': (
                'Manche Berge können wir auch '
                'gemeinsam entdecken.'
            ),
            'descripcion': (
                'Entdecke unsere geführten Wanderungen '
                'in den bayerischen Voralpen. Kleine '
                'Gruppen, Natur und genügend Zeit, '
                'um die Landschaft zu genießen.'
            ),
            'boton': 'Wanderungen entdecken'
        },
        'en': {
            'titulo': (
                'Some mountains are even better '
                'discovered together.'
            ),
            'descripcion': (
                'Discover our guided hikes in the '
                'Bavarian Prealps. Small groups, '
                'beautiful landscapes and plenty '
                'of time to enjoy nature.'
            ),
            'boton': 'Explore our guided hikes'
        }
    }

    texto = textos.get(idioma, textos['es'])

    return (
        '<section class="invitacion">'
        f'<h2>{seguro(texto["titulo"])}</h2>'
        f'<p>{seguro(texto["descripcion"])}</p>'
        f'<a class="boton" href="/">'
        f'{seguro(texto["boton"])}'
        '</a>'
        '</section>'
    )
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

/* FOTOGRAFÍA Y FICHA TÉCNICA */

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

/* RELATO */

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

/* FOTOGRAFÍAS DENTRO DEL RELATO */

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

/* INVITACIÓN A EXCURSIONES */

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

/* VISOR DE FOTOGRAFÍAS */

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

/* SELECTOR DE IDIOMAS */

.selector-idiomas {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 7px;
  margin: 24px 0 34px;
  font-family: Arial, sans-serif;
}

.selector-idiomas a,
.selector-idiomas span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  min-height: 34px;
  padding: 5px 9px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  text-decoration: none;
}

.selector-idiomas a {
  color: #627269;
  border: 1px solid #d7dfd0;
  background: transparent;
  transition:
    background .2s ease,
    color .2s ease;
}

.selector-idiomas a:hover {
  background: #eeefe3;
  color: #1f4033;
}

.selector-idiomas .idioma-activo {
  background: #1f4033;
  border: 1px solid #1f4033;
  color: white;
}

.selector-idiomas .idioma-no-disponible {
  color: #a8afa5;
  border: 1px solid #e6e8de;
  opacity: .6;
  cursor: not-allowed;
}

.selector-idiomas a:focus-visible {
  outline: 2px solid #b9a47b;
  outline-offset: 3px;
}

/* PANTALLAS PEQUEÑAS */

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

  .selector-idiomas {
    justify-content: flex-start;
    margin: 18px 0 28px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
  }
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
      foto.alt = enlace.querySelector('img')?.alt || '';
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


def crear_selector_idiomas(historia, idioma_actual):
    """Enlaza únicamente las traducciones disponibles."""

    elementos = []

    for idioma in IDIOMAS:
        traduccion = historia['traducciones'][idioma]
        codigo = idioma.upper()

        if idioma == idioma_actual:
            elementos.append(
                f'<span class="idioma-activo" '
                f'aria-current="page">{codigo}</span>'
            )

        elif traduccion['disponible']:
            url = seguro(ruta_articulo(historia, idioma))

            elementos.append(
                f'<a href="{url}" '
                f'lang="{idioma}" '
                f'aria-label="{codigo}">{codigo}</a>'
            )

        else:
            elementos.append(
                f'<span class="idioma-no-disponible" '
                f'aria-label="{codigo} no disponible" '
                f'title="Traducción pendiente">'
                f'{codigo}</span>'
            )

    return (
        '<nav class="selector-idiomas" '
        'aria-label="Seleccionar idioma">'
        + ''.join(elementos)
        + '</nav>'
    )


# Copiá aquí la Site Key PÚBLICA de Turnstile (nunca la Secret Key).
TURNSTILE_SITE_KEY = '0x4AAAAAAGHEiH-CdG-pin6w'
COMENTARIOS_API = 'https://blog-comentarios-api.ybarrerao.workers.dev/api/comentarios'


ESTILOS_NAVEGACION = '''
.navegacion-historias {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin: 15px 0 0;
  font-family: Arial, sans-serif;
}

.navegacion-historias a {
  display: inline-block;
  padding: 11px 18px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.boton-siguiente {
  background: #1f4033;
  color: white;
}

.boton-siguiente:hover {
  background: #345e49;
}

.boton-inicio {
  border: 1px solid #b8c6b7;
  color: #1f4033;
  background: transparent;
}

.boton-inicio:hover {
  background: #eeefe3;
}
'''

ESTILOS_COMENTARIOS = '''
.comentarios-blog {
  margin: 20px 0 25px;
  padding-top: 0;
  font-family: Arial, sans-serif;
  line-height: 1.6;
}

.comentarios-blog h2 {
  color: #1f4033;
  font: normal 30px Georgia, serif;
}

/* FORMULARIO MÁS COMPACTO */

.comentarios-blog form {
  max-width: 650px;
  display: grid;
  gap: 10px;
  padding: 18px 22px 12px;
  border-radius: 12px;
  background: #eeefe3;
  align-content: start;
}

.comentarios-blog input,
.comentarios-blog textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 12px;
  font: 15px Arial, sans-serif;
  border: 1px solid #9aaa9d;
  border-radius: 6px;
  background: white;
}

.comentarios-blog button {
  justify-self: start;
  background: #708B76;
  color: white;
  border: 0;
  border-radius: 6px;
  padding: 11px 20px;
  cursor: pointer;
}

.comentarios-blog button:disabled {
  opacity: .5;
  cursor: wait;
}

/* COMENTARIOS */

.comentario-blog {
  border-bottom: 1px solid #dfe5da;
  padding: 18px 0;
  overflow-wrap: anywhere;
}

.comentario-blog p {
  white-space: pre-wrap;
  margin: 8px 0 12px;
}

.comentario-blog small,
.comentarios-blog .nota-privacidad {
  color: #596e60;
  font-size: 12px;
}

.comentario-blog.respuesta {
  margin-left: 24px;
  padding-left: 16px;
  border-left: 2px solid #b9cbb8;
}

/* FECHA Y ACCIONES EN UNA MISMA FILA */

.comentario-acciones {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 8px;
}

.comentario-acciones small {
  font-size: 12px;
  white-space: nowrap;
}

/* RESPONDER: BOTÓN PRINCIPAL */

.comentarios-blog .comentario-responder {
  padding: 6px 12px;
  font-size: 12px;
  background: #708B76;
  border-radius: 5px;
}

/* VER ORIGINAL: ENLACE DISCRETO */

.comentarios-blog .comentario-idioma {
  margin-left: 4px;
  padding: 4px 0;
  background: transparent;
  border: none;
  border-radius: 0;
  color: #426b56;
  font-size: 12px;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.comentarios-blog .comentario-idioma:hover {
  color: #1f4033;
}

.comentarios-blog .comentario-idioma:focus-visible {
  outline: 2px solid #426b56;
  outline-offset: 4px;
}

/* MENSAJES DEL FORMULARIO */

.comentarios-blog .mensaje {
  min-height: 0;
  margin: 0;
}

.comentarios-blog .mensaje:empty {
  display: none;
}

@media (max-width: 480px) {
  .comentario-acciones {
    gap: 8px;
  }

  .comentarios-blog .comentario-idioma {
    margin-left: 0;
  }

  .comentarios-blog form {
    padding: 16px 16px 12px;
  }
}
'''

def crear_comentarios(historia, idioma='es'):
    # Un mismo hilo de comentarios para las tres traducciones.  
    textos = {
        'es': ('Comentarios', 'Todavía no hay comentarios. ¡Sé el primero!',
               'Tu nombre', 'Tu correo electrónico (opcional, no será público)',
               'Escribe tu comentario', 'Publicar comentario',
               'Puedes dejar tu correo si quieres. No será público.',
               'Cargando comentarios...', 'Comentario publicado.',
               'No se pudo completar la operación.', 'Responder', 'Cancelar respuesta',
               'Respondiendo a', 'Verificación antispam pendiente.',
               'Comentario recibido. Está pendiente de revisión y aparecerá cuando sea aprobado.'),
        'de': ('Kommentare', 'Noch keine Kommentare. Schreib den ersten!',
               'Dein Name', 'Deine E-Mail-Adresse (optional, nicht öffentlich)',
               'Schreib deinen Kommentar', 'Kommentar veröffentlichen',
               'Du kannst deine E-Mail-Adresse freiwillig angeben. Sie wird nicht veröffentlicht.',
               'Kommentare werden geladen...', 'Kommentar veröffentlicht.',
               'Vorgang fehlgeschlagen.', 'Antworten', 'Antwort abbrechen',
               'Antwort an', 'Spam-Schutz noch nicht eingerichtet.',
               'Kommentar erhalten. Er wird geprüft und nach Freigabe veröffentlicht.'),
        'en': ('Comments', 'No comments yet. Be the first!',
               'Your name', 'Your email (optional, not public)',
               'Write your comment', 'Post comment',
               'You can provide your email if you wish. It will not be public.',
               'Loading comments...', 'Comment posted.',
               'Something went wrong.', 'Reply', 'Cancel reply',
               'Replying to', 'Spam protection not configured yet.',
               'Comment received. It is awaiting review and will appear once approved.')
    }
    t = textos[idioma]
    historia_id = json.dumps(historia['slug'])
    api = json.dumps(COMENTARIOS_API)
    site_key = json.dumps(TURNSTILE_SITE_KEY)
    mensajes = json.dumps(t, ensure_ascii=False).replace('<', '\\u003c')
    idioma_js = json.dumps(idioma)
    # Este bloque se inserta en cada artículo; los datos se muestran como texto,
    # nunca como HTML, para impedir inyección de código en los comentarios.
    plantilla = r'''
<section class="comentarios-blog" id="comentarios" aria-label="__TITLE__">
  <h2>__TITLE__</h2>
  <div id="lista-comentarios" aria-live="polite">__LOADING__</div>
  <form id="form-comentario">
    <div id="respuesta-actual" hidden></div>
    <input name="nombre" autocomplete="name" maxlength="80" minlength="2" required placeholder="__NAME__" aria-label="__NAME__">
    <input name="correo" type="email" autocomplete="email" maxlength="254" placeholder="__EMAIL__" aria-label="__EMAIL__">
    <textarea name="contenido" rows="5" minlength="3" maxlength="2000" required placeholder="__CONTENT__" aria-label="__CONTENT__"></textarea>
    <div id="turnstile-comentarios"></div>
    <small class="nota-privacidad">__PRIVACY__</small>
    <button id="enviar-comentario" type="submit">__SEND__</button>
    <p class="mensaje" id="estado-comentario" role="status" aria-live="polite"></p>
  </form>
</section>
<script>
(() => {
  const API = __API__;
  const HISTORIA = __HISTORIA__;
  const IDIOMA = __IDIOMA__;
  const SITE_KEY = __SITE_KEY__;
  const T = __TEXTOS__;
  const lista = document.getElementById('lista-comentarios');
  const form = document.getElementById('form-comentario');
  const estado = document.getElementById('estado-comentario');
  const boton = document.getElementById('enviar-comentario');
  const aviso = document.getElementById('respuesta-actual');
  let padre = null;
  let widgetId = null;

  function elemento(tag, texto, clase) {
    const nodo = document.createElement(tag);
    if (texto !== undefined) nodo.textContent = texto;
    if (clase) nodo.className = clase;
    return nodo;
  }

  function responder(id, nombre) {
    padre = id;
    aviso.hidden = false;
    aviso.replaceChildren(elemento('span', T[12] + ' ' + nombre + ' '));
    const cancelar = elemento('button', T[11]);
    cancelar.type = 'button';
    cancelar.addEventListener('click', () => {
      padre = null;
      aviso.hidden = true;
    });
    aviso.append(cancelar);
    form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    form.elements.contenido.focus();
  }

  function dibujar(comentarios) {
    lista.replaceChildren();
    if (!comentarios.length) {
      lista.append(elemento('p', T[1]));
      return;
    }
    const porPadre = new Map();
    const ids = new Set(comentarios.map(c => c.id));
    comentarios.forEach(c => {
      const clave = c.comentario_padre_id && ids.has(c.comentario_padre_id)
        ? c.comentario_padre_id : 0;
      if (!porPadre.has(clave)) porPadre.set(clave, []);
      porPadre.get(clave).push(c);
    });
    const vistos = new Set();
    function pintar(idPadre, contenedor, nivel) {
      (porPadre.get(idPadre) || []).forEach(c => {
        if (vistos.has(c.id)) return;
        vistos.add(c.id);
        const item = elemento('article', undefined,
          'comentario-blog' + (nivel ? ' respuesta' : ''));


item.append(elemento('strong', c.nombre));

const hayTraduccion =
  Boolean(c.contenido_traducido) &&
  c.idioma !== IDIOMA;

const textoComentario = elemento(
  'p',
  hayTraduccion
    ? c.contenido_traducido
    : c.contenido
);

item.append(textoComentario);

// Fila para fecha y acciones
const acciones = elemento(
  'div',
  undefined,
  'comentario-acciones'
);

// Fecha de publicación
acciones.append(
  elemento('small', c.fecha_creacion || '')
);

// Botón responder
const accion = elemento('button', T[10]);
accion.type = 'button';
accion.className = 'comentario-responder';

accion.addEventListener(
  'click',
  () => responder(c.id, c.nombre)
);

acciones.append(accion);

// Alternar traducción y texto original
if (hayTraduccion) {
  const textosIdioma = {
    es: ['Ver original', 'Ver traducción'],
    de: ['Original anzeigen', 'Übersetzung anzeigen'],
    en: ['View original', 'View translation']
  };

  const etiquetas = textosIdioma[IDIOMA] || textosIdioma.es;

  const botonIdioma = elemento(
    'button',
    etiquetas[0]
  );

  botonIdioma.type = 'button';
  botonIdioma.className = 'comentario-idioma';

  let mostrandoOriginal = false;

  botonIdioma.addEventListener('click', () => {
    mostrandoOriginal = !mostrandoOriginal;

    textoComentario.textContent = mostrandoOriginal
      ? c.contenido
      : c.contenido_traducido;

botonIdioma.textContent =
  (
        mostrandoOriginal
          ? etiquetas[1]
          : etiquetas[0]
      );
  });

  acciones.append(botonIdioma);
}

item.append(acciones);
contenedor.append(item);
        pintar(c.id, contenedor, nivel + 1);
      });
    }
    pintar(0, lista, 0);
  }

async function cargar() {
  try {
    const respuesta = await fetch(
      API +
      '?historia=' + encodeURIComponent(HISTORIA) +
      '&idioma=' + encodeURIComponent(IDIOMA)
    );

    if (!respuesta.ok) {
      throw new Error('HTTP ' + respuesta.status);
    }

    const datos = await respuesta.json();
    dibujar(datos.comentarios || []);

  } catch (e) {
    lista.textContent = T[9];
  }
}

  function activarTurnstile() {
    if (!SITE_KEY || SITE_KEY === 'PEGAR_AQUI_SITE_KEY_PUBLICA') {
      boton.disabled = true;
      estado.textContent = T[13];
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.onload = () => {
      widgetId = window.turnstile.render('#turnstile-comentarios', {
        sitekey: SITE_KEY,
        theme: 'auto'
      });
    };
    script.onerror = () => {
      boton.disabled = true;
      estado.textContent = T[9];
    };
    document.head.append(script);
  }

  form.addEventListener('submit', async evento => {
    evento.preventDefault();
    if (widgetId === null || !window.turnstile) return;
    const token = window.turnstile.getResponse(widgetId);
    if (!token) {
      estado.textContent = T[13];
      return;
    }
    boton.disabled = true;
    estado.textContent = '';
    try {
      const respuesta = await fetch(API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          historia: HISTORIA,
          idioma: IDIOMA,
          nombre: form.elements.nombre.value.trim(),
          correo: form.elements.correo.value.trim(),
          contenido: form.elements.contenido.value.trim(),
          comentario_padre_id: padre,
          turnstileToken: token
        })
      });
      const datos = await respuesta.json();
      if (!respuesta.ok) throw new Error(datos.error || T[9]);
      form.elements.contenido.value = '';
      padre = null;
      aviso.hidden = true;
      estado.textContent = datos.pendiente ? T[14] : T[8];
      await cargar();
    } catch (e) {
      estado.textContent = e.message || T[9];
    } finally {
      window.turnstile.reset(widgetId);
      boton.disabled = false;
    }
  });

  cargar();
  activarTurnstile();
})();
</script>
'''
    reemplazos = {
        '__TITLE__': seguro(t[0]), '__LOADING__': seguro(t[7]),
        '__NAME__': seguro(t[2]), '__EMAIL__': seguro(t[3]),
        '__CONTENT__': seguro(t[4]), '__PRIVACY__': seguro(t[6]),
        '__SEND__': seguro(t[5]), '__API__': api,
        '__HISTORIA__': historia_id, '__IDIOMA__': idioma_js,
        '__SITE_KEY__': site_key, '__TEXTOS__': mensajes
    }
    for clave, valor in reemplazos.items():
        plantilla = plantilla.replace(clave, valor)
    return plantilla


def crear_navegacion_historias(historia, idioma='es'):
    """Enlaces a la siguiente historia publicada y a la portada."""

    etiquetas = {
        'es': ('Siguiente historia →', 'Inicio'),
        'de': ('Nächste Geschichte →', 'Startseite'),
        'en': ('Next story →', 'Home')
    }

    siguiente_texto, inicio_texto = etiquetas[idioma]

    siguiente = historia.get('siguiente', {}).get(idioma)

    boton_siguiente = ''

    if siguiente:
        boton_siguiente = (
            f'<a class="boton-siguiente" '
            f'href="{seguro(siguiente)}">'
            f'{seguro(siguiente_texto)}</a>'
        )

    return (
        '<nav class="navegacion-historias">'
        + boton_siguiente
        + f'<a class="boton-inicio" href="/blog/">'
        + f'{seguro(inicio_texto)}</a>'
        + '</nav>'
    )

def crear_articulo(historia, idioma='es'):
    """Genera una versión de la historia en el idioma indicado."""

    traduccion = historia['traducciones'][idioma]

    if not traduccion['disponible']:
        return

    textos = ETIQUETAS[idioma]

    titulo = seguro(traduccion['titulo'])
    numero = historia['numero']
    fecha = seguro(historia['fecha'])

    ficha = crear_ficha(historia, idioma)
    cuerpo, galeria_final = preparar_relato(historia, idioma)
    invitacion = crear_invitacion(idioma)
    selector = crear_selector_idiomas(historia, idioma)

    comentarios = crear_comentarios(historia, idioma)
    navegacion_historias = crear_navegacion_historias(historia, idioma)
    portada = ''

    if historia['imagen']:
        src = seguro(url_imagen(historia['imagen']))

        portada = (
            f'<a class="portada-enlace" href="{src}" '
            f'data-lightbox '
            f'aria-label="{seguro(textos["ampliar"])}">'
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

    enlaces_alternativos = '\n'.join(
        (
            f'<link rel="alternate" hreflang="{idioma_alt}" '
            f'href="{seguro(ruta_articulo(historia, idioma_alt))}">'
        )
        for idioma_alt in IDIOMAS
        if historia['traducciones'][idioma_alt]['disponible']
    )

    navegacion = f'''
    <nav class="navegacion" aria-label="Navegación principal">
      <a href="/blog/">{seguro(textos["inicio"])}</a>
      <a href="/blog/#historias">{seguro(textos["historias"])}</a>
      <a href="/blog/#proyecto">{seguro(textos["reto"])}</a>
      <a href="/blog/#mapa">{seguro(textos["mapa"])}</a>
      <a href="/blog/#sobre-mi">{seguro(textos["sobre"])}</a>
      <a href="/">{seguro(textos["excursiones"])}</a>
    </nav>
    '''

    html = f'''<!DOCTYPE html>
<html lang="{idioma}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>{titulo} | {'100 montañas en 365 días' if idioma == 'es' else '100 Berge in 365 Tagen' if idioma == 'de' else '100 Mountains in 365 Days'}</title>

<meta name="follow.it-verification-code" content="k8SzEx5mdNkp8feb9Ck4"/>

<meta name="description"
content="{seguro(f'Ruta de senderismo al {titulo}. Descubrí la experiencia de ascender esta montaña, con fotografías, información de la ruta y un relato personal del desafío de 100 montañas en 365 días.' if idioma == 'es' else f'Wanderung zum {titulo}: persönliche Erfahrungen, Fotos und Informationen zur Route. Teil der Herausforderung 100 Berge in 365 Tagen.' if idioma == 'de' else f'Hiking {titulo}: personal experiences, photos and trail information. Part of the 100 mountains in 365 days challenge.')}">

{enlaces_alternativos}

<style>{ESTILOS}
{ESTILOS_COMENTARIOS}
{ESTILOS_NAVEGACION}</style>
</head>

<body>

<header>
  <div class="contenedor cabecera">

    <a class="marca" href="/blog/">
      <img
        src="/logo-montes-de-gio.png"
        alt="Montes de Gio"
        class="logo-montes">
    </a>

    {navegacion}

  </div>
</header>

<main class="contenedor">

  {selector}

  <div class="numero">
    {seguro(textos['cumbre'])} {numero:03d}
    {seguro(textos['de'])} 100
  </div>

  <h1>{titulo}</h1>

  <div class="fecha">
    {seguro(textos['fecha'])}: {fecha}
  </div>

  {presentacion}

  <article class="relato">
    {cuerpo}
  </article>

  {galeria_final}

  {invitacion}

  {navegacion_historias}

  {comentarios}

  <div class="volver">
  
    <a href="/blog/">
      {seguro(textos['volver'])}
    </a>
  </div>

</main>

<footer>
  <div class="contenedor">
    Una pausa en tu viaje · Prealpes bávaros
  </div>
</footer>

<div class="lightbox"
     id="visor"
     role="dialog"
     aria-label="{seguro(textos['ampliar'])}"
     aria-modal="true"
     aria-hidden="true">

  <button class="lightbox-cerrar"
          id="visor-cerrar"
          type="button"
          aria-label="{seguro(textos['cerrar'])}">
    ×
  </button>

  <img id="visor-foto" alt="">

</div>

{SCRIPT_LIGHTBOX}

</body>
</html>'''

    if idioma == 'es':
        destino = SALIDA / historia['slug'] / 'index.html'
    else:
        destino = (
            BLOG / idioma / 'cumbres'
            / historia['slug'] / 'index.html'
        )

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding='utf-8')
def crear_tarjeta(historia, idioma='es'):
    """
    Genera una tarjeta para la portada del blog.

    Mantiene la estructura HTML original para conservar
    el diseño, el carrusel y los enlaces existentes.

    Si hay traducción disponible, utiliza el título
    y el enlace correspondientes al idioma solicitado.
    """

    numero = historia['numero']
    fecha = seguro(historia['fecha'])
    publicada = historia['publicado']

    traduccion = historia['traducciones'].get(idioma)

    # Si la traducción no está disponible,
    # utilizamos la versión española.
    if not traduccion or not traduccion['disponible']:
        idioma_tarjeta = 'es'
        traduccion = historia['traducciones']['es']
    else:
        idioma_tarjeta = idioma

    titulo = seguro(traduccion['titulo'])

    imagen_html = ''

    if historia['imagen']:
        src = seguro(url_imagen(historia['imagen']))

        imagen_html = (
            f'<img src="{src}" '
            f'alt="{titulo}" '
            f'loading="lazy">'
        )

    textos_tarjeta = {
        'es': {
            'cumbre': 'Cumbre',
            'de': 'de',
            'leer': 'Leer la historia',
            'preparacion': 'Historia en preparación'
        },
        'de': {
            'cumbre': 'Gipfel',
            'de': 'von',
            'leer': 'Geschichte lesen',
            'preparacion': 'Geschichte in Vorbereitung'
        },
        'en': {
            'cumbre': 'Summit',
            'de': 'of',
            'leer': 'Read the story',
            'preparacion': 'Story coming soon'
        }
    }

    textos = textos_tarjeta.get(
        idioma_tarjeta,
        textos_tarjeta['es']
    )

    estado = (
        textos['leer']
        if publicada
        else textos['preparacion']
    )

    contenido = f'''
<div class="story-content">

  <div class="story-number">
    {textos['cumbre']} {numero:03d}
    {textos['de']} 100
  </div>

  <h3>{titulo}</h3>

  <p>{fecha}</p>

  <span class="story-link">
    {estado}
  </span>

</div>'''

    if publicada:
        enlace = seguro(
            ruta_articulo(historia, idioma_tarjeta)
        )

        interior = (
            f'<a href="{enlace}">'
            f'{imagen_html}'
            f'{contenido}'
            '</a>'
        )
    else:
        interior = imagen_html + contenido

    return f'''
<article class="story-card">
{interior}
</article>'''
def actualizar_portada(historias, cumbres):
    """
    Actualiza la portada principal del blog.

    Conserva:
    - Las tarjetas de las historias.
    - El contador de cumbres realizadas.
    - La barra de progreso.
    - Los datos del mapa interactivo.
    """

    html = PORTADA.read_text(encoding='utf-8')

        # Verificación de propiedad para Follow.it
    etiqueta_followit = (
        '<meta name="follow.it-verification-code" '
        'content="k8SzEx5mdNkp8feb9Ck4"/>'
    )

    if 'name="follow.it-verification-code"' not in html:
        html = html.replace(
            '</head>',
            etiqueta_followit + '\n</head>',
            1
        )

    # Generar las tarjetas de las historias.
    # La portada principal sigue utilizando español.

    tarjetas = '\n'.join(
        crear_tarjeta(h, 'es')
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

    # Sustituir únicamente el bloque de historias.
    # No modificar el resto de la portada.

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

    # CONTADOR DE CUMBRES REALIZADAS

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

    # BARRA DE PROGRESO

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

    # DATOS DEL MAPA INTERACTIVO

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
                ruta_articulo(c, 'es')
                if c['publicado']
                else ''
            )
        })

    # Convertir los datos a JSON seguro para JavaScript.

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

def generar_sitemap(historias):
    """Genera automáticamente el sitemap del sitio."""

    from xml.etree import ElementTree as ET

    dominio = 'https://prealpes.pages.dev'

    raiz = ET.Element(
        'urlset',
        xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'
    )

    def agregar_url(ruta):
        elemento = ET.SubElement(raiz, 'url')
        ET.SubElement(elemento, 'loc').text = dominio + ruta

    # Página principal y portada del blog.
    agregar_url('/blog/')

    # Artículos publicados en sus idiomas disponibles.
    for historia in historias:
        slug = historia['slug']

        agregar_url(f'/blog/cumbres/{slug}/')

        for idioma in ('de', 'en'):
            if historia['traducciones'][idioma]['disponible']:
                agregar_url(
                    f'/blog/{idioma}/cumbres/{slug}/'
                )

    arbol = ET.ElementTree(raiz)

    ET.indent(arbol, space='  ')

    arbol.write(
        BLOG / 'sitemap.xml',
        encoding='utf-8',
        xml_declaration=True
    )

    print('Sitemap generado correctamente.')

def generar_rss(historias):
    """Genera el RSS de las historias publicadas del blog."""

    from xml.etree import ElementTree as ET
    from email.utils import format_datetime
    from datetime import datetime, timezone

    dominio = 'https://prealpes.pages.dev'

    rss = ET.Element('rss', version='2.0')
    canal = ET.SubElement(rss, 'channel')

    ET.SubElement(canal, 'title').text = (
        'Una pausa en tu camino | 100 montañas en 365 días'
    )
    ET.SubElement(canal, 'link').text = dominio + '/blog/'
    ET.SubElement(canal, 'description').text = (
        'Historias, fotografías y experiencias de montaña '
        'en los Alpes bávaros y sus alrededores.'
    )
    ET.SubElement(canal, 'language').text = 'es'

    # Publicaciones más recientes primero.
    for historia in reversed(historias):
        slug = historia['slug']
        titulo = str(historia['titulo'])
        enlace = f'{dominio}/blog/cumbres/{slug}/'

        item = ET.SubElement(canal, 'item')

        ET.SubElement(item, 'title').text = titulo
        ET.SubElement(item, 'link').text = enlace
        ET.SubElement(item, 'guid', isPermaLink='true').text = enlace

        ET.SubElement(item, 'description').text = (
            f'Nueva historia de montaña: {titulo}. '
            'Descubrí el relato, las fotografías '
            'y la información de la ruta.'
        )

    arbol = ET.ElementTree(rss)
    ET.indent(arbol, space='  ')

    arbol.write(
        BLOG / 'feed.xml',
        encoding='utf-8',
        xml_declaration=True
    )

    print('RSS generado correctamente.')

def main():
    """Lee las historias y genera las páginas publicadas."""

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

    # Solamente las historias publicadas
    # generan páginas individuales.

    historias = [
        r for r in registros
        if r['publicado']
    ]

    # Limpiar páginas generadas anteriormente.

    if SALIDA.exists():
        shutil.rmtree(SALIDA)

    SALIDA.mkdir(
        parents=True,
        exist_ok=True
    )

    # Limpiar también las versiones traducidas antiguas.
    # No borrar otros contenidos de blog/de o blog/en.

    for idioma in ('de', 'en'):
        carpeta = BLOG / idioma / 'cumbres'

        if carpeta.exists():
            shutil.rmtree(carpeta)

    # CALCULAR LA SIGUIENTE HISTORIA DISPONIBLE POR IDIOMA

    for indice, historia in enumerate(historias):
        historia['siguiente'] = {}

        for idioma in IDIOMAS:
            for proxima in historias[indice + 1:]:
                if proxima['traducciones'][idioma]['disponible']:
                    historia['siguiente'][idioma] = ruta_articulo(
                        proxima, idioma
                    )
                    break

    # GENERAR ARTÍCULOS EN LOS IDIOMAS DISPONIBLES

    total_traducciones = {
        'de': 0,
        'en': 0
    }

    for historia in historias:
        # El español siempre es la versión original.
        crear_articulo(historia, 'es')

        for idioma in ('de', 'en'):
            if historia['traducciones'][idioma]['disponible']:
                crear_articulo(historia, idioma)
                total_traducciones[idioma] += 1
    # GENERAR SITEMAP PARA GOOGLE
    generar_sitemap(historias)

    # GENERAR RSS PARA LOS SEGUIDORES
    generar_rss(historias)
    
    # ACTUALIZAR PORTADA, CONTADOR Y MAPA

    actualizar_portada(
        [r for r in registros if r['realizada']],
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

    print(
        f'Traducciones: '
        f'{total_traducciones["de"]} en alemán y '
        f'{total_traducciones["en"]} en inglés.'
    )


if __name__ == '__main__':
    main()
