# -- encoding: utf-8 --

import sys
import os
from os import path
import shutil
import time
import glob
import optparse
import cPickle

#Para poder hacer generar.py > log.txt
if sys.stdout.encoding is None:
    reload(sys)
    sys.setdefaultencoding('utf8')

import config
from src.preproceso import preprocesar
from src.armado import compresor
from src.armado import cdpindex
from src.imagenes import extraer, download, reducir

def mensaje(texto):
    fh = time.strftime("%Y-%m-%d %H:%M:%S")
    print "%-40s (%s)" % (texto, fh)

def copy_dir(src_dir, dst_dir):
    '''Copia un directorio.

    (no usamos shutil.copytree para no llevarnos el .svn)
    '''
    if not os.path.exists(dst_dir):
        os.mkdir(dst_dir)
    for fname in os.listdir(src_dir):
        if fname.startswith("."):
            continue
        src_path = path.join(src_dir, fname)
        dst_path = path.join(dst_dir, fname)
        if path.isdir(src_path):
            copy_dir(src_path, dst_path)
        else:
            shutil.copy(src_path, dst_path)

def copiarAssets(src_info, dest):
    """Copiar los assets."""
    if not os.path.exists(dest):
        os.makedirs(dest)
    for d in config.ASSETS:
        src_dir = path.join(src_info, d)
        dst_dir = path.join(dest, d)
        if not os.path.exists(src_dir):
            print "\nERROR: No se encuentra el directorio %r" % src_dir
            print "Este directorio es obligatorio para el procesamiento general"
            sys.exit()
        shutil.copytree(src_dir, dst_dir)

    # externos (de nosotros, bah)
    src_dir = "resources/external_assets"
    dst_dir = path.join(dest, "extern")
    copy_dir(src_dir, dst_dir)

    # info general
    src_dir = "resources/general_info"
    copy_dir(src_dir, config.DIR_CDBASE)

    # el tutorial de python
    src_dir = "resources/tutorial"
    dst_dir = path.join(dest, "tutorial")
    copy_dir(src_dir, dst_dir)

def copiarAutorun():
    src_dir = "resources/autorun.win/cdroot"
    copy_dir(src_dir, config.DIR_CDBASE)


def copiarSources():
    """Copiar los fuentes."""
    # el src
    dest_src = path.join(config.DIR_CDBASE, "src")
    dir_a_cero(dest_src)
    shutil.copy(path.join("src", "__init__.py"), dest_src)

    # las fuentes
    orig_src = path.join("src", "armado")
    dest_src = path.join(config.DIR_CDBASE, "src", "armado")
    dir_a_cero(dest_src)
    for name in os.listdir(orig_src):
        fullname = path.join(orig_src, name)
        if os.path.isfile(fullname):
            shutil.copy(fullname, dest_src)

    # los templates
    orig_src = path.join("src", "armado", "templates")
    dest_src = path.join(config.DIR_CDBASE, orig_src)
    dir_a_cero(dest_src)
    for name in glob.glob(path.join(orig_src, "*.tpl")):
        shutil.copy(name, dest_src)

    # el main va al root
    shutil.copy("main.py", config.DIR_CDBASE)

def dir_a_cero(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def armarIso(dest):
    os.system("mkisofs -quiet -V CDPedia -volset CDPedia -o %s -R -J %s " %
                                                    (dest, config.DIR_CDBASE))

def genera_run_config():
    f = open(path.join(config.DIR_CDBASE, "config.py"), "w")
    f.write('DIR_BLOQUES = "bloques"\n')
    f.write('DIR_ASSETS = "assets"\n')
    f.write('ASSETS = %s\n' % config.ASSETS)
    f.write('DIR_INDICE = "indice"\n')
    f.write('INDEX = "%s"' % config.INDEX)
    f.close()

def preparaTemporal():
    dtemp = config.DIR_TEMP
    if os.path.exists(dtemp):
        # borramos el cdroot excepto las imágenes de assets!
        imag_path = path.join(config.DIR_ASSETS, "images")
        if os.path.exists(imag_path):
            bkup_path = path.join(dtemp, "asset_imag_backup")
            os.rename(imag_path, bkup_path)
            shutil.rmtree(path.join(dtemp,"cdroot"), ignore_errors=True)
            os.makedirs(config.DIR_ASSETS)
            os.rename(bkup_path, imag_path)
        else:
            shutil.rmtree(path.join(dtemp,"cdroot"), ignore_errors=True)
    else:
        os.makedirs(dtemp)


class Estadisticas(object):
    '''Junta los nros de todo lo hecho.'''
    def __init__(self):
        self._attrs = "pags_total", "pags_incl", "imgs_incl", "imgs_bogus"
        for attr in self._attrs:
            setattr(self, attr, None)

    def dump(self, nomarch):
        '''Baja la info a un pickle'''
        for attr in self._attrs:
            if attr is None:
                raise ValueError("{0} en None al hacer el dump!".format(attr))

        obj = dict((x, getattr(self, x)) for x in self._attrs)
        with open(nomarch, "w") as fh:
            cPickle.dump(obj, fh)


def main(src_info, evitar_iso, verbose, desconectado, preprocesado):

    articulos = path.join(src_info, "articles")
    estad = Estadisticas()

    if not preprocesado:
        mensaje("Comenzando!")
        preparaTemporal()

        mensaje("Copiando los assets")
        copiarAssets(src_info, config.DIR_ASSETS)

        mensaje("Preprocesando")
        if not path.exists(articulos):
            print "\nERROR: No se encuentra el directorio %r" % articulos
            print "Este directorio es obligatorio para el procesamiento general"
            sys.exit()
        cantnew, cantold = preprocesar.run(articulos, verbose)
        print '  total %d páginas procesadas' % cantnew
        print '      y %d que ya estaban de antes' % cantold
        estad.pags_total = cantnew + cantold

        mensaje("Calculando los que quedan y los que no")
        preprocesar.calcula_top_htmls()

        mensaje("Generando el log de imágenes")
        taken, bogus, adesc = extraer.run(verbose)
        print '  total: %5d imágenes extraídas' % taken
        print '         %5d marcadas como bogus' % bogus
        print '         %5d a descargar' % adesc
        estad.imgs_incl = taken
        estad.imgs_bogus = bogus
    else:
        estad.pags_total = 0
        estad.imgs_incl = 0
        estad.imgs_bogus = 0

    if not desconectado:
        mensaje("Descargando las imágenes de la red")
        download.traer(verbose)

    # de acá para adelante es posterior al pre-procesado
    mensaje("Reduciendo las imágenes descargadas")
    notfound = reducir.run(verbose)

    # esto no es lo más exacto, pero good enough
    estad.imgs_incl -= notfound
    estad.imgs_bogus += notfound

    mensaje("Generando el índice")
    result = cdpindex.generar_de_html(articulos, verbose)
    print '  total: %d archivos' % result
    estad.pags_incl = result

    mensaje("Generando los bloques")
    result = compresor.generar(verbose)
    print '  total: %d bloques con %d archivos' % result

    estad.dump(path.join(config.DIR_ASSETS, "estad.pkl"))

    if not evitar_iso:
        mensaje("Copiando las fuentes")
        copiarSources()

        mensaje("Copiando los indices")
        dest_src = path.join(config.DIR_CDBASE, "indice")
        if os.path.exists(dest_src):
            shutil.rmtree(dest_src)
        shutil.copytree(config.DIR_INDICE, dest_src)

        mensaje("Copiando el autorun")
        copiarAutorun()

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
    parser.add_option("-d", "--desconectado", action="store_true",
                  dest="desconectado", help="trabaja desconectado de la red")
    parser.add_option("-p", "--preprocesado", action="store_true",
                  dest="preprocesado",
                  help="arranca el laburo con lo preprocesado de antes")

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        exit()

    direct = args[0]

    evitar_iso = bool(options.create_iso)
    verbose = bool(options.verbose)
    desconectado = bool(options.desconectado)
    preprocesado = bool(options.preprocesado)

    main(args[0], options.create_iso, verbose, desconectado, preprocesado)