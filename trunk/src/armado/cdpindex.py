# -*- coding: utf8 -*-

"""
Biblioteca para armar y leer los índices.

Se usa desde server.py para consulta, se utiliza directamente
para crear el índice.
"""

import time
import sys
import os
import codecs
import unicodedata
import config
import subprocess
import re
import threading
import shutil

from .compressed_index import Index

usage = """Indice de títulos de la CDPedia

Para generar el archivo de indice hacer:

  cdpindex.py fuente destino [max] [dirbase]

    fuente: archivo con los títulos
    destino: en donde se guardará el índice
    max: cantidad máxima de títulos a indizar
    dirbase: de dónde dependen los archivos
"""

# Buscamos todo hasta el último guión no inclusive, porque los
# títulos son como "Zaraza - Wikipedia, la enciclopedia libre"
SACATIT = re.compile(".*?<title>([^<]*)\s+-", re.S)

# separamos por palabras
PALABRAS = re.compile("\w+", re.UNICODE)

def normaliza(txt):
    """Recibe una frase y devuelve sus palabras ya normalizadas."""
    txt = unicodedata.normalize('NFKD', txt).encode('ASCII', 'ignore').lower()
    return txt

def _getHTMLTitle(arch):
    # Todavia no soportamos redirect, asi que todos los archivos son
    # válidos y debería tener TITLE en ellos
    html = codecs.open(arch, "r", "utf8").read()
    m = SACATIT.match(html)
    if m:
        tit = m.groups()[0]
    else:
        tit = u"<sin título>"
    return tit

def _getPalabrasHTML(arch):
    # FIXME: esta función es para cuando hagamos fulltext
    arch = os.path.abspath(arch)
    cmd = config.CMD_HTML_A_TEXTO % arch
    p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    txt = p.stdout.read()
    txt = txt.decode("utf8")
    return txt


class IndexInterface(threading.Thread):
    """Procesa toda la info para interfacear con el índice.

    Lo que guardamos en el índice para cada palabra es:

     - nomhtml: el path al archivo
     - titulo: del artículo
     - puntaje: para relativizar la importancia del artículo
    """
    def __init__(self, directory):
        super(IndexInterface, self).__init__()
        self.ready = threading.Event()
        self.directory = directory

    def is_ready(self):
        return self.ready.is_set()

    def run(self):
        """Levanta el índice."""
        self.indice = Index(self.directory)
        self.ready.set()

    def listado_palabras(self):
        """Devuelve las palabras."""
        self.ready.wait()
        return sorted(self.indice.keys())

    def listado_valores(self):
        """Devuelve la info de todos los artículos."""
        self.ready.wait()
        return sorted(set(x[:2] for x in self.indice.values()))

    def get_random(self):
        """Devuelve un artículo al azar."""
        self.ready.wait()
        value = self.indice.random()
        return value[:2]

    def search(self, words):
        """Busca palabras completas en el índice."""
        self.ready.wait()
        pals = PALABRAS.findall(normaliza(words))
        return self.indice.search(pals)

    def partial_search(self, words):
        """Busca palabras parciales en el índice."""
        self.ready.wait()
        pals = PALABRAS.findall(normaliza(words))
        return self.indice.partial_search(pals)


def filename2palabras(fname):
    """Transforma un filename en sus palabras y título."""
    x = fname[:-5]
    x = normaliza(x)
    p = x.split("_")

    # a veces tenemos un nro hexa de 4 dígitos al final que queremos sacar
    if len(p[-1]) == 4:
        try:
            int(p[-1], 16)
        except ValueError:
            # perfecto, no es para sacar
            pass
        else:
            p = p[:-1]

    # el tit lo tomamos como la suma de las partes
    t = " ".join(p)
    return p, t


def generar_de_html(dirbase, verbose):
    # lo importamos acá porque no es necesario en producción
    from src import utiles
    from src.preproceso import preprocesar

    # armamos las redirecciones
    redirs = {}
    for linea in codecs.open(config.LOG_REDIRECTS, "r", "utf-8"):
        orig, dest = linea.strip().split(config.SEPARADOR_COLUMNAS)

        # del original, que es el que redirecciona, no tenemos título, así
        # que sacamos las palabras del nombre de archivo mismo... no es lo
        # mejor, pero es lo que hay...
        palabras, titulo = filename2palabras(orig)
        redirs.setdefault(dest, []).append((palabras, titulo))

    filenames = preprocesar.get_top_htmls(config.LIMITE_PAGINAS)

    def gen():
        for dir3, arch, puntaje in filenames:
            # info auxiliar
            nomhtml = os.path.join(dir3, arch)
            nomreal = os.path.join(dirbase, nomhtml)
            if os.access(nomreal, os.F_OK):
                titulo = _getHTMLTitle(nomreal)
            else:
                print "WARNING: Archivo no encontrado:", nomreal
                continue

            if verbose:
                print "Agregando al índice [%r]  (%r)" % (titulo, nomhtml)

            # a las palabras del título le damos mucha importancia: 50, más
            # el puntaje original sobre 1000, como desempatador
            ptje = 50 + puntaje//1000
            for pal in PALABRAS.findall(normaliza(titulo)):
                yield pal, (nomhtml, titulo, ptje)

            # pasamos las palabras de los redirects también que apunten
            # a este html, con el mismo puntaje
            if arch in redirs:
                for (palabras, titulo) in redirs[arch]:
                    for pal in palabras:
                        yield pal, (nomhtml, titulo, ptje)

            # FIXME: las siguientes lineas son en caso de que la generación
            # fuese fulltext, pero no lo es (habrá fulltext en algún momento,
            # pero será desde los bloques, no desde el html, pero guardamos
            # esto para luego)
            #
            # # las palabras del texto importan tanto como las veces que están
            # all_words = {}
            # for pal in PALABRAS.findall(normaliza(palabs_texto)):
            #     all_words[pal] = all_words.get(pal, 0) + 1
            # for pal, cant in all_words.items():
            #     yield pal, (nomhtml, titulo, cant)

    # nos aseguramos que el directorio esté virgen
    if os.path.exists(config.DIR_INDICE):
        shutil.rmtree(config.DIR_INDICE)
    os.mkdir(config.DIR_INDICE)

    Index.create(config.DIR_INDICE, gen())
    return len(filenames)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print usage
        sys.exit()

    tini = time.time()
    cant = _create_index(*sys.argv[1:])
    delta = time.time()-tini
    print "Indice creado! (%.2fs)" % delta
    print "Archs: %d  (%.2f mseg/arch)" % (cant, 1000*delta/cant)
