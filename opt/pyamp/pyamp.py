import sys, os, random, json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QListWidget, QSlider, 
                             QFrame, QMessageBox, QMenu)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import Qt, QUrl, QTimer, QTime
from PyQt6.QtGui import QPainter, QColor, QPen, QAction, QFont

SETTINGS_FILE = os.path.expanduser("~/.pyamp_settings.json")

class EnhancedList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete: self.window().remove_selected_item()
        elif event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key.Key_A: self.selectAll()
        else: super().keyPressEvent(event)
    def show_context_menu(self, position):
        menu = QMenu(); sa = QAction("Tümünü Seç", self); sa.triggered.connect(self.selectAll)
        rs = QAction("Seçilenleri Sil", self); rs.triggered.connect(self.window().remove_selected_item)
        menu.addAction(sa); menu.addSeparator(); menu.addAction(rs); menu.exec(self.mapToGlobal(position))
    def dragEnterEvent(self, event): (event.accept() if event.mimeData().hasUrls() else event.ignore())
    def dragMoveEvent(self, event): (event.accept() if event.mimeData().hasUrls() else event.ignore())
    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        for f in files:
            if f.lower().endswith(valid): self.window().add_file_to_list(f)

class VisualizerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedHeight(80); self.bar_heights = [2] * 30
        self.animation_timer = QTimer(self); self.animation_timer.timeout.connect(self.update_bars)
        self.is_playing = False; self.current_color = QColor("#00FF88")
    def start_animation(self): self.is_playing = True; self.animation_timer.start(50)
    def stop_animation(self): self.is_playing = False; self.animation_timer.stop(); self.bar_heights = [2]*len(self.bar_heights); self.update()
    def update_bars(self):
        if self.is_playing:
            for i in range(len(self.bar_heights)):
                nh = random.randint(2, self.height()-5); self.bar_heights[i] = int(self.bar_heights[i]*0.4 + nh*0.6)
            self.update()
    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()/len(self.bar_heights)
        for i, h in enumerate(self.bar_heights):
            p.setBrush(self.current_color); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(int(i*w + 2), self.height()-h, int(w-4), h, 3, 3)

class PyAmp(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("PyAmp")
        self.resize(450, 750)
        self.player = QMediaPlayer(); self.audio_output = QAudioOutput(); self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)
        self.player.positionChanged.connect(self.update_slider)
        self.player.durationChanged.connect(self.update_duration); self.player.mediaStatusChanged.connect(self.status_manager)
        self.playlist_files = []; self.total_time_ms = 0; self.is_shuffle = False; self.is_repeat = False
        self.current_theme_hex = "#FF8AAE" 
        
        self.init_ui()
        self.load_settings()
        self.apply_styles(self.current_theme_hex)

    def init_ui(self):
        widget = QWidget(); self.setCentralWidget(widget); layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(15)

        h_lay = QHBoxLayout()
        h_lay.addSpacing(30) 
        h_lay.addStretch() 
        self.title_lbl = QLabel("PyAmp Music Player")
        self.title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        h_lay.addWidget(self.title_lbl)
        h_lay.addStretch() 
        btn_ab = QPushButton("?")
        btn_ab.setFixedSize(30, 30); btn_ab.setCursor(Qt.CursorShape.PointingHandCursor); btn_ab.clicked.connect(self.show_about)
        h_lay.addWidget(btn_ab); layout.addLayout(h_lay)
        
        main_screen_lay = QHBoxLayout()
        scr_f = QFrame(); scr_f.setObjectName("screen_container"); scr_f.setFixedHeight(120); scr_lay = QVBoxLayout(scr_f)
        self.info_screen = QLabel("Müzik Çalar Hazır"); self.info_screen.setObjectName("screen"); self.info_screen.setWordWrap(True)
        self.time_label = QLabel("00:00 / 00:00"); self.time_label.setObjectName("time_display"); self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        scr_lay.addWidget(self.info_screen); scr_lay.addWidget(self.time_label)
        
        # SES KONTROL ALANI (Kısaltıldı)
        vol_lay = QVBoxLayout()
        vol_lay.setSpacing(2) # Etiket ve çubuk arası mesafe daraltıldı
        
        self.vol_perc_lbl = QLabel("70%")
        self.vol_perc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vol_perc_lbl.setObjectName("vol_label")
        self.vol_perc_lbl.setFixedWidth(40)
        
        self.volume_slider = QSlider(Qt.Orientation.Vertical)
        self.volume_slider.setRange(0, 100); self.volume_slider.setValue(70); 
        self.volume_slider.setFixedWidth(30)
        self.volume_slider.setFixedHeight(90)
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        vol_lay.addStretch() # Üstten boşluk vererek ortaladık
        vol_lay.addWidget(self.vol_perc_lbl, alignment=Qt.AlignmentFlag.AlignHCenter)
        vol_lay.addWidget(self.volume_slider, alignment=Qt.AlignmentFlag.AlignHCenter)
        vol_lay.addStretch() # Alttan boşluk
        
        main_screen_lay.addWidget(scr_f, stretch=5); main_screen_lay.addLayout(vol_lay, stretch=1); layout.addLayout(main_screen_lay)
        
        self.visualizer = VisualizerWidget(); layout.addWidget(self.visualizer)
        self.prog_slider = QSlider(Qt.Orientation.Horizontal); self.prog_slider.sliderMoved.connect(lambda p: self.player.setPosition(p)); layout.addWidget(self.prog_slider)
        
        b_lay = QHBoxLayout(); b_lay.setSpacing(10)
        btns = [("⏮", self.prev_m), ("▶", self.play_m), ("⏸", self.pause_m), ("⏹", self.stop_m), ("⏭", self.next_m)]
        for t, f in btns: 
            b = QPushButton(t); b.setFixedHeight(55); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(f); b_lay.addWidget(b)
        layout.addLayout(b_lay)

        m_lay = QHBoxLayout()
        self.btn_shuffle = QPushButton("Karıştır"); self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_repeat = QPushButton("Tekrarla"); self.btn_repeat.clicked.connect(self.toggle_repeat)
        for b in [self.btn_shuffle, self.btn_repeat]: b.setFixedHeight(35); m_lay.addWidget(b)
        layout.addLayout(m_lay)

        u_lay = QHBoxLayout()
        self.btn_list = QPushButton("Liste ☰"); self.btn_list.clicked.connect(self.toggle_playlist)
        self.btn_theme = QPushButton("Tema 🎨"); self.btn_theme.clicked.connect(self.show_theme_menu)
        btn_add = QPushButton("Ekle +"); btn_add.clicked.connect(self.open_f)
        for b in [self.btn_list, self.btn_theme, btn_add]: b.setFixedHeight(40); u_lay.addWidget(b)
        layout.addLayout(u_lay)

        self.list = EnhancedList(self); self.list.setObjectName("playlist")
        self.list.doubleClicked.connect(self.play_sel); layout.addWidget(self.list)

    def apply_styles(self, color):
        self.current_theme_hex = color
        self.visualizer.current_color = QColor(color)
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: #121214; }}
            QWidget {{ font-family: 'Segoe UI', sans-serif; }}
            
            #screen_container {{ background-color: #1E1E22; border-radius: 15px; padding: 15px; border: 1px solid #2A2A2E; }}
            QLabel#screen {{ color: white; font-size: 14px; font-weight: 500; }}
            QLabel#time_display {{ color: {color}; font-size: 12px; font-family: 'Consolas'; }}
            
            QLabel#vol_label {{ 
                color: {color}; 
                font-size: 12px; 
                font-weight: bold; 
            }}
            
            QPushButton {{ background-color: #252529; color: white; border: none; border-radius: 10px; padding: 5px; }}
            QPushButton:hover {{ background-color: #323238; border: 1px solid {color}; }}
            
            #playlist {{ 
                background-color: #18181B; color: {color}; border-radius: 12px; border: none; padding: 5px; outline: none; font-size: 13px;
            }}
            #playlist::item {{ padding: 12px; border-radius: 8px; margin: 2px; background-color: transparent; }}
            #playlist::item:selected {{ background-color: transparent; color: {color}; font-weight: bold; border-left: 4px solid {color}; }}
            #playlist::item:hover {{ background-color: #252529; }}
            
            QSlider::groove:horizontal {{ background: #252529; height: 6px; border-radius: 3px; }}
            QSlider::handle:horizontal {{ background: {color}; width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }}
            QSlider::groove:vertical {{ background: #252529; width: 6px; border-radius: 3px; }}
            QSlider::handle:vertical {{ background: {color}; height: 14px; width: 14px; margin: 0 -4px; border-radius: 7px; }}
        """)

    def show_theme_menu(self):
        menu = QMenu(self)
        themes = {
            "Modern Turkuaz": "#00FF88", "Royal Blue": "#4D96FF", "Vivid Purple": "#B166CC",
            "Sunset Orange": "#FF6B6B", "Electric Gold": "#FFD93D", "Rose Pink": "#FF8AAE",
            "Buz Beyazı": "#F7F7F7", "Minimal Gri": "#8E8E93"
        }
        for name, hex_code in themes.items():
            action = QAction(name, self); action.triggered.connect(lambda checked, h=hex_code: self.apply_styles(h)); menu.addAction(action)
        menu.exec(self.btn_theme.mapToGlobal(self.btn_theme.rect().bottomLeft()))

    def set_volume(self, value): 
        self.audio_output.setVolume(value / 100)
        self.vol_perc_lbl.setText(f"{value}%")
        
    def toggle_shuffle(self): self.is_shuffle = not self.is_shuffle; self.btn_shuffle.setStyleSheet(f"color: {self.current_theme_hex if self.is_shuffle else 'white'};")
    def toggle_repeat(self): self.is_repeat = not self.is_repeat; self.btn_repeat.setStyleSheet(f"color: {self.current_theme_hex if self.is_repeat else 'white'};")
    def status_manager(self, s):
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            if self.is_repeat: self.play_sel()
            elif self.is_shuffle: r = random.randint(0, self.list.count()-1); self.list.setCurrentRow(r); self.play_sel()
            else: self.next_m()
    def format_time(self, ms): return QTime(0, 0).addMSecs(ms).toString("mm:ss")
    def update_slider(self, p): self.prog_slider.setValue(p); self.time_label.setText(f"{self.format_time(p)} / {self.format_time(self.total_time_ms)}")
    def update_duration(self, d): self.prog_slider.setRange(0, d); self.total_time_ms = d
    def remove_selected_item(self):
        sel = self.list.selectedItems()
        rows = sorted([self.list.row(i) for i in sel], reverse=True)
        for r in rows: self.list.takeItem(r); del self.playlist_files[r]
    def show_about(self): QMessageBox.information(self, "Hakkında", "Mobilturka-2026")
    def toggle_playlist(self): self.list.setVisible(not self.list.isVisible())
    def save_settings(self):
        try:
            data = {"playlist": self.playlist_files, "theme": self.current_theme_hex, "vol": self.volume_slider.value()}
            with open(SETTINGS_FILE, "w") as f: json.dump(data, f)
        except: pass
    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    for p in data.get("playlist", []): (self.add_file_to_list(p) if os.path.exists(p) else None)
                    self.current_theme_hex = data.get("theme", "#00FF88")
                    v = data.get("vol", 70); self.volume_slider.setValue(v); self.set_volume(v)
            except: pass
    def closeEvent(self, e): self.save_settings(); e.accept()
    def add_file_to_list(self, p):
        if p not in self.playlist_files: self.playlist_files.append(p); self.list.addItem(os.path.basename(p))
    def open_f(self):
        f, _ = QFileDialog.getOpenFileNames(self, "Müzik Seç", "", "Ses Dosyaları (*.mp3 *.wav *.flac)")
        for p in f: self.add_file_to_list(p)
    def play_sel(self):
        r = self.list.currentRow()
        if 0 <= r < len(self.playlist_files):
            self.player.setSource(QUrl.fromLocalFile(self.playlist_files[r])); self.player.play()
            self.visualizer.start_animation(); self.info_screen.setText(os.path.basename(self.playlist_files[r]))
    def play_m(self): self.player.play(); self.visualizer.start_animation()
    def pause_m(self): self.player.pause(); self.visualizer.stop_animation()
    def stop_m(self): self.player.stop(); self.visualizer.stop_animation()
    def next_m(self):
        if self.list.count() > 0:
            r = (self.list.currentRow()+1) % self.list.count(); self.list.setCurrentRow(r); self.play_sel()
    def prev_m(self):
        if self.list.count() > 0:
            r = (self.list.currentRow()-1) % self.list.count(); self.list.setCurrentRow(r); self.play_sel()

if __name__ == '__main__':
    app = QApplication(sys.argv); window = PyAmp(); window.show(); sys.exit(app.exec())
