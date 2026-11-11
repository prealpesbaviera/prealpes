
from pathlib import Path
from html import escape
from urllib.parse import quote
import re
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
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '-', texto.lower()).strip('-') or 'montana'


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


def leer_historia(archivo):
    contenido = archivo.read_text(encoding='utf-8')
    partes = re.split(r'^---\s*$', contenido, maxsplit=2, flags=re.MULTILINE)
    if len(partes) < 3:
        return None
    datos = yaml.safe_load(partes[1]) or {}
    if not isinstance(datos, dict):
        return None
    if str(datos.get('estado', '')).strip().lower() != 'publicado':
        return None
    titulo = str(datos.get('title') or '').strip()
    try:
        numero = int(datos.get('numero'))
    except (ValueError, TypeError):
        raise ValueError(f'Número incorrecto en {archivo.name}')
    if not titulo or not 1 <= numero <= 100:
        raise ValueError(f'Título o número incorrecto: {archivo.name}')
    galeria = datos.get('galeria') or []
    if isinstance(galeria, str):
        galeria = [galeria]
    if not isinstance(galeria, list):
        raise ValueError(f'Galería incorrecta: {archivo.name}')
    galeria = [str(f).strip() for f in galeria if f]
    imagen = str(datos.get('imagen') or '').strip() or (galeria[0] if galeria else '')
    campos = [('altitud', 'Altitud'), ('desnivel', 'Desnivel +'),
              ('distancia', 'Distancia'), ('duracion', 'Duración'),
              ('dificultad', 'Dificultad'), ('acceso', 'Acceso')]
    ficha = [(etiqueta, str(datos.get(clave) or '').strip())
             for clave, etiqueta in campos if str(datos.get(clave) or '').strip()]
    cuerpo = markdown.markdown(partes[2].strip(), extensions=['extra', 'sane_lists'])
    return dict(titulo=titulo, numero=numero, fecha=str(datos.get('fecha') or ''),
                imagen=imagen, galeria=galeria, ficha=ficha, cuerpo=cuerpo,
                slug=f'{numero:03d}-{crear_slug(titulo)}')


def crear_ficha(historia):
    if not historia['ficha']:
        return ''
    datos = ''.join(f'<div class="dato"><span>{seguro(e)}</span><strong>{seguro(v)}</strong></div>'
                    for e, v in historia['ficha'])
    return ('<section class="ficha"><div class="ficha-titulo">Ficha técnica de la ruta</div>'
            f'<div class="ficha-datos">{datos}</div></section>')


def preparar_relato(historia):
    galeria = historia['galeria']
    utilizadas = set()
    clases = {'foto': 'foto-mediana', 'grande': 'foto-grande',
              'izquierda': 'foto-izquierda', 'derecha': 'foto-derecha'}

    def crear_foto(indice, modo='foto'):
        if indice < 1 or indice > len(galeria):
            return '<p>Fotografía no encontrada.</p>'
        utilizadas.add(indice)
        src = seguro(url_imagen(galeria[indice - 1]))
        titulo = seguro(historia['titulo'])
        clase = clases.get(modo, 'foto-mediana')
        return (f'<figure class="foto-relato {clase}">'
                f'<a href="{src}" class="ampliar" data-lightbox aria-label="Ampliar fotografía {indice}">'
                f'<img src="{src}" alt="{titulo} - fotografía {indice}" loading="lazy"></a></figure>')

    def reemplazar(m):
        modo = m.group(1).lower()
        indices = [int(n) for n in re.findall(r'\d+', m.group(2))]
        if not indices:
            return ''
        if modo == 'fotos':
            return '<div class="grupo-fotos">' + ''.join(crear_foto(i) for i in indices) + '</div>'
        return crear_foto(indices[0], modo)

    patron = (r'<p>\s*\[\[(foto|fotos|izquierda|derecha|grande):\s*'
              r'([0-9, ]+)\]\]\s*</p>')
    cuerpo = re.sub(patron, reemplazar, historia['cuerpo'], flags=re.IGNORECASE)
    # La portada ya se muestra arriba. No volver a añadirla a la galería final.
    portada_url = url_imagen(historia['imagen'])
    restantes = [i for i in range(1, len(galeria) + 1)
                if i not in utilizadas and url_imagen(galeria[i - 1]) != portada_url]
    galeria_final = ''
    if restantes:
        fotos = ''.join(crear_foto(i) for i in restantes)
        galeria_final = ('<section class="galeria-final"><h2>Más fotografías de esta montaña</h2>'
                        f'<div class="grupo-fotos">{fotos}</div></section>')
    return cuerpo, galeria_final


def crear_invitacion():
    if not MOSTRAR_EXCURSIONES:
        return ''
    return '''<section class="invitacion"><h2>Algunas montañas también podemos descubrirlas juntos.</h2>
    <p>Descubre nuestras caminatas por los Prealpes bávaros. Grupos pequeños,
    naturaleza y tiempo para disfrutar de cada paisaje.</p>
    <a class="boton" href="/">Descubrir las excursiones</a></section>'''


ESTILOS = '''
* { box-sizing: border-box; }
body { margin: 0; background: #faf8f2; color: #25382e; font-family: Georgia, serif; line-height: 1.8; }
.contenedor { width: min(980px, 92%); margin: auto; }
header { background: #faf8f2; border-bottom: 1px solid #e6e8de; }
.cabecera { min-height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
.marca { color: #1f4033; font-family: Arial, sans-serif; font-size: 17px; font-weight: 600; text-decoration: none; letter-spacing: .3px; }
.navegacion { display: flex; flex-wrap: wrap; gap: 22px; }
.navegacion a { color: #67776c; font: 13px Arial, sans-serif; text-decoration: none; }
.navegacion a:hover, .marca:hover { text-decoration: underline; }
main { padding: 65px 0 90px; }
.numero { font: 12px Arial, sans-serif; color: #71816f; letter-spacing: 3px; text-transform: uppercase; }
h1 { font-size: clamp(38px, 6vw, 62px); line-height: 1.12; font-weight: normal; color: #1f4033; margin: 22px 0; }
.fecha { font: 14px Arial, sans-serif; color: #728473; margin-bottom: 32px; }
/* Imagen principal y ficha técnica, una junto a la otra. */
.presentacion { display: grid; grid-template-columns: minmax(0, 42fr) minmax(0, 58fr); gap: 22px; align-items: stretch; margin: 0 0 50px; }
.presentacion.solo-ficha { grid-template-columns: 1fr; }
.presentacion.solo-foto { grid-template-columns: minmax(0, 1fr); }
.portada-enlace { display: block; height: 100%; min-height: 280px; max-height: 390px; overflow: hidden; border-radius: 15px; cursor: zoom-in; }
.portada { display: block; width: 100%; height: 100%; object-fit: cover; }
.ficha { display: grid; grid-template-columns: 1fr; grid-template-rows: auto 1fr; background: #eeefe3; border: 1px solid #d7dfd0; border-radius: 15px; overflow: hidden; margin: 0; }
.ficha-titulo { background: #1f4033; color: white; font-size: 18px; line-height: 1.3; padding: 17px 20px; }
.ficha-datos { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px 16px; padding: 20px; align-content: center; }
.dato { display: flex; flex-direction: column; line-height: 1.4; min-width: 0; overflow-wrap: anywhere; }
.dato span { color: #687967; font: 12px Arial, sans-serif; margin-bottom: 5px; }
.dato strong { color: #1f4033; font-size: 16px; }
/* Se mantiene el tamaño de texto del archivo original. */
.relato { font-size: 19px; line-height: 1.85; overflow-wrap: break-word; display: flow-root; }
.relato p { margin: 0 0 1.55em; }
.relato h2, .relato h3, .galeria-final h2 { color: #1f4033; font-weight: normal; line-height: 1.3; }
.relato h2 { font-size: 31px; margin-top: 2em; }
.relato h3 { font-size: 24px; margin-top: 1.7em; }
.relato blockquote { margin: 35px 0; padding: 18px 30px; border-left: 4px solid #718a69; background: #eeefe3; font-style: italic; }
.relato img { max-width: 100%; }
.foto-relato { margin: 32px auto; }
.foto-relato img { display: block; width: 100%; height: auto; border-radius: 15px; }
.ampliar { display: block; cursor: zoom-in; }
.foto-mediana { width: min(76%, 650px); }
.foto-grande { width: 100%; clear: both; }
.foto-izquierda { float: left; width: 39%; margin: 8px 27px 20px 0; }
.foto-derecha { float: right; width: 39%; margin: 8px 0 20px 27px; }
.grupo-fotos { clear: both; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin: 38px 0; }
.grupo-fotos .foto-relato { width: 100%; margin: 0; }
.grupo-fotos .foto-relato img { width: 100%; height: 100%; aspect-ratio: 4 / 3; object-fit: cover; }
.galeria-final { margin-top: 60px; }
.invitacion { margin-top: 80px; padding-top: 38px; border-top: 1px solid #dfe5da; }
.invitacion h2 { font-size: 30px; font-weight: normal; color: #1f4033; line-height: 1.3; }
.boton { display: inline-block; background: #1f4033; color: white; text-decoration: none; padding: 13px 24px; border-radius: 5px; margin-top: 12px; }
.volver { margin-top: 65px; font-size: 15px; }
.volver a { color: #1f4033; text-decoration: none; }
footer { background: #1f4033; color: white; padding: 30px 0; font: 13px Arial, sans-serif; }
/* Visor de fotografías en pantalla completa. */
.lightbox { position: fixed; inset: 0; z-index: 9999; background: rgba(8, 16, 12, .94); display: none; align-items: center; justify-content: center; padding: 52px 18px 20px; }
.lightbox.abierto { display: flex; }
.lightbox img { display: block; max-width: 96vw; max-height: 88vh; object-fit: contain; border-radius: 5px; }
.lightbox-cerrar { position: absolute; top: 10px; right: 18px; color: white; background: transparent; border: 0; font-size: 35px; cursor: pointer; }
@media (max-width: 680px) {
  main { padding-top: 40px; }
  .cabecera { padding: 16px 0; align-items: flex-start; flex-direction: column; gap: 12px; }
  .presentacion { grid-template-columns: 1fr; gap: 12px; }
  .portada-enlace { height: 290px; min-height: 0; }
  .ficha-datos { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .relato { font-size: 17px; }
  .foto-mediana, .foto-izquierda, .foto-derecha { float: none; width: 100%; margin: 28px 0; }
  .grupo-fotos { gap: 8px; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; } }
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
  visor.addEventListener('click', evento => { if (evento.target === visor) ocultar(); });
  document.addEventListener('keydown', evento => {
    if (evento.key === 'Escape' && visor.classList.contains('abierto')) ocultar();
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
        portada = (f'<a class="portada-enlace" href="{src}" data-lightbox aria-label="Ampliar fotografía principal">'
                   f'<img class="portada" src="{src}" alt="{titulo}"></a>')
    clase = 'presentacion'
    if ficha and not portada:
        clase += ' solo-ficha'
    if portada and not ficha:
        clase += ' solo-foto'
    presentacion = f'<div class="{clase}">{portada}{ficha}</div>' if portada or ficha else ''
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
<header><div class="contenedor cabecera">
<a class="marca" href="/blog/">100 montañas en 365 días</a>
<nav class="navegacion" aria-label="Navegación principal">
<a href="/blog/">Historias</a><a href="/blog/">El reto</a><a href="/">Prealpes bávaros</a>
</nav></div></header>
<main class="contenedor">
<div class="numero">Cumbre {numero:03d} de 100</div>
<h1>{titulo}</h1>
<div class="fecha">Fecha de ascenso: {fecha}</div>
{presentacion}
<article class="relato">{cuerpo}</article>
{galeria_final}
{invitacion}
<div class="volver"><a href="/blog/">← Volver a las 100 montañas</a></div>
</main>
<footer><div class="contenedor">Una pausa en tu viaje · Prealpes bávaros</div></footer>
<div class="lightbox" id="visor" role="dialog" aria-label="Fotografía ampliada" aria-modal="true" aria-hidden="true">
<button class="lightbox-cerrar" id="visor-cerrar" type="button" aria-label="Cerrar fotografía">×</button>
<img id="visor-foto" alt="">
</div>
{SCRIPT_LIGHTBOX}
</body></html>'''
    destino = SALIDA / historia['slug'] / 'index.html'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding='utf-8')


def crear_tarjeta(historia):
    titulo = seguro(historia['titulo'])
    numero = historia['numero']
    fecha = seguro(historia['fecha'])
    enlace = f"/blog/cumbres/{historia['slug']}/"
    imagen_html = ''
    if historia['imagen']:
        src = seguro(url_imagen(historia['imagen']))
        imagen_html = f'<img src="{src}" alt="{titulo}" loading="lazy">'
    return f'''<article class="story-card"><a href="{enlace}">
{imagen_html}<div class="story-content">
<div class="story-number">Cumbre {numero:03d} de 100</div>
<h3>{titulo}</h3><p>{fecha}</p>
<span class="story-link">Leer la historia</span>
</div></a></article>'''


def actualizar_portada(historias):
    html = PORTADA.read_text(encoding='utf-8')
    tarjetas = '\n'.join(crear_tarjeta(h) for h in historias)
    if not tarjetas:
        tarjetas = ('<div class="empty-state"><h3>Las primeras historias llegarán pronto.</h3>'
                    '<p>Este diario irá reuniendo las experiencias y fotografías de cada cumbre.</p></div>')
    if INICIO in html and FIN in html:
        patron = re.escape(INICIO) + r'.*?' + re.escape(FIN)
        html = re.sub(patron, lambda m: INICIO + '\n' + tarjetas + '\n' + FIN,
                      html, flags=re.DOTALL)
    else:
        apertura = '<div class="stories-grid" id="stories-grid">'
        if apertura not in html:
            raise ValueError('No se encontró stories-grid en blog/index.html')
        comienzo = html.index(apertura) + len(apertura)
        cierre = html.find('\n        </div>\n\n      </div>\n    </section>', comienzo)
        if cierre == -1:
            raise ValueError('No se encontró el cierre de la sección')
        html = (html[:comienzo] + '\n' + INICIO + '\n' + tarjetas + '\n' + FIN
                + html[cierre:])
    cantidad = len(historias)
    html = re.sub(r'(<span id="summit-count">).*?(</span>)',
                  lambda m: m.group(1) + str(cantidad) + m.group(2),
                  html, count=1, flags=re.DOTALL)
    porcentaje = min(cantidad, 100)

    def actualizar_progreso(m):
        etiqueta = m.group(0)
        estilo = re.search(r'\sstyle=["\']([^"\']*)["\']', etiqueta)
        if estilo:
            anterior = estilo.group(1)
            nuevo = re.sub(r'width\s*:\s*[^;]+;?', '', anterior).strip()
            if nuevo:
                nuevo = nuevo.rstrip(';') + '; '
            nuevo += f'width: {porcentaje}%'
            return etiqueta[:estilo.start()] + f' style="{nuevo}"' + etiqueta[estilo.end():]
        return etiqueta[:-1] + f' style="width: {porcentaje}%">'

    html = re.sub(r'<div\b(?=[^>]*\bid=["\']progress-fill["\'])[^>]*>',
                  actualizar_progreso, html, count=1)
    PORTADA.write_text(html, encoding='utf-8')


def main():
    historias = []
    if HISTORIAS.exists():
        for archivo in sorted(HISTORIAS.glob('*.md')):
            historia = leer_historia(archivo)
            if historia is not None:
                historias.append(historia)
    historias.sort(key=lambda h: h['numero'])
    numeros = [h['numero'] for h in historias]
    if len(numeros) != len(set(numeros)):
        raise ValueError('Hay dos historias publicadas con el mismo número de cumbre.')
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for historia in historias:
        crear_articulo(historia)
    actualizar_portada(historias)
    print(f'Blog generado correctamente: {len(historias)} historias publicadas.')


if __name__ == '__main__':
    main()
