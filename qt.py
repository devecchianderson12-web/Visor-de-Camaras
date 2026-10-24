"""Capa de compatibilidad: PyQt6 (Windows 10/11) o PyQt5 (Windows 8.1).
El resto del programa importa SOLO desde aquí y usa la sintaxis de PyQt6."""
try:
    from PyQt6.QtCore import *      # noqa: F401,F403
    from PyQt6.QtGui import *       # noqa: F401,F403
    from PyQt6.QtWidgets import *   # noqa: F401,F403
    QT_VERSION = 6
except ImportError:                 # también cubre «DLL load failed» de Qt6 en sistemas antiguos
    from PyQt5.QtCore import *      # noqa: F401,F403
    from PyQt5.QtGui import *       # noqa: F401,F403
    from PyQt5.QtWidgets import *   # noqa: F401,F403
    QT_VERSION = 5

if QT_VERSION == 5:
    class _EnumView:
        """Clase.Enum.Miembro  ->  Clase.Miembro (estilo PyQt5), si el enum no tiene el miembro."""
        def __init__(self, owner, enum):
            self._owner, self._enum = owner, enum

        def __getattr__(self, name):
            try:
                return getattr(self._enum, name)
            except AttributeError:
                return getattr(self._owner, name)

        def __call__(self, *a, **k):
            return self._enum(*a, **k)

    class _Scoped:
        """Proxy de una clase Qt para aceptar la sintaxis calificada de PyQt6."""
        def __init__(self, cls):
            self._cls = cls

        def __getattr__(self, name):
            v = getattr(self._cls, name)
            if isinstance(v, type) and issubclass(v, int):      # tipo enum
                return _EnumView(self._cls, v)
            return v

        def __call__(self, *a, **k):
            return self._cls(*a, **k)

    Qt = _Scoped(Qt)
    QImage = _Scoped(QImage)
    QEvent = _Scoped(QEvent)
    QLineEdit = _Scoped(QLineEdit)
    QDialogButtonBox = _Scoped(QDialogButtonBox)


def event_pos(e):
    """Posición del evento de ratón (PyQt6: position(), PyQt5: pos())."""
    return e.position().toPoint() if QT_VERSION == 6 else e.pos()


def qexec(obj, *args):
    """exec() en PyQt6 / exec_() en versiones de PyQt5 que no tienen exec()."""
    fn = obj.exec if hasattr(obj, "exec") else obj.exec_
    return fn(*args)
