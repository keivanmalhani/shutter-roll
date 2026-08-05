# shutter-roll

[![CI](https://github.com/keivanmalhani/shutter-roll/actions/workflows/ci.yml/badge.svg)](https://github.com/keivanmalhani/shutter-roll/actions/workflows/ci.yml)
![Licencia MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)

[English](README.md) | Espanol

![Demo de shutter-roll: crea el archivo del rollo, planea las etiquetas, aplicalas, genera la hoja de contactos](docs/demo.gif)

Devuelvele la historia a tu pelicula escaneada. Los escaneos llegan sin stock, sin camara, sin ISO, y con la fecha del escaneo donde deberia ir la fecha de la toma, asi que Lightroom archiva tu rollo de julio bajo octubre. shutter-roll toma una carpeta de escaneos de un rollo mas una descripcion de seis lineas e inyecta los metadatos reales en cada cuadro, y ademas genera una hoja de contactos. Solo local, con respaldos por defecto.

## Inicio rapido

Requiere Python 3.11+ y [exiftool](https://exiftool.org).

```bash
brew install exiftool          # macOS
```

```bash
pip install git+https://github.com/keivanmalhani/shutter-roll.git
```

Describe el rollo una vez:

```bash
shutter-roll init ~/escaneos/portra-baja
```

Eso escribe una plantilla `roll.txt` junto a los escaneos:

```text
stock: Portra 400
camera: Canon Canonet QL17 GIII
iso: 400
shot: 2026-07-15
lens: 40mm f/1.7
roll: R012
```

Mira exactamente que se escribiria, y despues escribelo:

```bash
shutter-roll plan ~/escaneos/portra-baja
```

```bash
shutter-roll apply ~/escaneos/portra-baja
```

```bash
shutter-roll sheet ~/escaneos/portra-baja
```

Cada clave de `roll.txt` tambien es una bandera (`--stock "HP5 Plus" --iso 1600`), y las banderas ganan. Solo `stock` es obligatorio.

## Que se escribe y donde

| campo | destino | por que |
| --- | --- | --- |
| `camera` | EXIF Make + Model | aparece como la camara en el panel de Lightroom |
| `lens` | EXIF LensModel | la columna de lente simplemente funciona |
| `iso` | EXIF ISO | filtrable en cualquier gestor |
| `shot` + orden de cuadros | DateTimeOriginal y CreateDate, fecha base a las 12:00 mas un minuto por cuadro | los rollos ordenan por fecha Y los cuadros conservan el orden de disparo dentro del rollo |
| `stock`, `roll` | palabras clave (`film`, el stock, el id del rollo) mas un UserComment como `Film: Portra 400, roll R012, frame 14/36` | filtrado por palabra clave mas un registro legible dentro del archivo |

Los numeros de cuadro siguen el orden de nombre de archivo; `--start-frame 20` maneja medios rollos y sesiones de escaneo divididas. Una fecha `shot` sin dia (`2026-07`) usa el dia 1. `--title` escribe ademas un titulo XMP como `R012 frame 14`.

## Modelo de seguridad

- `plan` (y `apply --dry-run`) imprimen el plan completo de etiquetas sin escribir nada.
- `apply` conserva los respaldos `_original` de exiftool junto a cada escaneo. `--overwrite` es la unica opcion destructiva.
- Repetir `apply` reemplaza etiquetas limpiamente, nunca apila palabras clave duplicadas.
- Los pixeles nunca se tocan: los metadatos pasan por [exiftool](https://exiftool.org), que escribe JPEG, TIFF, PNG y DNG de forma nativa. Nunca un escritor hecho a mano.
- Solo local. Sin llamadas de red, sin telemetria, nada sale de tu maquina.

## La hoja de contactos

`shutter-roll sheet` genera `<rollo>-contact.jpg` en la carpeta: una rejilla oscura con el encabezado del rollo (stock, camara, ISO, fecha) y miniaturas numeradas, 2000 px de ancho. Solo Pillow, sin ImageMagick.

## Desarrollo

```bash
pip install -e ".[dev]"
pytest
```

31 pruebas, sin binarios en el repo: los escaneos de prueba se generan con Pillow al momento, y las pruebas de inyeccion hacen viajes redondos reales con exiftool (se saltan limpiamente cuando falta). El CI corre la suite en Python 3.11 y 3.12 con exiftool instalado.

## Hoja de ruta

- Overrides por cuadro (un `frames.txt` para cambios de lente o push a mitad de rollo)
- Modo por lotes sobre una carpeta de rollos
- Miniaturas de negativo a positivo opcionales en la hoja de contactos

## Licencia

MIT, ver [LICENSE](LICENSE).
