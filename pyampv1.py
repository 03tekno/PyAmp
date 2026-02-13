import sys
import os
import random
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QListWidget, QSlider, QFrame, QMessageBox, QMenu)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl, QTimer, QTime
from PyQt6.QtGui import QPainter, QColor, QPen, QAction

SETTINGS_FILE = os.path.expanduser("~/.pyamp_settings.json")

class EnhancedList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Çoklu seçimi aktif et
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def keyPressEvent(self, event):
        # Del tuşu ile silme
        if event.key() == Qt.Key.Key_Delete:
            self.window().remove_selected_item()
        # Ctrl+A ile tümünü seçme
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key.Key_A:
            self.selectAll()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, position):
        menu = QMenu()
        select_all_action = QAction("Tümünü Seç (Ctrl+A)", self)
        select_all_action.triggered.connect(self.selectAll)
        
        remove_action = QAction("Seçilenleri Sil (Del)", self)
        remove_action.triggered.connect(self.window().remove_selected_item)
        
        menu.addAction(select_all_action)
        menu.addSeparator()
        menu.addAction(remove_action)
        menu.exec(self.mapToGlobal(position))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid_exts = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        for f in files:
            if f.lower().endswith(valid_exts):
                self.window().add_file_to_list(f)

class VisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.bar_heights = [0] * 40
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_bars)
        self.is_playing = False

    def start_animation(self):
        self.is_playing = True
        self.animation_timer.start(50)

    def stop_animation(self):
        self.is_playing = False
        self.animation_timer.stop()
        self.bar_heights = [0] * len(self.bar_heights)
        self.update()

    def update_bars(self):
        if self.is_playing:
            for i in range(len(self.bar_heights)):
                new_h = random.randint(5, self.height())
                self.bar_heights[i] = int(self.bar_heights[i] * 0.5 + new_h * 0.5)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() / len(self.bar_heights)
        for i, h in enumerate(self.bar_heights):
            painter.setBrush(QColor(0, 255, 68))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(i*w), self.height()-h, int(w-1), h)

class PyAmp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAmp v1.0")
        self.setFixedSize(420, 850)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)
        
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration)
        self.player.mediaStatusChanged.connect(self.status_manager)

        self.playlist_files = []
        self.total_time_ms = 0
        self.is_shuffle = False
        self.is_repeat = False

        self.init_ui()
        self.apply_styles()
        self.load_settings()

    def init_ui(self):
        widget = QWidget()
        self.setCentralWidget(widget)
        layout = QVBoxLayout(widget)

        # --- ÜST BAŞLIK ---
        header_layout = QHBoxLayout()
        title_label = QLabel("PyAmp Music Player")
        title_label.setStyleSheet("color: #0f0; font-weight: bold; font-size: 10px;")
        btn_about = QPushButton("INFO ℹ")
        btn_about.setFixedSize(50, 20)
        btn_about.setStyleSheet("font-size: 8px; background-color: #222; border: 1px solid #444;")
        btn_about.clicked.connect(self.show_about)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(btn_about)
        layout.addLayout(header_layout)

        # --- LCD SCREEN ---
        screen_frame = QFrame()
        screen_frame.setObjectName("screen_container")
        screen_frame.setFixedHeight(100)
        screen_layout = QVBoxLayout(screen_frame)
        
        self.info_screen = QLabel("PyAmp v1.0\nSystem Ready")
        self.info_screen.setObjectName("screen")
        self.info_screen.setWordWrap(True)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("time_display")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        screen_layout.addWidget(self.info_screen)
        screen_layout.addWidget(self.time_label)
        layout.addWidget(screen_frame)

        # --- VISUALIZER ---
        self.visualizer = VisualizerWidget()
        layout.addWidget(self.visualizer)

        # --- PROGRESS SLIDER ---
        self.prog_slider = QSlider(Qt.Orientation.Horizontal)
        self.prog_slider.sliderMoved.connect(lambda p: self.player.setPosition(p))
        layout.addWidget(self.prog_slider)

        # --- ANA KONTROLLER ---
        btn_layout = QHBoxLayout()
        btns = [("⏮", self.prev_m), ("▶", self.play_m), ("⏸", self.pause_m), 
                ("⏹", self.stop_m), ("⏭", self.next_m)]
        for txt, fn in btns:
            b = QPushButton(txt)
            b.clicked.connect(fn)
            btn_layout.addWidget(b)
        layout.addLayout(btn_layout)

        # --- SHUFFLE & REPEAT ---
        mode_layout = QHBoxLayout()
        self.btn_shuffle = QPushButton("SHUFFLE")
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        
        self.btn_repeat = QPushButton("REPEAT")
        self.btn_repeat.clicked.connect(self.toggle_repeat)

        for b in [self.btn_shuffle, self.btn_repeat]:
            b.setFixedHeight(25)
            b.setStyleSheet("font-size: 9px; background-color: #222;")
            mode_layout.addWidget(b)
        layout.addLayout(mode_layout)

        # --- ARAÇLAR ---
        util_layout = QHBoxLayout()
        self.btn_list = QPushButton("LIST ☰")
        self.btn_list.clicked.connect(self.toggle_playlist)
        btn_add = QPushButton("ADD +")
        btn_add.clicked.connect(self.open_f)
        for b in [self.btn_list, btn_add]:
            b.setFixedHeight(30)
            b.setStyleSheet("font-size: 10px; background-color: #222;")
            util_layout.addWidget(b)
        layout.addLayout(util_layout)

        # --- EQUALIZER ---
        self.eq_frame = QFrame()
        self.eq_frame.setObjectName("eq_panel")
        eq_layout = QVBoxLayout(self.eq_frame)
        eq_layout.addWidget(QLabel("10-BAND GRAPHIC EQUALIZER"))
        sliders_layout = QHBoxLayout()
        self.eq_bands = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
        for freq in self.eq_bands:
            v_box = QVBoxLayout()
            s = QSlider(Qt.Orientation.Vertical)
            s.setRange(-12, 12)
            s.setValue(0)
            s.setFixedHeight(100)
            s.valueChanged.connect(lambda val, f=freq: self.update_eq_info(f, val))
            lbl = QLabel(freq)
            lbl.setStyleSheet("font-size: 7px; color: #0f0;")
            v_box.addWidget(s, alignment=Qt.AlignmentFlag.AlignCenter)
            v_box.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
            sliders_layout.addLayout(v_box)
        eq_layout.addLayout(sliders_layout)
        layout.addWidget(self.eq_frame)

        # --- PLAYLIST ---
        self.list = EnhancedList(self)
        self.list.doubleClicked.connect(self.play_sel)
        layout.addWidget(self.list)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            #screen_container { background-color: #050505; border: 2px solid #333; padding: 10px; }
            QLabel#screen { color: #00FF00; font-family: 'Consolas'; font-size: 13px; }
            QLabel#time_display { color: #00FF00; font-family: 'Courier New'; font-size: 14px; font-weight: bold; }
            QPushButton { background-color: #333; color: #0f0; border: 1px solid #444; border-radius: 2px; }
            QPushButton:hover { background-color: #444; border-color: #0f0; }
            QFrame#eq_panel { background-color: #1a1a1a; border: 1px solid #333; padding: 5px; }
            QListWidget { background-color: #000; color: #0f0; border: 1px solid #222; outline: none; }
            QListWidget::item:selected { background-color: #111; border-left: 2px solid #0f0; color: #fff; }
        """)

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        color = "#005500" if self.is_shuffle else "#222"
        self.btn_shuffle.setStyleSheet(f"background-color: {color}; color: #0f0; font-size: 9px;")

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        color = "#005500" if self.is_repeat else "#222"
        self.btn_repeat.setStyleSheet(f"background-color: {color}; color: #0f0; font-size: 9px;")

    def status_manager(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_repeat:
                self.play_sel()
            elif self.is_shuffle:
                row = random.randint(0, self.list.count() - 1)
                self.list.setCurrentRow(row)
                self.play_sel()
            else:
                self.next_m()

    def format_time(self, ms):
        time = QTime(0, 0).addMSecs(ms)
        return time.toString("mm:ss")

    def update_slider(self, pos):
        self.prog_slider.setValue(pos)
        self.time_label.setText(f"{self.format_time(pos)} / {self.format_time(self.total_time_ms)}")

    def update_duration(self, dur):
        self.prog_slider.setRange(0, dur)
        self.total_time_ms = dur

    def remove_selected_item(self):
        # Seçili tüm öğeleri al
        selected_items = self.list.selectedItems()
        if not selected_items:
            return
        
        # İndekslerin silme sırasında kaymaması için büyükten küçüğe sıralıyoruz
        rows = sorted([self.list.row(item) for item in selected_items], reverse=True)
        
        for row in rows:
            self.list.takeItem(row)
            if row < len(self.playlist_files):
                del self.playlist_files[row]
        
        self.info_screen.setText(f"SİSTEM:\n{len(rows)} dosya silindi.")

    def show_about(self):
        QMessageBox.information(self, "PyAmp v1.0", "Linux için Python ile yazılmış Müzik Çalar")

    def toggle_playlist(self):
        if self.list.isVisible():
            self.list.hide()
            self.setFixedSize(420, 560)
        else:
            self.list.show()
            self.setFixedSize(420, 850)

    def save_settings(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.playlist_files, f)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    for path in json.load(f):
                        if os.path.exists(path): self.add_file_to_list(path)
            except: pass

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def update_eq_info(self, freq, val):
        self.info_screen.setText(f"EQ Adjustment:\n{freq}Hz -> {val} dB")

    def add_file_to_list(self, path):
        if path not in self.playlist_files:
            self.playlist_files.append(path)
            self.list.addItem(os.path.basename(path))

    def open_f(self):
        f, _ = QFileDialog.getOpenFileNames(self, "Add Music", "", "Audio (*.mp3 *.wav *.m4a *.flac)")
        for path in f: self.add_file_to_list(path)

    def play_sel(self):
        row = self.list.currentRow()
        if row >= 0:
            self.player.setSource(QUrl.fromLocalFile(self.playlist_files[row]))
            self.play_m()

    def play_m(self):
        if self.player.source().isEmpty() and self.list.count() > 0:
            if self.list.currentRow() < 0:
                self.list.setCurrentRow(0)
            self.play_sel()
        self.player.play()
        self.visualizer.start_animation()
        if self.list.currentRow() >= 0:
            self.info_screen.setText(f"PLAYING:\n{os.path.basename(self.playlist_files[self.list.currentRow()])}")

    def pause_m(self):
        self.player.pause()
        self.visualizer.stop_animation()

    def stop_m(self):
        self.player.stop()
        self.visualizer.stop_animation()
        self.info_screen.setText("STOPPED")

    def next_m(self):
        if self.is_shuffle:
            row = random.randint(0, self.list.count() - 1)
            self.list.setCurrentRow(row)
            self.play_sel()
        else:
            idx = self.list.currentRow()
            if idx < self.list.count() - 1:
                self.list.setCurrentRow(idx + 1)
                self.play_sel()

    def prev_m(self):
        idx = self.list.currentRow()
        if idx > 0:
            self.list.setCurrentRow(idx - 1)
            self.play_sel()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = PyAmp()
    window.show()
    sys.exit(app.exec())