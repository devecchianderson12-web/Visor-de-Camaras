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
- Doble clic: maximiza una cámara (pausa las demás). Doble clic o Esc: volver.
- F11: pantalla completa (oculta la barra). Minimizar = todo en pausa.

## Notas
- Si Windows pregunta por el firewall al buscar ONVIF, acepta «Redes privadas» (usa multicast UDP 3702).
- config.json (junto al .exe): `hwaccel`, `fps_grid`, `fps_zoom`, `auto_quality_on_zoom`, `layout_mode`.

## Compilar
Sube a GitHub: Actions genera `TheWatcher.exe` (con el icono del ojo) (Artifacts).
