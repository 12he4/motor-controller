# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QComboBox, QPushButton, QLineEdit, QSlider, QMenu, QDialog,
    QTextEdit, QCheckBox, QSpinBox, QScrollArea, QSizePolicy, QSplitter
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QSettings

import pyqtgraph as pg

VOFA_STYLE = """
/* 全局背景与字体 */
QWidget {{
    background-color: #F5F7FB;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: {base_font}px;
    color: #2B2F36;
}}

QGroupBox {{
    background-color: #FFFFFF;
    border: 1px solid #DDE3EE;
    border-radius: {radius}px;
    margin-top: {group_margin}px;
    padding-top: {title_gap}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 18px;
    top: 2px;
    padding: 2px 12px;
    color: #FFFFFF;
    background-color: #1F4E79;
    border-radius: {title_radius}px;
    font-weight: 800;
    font-size: {title_font}px;
}}

QPushButton {{
    background-color: #3A86FF;
    color: white;
    border: none;
    border-radius: {radius}px;
    padding: {btn_pad_v}px {btn_pad_h}px;
    font-weight: bold;
    font-size: {btn_font}px;
}}
QPushButton:hover {{ background-color: #5AA0FF; }}
QPushButton:pressed {{ background-color: #2F6FE0; }}

QComboBox, QLineEdit, QSpinBox {{
    border: 1px solid #D6DCE8;
    border-radius: {radius}px;
    padding: {input_pad_v}px {input_pad_h}px;
    background: #FFFFFF;
    selection-background-color: #3A86FF;
    font-size: {input_font}px;
}}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover {{ border: 1px solid #AFC0DE; }}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {{ border: 1px solid #3A86FF; }}
QComboBox::drop-down {{ border: none; width: {dropdown_width}px; }}
QComboBox::down-arrow {{ image: none; }}

QComboBox QAbstractItemView {{
    border: 1px solid #DDE3EE;
    border-radius: 4px;
    background-color: #FFFFFF;
    selection-background-color: #EEF5FF;
    selection-color: #1F4E79;
}}

QTextEdit {{
    border: 1px solid #D6DCE8;
    border-radius: {radius}px;
    background: #FFFFFF;
    padding: {text_pad}px;
    font-size: {text_font}px;
}}
"""


class PIDSliderWidget(QWidget):
    def __init__(self, name, default_val, min_val, max_val, step_val, is_highlight=False):
        super().__init__()
        self.name = name
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.step_val = float(step_val)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl = QLabel(f"{name}:")
        if is_highlight:
            self.lbl.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.lbl)

        self.slider = QSlider(Qt.Horizontal)
        self.update_slider_range()
        layout.addWidget(self.slider)

        self.le = QLineEdit(str(default_val))
        self.le.setMinimumWidth(150)
        self.le.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.le.setAlignment(Qt.AlignCenter)
        le_style = "font-size: 18px; font-weight: bold;"
        if is_highlight:
            le_style += " border: 2px solid red; background-color: #ffe6e6;"
        self.le.setStyleSheet(le_style)
        layout.addWidget(self.le)

        self.slider.valueChanged.connect(self.on_slider_changed)
        self.le.editingFinished.connect(self.on_le_changed)
        self.set_value(float(default_val))

    def update_slider_range(self):
        if self.step_val <= 0:
            self.step_val = 1.0
        steps = int((self.max_val - self.min_val) / self.step_val)
        self.slider.setRange(0, steps)

    def on_slider_changed(self, val):
        real_val = self.min_val + val * self.step_val
        decimals = max(0, len(str(self.step_val).split('.')[-1]) if '.' in str(self.step_val) else 0)
        self.le.setText(f"{real_val:.{decimals}f}")

    def on_le_changed(self):
        try:
            self.set_value(float(self.le.text()))
        except ValueError:
            pass

    def set_value(self, val):
        val = max(self.min_val, min(self.max_val, val))
        steps = int(round((val - self.min_val) / self.step_val))
        self.slider.blockSignals(True)
        self.slider.setValue(steps)
        self.slider.blockSignals(False)
        decimals = max(0, len(str(self.step_val).split('.')[-1]) if '.' in str(self.step_val) else 0)
        self.le.setText(f"{val:.{decimals}f}")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = menu.addAction(f"设置 {self.name} 范围与步长")
        res = menu.exec_(event.globalPos())
        if res == action:
            self.open_config_dialog()

    def open_config_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{self.name} 滑动条参数设置")
        layout = QGridLayout(dialog)

        layout.addWidget(QLabel("最小值:"), 0, 0)
        le_min = QLineEdit(str(self.min_val))
        layout.addWidget(le_min, 0, 1)

        layout.addWidget(QLabel("最大值:"), 1, 0)
        le_max = QLineEdit(str(self.max_val))
        layout.addWidget(le_max, 1, 1)

        layout.addWidget(QLabel("步长:"), 2, 0)
        le_step = QLineEdit(str(self.step_val))
        layout.addWidget(le_step, 2, 1)

        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dialog.accept)
        layout.addWidget(btn_ok, 3, 0, 1, 2)

        if dialog.exec_() == QDialog.Accepted:
            try:
                self.min_val = float(le_min.text())
                self.max_val = float(le_max.text())
                self.step_val = float(le_step.text())
                self.update_slider_range()
                self.on_le_changed()
            except ValueError:
                pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("被动支撑误差补偿上位机控制系统")
        self.scale_factor = self._calc_scale_factor()
        self.setMinimumSize(self._scaled(1000), self._scaled(700))
        self.setStyleSheet(self._build_scaled_style())
        self.setFont(QFont("Microsoft YaHei", self._scaled(12)))

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(self._scaled(6), self._scaled(6), self._scaled(6), self._scaled(6))
        main_layout.setSpacing(self._scaled(6))

        self.settings = QSettings("PassiveSupport", "ErrorCompensationHost")
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.splitterMoved.connect(self._save_splitter_state)

        lbl_blue_style = (
            "background-color: #ECF5FF; color: #1F4E79; border-radius: 6px; "
            f"padding: {self._scaled(4)}px; font-weight: bold;"
        )

        def setup_combo(cb, items, default_idx=0):
            cb.addItems(items)
            cb.setCurrentIndex(default_idx)
            cb.setMinimumSize(self._scaled(140), self._scaled(42))
            cb.setEditable(True)
            cb.lineEdit().setReadOnly(True)
            cb.lineEdit().setAlignment(Qt.AlignCenter)
            cb.setStyleSheet(f"""
                QComboBox, QLineEdit {{
                    background: transparent;
                    font-size: {self._scaled(15)}px;
                    font-weight: bold;
                    color: black;
                }}
            """)
            return cb

        # 左侧滚动区
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        left_container = QWidget()
        left_container_layout = QVBoxLayout(left_container)
        left_container_layout.setContentsMargins(0, 0, 0, 0)
        left_container_layout.setSpacing(self._scaled(8))

        # 1. 通信设置区
        comm_group = QGroupBox("通信设置区")
        comm_group.setStyleSheet(self._group_style("#EAF3FF", "#2F6FE0"))
        comm_layout = QGridLayout()
        comm_layout.setContentsMargins(self._scaled(14), self._scaled(20), self._scaled(14), self._scaled(14))
        comm_layout.setVerticalSpacing(self._scaled(10))

        lbl_port = QLabel("串口号:")
        lbl_port.setAlignment(Qt.AlignCenter)
        lbl_port.setStyleSheet(lbl_blue_style)
        comm_layout.addWidget(lbl_port, 0, 0)

        self.cb_port = QComboBox()
        setup_combo(self.cb_port, ["COM1"])
        comm_layout.addWidget(self.cb_port, 0, 1)

        lbl_baud = QLabel("波特率:")
        lbl_baud.setAlignment(Qt.AlignCenter)
        lbl_baud.setStyleSheet(lbl_blue_style)
        comm_layout.addWidget(lbl_baud, 1, 0)

        self.cb_baud = QComboBox()
        setup_combo(self.cb_baud, ["9600", "115200", "460800"], 1)
        comm_layout.addWidget(self.cb_baud, 1, 1)

        lbl_data = QLabel("数据位:")
        lbl_data.setAlignment(Qt.AlignCenter)
        lbl_data.setStyleSheet(lbl_blue_style)
        comm_layout.addWidget(lbl_data, 2, 0)

        self.cb_data_bits = QComboBox()
        setup_combo(self.cb_data_bits, ["8", "7", "6", "5"], 0)
        comm_layout.addWidget(self.cb_data_bits, 2, 1)

        lbl_stop = QLabel("停止位:")
        lbl_stop.setAlignment(Qt.AlignCenter)
        lbl_stop.setStyleSheet(lbl_blue_style)
        comm_layout.addWidget(lbl_stop, 3, 0)

        self.cb_stop_bits = QComboBox()
        setup_combo(self.cb_stop_bits, ["1", "1.5", "2"], 0)
        comm_layout.addWidget(self.cb_stop_bits, 3, 1)

        lbl_parity = QLabel("校验位:")
        lbl_parity.setAlignment(Qt.AlignCenter)
        lbl_parity.setStyleSheet(lbl_blue_style)
        comm_layout.addWidget(lbl_parity, 4, 0)

        self.cb_parity = QComboBox()
        setup_combo(self.cb_parity, ["None", "Even", "Odd", "Mark", "Space"], 0)
        comm_layout.addWidget(self.cb_parity, 4, 1)

        self.btn_open_serial = QPushButton("打开串口")
        self.btn_open_serial.setMinimumSize(self._scaled(160), self._scaled(45))
        comm_layout.addWidget(self.btn_open_serial, 5, 0, 1, 2, Qt.AlignCenter)
        comm_group.setLayout(comm_layout)
        left_container_layout.addWidget(comm_group)

        # 2. 系统控制区
        ctrl_group = QGroupBox("系统控制区")
        ctrl_group.setStyleSheet(self._group_style("#F1FFF6", "#2E8B57"))
        ctrl_layout = QVBoxLayout()
        self.btn_homing = QPushButton("回中校准")
        ctrl_layout.addWidget(self.btn_homing)

        homing_grid = QGridLayout()
        homing_grid.setVerticalSpacing(self._scaled(6))
        read_only_style = f"background-color: #F5F7FA; color: #4E5D78; font-size: {self._scaled(22)}px; font-weight: bold;"

        lbl_b1 = QLabel("边界1(kg):")
        lbl_b1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        homing_grid.addWidget(lbl_b1, 0, 0)
        self.le_bound1 = QLineEdit("--")
        self.le_bound1.setReadOnly(True)
        self.le_bound1.setAlignment(Qt.AlignCenter)
        self.le_bound1.setStyleSheet(read_only_style)
        homing_grid.addWidget(self.le_bound1, 0, 1)

        lbl_b2 = QLabel("边界2(kg):")
        lbl_b2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        homing_grid.addWidget(lbl_b2, 1, 0)
        self.le_bound2 = QLineEdit("--")
        self.le_bound2.setReadOnly(True)
        self.le_bound2.setAlignment(Qt.AlignCenter)
        self.le_bound2.setStyleSheet(read_only_style)
        homing_grid.addWidget(self.le_bound2, 1, 1)

        lbl_zero = QLabel("零位(kg):")
        lbl_zero.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        homing_grid.addWidget(lbl_zero, 2, 0)
        self.le_zero = QLineEdit("--")
        self.le_zero.setReadOnly(True)
        self.le_zero.setAlignment(Qt.AlignCenter)
        self.le_zero.setStyleSheet(read_only_style)
        homing_grid.addWidget(self.le_zero, 2, 1)
        ctrl_layout.addLayout(homing_grid)

        self.btn_resolution = QPushButton("分辨率测试")
        ctrl_layout.addSpacing(self._scaled(6))
        ctrl_layout.addWidget(self.btn_resolution)

        res_grid = QGridLayout()
        lbl_gain = QLabel("系统增益\n(pulses/kg):")
        lbl_gain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        res_grid.addWidget(lbl_gain, 0, 0)

        self.le_gain = QLineEdit("--")
        self.le_gain.setReadOnly(True)
        self.le_gain.setAlignment(Qt.AlignCenter)
        self.le_gain.setStyleSheet(read_only_style)
        res_grid.addWidget(self.le_gain, 0, 1)
        ctrl_layout.addLayout(res_grid)
        ctrl_group.setLayout(ctrl_layout)
        left_container_layout.addWidget(ctrl_group)

        # 3. 调参配置区
        pid_group = QGroupBox("调参配置区")
        pid_group.setStyleSheet(self._group_style("#FFF7E8", "#E58A00"))
        pid_layout = QVBoxLayout()
        self.widget_kp = PIDSliderWidget("Kp", 0, 0, 10000, 10)
        self.widget_ki = PIDSliderWidget("Ki", 0, 0, 10000, 1, is_highlight=True)
        self.widget_kd = PIDSliderWidget("Kd", 0, 0, 10000, 5)
        pid_layout.addWidget(self.widget_kp)
        pid_layout.addWidget(self.widget_ki)
        pid_layout.addWidget(self.widget_kd)
        self.btn_send_pid = QPushButton("下发 PID 参数")
        pid_layout.addWidget(self.btn_send_pid)
        pid_group.setLayout(pid_layout)
        left_container_layout.addWidget(pid_group)

        # 4. 数据收发区
        term_group = QGroupBox("数据收发区")
        term_group.setStyleSheet(self._group_style("#F4F0FF", "#7B4DFF"))
        term_layout = QVBoxLayout()

        recv_tools_layout = QHBoxLayout()
        self.chk_hex_show = QCheckBox("HEX显示")
        self.chk_hex_show.setChecked(True)
        self.btn_clear_recv = QPushButton("清空接收")
        recv_tools_layout.addWidget(self.chk_hex_show)
        recv_tools_layout.addStretch()
        recv_tools_layout.addWidget(self.btn_clear_recv)
        term_layout.addLayout(recv_tools_layout)

        self.txt_recv = QTextEdit()
        self.txt_recv.setReadOnly(True)
        term_layout.addWidget(self.txt_recv)

        send_tools_layout = QHBoxLayout()
        self.chk_hex_send = QCheckBox("HEX发送")
        self.chk_hex_send.setChecked(True)
        send_tools_layout.addWidget(self.chk_hex_send)
        send_tools_layout.addWidget(QLabel("编码:"))

        self.cb_term_encoding = QComboBox()
        setup_combo(self.cb_term_encoding, ["UTF-8", "GBK", "ASCII"], 0)
        send_tools_layout.addWidget(self.cb_term_encoding)

        self.chk_newline = QCheckBox("追加回车换行")
        send_tools_layout.addWidget(self.chk_newline)
        send_tools_layout.addStretch()
        term_layout.addLayout(send_tools_layout)

        send_input_layout = QHBoxLayout()
        self.le_send = QLineEdit()
        self.le_send.setMinimumHeight(self._scaled(42))
        send_input_layout.addWidget(self.le_send)

        self.btn_send_data = QPushButton("发送")
        self.btn_send_data.setMinimumSize(self._scaled(100), self._scaled(42))
        send_input_layout.addWidget(self.btn_send_data)
        term_layout.addLayout(send_input_layout)
        term_group.setLayout(term_layout)
        left_container_layout.addWidget(term_group, 1)

        left_scroll.setWidget(left_container)
        self.splitter.addWidget(left_scroll)

        # 右侧显示面板
        right_panel = QVBoxLayout()

        status_group = QGroupBox("实时状态区")
        status_group.setStyleSheet(self._group_style("#F0FBF8", "#138A72"))
        status_layout = QHBoxLayout()

        title_font = QFont("Microsoft YaHei", self._scaled(20), QFont.Bold)
        lcd_font = QFont("Consolas", self._scaled(32), QFont.Bold)

        angle_layout = QVBoxLayout()
        lbl_angle_title = QLabel("当前天顶角 (°)")
        lbl_angle_title.setFont(title_font)
        lbl_angle_title.setAlignment(Qt.AlignCenter)
        angle_layout.addWidget(lbl_angle_title)
        self.lbl_angle = QLabel("00.00")
        self.lbl_angle.setFont(lcd_font)
        self.lbl_angle.setStyleSheet("color: #2F6FE0;")
        self.lbl_angle.setAlignment(Qt.AlignCenter)
        self.lbl_angle.setMinimumHeight(self._scaled(60))
        self.lbl_angle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        angle_layout.addWidget(self.lbl_angle)
        status_layout.addLayout(angle_layout)

        target_layout_disp = QVBoxLayout()
        lbl_target_title = QLabel("目标力 (kg / N)")
        lbl_target_title.setFont(title_font)
        lbl_target_title.setAlignment(Qt.AlignCenter)
        target_layout_disp.addWidget(lbl_target_title)
        self.lbl_target = QLabel("0.000      0.000")
        self.lbl_target.setFont(lcd_font)
        self.lbl_target.setStyleSheet("color: #2E8B57;")
        self.lbl_target.setAlignment(Qt.AlignCenter)
        self.lbl_target.setMinimumHeight(self._scaled(60))
        self.lbl_target.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        target_layout_disp.addWidget(self.lbl_target)
        status_layout.addLayout(target_layout_disp)

        actual_layout = QVBoxLayout()
        lbl_actual_title = QLabel("实际力 (kg / N)")
        lbl_actual_title.setFont(title_font)
        lbl_actual_title.setAlignment(Qt.AlignCenter)
        actual_layout.addWidget(lbl_actual_title)
        self.lbl_actual = QLabel("0.000     0.000")
        self.lbl_actual.setFont(lcd_font)
        self.lbl_actual.setStyleSheet("color: #C94A4A;")
        self.lbl_actual.setAlignment(Qt.AlignCenter)
        self.lbl_actual.setMinimumHeight(self._scaled(60))
        self.lbl_actual.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        actual_layout.addWidget(self.lbl_actual)
        status_layout.addLayout(actual_layout)

        error_layout = QVBoxLayout()
        lbl_error_title = QLabel("误差值 (kg / N)")
        lbl_error_title.setFont(title_font)
        lbl_error_title.setAlignment(Qt.AlignCenter)
        error_layout.addWidget(lbl_error_title)
        self.lbl_error = QLabel("+0.000     +0.000")
        self.lbl_error.setFont(lcd_font)
        self.lbl_error.setStyleSheet("color: #8A3FFC;")
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setMinimumHeight(self._scaled(60))
        self.lbl_error.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        error_layout.addWidget(self.lbl_error)
        status_layout.addLayout(error_layout)

        status_group.setLayout(status_layout)
        right_panel.addWidget(status_group, 1)

        plot_group = QGroupBox("波形显控区")
        plot_group.setStyleSheet(self._group_style("#FFFFFF", "#1F4E79"))
        plot_layout = QVBoxLayout()

        btn_layout = QHBoxLayout()
        self.btn_pause_plot = QPushButton("暂停/继续")
        self.btn_clear_plot = QPushButton("清空波形")
        self.btn_auto_range = QPushButton("自动缩放 (Auto)")
        self.btn_pause_plot.setMinimumSize(self._scaled(92), self._scaled(34))
        self.btn_clear_plot.setMinimumSize(self._scaled(92), self._scaled(34))
        self.btn_auto_range.setMinimumSize(self._scaled(120), self._scaled(34))
        btn_layout.addWidget(self.btn_pause_plot)
        btn_layout.addWidget(self.btn_clear_plot)
        btn_layout.addWidget(self.btn_auto_range)

        lbl_dt = QLabel("Δt(ms):")
        lbl_dt.setAlignment(Qt.AlignCenter)
        lbl_dt.setStyleSheet(lbl_blue_style)
        btn_layout.addWidget(lbl_dt)

        self.sb_dt = QSpinBox()
        self.sb_dt.setRange(1, 5000)
        self.sb_dt.setValue(40)
        self.sb_dt.setSingleStep(10)
        self.sb_dt.setMinimumWidth(self._scaled(110))
        self.sb_dt.setAlignment(Qt.AlignCenter)
        self.sb_dt.setStyleSheet(f"""
            QSpinBox, QLineEdit {{
                background-color: #F0F6FF;
                color: #000000;
                font-size: {self._scaled(18)}px;
                font-weight: bold;
            }}
            QSpinBox {{
                border: 1px solid #b9cfee;
                border-radius: {self._scaled(10)}px;
            }}
        """)
        btn_layout.addWidget(self.sb_dt)

        self.btn_record_data = QPushButton("开始录制数据")
        self.btn_record_data.setMinimumSize(self._scaled(104), self._scaled(34))
        btn_layout.addWidget(self.btn_record_data)

        self.btn_x_setting = QPushButton("X轴设置")
        self.btn_record_data.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        self.btn_y_setting = QPushButton("Y轴设置")
        self.btn_x_setting.setMinimumSize(self._scaled(84), self._scaled(34))
        self.btn_y_setting.setMinimumSize(self._scaled(84), self._scaled(34))
        btn_layout.addWidget(self.btn_x_setting)
        btn_layout.addWidget(self.btn_y_setting)
        btn_layout.addStretch()
        plot_layout.addLayout(btn_layout)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(useOpenGL=True)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setClipToView(True)
        self.plot_widget.setDownsampling(mode='peak', auto=True)
        self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Force', units='N')
        self.plot_widget.setLabel('bottom', 'Time', units='s')

        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color=(100, 100, 100), style=Qt.DashLine))
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color=(100, 100, 100), style=Qt.DashLine))
        self.text_tooltip = pg.TextItem(text="", color='k', fill=pg.mkBrush(255, 255, 255, 200))
        self.plot_widget.addItem(self.v_line, ignoreBounds=True)
        self.plot_widget.addItem(self.h_line, ignoreBounds=True)
        self.plot_widget.addItem(self.text_tooltip, ignoreBounds=True)
        self.v_line.hide()
        self.h_line.hide()
        self.text_tooltip.hide()

        self.curve_target = self.plot_widget.plot(pen=pg.mkPen('g', width=2), name="Target Force (N)")
        self.curve_actual = self.plot_widget.plot(pen=pg.mkPen('r', width=2), name="Actual Force (N)")
        self.curve_angle = self.plot_widget.plot(pen=pg.mkPen('b', width=2), name="Angle (°)")

        plot_layout.addWidget(self.plot_widget)
        plot_group.setLayout(plot_layout)
        right_panel.addWidget(plot_group, 5)

        right_wrapper = QWidget()
        right_wrapper.setLayout(right_panel)
        right_wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(right_wrapper)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 4)
        self._restore_splitter_state()
        main_layout.addWidget(self.splitter)

    def _calc_scale_factor(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return 1.0
        geo = screen.availableGeometry()
        ref_w, ref_h = 1920.0, 1080.0
        scale = min(geo.width() / ref_w, geo.height() / ref_h)
        return max(0.65, min(scale, 1.0))

    def _scaled(self, value):
        return max(1, int(round(value * self.scale_factor)))

    def _build_scaled_style(self):
        return VOFA_STYLE.format(
            base_font=self._scaled(18),
            title_font=self._scaled(18),
            btn_font=self._scaled(18),
            input_font=self._scaled(13),
            text_font=self._scaled(14),
            btn_pad_v=self._scaled(7),
            btn_pad_h=self._scaled(10),
            input_pad_v=self._scaled(4),
            input_pad_h=self._scaled(8),
            text_pad=self._scaled(8),
            dropdown_width=self._scaled(22),
            radius=self._scaled(6),
            title_radius=self._scaled(8),
            group_margin=self._scaled(22),
            title_gap=self._scaled(10),
        )

    def _group_style(self, background, accent):
        return f"""
            QGroupBox {{
                background-color: {background};
                border: 2px solid {accent};
                border-radius: {self._scaled(10)}px;
                margin-top: {self._scaled(24)}px;
                padding-top: {self._scaled(8)}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: {self._scaled(16)}px;
                top: {self._scaled(2)}px;
                padding: {self._scaled(2)}px {self._scaled(12)}px;
                color: #FFFFFF;
                background-color: {accent};
                border-radius: {self._scaled(8)}px;
                font-weight: 800;
                font-size: {self._scaled(18)}px;
            }}
        """

    def _splitter_key(self):
        return "main_splitter_sizes"

    def _save_splitter_state(self, *_):
        self.settings.setValue(self._splitter_key(), self.splitter.sizes())

    def _restore_splitter_state(self):
        sizes = self.settings.value(self._splitter_key())
        if sizes:
            try:
                sizes = [int(s) for s in sizes]
                if len(sizes) == 2:
                    self.splitter.setSizes(sizes)
                    return
            except Exception:
                pass
        self.splitter.setSizes([self._scaled(320), self._scaled(880)])


if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())
