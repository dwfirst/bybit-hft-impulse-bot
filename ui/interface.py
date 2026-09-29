from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, 
    QSlider, QLabel, QPushButton, QTextEdit, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt

SLIDER_LABELS = {
    "slider_1_momentum_threshold_pct": {
        "name": "Momentum Threshold", 
        "desc": "Minimum percentage of sharp price change.",
        "min": 1, "max": 150, "div": 10.0, "unit": "%"
    },
    "slider_2_panic_window_sec": {
        "name": "Panic Window", 
        "desc": "Interval for tick analysis.",
        "min": 1, "max": 60, "div": 1.0, "unit": "s"
    },
    "slider_3_liquidation_volume_threshold_usdt": {
        "name": "Liquidation Volume", 
        "desc": "Volume filter for liquidation orders.",
        "min": 1000, "max": 100000, "div": 1.0, "unit": "$"
    },
    "slider_4_rebound_entry_trigger_pct": {
        "name": "Rebound Depth", 
        "desc": "Rebound from peak to enter short position.",
        "min": 1, "max": 50, "div": 10.0, "unit": "%"
    },
    "slider_5_trend_exhaustion_limit_1m_candles": {
        "name": "Candle Filter", 
        "desc": "Limit of 1m trend candles.",
        "min": 3, "max": 15, "div": 1.0, "unit": ""
    },
    "slider_6_fixed_margin_per_trade_usdt": {
        "name": "Trade Margin", 
        "desc": "Fixed deposit per position.",
        "min": 1, "max": 50, "div": 1.0, "unit": "$"
    },
    "slider_8_trailing_activation_pct": {
        "name": "Trailing Activation", 
        "desc": "Profit level to start trailing stop.",
        "min": 1, "max": 50, "div": 10.0, "unit": "%"
    },
    "slider_9_instability_rollback_exit_pct": {
        "name": "Rollback Exit", 
        "desc": "Rollback threshold from peak profit.",
        "min": 1, "max": 20, "div": 10.0, "unit": "%"
    },
}

class TradingTerminalUI(QMainWindow):
    def __init__(self, config: dict, kill_switch_callback):
        super().__init__()
        self.config = config
        self.sliders_config = config["sliders"]
        self.kill_switch = kill_switch_callback
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("IMPULSECATCHER V5 // CYBER-ANTIQUE TERMINAL")
        self.resize(920, 650)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0e0e11;
            }
            QLabel {
                color: #b0b0b8;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            QFrame#ParamCard {
                background-color: #141418;
                border: 1px solid #23232b;
                border-radius: 8px;
                padding: 8px;
            }
            QFrame#ParamCard:hover {
                border: 1px solid #3a3a48;
                background-color: #17171c;
            }
            QSlider::groove:horizontal {
                border: none;
                height: 3px;
                background: #252530;
                border-radius: 1px;
            }
            QSlider::sub-page:horizontal {
                background: #d8d8e0;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                background: #f0f0f5;
                border: 2px solid #0e0e11;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                border: 2px solid #505060;
            }
            QTextEdit {
                background-color: #08080a;
                color: #00ff77;
                font-family: 'Consolas', monospace;
                font-size: 12px;
                border: 1px solid #202028;
                border-radius: 6px;
                padding: 10px;
            }
            QPushButton#KillButton {
                background-color: #1c0c0c;
                color: #ff5555;
                border: 1px solid #501c1c;
                font-family: 'Consolas', monospace;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                height: 45px;
                letter-spacing: 1px;
            }
            QPushButton#KillButton:hover {
                background-color: #2b1010;
                border: 1px solid #ff4444;
            }
            QPushButton#KillButton:pressed {
                background-color: #ff4444;
                color: #000000;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(14, 14, 14, 14)

        top_bar = QHBoxLayout()
        sys_title = QLabel("✦CORE SYSTEM✦ // V5.0 HFT ENGINE by Deus Gevorgyan")
        sys_title.setStyleSheet("color: #6a6a75; font-size: 11px; font-weight: bold; letter-spacing: 1.5px;")
        top_bar.addWidget(sys_title)
        top_bar.addStretch()
        
        status_lbl = QLabel("STATUS: [ONLINE & SECURE]")
        status_lbl.setStyleSheet("color: #00ff77; font-size: 11px; font-weight: bold;")
        top_bar.addWidget(status_lbl)
        main_layout.addLayout(top_bar)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #0e0e11;")
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setSpacing(12)
        scroll_content_layout.setContentsMargins(0, 0, 4, 0)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        slider_items = list(SLIDER_LABELS.items())
        for index, (key, info) in enumerate(slider_items):
            if key not in self.sliders_config:
                continue
                
            row = index // 2
            col = index % 2

            card = QFrame()
            card.setObjectName("ParamCard")
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)
            card_layout.setContentsMargins(8, 8, 8, 8)

            current_val = self.sliders_config[key]
            unit = info["unit"]

            lbl_title = QLabel(f"{info['name'].upper()}: <span style='color: #ffffff; font-weight: bold;'>{current_val} {unit}</span>")
            lbl_title.setStyleSheet("font-size: 11px;")

            lbl_desc = QLabel(f"{info['desc']}")
            lbl_desc.setStyleSheet("color: #70707c; font-size: 10px;")

            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setMinimum(info["min"])
            slider.setMaximum(info["max"])
            slider.setValue(int(current_val * info["div"]))
            
            slider.valueChanged.connect(
                lambda val, k=key, d=info["div"], un=unit, name=info["name"], l=lbl_title: 
                self._on_slider_changed(k, val, d, un, name, l)
            )

            card_layout.addWidget(lbl_title)
            card_layout.addWidget(lbl_desc)
            card_layout.addWidget(slider)
            grid_layout.addWidget(card, row, col)

        scroll_content_layout.addLayout(grid_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #1c1c24; max-height: 1px;")
        scroll_content_layout.addWidget(line)

        term_label = QLabel("LIVE TELEMETRY STREAM:")
        term_label.setStyleSheet("color: #7a7a85; font-size: 11px; font-weight: bold;")
        scroll_content_layout.addWidget(term_label)
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMinimumHeight(140)
        scroll_content_layout.addWidget(self.log_viewer)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        btn = QPushButton("🚨 EMERGENCY KILL SWITCH [F12]")
        btn.setObjectName("KillButton")
        btn.clicked.connect(self.kill_switch)
        main_layout.addWidget(btn)

        self.append_log("[UI] Adaptive interface initialized successfully.")

    def _on_slider_changed(self, key, value, div, unit, name, label_widget):
        try:
            actual = value / div
            self.sliders_config[key] = actual
            label_widget.setText(f"{name.upper()}: <span style='color: #ffffff; font-weight: bold;'>{actual} {unit}</span>")
        except Exception as e:
            self.append_log(f"[UI ERROR] Parameter error: {e}")

    def append_log(self, text: str):
        self.log_viewer.append(text)
        self.log_viewer.moveCursor(self.log_viewer.textCursor().MoveOperation.End)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F12:
            self.kill_switch()
