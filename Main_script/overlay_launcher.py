import sys
import os
import asyncio
import json
import tempfile
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QGroupBox, QSpinBox, 
                             QSystemTrayIcon, QMenu, QAction, QFrame)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QThread, QTimer, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QColor

try:
    import win32gui
    import win32con
    WINDOWS = True
except ImportError:
    WINDOWS = False

def create_icon(color):
    """Crée une icône colorée pour le system tray"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    painter.setBrush(QColor(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    
    painter.setBrush(Qt.NoBrush)
    painter.setPen(QColor(255, 255, 255, 180))
    painter.drawEllipse(4, 4, 56, 56)
    
    painter.end()
    return QIcon(pixmap)

class WebSocketThread(QThread):
    video_added = pyqtSignal(dict)
    video_skipped = pyqtSignal()
    queue_synced = pyqtSignal(list)
    queue_updated = pyqtSignal(list)
    connection_error = pyqtSignal(str)
    connection_success = pyqtSignal()
    clear_all = pyqtSignal()
    
    def __init__(self, server_url, room_id):
        super().__init__()
        self.server_url = server_url
        self.room_id = room_id
        self.running = True
        self.ws = None
        self.loop = None
    
    def notify_video_finished(self):
        """Notifie le serveur qu'une vidéo est terminée"""
        if self.ws and not self.ws.closed and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    self.ws.send(json.dumps({
                        'action': 'video_finished',
                        'room_id': self.room_id
                    })),
                    self.loop
                )
                print(f"📤 Vidéo terminée signalée au serveur")
            except Exception as e:
                print(f"⚠️ Erreur signalement: {e}")
    
    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.connect())
        self.loop.close()
    
    async def connect(self):
        retry_count = 0
        max_retries = 5
        
        while self.running and retry_count < max_retries:
            try:
                import websockets
                
                self.ws = await websockets.connect(
                    self.server_url,
                    ping_interval=None,
                    close_timeout=10
                )
                
                self.connection_success.emit()
                
                join_msg = {'action': 'join', 'room_id': self.room_id}
                await self.ws.send(json.dumps(join_msg))
                
                while self.running:
                    try:
                        message = await asyncio.wait_for(self.ws.recv(), timeout=0.5)
                        data = json.loads(message)
                        action = data.get('action')
                        
                        if action == 'sync':
                            queue = data.get('queue', [])
                            self.queue_synced.emit(queue)
                        elif action == 'new_video':
                            video = data.get('video')
                            if video:
                                self.video_added.emit(video)
                        elif action == 'video_skipped':
                            self.video_skipped.emit()
                        elif action == 'clear_all':
                            self.clear_all.emit()
                        elif action == 'queue_updated':
                            queue = data.get('queue', [])
                            self.queue_updated.emit(queue)
                    
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError:
                        pass
                
                if self.ws and not self.ws.closed:
                    await self.ws.close()
                break
            
            except Exception as e:
                self.connection_error.emit(str(e))
                retry_count += 1
                if retry_count < max_retries and self.running:
                    await asyncio.sleep(2)
        
        if retry_count >= max_retries:
            self.connection_error.emit("Échec après 5 tentatives")
    
    def stop(self):
        self.running = False

class ConfigWindow(QMainWindow):
    start_overlay = pyqtSignal(str, str, str, int, int)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Overlay Configuration")
        self.setFixedSize(700, 580)  # Plus court
        
        # Style Notion Dark Mode (noir/blanc inversé)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #191919;
            }
            QLabel {
                color: #E3E2E0;
                font-size: 14px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            QLineEdit, QSpinBox {
                background-color: #2F2F2F;
                border: 1px solid #3F3F3F;
                border-radius: 6px;
                padding: 12px 14px;
                color: #E3E2E0;
                font-size: 15px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #2383E2;
                background-color: #2F2F2F;
            }
            QLineEdit::placeholder {
                color: #6F6F6F;
            }
            QPushButton {
                background-color: #2383E2;
                border: none;
                border-radius: 6px;
                padding: 14px 24px;
                color: white;
                font-weight: 600;
                font-size: 15px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            QPushButton:hover {
                background-color: #1A6DC1;
            }
            QPushButton:pressed {
                background-color: #155A9E;
            }
            QComboBox {
                background-color: #2F2F2F;
                border: 1px solid #3F3F3F;
                border-radius: 6px;
                padding: 12px 14px;
                color: #E3E2E0;
                font-size: 15px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }
            QComboBox:focus {
                border: 1px solid #2383E2;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #E3E2E0;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: #2F2F2F;
                border: 1px solid #3F3F3F;
                selection-background-color: #2383E2;
                color: #E3E2E0;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #0F0F0F; border-bottom: 1px solid #2F2F2F;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(40, 30, 40, 30)
        
        title = QLabel("Video Overlay")
        title.setFont(QFont("", 28, QFont.Bold))
        title.setStyleSheet("color: #E3E2E0; background: transparent; border: none;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Configure your synchronized video overlay")
        subtitle.setStyleSheet("color: #9B9A97; font-size: 15px; background: transparent; border: none; margin-top: 4px;")
        header_layout.addWidget(subtitle)
        
        layout.addWidget(header)
        
        # Content
        content = QWidget()
        content.setStyleSheet("background-color: #191919;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 35, 40, 35)
        content_layout.setSpacing(28)
        
        # Section: Server
        server_section = QWidget()
        server_layout = QVBoxLayout(server_section)
        server_layout.setSpacing(12)
        server_layout.setContentsMargins(0, 0, 0, 0)
        
        server_label = QLabel("WebSocket Server")
        server_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #9B9A97; text-transform: uppercase; letter-spacing: 0.5px;")
        server_layout.addWidget(server_label)
        
        self.server_input = QLineEdit()
        self.server_input.setText("ws://localhost:8765")
        self.server_input.setPlaceholderText("ws://yourserver.com:8765")
        server_layout.addWidget(self.server_input)
        
        content_layout.addWidget(server_section)
        
        # Section: Room
        room_section = QWidget()
        room_layout = QVBoxLayout(room_section)
        room_layout.setSpacing(12)
        room_layout.setContentsMargins(0, 0, 0, 0)
        
        room_label = QLabel("Room ID")
        room_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #9B9A97; text-transform: uppercase; letter-spacing: 0.5px;")
        room_layout.addWidget(room_label)
        
        self.room_input = QLineEdit()
        self.room_input.setText("test")
        self.room_input.setPlaceholderText("Enter your room name")
        room_layout.addWidget(self.room_input)
        
        content_layout.addWidget(room_section)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("background-color: #2F2F2F; max-height: 1px;")
        content_layout.addWidget(divider)
        
        # Section: Window Size
        size_section = QWidget()
        size_section_layout = QVBoxLayout(size_section)
        size_section_layout.setSpacing(16)
        size_section_layout.setContentsMargins(0, 0, 0, 0)
        
        size_label = QLabel("Maximum Window Size")
        size_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #9B9A97; text-transform: uppercase; letter-spacing: 0.5px;")
        size_section_layout.addWidget(size_label)
        
        size_inputs = QHBoxLayout()
        size_inputs.setSpacing(20)
        
        # Width
        width_container = QWidget()
        width_layout = QVBoxLayout(width_container)
        width_layout.setSpacing(8)
        width_layout.setContentsMargins(0, 0, 0, 0)
        
        width_label = QLabel("Width (px)")
        width_label.setStyleSheet("color: #9B9A97; font-size: 13px;")
        width_layout.addWidget(width_label)
        
        self.width_input = QSpinBox()
        self.width_input.setRange(100, 3840)
        self.width_input.setValue(800)
        self.width_input.setSingleStep(50)
        self.width_input.setMinimumHeight(46)
        width_layout.addWidget(self.width_input)
        
        size_inputs.addWidget(width_container)
        
        # Height
        height_container = QWidget()
        height_layout = QVBoxLayout(height_container)
        height_layout.setSpacing(8)
        height_layout.setContentsMargins(0, 0, 0, 0)
        
        height_label = QLabel("Height (px)")
        height_label.setStyleSheet("color: #9B9A97; font-size: 13px;")
        height_layout.addWidget(height_label)
        
        self.height_input = QSpinBox()
        self.height_input.setRange(100, 2160)
        self.height_input.setValue(600)
        self.height_input.setSingleStep(50)
        self.height_input.setMinimumHeight(46)
        height_layout.addWidget(self.height_input)
        
        size_inputs.addWidget(height_container)
        
        size_section_layout.addLayout(size_inputs)
        
        size_hint = QLabel("Videos will be automatically resized to fit within these dimensions")
        size_hint.setStyleSheet("color: #6F6F6F; font-size: 13px; margin-top: 4px;")
        size_hint.setWordWrap(True)
        size_section_layout.addWidget(size_hint)
        
        content_layout.addWidget(size_section)
        
        # Spacer
        content_layout.addStretch()
        
        layout.addWidget(content)
        
        # Footer avec bouton
        footer = QWidget()
        footer.setStyleSheet("background-color: #0F0F0F; border-top: 1px solid #2F2F2F;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(40, 24, 40, 24)
        
        footer_layout.addStretch()
        
        self.start_button = QPushButton("Start Overlay")
        self.start_button.clicked.connect(self.start_clicked)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setMinimumWidth(180)
        footer_layout.addWidget(self.start_button)
        
        layout.addWidget(footer)
    
    def start_clicked(self):
        server_url = self.server_input.text().strip()
        room_id = self.room_input.text().strip()
        
        if not server_url:
            self.show_error("Server URL is required")
            return
        
        if not room_id:
            self.show_error("Room ID is required")
            return
        
        http_server = server_url.replace('ws://', 'http://').replace(':8765', ':5000')
        max_width = self.width_input.value()
        max_height = self.height_input.value()
        
        self.start_overlay.emit(server_url, room_id, http_server, max_width, max_height)
        self.hide()
    
    def show_error(self, message):
        self.start_button.setText(f"⚠️ {message}")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #EB5757;
                border: none;
                border-radius: 6px;
                padding: 14px 24px;
                color: white;
                font-weight: 600;
                font-size: 15px;
            }
        """)
        QTimer.singleShot(2500, lambda: [
            self.start_button.setText("Start Overlay"),
            self.start_button.setStyleSheet("""
                QPushButton {
                    background-color: #2383E2;
                    border: none;
                    border-radius: 6px;
                    padding: 14px 24px;
                    color: white;
                    font-weight: 600;
                    font-size: 15px;
                }
                QPushButton:hover {
                    background-color: #1A6DC1;
                }
            """)
        ])

class VideoOverlay(QMainWindow):
    status_changed = pyqtSignal(str, str)
    
    def __init__(self, server_url, room_id, http_server, max_width, max_height):
        super().__init__()
        self.video_queue = []
        self.is_playing = False
        self.http_server = http_server
        self.temp_files = []
        self.max_width = max_width
        self.max_height = max_height
        self.room_id = room_id
        
        self.setWindowTitle("Video Overlay Sync")
        self.setGeometry(100, 100, 400, 300)
        
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool
        )
        
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(self.layout)
        
        self.video_widget = QVideoWidget()
        self.layout.addWidget(self.video_widget)
        
        self.status_label = QLabel("🔄", self)
        self.status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: rgba(0, 0, 0, 180);
                border: 1px solid rgba(255, 255, 255, 100);
                border-radius: 15px;
                padding: 8px 12px;
                font-size: 16px;
            }
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedSize(40, 40)
        self.status_label.move(10, 10)
        
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.error.connect(self.on_player_error)
        self.media_player.metaDataChanged.connect(self.adjust_window_size)
        
        self.ws_thread = WebSocketThread(server_url, room_id)
        self.ws_thread.video_added.connect(self.add_to_queue)
        self.ws_thread.video_skipped.connect(self.skip_current)
        self.ws_thread.queue_synced.connect(self.sync_queue)
        self.ws_thread.queue_updated.connect(self.sync_queue)
        self.ws_thread.connection_error.connect(self.on_connection_error)
        self.ws_thread.connection_success.connect(self.on_connection_success)
        self.ws_thread.clear_all.connect(self.clear_all)
        
        self.set_transparent_mode(True)
        
        self.show()
        QApplication.processEvents()
        
        if WINDOWS:
            self.set_click_through()
        
        self.ws_thread.start()
        self.status_changed.emit("connecting", f"Connexion à {room_id}...")
    
    def set_transparent_mode(self, transparent):
        if transparent:
            self.setWindowOpacity(0.0)
            self.video_widget.hide()
            self.status_label.hide()
        else:
            self.setWindowOpacity(1.0)
            self.video_widget.show()
            self.status_label.show()
            self.setStyleSheet("background-color: black;")
    
    def adjust_window_size(self):
        if self.media_player.isMetaDataAvailable():
            size = self.media_player.metaData("Resolution")
            
            if size and isinstance(size, QSize):
                video_width = size.width()
                video_height = size.height()
                
                if video_width > self.max_width or video_height > self.max_height:
                    width_ratio = self.max_width / video_width
                    height_ratio = self.max_height / video_height
                    ratio = min(width_ratio, height_ratio)
                    
                    new_width = int(video_width * ratio)
                    new_height = int(video_height * ratio)
                else:
                    new_width = video_width
                    new_height = video_height
                
                self.resize(new_width, new_height)
                self.status_label.move(10, 10)
    
    def on_connection_success(self):
        self.status_label.setText("✅")
        self.status_changed.emit("connected", f"Connecté à {self.room_id}")
        QTimer.singleShot(2000, lambda: self.status_label.setText("💤"))
    
    def on_connection_error(self, error):
        self.status_label.setText("❌")
        self.status_changed.emit("error", f"Erreur: {error[:30]}")
    
    def sync_queue(self, queue):
        self.video_queue = queue.copy()
        if not self.is_playing and self.video_queue:
            self.play_next()
    
    def add_to_queue(self, video):
        self.video_queue.append(video)
        self.status_changed.emit("connected", f"{self.room_id} ({len(self.video_queue)} en attente)")
        if not self.is_playing:
            self.play_next()
    
    def download_video(self, url):
        try:
            self.status_label.setText("⬇️")
            
            if url.startswith('/'):
                full_url = f"{self.http_server}{url}"
            else:
                full_url = url
            
            response = requests.get(full_url, stream=True, timeout=30)
            response.raise_for_status()
            
            ext = url.split('.')[-1] if '.' in url else 'mp4'
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}')
            
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            
            temp_file.close()
            self.temp_files.append(temp_file.name)
            
            return temp_file.name
        except Exception as e:
            return None
    
    def play_next(self):
        if self.video_queue:
            video = self.video_queue.pop(0)
            self.status_changed.emit("playing", f"Lecture dans {self.room_id}")
            
            self.set_transparent_mode(False)
            
            video_type = video.get('type', '')
            video_url = video.get('url', '')
            
            if video_type == 'youtube':
                self.status_label.setText("⚠️")
                QTimer.singleShot(2000, lambda: [self.set_transparent_mode(True), self.play_next()])
            elif video_url.startswith('/uploads/'):
                local_path = self.download_video(video_url)
                if local_path:
                    url = QUrl.fromLocalFile(local_path)
                    self.media_player.setMedia(QMediaContent(url))
                    self.media_player.setVolume(70)
                    self.media_player.play()
                else:
                    self.status_label.setText("❌")
                    QTimer.singleShot(2000, lambda: [self.set_transparent_mode(True), self.play_next()])
            elif os.path.exists(video_url):
                url = QUrl.fromLocalFile(os.path.abspath(video_url))
                self.media_player.setMedia(QMediaContent(url))
                self.media_player.setVolume(70)
                self.media_player.play()
            else:
                url = QUrl(video_url)
                self.media_player.setMedia(QMediaContent(url))
                self.media_player.setVolume(70)
                self.media_player.play()
        else:
            self.set_transparent_mode(True)
            self.status_changed.emit("connected", f"Connecté à {self.room_id}")
    
    def on_state_changed(self, state):
        self.is_playing = (state == QMediaPlayer.PlayingState)
        if self.is_playing:
            self.status_label.setText("▶️")
    
    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            print("✅ Vidéo terminée")
            
            # Notifier le serveur
            self.ws_thread.notify_video_finished()
            
            self.set_transparent_mode(True)
            QTimer.singleShot(500, self.play_next)
        elif status == QMediaPlayer.InvalidMedia:
            print("❌ Média invalide")
            
            # Notifier le serveur même en cas d'erreur
            self.ws_thread.notify_video_finished()
            
            self.set_transparent_mode(True)
            self.play_next()
    
    def on_player_error(self, error):
        self.status_label.setText("❌")
        self.set_transparent_mode(True)
        QTimer.singleShot(1000, self.play_next)
    
    def skip_current(self):
        self.media_player.stop()
        self.set_transparent_mode(True)
        self.play_next()
    
    def clear_all(self):
        self.media_player.stop()
        self.video_queue.clear()
        self.set_transparent_mode(True)
        self.status_changed.emit("connected", f"Queue vidée - {self.room_id}")
    
    def set_click_through(self):
        try:
            hwnd = int(self.winId())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            new_style = ex_style | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
        except:
            pass
    
    def closeEvent(self, event):
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
        
        self.ws_thread.stop()
        self.ws_thread.wait(2000)
        event.accept()

class TrayManager:
    def __init__(self, app):
        self.app = app
        
        self.icon_connecting = create_icon("#FFA500")
        self.icon_connected = create_icon("#22C55E")
        self.icon_error = create_icon("#DC2626")
        self.icon_playing = create_icon("#3B82F6")
        
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.icon_connecting)
        self.tray.setToolTip("Video Overlay - Démarrage...")
        
        self.menu = QMenu()
        
        self.status_action = QAction("📡 Statut: Démarrage...")
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        
        self.menu.addSeparator()
        
        self.show_config_action = QAction("⚙️ Configuration")
        self.show_config_action.triggered.connect(self.show_config)
        self.menu.addAction(self.show_config_action)
        
        self.menu.addSeparator()
        
        self.quit_action = QAction("❌ Quitter")
        self.quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(self.quit_action)
        
        self.tray.setContextMenu(self.menu)
        self.tray.show()
        
        self.tray.activated.connect(self.on_tray_activated)
    
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_config()
    
    def update_status(self, status_type, message):
        if status_type == "connecting":
            self.tray.setIcon(self.icon_connecting)
            icon_emoji = "🔄"
        elif status_type == "connected":
            self.tray.setIcon(self.icon_connected)
            icon_emoji = "✅"
        elif status_type == "playing":
            self.tray.setIcon(self.icon_playing)
            icon_emoji = "▶️"
        elif status_type == "error":
            self.tray.setIcon(self.icon_error)
            icon_emoji = "❌"
        else:
            icon_emoji = "📡"
        
        self.status_action.setText(f"{icon_emoji} {message}")
        self.tray.setToolTip(f"Video Overlay\n{message}")
    
    def show_config(self):
        if hasattr(self.app, 'config_window'):
            self.app.config_window.show()
            self.app.config_window.raise_()
            self.app.config_window.activateWindow()
    
    def quit_app(self):
        QApplication.quit()

class MainApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        
        self.tray_manager = TrayManager(self)
        
        self.config_window = ConfigWindow()
        self.overlay_window = None
        
        self.config_window.start_overlay.connect(self.start_overlay)
        self.config_window.show()
    
    def start_overlay(self, server_url, room_id, http_server, max_width, max_height):
        if self.overlay_window:
            self.overlay_window.close()
        
        self.overlay_window = VideoOverlay(server_url, room_id, http_server, max_width, max_height)
        self.overlay_window.status_changed.connect(self.tray_manager.update_status)

if __name__ == '__main__':
    app = MainApp(sys.argv)
    sys.exit(app.exec_())