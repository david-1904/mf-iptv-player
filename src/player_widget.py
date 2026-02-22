"""
MPV Player Widget fuer PySide6 - OpenGL-basiert (Wayland-kompatibel)
"""
from ctypes import CFUNCTYPE, c_void_p, c_char_p
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, Signal
import mpv

import sys

try:
    import dbus
    _DBUS_AVAILABLE = True
except ImportError:
    _DBUS_AVAILABLE = False

if sys.platform == 'win32':
    import ctypes
    _ES_CONTINUOUS       = 0x80000000
    _ES_SYSTEM_REQUIRED  = 0x00000001
    _ES_DISPLAY_REQUIRED = 0x00000002

_GL_GET_PROC_ADDR_FN = CFUNCTYPE(c_void_p, c_void_p, c_char_p)


class MpvPlayerWidget(QOpenGLWidget):
    """Widget das mpv via OpenGL Render-API in Qt rendert"""

    stream_info_changed = Signal(dict)
    double_clicked = Signal()
    escape_pressed = Signal()
    buffering_changed = Signal(bool)  # True = buffering, False = playing
    stream_ended = Signal(str)        # reason: 'error', 'eof', 'stop', ...
    _mpv_update = Signal()
    _buffering_signal = Signal(bool)
    _stream_ended_signal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)

        self.player = None
        self.ctx = None
        self._proc_addr_wrapper = None
        self._pending_url = None
        self._player_initialized = False
        self._is_buffering = False
        self._screensaver_inhibitions = []  # [(service, path, iface_name, cookie), ...]

        self._mpv_update.connect(self.update)
        self._buffering_signal.connect(self._on_buffering_changed)
        self._stream_ended_signal.connect(self.stream_ended)

    def initializeGL(self):
        """OpenGL-Kontext bereit - MPV initialisieren"""
        if self._player_initialized:
            return
        self._init_player()

    def _init_player(self):
        if self._player_initialized:
            return

        self.player = mpv.MPV(vo='libmpv', hwdec='auto')
        self.player['keep-open'] = True

        def _get_proc_address(ctx, name):
            glctx = self.context()
            if not glctx:
                return 0
            addr = glctx.getProcAddress(name)
            return addr if addr else 0

        self._proc_addr_wrapper = _GL_GET_PROC_ADDR_FN(_get_proc_address)

        self.ctx = mpv.MpvRenderContext(
            self.player, 'opengl',
            opengl_init_params={'get_proc_address': self._proc_addr_wrapper}
        )
        self.ctx.update_cb = lambda: self._mpv_update.emit()

        self._player_initialized = True

        # Buffering-State beobachten
        @self.player.property_observer('paused-for-cache')
        def _on_paused_for_cache(_name, value):
            self._buffering_signal.emit(bool(value))

        @self.player.property_observer('core-idle')
        def _on_core_idle(_name, value):
            # core-idle + nicht pausiert = buffering/laden
            if value and self.player and not self.player.pause and self.player.path:
                self._buffering_signal.emit(True)
            elif not value:
                self._buffering_signal.emit(False)

        @self.player.event_callback('end-file')
        def _on_end_file(event):
            # mpv liefert reason als ctypes.c_int (integer), nicht als String
            _reason_map = {0: 'eof', 1: 'stop', 2: 'quit', 3: 'error', 4: 'redirect'}
            try:
                raw = event['event']['reason']
                # ctypes c_int hat .value, Enums haben .name
                if hasattr(raw, 'name'):
                    reason = raw.name.lower()
                elif hasattr(raw, 'value'):
                    reason = _reason_map.get(int(raw.value), 'unknown')
                elif isinstance(raw, int):
                    reason = _reason_map.get(raw, 'unknown')
                else:
                    reason = str(raw).lower()
            except Exception:
                reason = 'unknown'
            self._stream_ended_signal.emit(reason)

        if self._pending_url:
            self.player.play(self._pending_url)
            self._pending_url = None

    def paintGL(self):
        if self.ctx:
            ratio = self.devicePixelRatioF()
            w = int(self.width() * ratio)
            h = int(self.height() * ratio)
            self.ctx.render(flip_y=True, opengl_fbo={
                'fbo': self.defaultFramebufferObject(),
                'w': w,
                'h': h,
            })

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
        elif event.key() == Qt.Key_Space:
            self.pause()
        else:
            super().keyPressEvent(event)

    def _on_buffering_changed(self, buffering: bool):
        """Thread-safe handler for buffering state changes"""
        if buffering != self._is_buffering:
            self._is_buffering = buffering
            self.buffering_changed.emit(buffering)

    def _inhibit_screensaver(self):
        """Verhindert Bildschirmschoner/Sperrbildschirm (Windows: SetThreadExecutionState, Linux: D-Bus)"""
        if sys.platform == 'win32':
            ctypes.windll.kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_DISPLAY_REQUIRED | _ES_SYSTEM_REQUIRED
            )
            return
        if not _DBUS_AVAILABLE or self._screensaver_inhibitions:
            return
        # Verschiedene D-Bus-Interfaces probieren (KDE, GNOME, generisch)
        candidates = [
            ('org.freedesktop.ScreenSaver', '/ScreenSaver', 'org.freedesktop.ScreenSaver'),
            ('org.freedesktop.ScreenSaver', '/org/freedesktop/ScreenSaver', 'org.freedesktop.ScreenSaver'),
            ('org.gnome.SessionManager', '/org/gnome/SessionManager', 'org.gnome.SessionManager'),
        ]
        try:
            bus = dbus.SessionBus()
            for service, path, iface_name in candidates:
                try:
                    proxy = bus.get_object(service, path)
                    iface = dbus.Interface(proxy, iface_name)
                    if iface_name == 'org.gnome.SessionManager':
                        cookie = iface.Inhibit('iptv-app', dbus.UInt32(0), 'Video playback', dbus.UInt32(8))
                    else:
                        cookie = iface.Inhibit('iptv-app', 'Video playback')
                    self._screensaver_inhibitions.append((service, path, iface_name, cookie))
                except Exception:
                    pass
        except Exception:
            pass

    def _uninhibit_screensaver(self):
        """Gibt Bildschirmschoner/Sperrbildschirm wieder frei"""
        if sys.platform == 'win32':
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
            return
        if not _DBUS_AVAILABLE or not self._screensaver_inhibitions:
            return
        try:
            bus = dbus.SessionBus()
            for service, path, iface_name, cookie in self._screensaver_inhibitions:
                try:
                    proxy = bus.get_object(service, path)
                    iface = dbus.Interface(proxy, iface_name)
                    if iface_name == 'org.gnome.SessionManager':
                        iface.Uninhibit(cookie)
                    else:
                        iface.UnInhibit(cookie)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._screensaver_inhibitions = []

    def play(self, url: str):
        """Spielt eine URL ab"""
        self._buffering_signal.emit(True)
        self._inhibit_screensaver()
        if not self._player_initialized:
            self._pending_url = url
        else:
            self.player.play(url)

    def stop(self):
        """Stoppt die Wiedergabe"""
        self._uninhibit_screensaver()
        if self.player:
            self.player.stop()

    def pause(self):
        """Pausiert/Fortsetzt die Wiedergabe"""
        if self.player:
            self.player.pause = not self.player.pause

    def set_volume(self, volume: int):
        """Setzt die Lautstaerke (0-100)"""
        if self.player:
            self.player.volume = max(0, min(100, volume))

    def seek(self, seconds: float, relative: bool = True):
        """Spult vor/zurueck"""
        if self.player:
            try:
                if relative:
                    self.player.seek(seconds, "relative")
                else:
                    self.player.seek(seconds, "absolute")
            except Exception:
                pass

    @property
    def duration(self) -> float:
        """Gibt die Gesamtdauer zurueck"""
        return self.player.duration if self.player else 0

    @property
    def position(self) -> float:
        """Gibt die aktuelle Position zurueck"""
        return self.player.time_pos if self.player else 0

    @property
    def is_playing(self) -> bool:
        """Prueft ob gerade abgespielt wird"""
        if not self.player:
            return False
        return not self.player.pause and self.player.time_pos is not None

    def get_stream_info(self) -> dict:
        """Returns stream info from MPV properties"""
        info = {
            "video_width": None,
            "video_height": None,
            "fps": None,
            "video_codec": None,
            "audio_codec": None,
            "audio_tracks": [],
            "subtitle_tracks": [],
        }

        if not self.player:
            return info

        try:
            video_params = self.player.video_params
            if video_params:
                info["video_width"] = video_params.get("w")
                info["video_height"] = video_params.get("h")

            info["fps"] = self.player.container_fps
            info["video_codec"] = self.player.video_codec
            info["audio_codec"] = self.player.audio_codec_name

            track_list = self.player.track_list
            if track_list:
                for track in track_list:
                    if track.get("type") == "audio":
                        info["audio_tracks"].append({
                            "id": track.get("id"),
                            "lang": track.get("lang", "Unknown"),
                            "title": track.get("title", ""),
                            "channels": track.get("demux-channels", ""),
                            "selected": track.get("selected", False),
                        })
                    elif track.get("type") == "sub":
                        info["subtitle_tracks"].append({
                            "id": track.get("id"),
                            "lang": track.get("lang", ""),
                            "title": track.get("title", ""),
                            "selected": track.get("selected", False),
                        })
        except Exception:
            pass

        return info

    def set_subtitle_track(self, track_id):
        """Setzt Untertitel-Track (False = aus)"""
        if self.player:
            self.player["sid"] = track_id

    def set_audio_track(self, track_id):
        """Setzt Audio-Track"""
        if self.player:
            self.player["aid"] = track_id

    def get_audio_tracks(self) -> list[dict]:
        """Gibt verfuegbare Audio-Spuren zurueck"""
        if not self.player:
            return []
        tracks = []
        try:
            track_list = self.player.track_list
            if track_list:
                for track in track_list:
                    if track.get("type") == "audio":
                        tracks.append({
                            "id": track.get("id"),
                            "lang": track.get("lang", ""),
                            "title": track.get("title", ""),
                            "channels": track.get("demux-channels", ""),
                            "selected": track.get("selected", False),
                        })
        except Exception:
            pass
        return tracks

    def get_subtitle_tracks(self) -> list[dict]:
        """Gibt verfuegbare Untertitel zurueck"""
        if not self.player:
            return []
        tracks = []
        try:
            track_list = self.player.track_list
            if track_list:
                print(f"[DEBUG] Alle Tracks ({len(track_list)}):")
                for track in track_list:
                    print(f"  type={track.get('type')} id={track.get('id')} lang={track.get('lang')} title={track.get('title')} codec={track.get('codec')} selected={track.get('selected')}")
                    if track.get("type") == "sub":
                        tracks.append({
                            "id": track.get("id"),
                            "lang": track.get("lang", ""),
                            "title": track.get("title", ""),
                            "selected": track.get("selected", False),
                        })
                print(f"[DEBUG] Sub-Tracks gefunden: {len(tracks)}")
        except Exception as e:
            print(f"[DEBUG] Fehler: {e}")
        return tracks

    def emit_stream_info(self):
        """Emit current stream info via signal"""
        info = self.get_stream_info()
        self.stream_info_changed.emit(info)

    def cleanup(self):
        """Raeumt auf bevor das Widget zerstoert wird"""
        self._uninhibit_screensaver()
        self.makeCurrent()
        if self.ctx:
            self.ctx.free()
            self.ctx = None
        self.doneCurrent()
        if self.player:
            self.player.terminate()
            self.player = None

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
