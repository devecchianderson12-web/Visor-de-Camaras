# The Watcher

Visor multicámara RTSP / ONVIF ultraligero para cámaras iCSee y compatibles. Sin VLC ni nada instalado
(FFmpeg vía PyAV y Qt van dentro). Windows 8.1 / 10 / 11 (64 bits) y Linux (x86_64, glibc 2.35+: Debian 12+, Ubuntu 22.04+, antiX 23+).

## Descargas (Releases)
En **Releases → «Última versión (automática)»** están siempre los archivos de la última subida (Windows y Linux).

- **Windows:** `TheWatcher-Setup-Win81.exe` (instalador) o `TheWatcher-Win81-portable.zip`.
- **Linux (Debian, Ubuntu, Mint, antiX 23+):** `thewatcher_X.Y.Z_amd64.deb` →
  `sudo apt install ./thewatcher_X.Y.Z_amd64.deb` (apt instala solo las librerías que falten).
  Se abre desde el menú o con el comando `thewatcher`. Desinstalar: `sudo apt remove thewatcher`.
- **Linux (cualquier distribución):** `TheWatcher-Linux-x86_64.tar.gz` → descomprimir y ejecutar `./TheWatcher`, o `./install.sh` para el menú.

## Uso
- **Barra inferior:** vistas *Cuadrícula / Destacada / Panorámica / Mi planilla*, *Buscar ONVIF*, *Buscar en red*,
  *Pantalla completa*, *Cámaras*.
- **Clic derecho en una cámara:** Transmisión / Convencional · Resolución · Ajuste de imagen · Fluidez (FPS) ·
  Monitor de rendimiento (opacidad, actualización) · Pantalla completa · Personalizar cuadrícula · Cámaras.
- **Arrastrar** una cámara sobre otra las intercambia. **Doble clic** maximiza (Esc para volver). **F11** pantalla completa.

## Configuración
`config.json`: Windows `%APPDATA%\TheWatcher` (portable: junto al .exe) · Linux `~/.config/TheWatcher`.
Claves útiles: `fps_grid`, `fit_mode`, `perf_opacity`, `perf_interval`, `hwaccel`.

## Compilar (GitHub Actions)
- `build-win81.yml` → instalador + portable de Windows (PyQt5 + PyAV 12).
- `linux.yml` → `.tar.gz` y `.deb` de Linux (PyQt5 + PyAV 14). El `.deb` se instala en un Debian 12 limpio
  para comprobar que no falta ninguna dependencia.
Con un tag `vX.Y.Z` los archivos se adjuntan solos al Release. Ambos hacen un autodiagnóstico del programa
compilado y se ponen en rojo si algo no abre.

## Desde el código fuente
`pip install -r requirements.txt` (PyQt6) y `python main.py`. Linux: `requirements-linux.txt`.

## Notas
- GPU del monitor: Windows 10+ (cualquier marca) o NVIDIA; Linux: NVIDIA o AMD. Si no se puede medir, «n/d».
- En Windows 8.1 / Linux la decodificación es por CPU por defecto: usa «Transmisión» en la cuadrícula.
- Diagnóstico: `TheWatcher --diagnose` (Windows: acceso directo en el menú Inicio).
