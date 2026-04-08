import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QComboBox, QPushButton, QLineEdit, QSlider, QMenu, QDialog,
                             QTextEdit, QCheckBox, QSpinBox) 
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer

import pyqtgraph as pg

VOFA_STYLE = """
/* 全局背景与字体 */
QWidget {
    background-color: #F4F6F9;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 25px; /* 基础字号加大 */
    color: #303133;
}

/* 卡片式 GroupBox 设计 */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E4E7ED;
    border-radius: 8px;
    margin-top: 25px; 
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    left: 15px;
    top: 5px;
    color: gray;           /* 标题颜色变为灰色 */
    font-weight: bold;     /* 标题加粗 */
    font-size: 25px;       /* 标题字号加大 */
}

/* 扁平化按钮 */
QPushButton {
    background-color: #409EFF;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 10px 15px;
    font-weight: bold;
    font-size: 25px; /* 按钮字号加大 */
}
QPushButton:hover {
    background-color: #66B1FF;
}
QPushButton:pressed {
    background-color: #3A8EE6;
}

/* 下拉框与输入框 */
QComboBox, QLineEdit, QSpinBox {
    border: 1px solid #DCDFE6;
    border-radius: 6px;
    padding: 5px 10px;
    background: #FFFFFF;
    selection-background-color: #409EFF;
    font-size: 16px; 
}
QComboBox:hover, QLineEdit:hover, QSpinBox:hover {
    border: 1px solid #C0C4CC;
}
QComboBox:focus, QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #409EFF;
}
QComboBox::drop-down {
    border: none;
    width: 25px; 
}
QComboBox::down-arrow {
    image: none; 
}

/* 下拉框展开时的列表样式 */
QComboBox QAbstractItemView {
    border: 1px solid #E4E7ED;
    border-radius: 4px;
    background-color: #FFFFFF;
    selection-background-color: #F5F7FA;
    selection-color: #409EFF;
}

/* 文本区域 */
QTextEdit {
    border: 1px solid #DCDFE6;
    border-radius: 6px;
    background: #FFFFFF;
    padding: 10px;
    font-size: 20px;
}
"""

# ================= 支持右键配置与浮点数的 PID 调参自定义组件 =================
class PIDSliderWidget(QWidget):
    def __init__(self, name, default_val, min_val, max_val, step_val, is_highlight=False):
        super().__init__()
        self.name = name
        self.min_val = float(min_val)
        self.max_val = float(max_val)
        self.step_val = float(step_val)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. 标签
        self.lbl = QLabel(f"{name}:")
        if is_highlight:
            self.lbl.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.lbl)
        
        # 2. 滑动条
        self.slider = QSlider(Qt.Horizontal)
        self.update_slider_range()
        layout.addWidget(self.slider)
        
        # 3. 输入框
        self.le = QLineEdit(str(default_val))
        self.le.setFixedWidth(150)  
        self.le.setAlignment(Qt.AlignCenter) 
        
        le_style = "font-size: 25px; font-weight: bold;"
        if is_highlight:
            le_style += " border: 2px solid red; background-color: #ffe6e6;"
        self.le.setStyleSheet(le_style)
        
        layout.addWidget(self.le)
        
        # 信号绑定
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.le.editingFinished.connect(self.on_le_changed)
        
        self.set_value(float(default_val))

    def update_slider_range(self):
        if self.step_val <= 0: self.step_val = 1.0 
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


# ================= 主界面 UI 布局类 =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("被动支撑误差补偿上位机控制系统")
        self.resize(1200, 800)

        self.setStyleSheet(VOFA_STYLE)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # 定义一个统一的标签蓝底样式
        lbl_blue_style = "background-color: #ECF5FF; color: #409EFF; border-radius: 6px; padding: 4px; font-weight: bold;"

        # 内部封装一个辅助函数，实现定长定高与强制居中，供全局下拉框复用
        def setup_combo(cb, items, default_idx=0):
            cb.addItems(items)
            cb.setCurrentIndex(default_idx)
            cb.setFixedSize(140, 42) 
            cb.setEditable(True)
            cb.lineEdit().setReadOnly(True)
            cb.lineEdit().setAlignment(Qt.AlignCenter)
            
            cb.setStyleSheet("""
                QComboBox, QLineEdit {
                    background: transparent; 
                    font-size: 25px;        
                    font-weight: bold;      
                    color: black;         
                }
            """)
            return cb

        # ================= 左侧控制面板 =================
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        # 1. 通信设置区
        comm_group = QGroupBox("通信设置区")
        comm_layout = QGridLayout()
        comm_layout.setContentsMargins(20, 30, 20, 20) 
        comm_layout.setVerticalSpacing(20) 
        
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
        self.btn_open_serial.setFixedSize(160, 45) 
        comm_layout.addWidget(self.btn_open_serial, 5, 0, 1, 2, Qt.AlignCenter)
        
        comm_layout.setColumnStretch(2, 1)
        
        comm_group.setLayout(comm_layout)
        left_panel.addWidget(comm_group)
        
        # 2. 系统控制区
        ctrl_group = QGroupBox("系统控制区")
        ctrl_layout = QVBoxLayout()
        
       # --- 回中校准部分 ---
        self.btn_homing = QPushButton("回中校准")
        ctrl_layout.addWidget(self.btn_homing)
        
        homing_grid = QGridLayout()
        homing_grid.setVerticalSpacing(10)
        
        # 定义统一的灰色大字号只读样式
        read_only_style = "background-color: #F5F7FA; color: #909399; font-size: 32px; font-weight: bold;"
        
        lbl_b1 = QLabel("边界1(kg):")
        lbl_b1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        homing_grid.addWidget(lbl_b1, 0, 0)
        self.le_bound1 = QLineEdit("--")
        self.le_bound1.setReadOnly(True)
        self.le_bound1.setAlignment(Qt.AlignCenter)
        self.le_bound1.setStyleSheet(read_only_style) # 应用大字号样式
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
        
        # --- 分辨率测试部分 ---
        self.btn_resolution = QPushButton("分辨率测试")
        ctrl_layout.addSpacing(10) 
        ctrl_layout.addWidget(self.btn_resolution)
        
        res_grid = QGridLayout()
        lbl_gain = QLabel("系统增益\n(pulses/kg):")
        lbl_gain.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        res_grid.addWidget(lbl_gain, 0, 0)
        
        self.le_gain = QLineEdit("--")
        self.le_gain.setReadOnly(True)
        self.le_gain.setAlignment(Qt.AlignCenter)
        self.le_gain.setStyleSheet(read_only_style) # 应用大字号样式
        res_grid.addWidget(self.le_gain, 0, 1)
        
        ctrl_layout.addLayout(res_grid)
        
        ctrl_group.setLayout(ctrl_layout)
        left_panel.addWidget(ctrl_group)
        
        # 3. 调参配置区 
        pid_group = QGroupBox("调参配置区")
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
        left_panel.addWidget(pid_group)
        
        # 4. 数据收发区
        term_group = QGroupBox("数据收发区")
        term_layout = QVBoxLayout()
        
        # --- 接收区顶部工具栏 ---
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
        
        # --- 发送区工具栏 ---
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
        
        # --- 发送区输入栏 ---
        send_input_layout = QHBoxLayout()
        self.le_send = QLineEdit()
        send_input_layout.addWidget(self.le_send)
        
        self.btn_send_data = QPushButton("发送")
        send_input_layout.addWidget(self.btn_send_data)
        
        term_layout.addLayout(send_input_layout)
        term_group.setLayout(term_layout)
        
        # 赋予拉伸因子 1，让它自动填满下方所有空白区域
        left_panel.addWidget(term_group, 1) 
        
        # 注释掉底部的弹簧，取消向上挤压的效果
        # left_panel.addStretch() 
        
        main_layout.addLayout(left_panel, 1)
        
        # ================= 右侧显示面板 =================
        right_panel = QVBoxLayout()
        
        # 5. 实时状态区 
        status_group = QGroupBox("实时状态区")
        status_layout = QHBoxLayout()
        
        title_font = QFont("Microsoft YaHei", 20, QFont.Bold)
        lcd_font = QFont("Consolas", 32, QFont.Bold)
        
        angle_layout = QVBoxLayout()
        lbl_angle_title = QLabel("当前天顶角 (°)")
        lbl_angle_title.setFont(title_font)
        lbl_angle_title.setAlignment(Qt.AlignCenter) 
        angle_layout.addWidget(lbl_angle_title)
        
        self.lbl_angle = QLabel("00.00")
        self.lbl_angle.setFont(lcd_font)
        self.lbl_angle.setStyleSheet("color: blue;")
        self.lbl_angle.setAlignment(Qt.AlignCenter) 
        angle_layout.addWidget(self.lbl_angle)
        status_layout.addLayout(angle_layout)
        
        target_layout_disp = QVBoxLayout()
        lbl_target_title = QLabel("目标力 (kg / N)")
        lbl_target_title.setFont(title_font)
        lbl_target_title.setAlignment(Qt.AlignCenter)
        target_layout_disp.addWidget(lbl_target_title)
        
        self.lbl_target = QLabel("0.000      0.000")
        self.lbl_target.setFont(lcd_font)
        self.lbl_target.setStyleSheet("color: darkgreen;")
        self.lbl_target.setAlignment(Qt.AlignCenter)
        target_layout_disp.addWidget(self.lbl_target)
        status_layout.addLayout(target_layout_disp)
        
        actual_layout = QVBoxLayout()
        lbl_actual_title = QLabel("实际力 (kg / N)")
        lbl_actual_title.setFont(title_font)
        lbl_actual_title.setAlignment(Qt.AlignCenter)
        actual_layout.addWidget(lbl_actual_title)
        
        self.lbl_actual = QLabel("0.000     0.000")
        self.lbl_actual.setFont(lcd_font)
        self.lbl_actual.setStyleSheet("color: darkred;")
        self.lbl_actual.setAlignment(Qt.AlignCenter)
        actual_layout.addWidget(self.lbl_actual)
        status_layout.addLayout(actual_layout)
        
        error_layout = QVBoxLayout()
        lbl_error_title = QLabel("误差值 (kg / N)")
        lbl_error_title.setFont(title_font)
        lbl_error_title.setAlignment(Qt.AlignCenter)
        error_layout.addWidget(lbl_error_title)
        
        self.lbl_error = QLabel("+0.000     +0.000") 
        self.lbl_error.setFont(lcd_font)
        self.lbl_error.setStyleSheet("color: darkmagenta;") 
        self.lbl_error.setAlignment(Qt.AlignCenter)
        error_layout.addWidget(self.lbl_error)
        status_layout.addLayout(error_layout)
        
        status_group.setLayout(status_layout)
        right_panel.addWidget(status_group, 1)
        
        # 6. 波形显控区
        plot_group = QGroupBox("波形显控区")
        plot_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        self.btn_pause_plot = QPushButton("暂停/继续")
        self.btn_clear_plot = QPushButton("清空波形")
        self.btn_auto_range = QPushButton("自动缩放 (Auto)") 
        
        btn_layout.addWidget(self.btn_pause_plot)
        btn_layout.addWidget(self.btn_clear_plot)
        btn_layout.addWidget(self.btn_auto_range) 
        
        btn_layout.addWidget(QLabel("Δt(ms):"))
        self.sb_dt = QSpinBox()
        self.sb_dt.setRange(1, 5000)
        self.sb_dt.setValue(40)
        self.sb_dt.setSingleStep(10)
        self.sb_dt.setFixedWidth(85)            
        self.sb_dt.setAlignment(Qt.AlignCenter) 
        
        self.sb_dt.setStyleSheet("""
            QSpinBox, QLineEdit {
                background-color: #ECF5FF; 
                color: #409EFF;            
                font-size: 30px;           
                font-weight: bold;         
            }
            QSpinBox {
                border: 1px solid #b3d8ff;
                border-radius: 6px;
            }
        """)
        btn_layout.addWidget(self.sb_dt)
        
        self.btn_record_data = QPushButton("开始录制数据")
        btn_layout.addWidget(self.btn_record_data)   

        self.btn_x_setting = QPushButton("X轴设置")
        self.btn_y_setting = QPushButton("Y轴设置")
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
        
        main_layout.addLayout(right_panel, 4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())