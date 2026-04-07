import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QGroupBox, QLabel, 
                             QComboBox, QPushButton, QLineEdit, QSlider, QMenu, QDialog,
                             QTextEdit, QCheckBox) 
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QTimer
import pyqtgraph as pg

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
        self.le.setFixedWidth(100)  
        if is_highlight:
            self.le.setStyleSheet("border: 2px solid red; background-color: #ffe6e6;")
        layout.addWidget(self.le)
        
        # 信号绑定 (仅做 UI 同步，不下发指令)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.le.editingFinished.connect(self.on_le_changed)
        
        self.set_value(float(default_val))

    def update_slider_range(self):
        if self.step_val <= 0: self.step_val = 1.0 # 防御性除零保护
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

    # 右键菜单事件
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
                self.on_le_changed() # 更新同步
            except ValueError:
                pass


# ================= 主界面 UI 布局类 =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("被动支撑误差补偿上位机控制系统")
        self.resize(1200, 800)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # ================= 左侧控制面板 =================
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)
        
        # 1. 通信设置区 
        comm_group = QGroupBox("通信设置区")
        comm_layout = QGridLayout()
        
        comm_layout.addWidget(QLabel("串口号:"), 0, 0)
        self.cb_port = QComboBox()
        self.cb_port.addItem("COM1") 
        comm_layout.addWidget(self.cb_port, 0, 1)
        
        comm_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.cb_baud = QComboBox()
        self.cb_baud.addItems(["9600", "115200", "460800"])
        self.cb_baud.setCurrentText("115200")
        comm_layout.addWidget(self.cb_baud, 1, 1)
        
        comm_layout.addWidget(QLabel("数据位:"), 2, 0)
        self.cb_data_bits = QComboBox()
        self.cb_data_bits.addItems(["8", "7", "6", "5"])
        self.cb_data_bits.setCurrentText("8")
        comm_layout.addWidget(self.cb_data_bits, 2, 1)
        
        comm_layout.addWidget(QLabel("停止位:"), 3, 0)
        self.cb_stop_bits = QComboBox()
        self.cb_stop_bits.addItems(["1", "1.5", "2"])
        self.cb_stop_bits.setCurrentText("1")
        comm_layout.addWidget(self.cb_stop_bits, 3, 1)
        
        comm_layout.addWidget(QLabel("校验位:"), 4, 0)
        self.cb_parity = QComboBox()
        self.cb_parity.addItems(["None", "Even", "Odd", "Mark", "Space"])
        self.cb_parity.setCurrentText("None")
        comm_layout.addWidget(self.cb_parity, 4, 1)
        
        self.btn_open_serial = QPushButton("打开串口")
        comm_layout.addWidget(self.btn_open_serial, 5, 0, 1, 2)
        
        comm_group.setLayout(comm_layout)
        left_panel.addWidget(comm_group)
        
        # 2. 系统控制区
        ctrl_group = QGroupBox("系统控制区")
        ctrl_layout = QVBoxLayout()
        self.btn_homing = QPushButton("回中校准")
        self.btn_resolution = QPushButton("分辨率测试")
        ctrl_layout.addWidget(self.btn_homing)
        ctrl_layout.addWidget(self.btn_resolution)
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
        terminal_group = QGroupBox("数据收发区")
        terminal_layout = QVBoxLayout()
        
        self.txt_recv = QTextEdit()
        self.txt_recv.setReadOnly(True)
        terminal_layout.addWidget(self.txt_recv)
        
        term_ctrl_layout = QHBoxLayout()
        term_ctrl_layout.addWidget(QLabel("格式:"))
        self.cb_term_mode = QComboBox()
        self.cb_term_mode.addItems(["字符串", "HEX"])
        term_ctrl_layout.addWidget(self.cb_term_mode)
        
        term_ctrl_layout.addWidget(QLabel("编码:"))
        self.cb_term_encoding = QComboBox()
        self.cb_term_encoding.addItems(["UTF-8", "GBK"])
        term_ctrl_layout.addWidget(self.cb_term_encoding)
        
        self.chk_newline = QCheckBox("发送添加新行")
        self.chk_newline.setChecked(True) 
        term_ctrl_layout.addWidget(self.chk_newline)
        
        self.btn_clear_recv = QPushButton("清空数据")
        term_ctrl_layout.addWidget(self.btn_clear_recv)
        terminal_layout.addLayout(term_ctrl_layout)
        
        send_layout = QHBoxLayout()
        self.le_send = QLineEdit()
        self.btn_send_data = QPushButton("发送")
        send_layout.addWidget(self.le_send)
        send_layout.addWidget(self.btn_send_data)
        
        terminal_layout.addLayout(send_layout)
        terminal_group.setLayout(terminal_layout)
        left_panel.addWidget(terminal_group)
        
        left_panel.addStretch()
        main_layout.addLayout(left_panel, 1)
        
        # ================= 右侧显示面板 =================
        right_panel = QVBoxLayout()
        
        # 5. 实时状态区 
        status_group = QGroupBox("实时状态区")
        status_layout = QHBoxLayout()
        
        lcd_font = QFont("Consolas", 24, QFont.Bold)
        
        angle_layout = QVBoxLayout()
        angle_layout.addWidget(QLabel("当前天顶角 (°)"))
        self.lbl_angle = QLabel("00.00")
        self.lbl_angle.setFont(lcd_font)
        self.lbl_angle.setStyleSheet("color: blue;")
        angle_layout.addWidget(self.lbl_angle)
        status_layout.addLayout(angle_layout)
        
        target_layout_disp = QVBoxLayout()
        target_layout_disp.addWidget(QLabel("目标力 (kg / N)"))
        self.lbl_target = QLabel("0.000 / 0.000")
        self.lbl_target.setFont(lcd_font)
        self.lbl_target.setStyleSheet("color: darkgreen;")
        target_layout_disp.addWidget(self.lbl_target)
        status_layout.addLayout(target_layout_disp)
        
        actual_layout = QVBoxLayout()
        actual_layout.addWidget(QLabel("实际力 (kg / N)"))
        self.lbl_actual = QLabel("0.000 / 0.000")
        self.lbl_actual.setFont(lcd_font)
        self.lbl_actual.setStyleSheet("color: darkred;")
        actual_layout.addWidget(self.lbl_actual)
        status_layout.addLayout(actual_layout)
        
        error_layout = QVBoxLayout()
        error_layout.addWidget(QLabel("误差值 (kg / N)"))
        self.lbl_error = QLabel("+0.000 / +0.000") 
        self.lbl_error.setFont(lcd_font)
        self.lbl_error.setStyleSheet("color: darkmagenta;") 
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
        self.btn_record_data = QPushButton("开始录制数据")
        
        btn_layout.addWidget(self.btn_pause_plot)
        btn_layout.addWidget(self.btn_clear_plot)
        btn_layout.addWidget(self.btn_auto_range) 
        btn_layout.addWidget(self.btn_record_data)
        plot_layout.addLayout(btn_layout)
        
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.addLegend()
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', 'Force', units='N')
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        
        self.curve_target = self.plot_widget.plot(pen=pg.mkPen('g', width=2), name="Target Force (N)")
        self.curve_actual = self.plot_widget.plot(pen=pg.mkPen('r', width=2), name="Actual Force (N)")
        
        plot_layout.addWidget(self.plot_widget)
        plot_group.setLayout(plot_layout)
        right_panel.addWidget(plot_group, 5)
        
        main_layout.addLayout(right_panel, 4)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())