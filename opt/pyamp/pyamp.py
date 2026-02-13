import sys
import os
import random
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QListWidget, QSlider, QFrame, QMenu)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl, QTimer, QTime
from PyQt6.QtGui import QPainter, QColor, QAction, QLinearGradient

SETTINGS_FILE = os.path.expanduser("~/.pyamp_settings.json")

class EnhancedList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.window().remove_selected_item()
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

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid_exts = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        for f in files:
            if f.lower().endswith(valid_exts):
                self.window().add_file_to_list(f)

class VisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self.bar_heights = [0] * 35
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_bars)
        self.is_playing = False

    def start_animation(self):
        self.is_playing = True
        self.animation_timer.start(60)

    def stop_animation(self):
        self.is_playing = False
        self.animation_timer.stop()
        self.bar_heights = [0] * len(self.bar_heights)
        self.update()

    def update_bars(self):
        if self.is_playing:
            for i in range(len(self.bar_heights)):
                new_h = random.randint(10, self.height() - 10)
                self.bar_heights[i] = int(self.bar_heights[i] * 0.4 + new_h * 0.6)
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() / len(self.bar_heights)
        for i, h in enumerate(self.bar_heights):
            gradient = QLinearGradient(0, self.height() - h, 0, self.height())
            hue = int((i / len(self.bar_heights)) * 300) 
            color = QColor.fromHsv(hue, 200, 255)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(i*w + 2), self.height()-h, int(w-4), h, 3, 3)

class PyAmp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAmp Pro")
        self.setFixedSize(450, 900)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)
        
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration)
        self.player.mediaStatusChanged.connect(self.status_manager)

        self.playlist_files = []
        self.is_shuffle = False
        self.is_repeat = False

        self.init_ui()
        self.apply_styles()
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # LCD Screen
        screen_frame = QFrame()
        screen_frame.setObjectName("screen_container")
        screen_frame.setFixedHeight(150)
        screen_layout = QVBoxLayout(screen_frame)
        self.info_screen = QLabel("READY TO PLAY")
        self.info_screen.setObjectName("screen")
        self.info_screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_screen.setWordWrap(True)
        screen_layout.addWidget(self.info_screen)
        layout.addWidget(screen_frame)

        # Time & Progress
        time_layout = QHBoxLayout()
        self.current_time_lbl = QLabel("0:00")
        self.total_time_lbl = QLabel("00:00")
        for lbl in [self.current_time_lbl, self.total_time_lbl]:
            lbl.setStyleSheet("color: #888; font-size: 11px;")
        self.prog_slider = QSlider(Qt.Orientation.Horizontal)
        self.prog_slider.setObjectName("progress_slider")
        self.prog_slider.sliderMoved.connect(lambda p: self.player.setPosition(p))
        time_layout.addWidget(self.current_time_lbl)
        time_layout.addWidget(self.prog_slider)
        time_layout.addWidget(self.total_time_lbl)
        layout.addLayout(time_layout)

        # Ana Kontroller
        btn_layout = QHBoxLayout()
        btns = [("«", self.seek_backward), ("◀◀", self.prev_m), ("▶", self.play_m), 
                ("⏸", self.pause_m), ("▶▶", self.next_m), ("»", self.seek_forward)]
        for txt, fn in btns:
            b = QPushButton(txt)
            b.setFixedSize(45, 45)
            b.setObjectName("control_btn")
            b.clicked.connect(fn)
            btn_layout.addWidget(b)
        layout.addLayout(btn_layout)

        # Çalma Modları (Yeni Eklenen Bölüm)
        modes_layout = QHBoxLayout()
        self.btn_shuffle = QPushButton("KARIŞTIR: KAPALI")
        self.btn_repeat = QPushButton("TEKRARLA: KAPALI")
        for b in [self.btn_shuffle, self.btn_repeat]:
            b.setFixedHeight(35)
            b.setObjectName("mode_btn")
            modes_layout.addWidget(b)
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        layout.addLayout(modes_layout)

        # Visualizer
        vis_label = QLabel("Audio visualizer")
        vis_label.setStyleSheet("color: #888; font-size: 10px;")
        vis_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(vis_label)
        self.visualizer = VisualizerWidget()
        layout.addWidget(self.visualizer)

        # Playlist & Add Buttons
        util_layout = QHBoxLayout()
        self.btn_list = QPushButton("PLAYLIST")
        self.btn_list.clicked.connect(self.toggle_playlist)
        btn_add = QPushButton("ADD +")
        btn_add.clicked.connect(self.open_f)
        for b in [self.btn_list, btn_add]:
            b.setFixedHeight(30)
            b.setObjectName("util_btn")
            util_layout.addWidget(b)
        layout.addLayout(util_layout)

        self.list = EnhancedList(self)
        self.list.doubleClicked.connect(self.play_sel)
        layout.addWidget(self.list)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a1a; }
            #screen_container { background-color: #000; border-radius: 10px; border: 1px solid #333; }
            QLabel#screen { color: #4CAF50; font-family: 'Segoe UI'; font-size: 20px; font-weight: bold; }
            QPushButton#control_btn { background-color: #2a2a2a; color: #ddd; border-radius: 22px; font-size: 16px; border: 1px solid #333; }
            QPushButton#mode_btn { background-color: #222; color: #888; border: 1px solid #333; border-radius: 5px; font-size: 10px; font-weight: bold; }
            QPushButton#util_btn { background-color: #222; color: #888; border: 1px solid #333; border-radius: 5px; font-size: 10px; }
            QListWidget { background-color: #111; border: 1px solid #222; color: #aaa; }
            QListWidget::item:selected { background-color: #222; color: #4CAF50; border-left: 3px solid #4CAF50; }
            QSlider::groove:horizontal { border: 1px solid #333; height: 4px; background: #333; }
            QSlider::handle:horizontal { background: #fff; width: 12px; height: 12px; margin: -5px 0; border-radius: 6px; }
        """)

    def toggle_shuffle(self):
        self.is_shuffle = not self.is_shuffle
        style = "color: #4CAF50; border-color: #4CAF50;" if self.is_shuffle else ""
        self.btn_shuffle.setText(f"KARIŞTIR: {'AÇIK' if self.is_shuffle else 'KAPALI'}")
        self.btn_shuffle.setStyleSheet(style)

    def toggle_repeat(self):
        self.is_repeat = not self.is_repeat
        style = "color: #4CAF50; border-color: #4CAF50;" if self.is_repeat else ""
        self.btn_repeat.setText(f"TEKRARLA: {'AÇIK' if self.is_repeat else 'KAPALI'}")
        self.btn_repeat.setStyleSheet(style)

    def seek_forward(self):
        self.player.setPosition(self.player.position() + 5000)

    def seek_backward(self):
        self.player.setPosition(self.player.position() - 5000)

    def status_manager(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_repeat:
                self.play_sel()
            else:
                self.next_m()

    def format_time(self, ms):
        return QTime(0, 0).addMSecs(ms).toString("mm:ss")

    def update_slider(self, pos):
        self.prog_slider.setValue(pos)
        self.current_time_lbl.setText(self.format_time(pos))

    def update_duration(self, dur):
        self.prog_slider.setRange(0, dur)
        self.total_time_lbl.setText(self.format_time(dur))

    def next_m(self):
        if self.list.count() == 0: return
        if self.is_shuffle and self.list.count() > 1:
            idx = random.randint(0, self.list.count() - 1)
        else:
            idx = (self.list.currentRow() + 1) % self.list.count()
        self.list.setCurrentRow(idx)
        self.play_sel()

    def prev_m(self):
        if self.list.count() == 0: return
        idx = (self.list.currentRow() - 1) % self.list.count()
        self.list.setCurrentRow(idx)
        self.play_sel()

    def add_file_to_list(self, path):
        if path not in self.playlist_files:
            self.playlist_files.append(path)
            self.list.addItem(os.path.basename(path))

    def open_f(self):
        f, _ = QFileDialog.getOpenFileNames(self, "Müzik Ekle", "", "Ses Dosyaları (*.mp3 *.wav *.m4a *.flac)")
        for path in f: self.add_file_to_list(path)

    def play_sel(self):
        row = self.list.currentRow()
        if row >= 0:
            self.player.setSource(QUrl.fromLocalFile(self.playlist_files[row]))
            self.play_m()

    def play_m(self):
        if self.player.source().isEmpty() and self.list.count() > 0:
            self.list.setCurrentRow(0)
            self.play_sel()
        self.player.play()
        self.visualizer.start_animation()
        if self.list.currentRow() >= 0:
            name = os.path.basename(self.playlist_files[self.list.currentRow()])
            self.info_screen.setText(f"OYNATILIYOR:\n{name}")

    def pause_m(self):
        self.player.pause()
        self.visualizer.stop_animation()

    def toggle_playlist(self):
        if self.list.isVisible():
            self.list.hide()
            self.setFixedSize(450, 600)
        else:
            self.list.show()
            self.setFixedSize(450, 900)

    def remove_selected_item(self):
        items = self.list.selectedItems()
        for item in items:
            row = self.list.row(item)
            self.list.takeItem(row)
            del self.playlist_files[row]

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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PyAmp()
    window.show()
    sys.exit(app.exec())