# iCSee Lite (independiente)

Visor multicámara RTSP ultraligero. **No requiere VLC ni nada instalado**: FFmpeg (PyAV) y Qt van dentro del .exe.

## Ejecutar desde código
    pip install -r requirements.txt
    python main.py

## Uso
- Primera vez: se abre "Administrar cámaras" → Agregar (nombre, IP, usuario, contraseña).
- Todas las cámaras se ven a la vez en una cuadrícula automática.
- **Clic derecho** en una cámara: *Transmisión* (substream) / *Convencional* (mainstream).
- **Doble clic**: maximiza una cámara (pausa las demás). Doble clic o Esc para volver.
- **Clic derecho → Personalizar cuadrícula…**: base de 2×2 (ajustable hasta 6×6). Selecciona celdas,
  «Unir seleccionadas» las fusiona en una sola (ej.: con 3 cámaras une las 2 celdas de abajo y no queda
  ningún hueco). «Separar» deshace la unión; el desplegable asigna qué cámara va en cada celda.
  «Usar automático» vuelve a la cuadrícula automática. Se guarda en `config.json`.
- F11: pantalla completa. Minimizar = todo en pausa (0 % CPU).

## Ruta RTSP iCSee/XM
`rtsp://IP:554/user=admin&password=CLAVE&channel=1&stream=0.sdp?real_stream`
(stream=0 Convencional, stream=1 Transmisión). Si tu modelo usa otra, rellena
"URL Transmisión/Convencional" en el diálogo de la cámara.

## config.json (junto al .exe)
`hwaccel` (GPU, con respaldo a CPU), `fps_grid`, `fps_zoom`, `auto_quality_on_zoom`.
Para bajar aún más el CPU reduce `fps_grid` (p. ej. 8).

## Compilar
Sube a GitHub: Actions genera `ICSeeLite.exe` (Artifacts). Con un tag `vX.Y.Z` crea un Release.
