# -- encoding: utf-8 --

import sys
import os
from os import path
import shutil
import time
import glob
import optparse

import config
from src.preproceso import preprocesar
from src.armado import compresor
from src.armado import cdpindex
from src.imagenes import extraer, download, reducir

def mensaje(texto):
    fh = time.strftime("%Y-%m-%d %H:%M:%S")
    print "%-40s (%s)" % (texto, fh)

def copiarAssets(src_info, dest):
    """Copiar los assets."""
    os.makedirs(dest)
    for d in config.ASSETS:
        src_dir = path.join(src_info, d)
        dst_dir = path.join(dest, d)
        if not os.path.exists(src_dir):
            print "\nERROR: No se encuentra el directorio %r" % src_dir
            print "Este directorio es obligatorio para el procesamiento general"
            sys.exit()
        shutil.copytree(src_dir, dst_dir)

def copiarSources():
    """Copiar los fuentes."""
    # el src
    dest_src = path.join(config.DIR_CDBASE, "src")
    os.makedirs(dest_src)
    shutil.copy(path.join("src", "__init__.py"), dest_src)

    # las fuentes
    orig_src = path.join("src", "armado")
    dest_src = path.join(config.DIR_CDBASE, "src", "armado")
    os.makedirs(dest_src)
    for name in os.listdir(orig_src):
        fullname = path.join(orig_src, name)
        if os.path.isfile(fullname):
            shutil.copy(fullname, dest_src)

    # los templates
    orig_src = path.join("src", "armado", "templates")
    dest_src = path.join(config.DIR_CDBASE, orig_src)
    os.makedirs(dest_src)
    for name in glob.glob(path.join(orig_src, "*.tpl")):
        shutil.copy(name, dest_src)

    # el main va al root
    shutil.copy("main.py", config.DIR_CDBASE)

def copiarIndices():
    """Copiar los indices."""
    # las fuentes
    dest_src = path.join(config.DIR_CDBASE, "indice")
    os.makedirs(dest_src)
    for name in glob.glob("%s.*" % config.PREFIJO_INDICE):
        shutil.copy(name, dest_src)

def armarEjecutable():
    pass

def armarIso(dest):
    os.system("mkisofs -quiet -o " + dest + " -R -J " + config.DIR_CDBASE)

def genera_run_config():
    f = open(path.join(config.DIR_CDBASE, "config.py"), "w")
    f.write('DIR_BLOQUES = "bloques"\n')
    f.write('DIR_ASSETS = "assets"\n')
    f.write('ASSETS = %s\n' % config.ASSETS)
    f.write('PREFIJO_INDICE = "indice/wikiindex"\n')
    f.close()

def preparaTemporal():
    dtemp = config.DIR_TEMP
    if os.path.exists(dtemp):
        # borramos los dirs (excepto imagenes)
        shutil.rmtree(os.path.join(dtemp,"cdroot"), ignore_errors=True)
        shutil.rmtree(os.path.join(dtemp,"preprocesado"), ignore_errors=True)
        # borramos los archivos
        for arch in glob.glob(os.path.join(dtemp, "*.txt")):
            os.unlink(arch)
    else:
        os.makedirs(dtemp)


def main(src_info, evitar_iso, verbose):
    mensaje("Comenzando!")
    preparaTemporal()

    mensaje("Copiando los assets")
    copiarAssets(src_info, config.DIR_ASSETS)

    mensaje("Preprocesando")
    articulos = path.join(src_info, "articles")
    if not path.exists(articulos):
        print "\nERROR: No se encuentra el directorio %r" % articulos
        print "Este directorio es obligatorio para el procesamiento general"
        sys.exit()
    cant = preprocesar.run(articulos, verbose)
    print '  total: %d páginas procesadas' % cant

    mensaje("Generando el log de imágenes")
    result = extraer.run(verbose)
    print '  total: %d imágenes sacadas de %d archivos' % result

    mensaje("Descargando las imágenes de la red")
    download.traer(verbose)
    reducir.run(verbose)

    mensaje("Generando el índice")
    result = cdpindex.generar(articulos, verbose)
    print '  total: %d archivos' % result

    mensaje("Generando los bloques")
    dest = path.join(config.DIR_BLOQUES)
    os.makedirs(dest)
    result = compresor.generar(verbose)
    print '  total: %d bloques con %d archivos' % result

    if not evitar_iso:
        mensaje("Copiando las fuentes")
        copiarSources()

        mensaje("Copiando los indices")
        copiarIndices()

        # FIXME: ¿esto al final se hace por afuera?
        if sys.platform == "win32":
            armarEjecutable()

        mensaje("Generamos la config para runtime")
        genera_run_config()

        mensaje("Armamos el ISO")
        armarIso("cdpedia.iso")

    mensaje("Todo terminado!")


if __name__ == "__main__":
    msg = u"""
  generar.py [--no-iso] <directorio>
    donde directorio es el lugar donde está la info
"""

    parser = optparse.OptionParser()
    parser.set_usage(msg)
    parser.add_option("-n", "--no-iso", action="store_true",
                      dest="create_iso", help="evita crear el ISO al final")
    parser.add_option("-v", "--verbose", action="store_true",
                  dest="verbose", help="muestra info de lo que va haciendo")

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        exit()

    direct = args[0]
    evitar_iso = bool(options.create_iso)
    verbose = bool(options.verbose)

    main(args[0], evitar_iso, verbose)
