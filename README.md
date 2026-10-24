# The Watcher

Visor multicámara RTSP ultraligero. **No requiere VLC ni nada instalado**: FFmpeg (PyAV) y Qt van dentro del .exe.

## Barra inferior
- **Cuadrícula / Destacada / Panorámica**: 3 vistas listas, sin huecos vacíos.
  En *Destacada* y *Panorámica* la cámara grande es la primera; clic derecho → «Hacer principal» para cambiarla.
- **Mi planilla**: tu propia distribución (editor con celdas que se unen/separan). 1.er clic aplica, 2.º clic edita.
- **Buscar ONVIF**: encuentra los dispositivos ONVIF de la red (como VMS Lite), lee sus perfiles y
  configura solo «Transmisión» (menor resolución) y «Convencional» (mayor resolución).
- **Buscar en red**: escanea un rango IPv4 (por defecto tu /24) buscando equipos con puertos de cámara.
- **Cámaras**: alta/edición manual.

## Controles
- Clic derecho en una cámara: *Transmisión* / *Convencional*.
- **Arrastra una cámara sobre otra** para intercambiarlas de lugar (se guarda; no reconecta ni gasta CPU extra).
- Clic derecho → **Resolución**: Automática, 720p, 480p, 360p, 240p. Limita la resolución *mostrada* (menos
  conversión y dibujo = menos CPU). Para ahorrar de verdad en la decodificación usa «Transmisión».
- Clic derecho → **Pantalla completa**, o botón «Pantalla completa» de la barra, o F11.
  En pantalla completa aparece un botón **✕ Salir** arriba a la derecha solo cuando acercas el mouse.
- Clic derecho → **Ajuste de imagen**: *Estirar* (sin barras negras, por defecto), *Llenar* (recorta los bordes)
  u *Original* (con barras).
- Clic derecho → **Fluidez (FPS)**: 8, 12, 15, 20, 25, 30 o todos los fotogramas. Es solo un tope de lo que se
  *muestra*: la cámara envía los fps que tenga configurados (se cambian en la app iCSee). Más fps = más CPU.
  «Mostrar FPS reales» pone en la etiqueta `mostrados/cámara fps`.
- **Monitor de rendimiento** (CPU / RAM / GPU) arriba al centro, con bordes redondeados. Clic derecho →
  Monitor de rendimiento: *Mostrar*, *Opacidad* (100–20 %, o +/−10 %) y *Actualización* (1, 2 o 5 s).
  GPU: contadores de Windows 10+ (cualquier marca) o NVIDIA (NVML) en 8.1; si no, «n/d».
- Doble clic: maximiza una cámara (pausa las demás). Doble clic o Esc: volver.
- F11: pantalla completa (oculta la barra). Minimizar = todo en pausa.

## Notas
- Si Windows pregunta por el firewall al buscar ONVIF, acepta «Redes privadas» (usa multicast UDP 3702).
- config.json (junto al .exe): `hwaccel`, `fps_grid`, `fps_zoom`, `auto_quality_on_zoom`, `layout_mode`.

## Compilar
Sube a GitHub: Actions genera `TheWatcher.exe` (con el icono del ojo) (Artifacts).

## Windows 8.1 (6.3.9600) + instalador
- Workflow `build-win81.yml` → genera `TheWatcher-Setup-Win81.exe` (instalador) y `TheWatcher-Win81-portable.zip`.
- Usa PyQt5 (Qt 5.15) y PyAV 12, compatibles con Windows 8.1. **Solo 64 bits.**
- El instalador incluye todo lo necesario (Python, Qt, FFmpeg, UCRT y runtime de C++ de Microsoft) y,
  opcionalmente, crea la regla del Firewall para «Buscar ONVIF».
- En Windows 8.1 la decodificación es por CPU (la aceleración por GPU requiere PyAV 14). Usa «Transmisión».
- Menú Inicio → «Diagnóstico de The Watcher» genera un informe si algo no arranca (`--diagnose`).
- La configuración instalada se guarda en `%APPDATA%\TheWatcher\config.json` (no se borra al desinstalar).
  El portable (`portable.flag`) la guarda junto al .exe.
