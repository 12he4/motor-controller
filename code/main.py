import sys
import time
import struct
from PyQt5.QtWidgets import (QApplication, QFileDialog, QMessageBox, QMenu, 
                             QWidgetAction, QWidget, QHBoxLayout, QLabel, 
                             QSpinBox, QActionGroup)
from PyQt5.QtCore import pyqtSlot, QObject, Qt
import pyqtgraph as pg

# 导入已构建完成的三个独立模块
from ui_window import MainWindow
from serial_worker import SerialWorker
from data_logger import CSVLogger

class MainApp(QObject): 
    def __init__(self):
        super().__init__()
        
        self.ui = MainWindow()
        self.worker = SerialWorker()
        self.logger = CSVLogger()
       
        # 波形数据缓存配置
        self.max_data_points = 5000 
        self.time_data = []
        self.target_data = []
        self.actual_data = []
        self.angle_data = [] # 新增存储 Angle 数据
        self.start_time = 0
        self.is_paused = False
        
        # ================= 坐标轴与曲线状态配置 =================
        self.x_axis_source = 'time' # 可选: 'time', 'target', 'actual', 'angle'
        self.y_axis_sources = {'target': True, 'actual': True, 'angle': False}
        self.x_decimals = 3
        self.y_decimals = 3
        
        self.annotations = [] 
        self.cursors = []     
        
        self.bind_signals()
        self.setup_axis_formatters()
        self.update_plot_display()
        
    def setup_axis_formatters(self):
        """利用 Python 动态特性拦截 PyQtGraph 的底层坐标轴渲染，强制修改小数位数"""
        def bottom_tickStrings(values, scale, spacing):
            return [f"{v:.{self.x_decimals}f}" for v in values]
            
        def left_tickStrings(values, scale, spacing):
            return [f"{v:.{self.y_decimals}f}" for v in values]
            
        self.ui.plot_widget.getAxis('bottom').tickStrings = bottom_tickStrings
        self.ui.plot_widget.getAxis('left').tickStrings = left_tickStrings

    def bind_signals(self):
        # 1. 后台通信线程 -> UI 界面更新
        self.worker.sig_status_data.connect(self.update_status_and_plot)
        self.worker.sig_log_msg.connect(self.append_log)
        self.worker.sig_raw_data.connect(self.append_raw_data)
        self.worker.sig_homing_data.connect(self.update_homing_data)
        self.worker.sig_resolution_data.connect(self.update_resolution_data)
        # 2. UI 按钮 -> 串口指令下发
        self.ui.btn_open_serial.clicked.connect(self.toggle_serial)
        self.ui.btn_homing.clicked.connect(lambda: self.worker.send_cmd(0x10))
        self.ui.btn_resolution.clicked.connect(lambda: self.worker.send_cmd(0x11))
        self.ui.btn_send_pid.clicked.connect(self.send_pid_params)
        
        # 3. 数据收发区独立逻辑
        self.ui.btn_send_data.clicked.connect(self.send_terminal_data)
        self.ui.btn_clear_recv.clicked.connect(self.ui.txt_recv.clear)
        
        # 4. 波形控制与数据持久化逻辑
        self.ui.btn_pause_plot.clicked.connect(self.toggle_pause_plot)
        self.ui.btn_clear_plot.clicked.connect(self.clear_plot)
        self.ui.btn_record_data.clicked.connect(self.toggle_recording)
        
        self.ui.sb_dt.valueChanged.connect(self.recalculate_time_axis)
        self.ui.btn_auto_range.clicked.connect(self.trigger_auto_range)
        
        # ================= 新增：坐标轴右键配置菜单 =================
        self.ui.btn_x_setting.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.btn_x_setting.customContextMenuRequested.connect(self.show_x_menu)
        self.ui.btn_y_setting.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.btn_y_setting.customContextMenuRequested.connect(self.show_y_menu)
        
        # 5. 绑定鼠标交互事件
        self.ui.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)    
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_clicked) 

    # ================= 右键菜单生成与事件流 =================
    def show_x_menu(self, pos):
        menu = QMenu(self.ui.plot_widget)
        
        # 1. 挂载 QSpinBox
        spin_action = QWidgetAction(menu)
        spin_widget = QWidget()
        spin_layout = QHBoxLayout(spin_widget)
        spin_layout.setContentsMargins(10, 2, 10, 2)
        spin_layout.addWidget(QLabel("波形X轴小数位数:"))
        spin_box = QSpinBox()
        spin_box.setRange(0, 6)
        spin_box.setValue(self.x_decimals)
        spin_box.valueChanged.connect(self.on_x_decimals_changed)
        spin_layout.addWidget(spin_box)
        spin_action.setDefaultWidget(spin_widget)
        menu.addAction(spin_action)
        menu.addSeparator()
        
        # 2. X 轴通道选择 (单选)
        menu.addAction("通道选择：").setEnabled(False)
        ag = QActionGroup(menu)
        ag.setExclusive(True)
        actions_data = [('time', '使用时间轴'), ('target', '指定通道: Target Force'), 
                        ('actual', '指定通道: Actual Force'), ('angle', '指定通道: Angle')]
        
        for val, text in actions_data:
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.x_axis_source == val)
            act.triggered.connect(lambda checked, v=val: self.on_x_source_changed(v))
            ag.addAction(act)
            
        menu.exec_(self.ui.btn_x_setting.mapToGlobal(pos))

    def show_y_menu(self, pos):
        menu = QMenu(self.ui.plot_widget)
        
        # 1. 挂载 QSpinBox
        spin_action = QWidgetAction(menu)
        spin_widget = QWidget()
        spin_layout = QHBoxLayout(spin_widget)
        spin_layout.setContentsMargins(10, 2, 10, 2)
        spin_layout.addWidget(QLabel("波形Y轴小数位数:"))
        spin_box = QSpinBox()
        spin_box.setRange(0, 6)
        spin_box.setValue(self.y_decimals)
        spin_box.valueChanged.connect(self.on_y_decimals_changed)
        spin_layout.addWidget(spin_box)
        spin_action.setDefaultWidget(spin_widget)
        menu.addAction(spin_action)
        menu.addSeparator()
        
        # 2. Y 轴通道选择 (多选复选框)
        menu.addAction("通道选择：").setEnabled(False)
        actions_data = [('target', '指定通道: Target Force (绿)'), 
                        ('actual', '指定通道: Actual Force (红)'), 
                        ('angle', '指定通道: Angle (蓝)')]
        
        for val, text in actions_data:
            act = menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.y_axis_sources[val])
            act.triggered.connect(lambda checked, v=val: self.on_y_source_changed(v, checked))
            
        menu.exec_(self.ui.btn_y_setting.mapToGlobal(pos))

    def on_x_decimals_changed(self, val):
        self.x_decimals = val
        self.ui.plot_widget.getAxis('bottom').picture = None
        self.ui.plot_widget.update()
        self.refresh_all_annotations()

    def on_y_decimals_changed(self, val):
        self.y_decimals = val
        self.ui.plot_widget.getAxis('left').picture = None
        self.ui.plot_widget.update()
        self.refresh_all_annotations()

    def on_x_source_changed(self, val):
        self.x_axis_source = val
        self.update_plot_display()
        self.refresh_all_annotations()

    def on_y_source_changed(self, val, checked):
        self.y_axis_sources[val] = checked
        self.update_plot_display()
        self.refresh_all_annotations()

    def get_current_x_array(self):
        """根据配置返回当前作为 X 轴的数据源"""
        if self.x_axis_source == 'time': return self.time_data
        if self.x_axis_source == 'target': return self.target_data
        if self.x_axis_source == 'actual': return self.actual_data
        if self.x_axis_source == 'angle': return self.angle_data
        return self.time_data

    def update_plot_display(self):
        """核心数据路由：重组并刷新所有显示的曲线"""
        x_array = self.get_current_x_array()
        
        # 【修复核心BUG】：当数组被清空时，必须显式清空界面的波形
        if not x_array: 
            self.ui.curve_target.setData([], [])
            self.ui.curve_actual.setData([], [])
            self.ui.curve_angle.setData([], [])
            return

        # Target Force 路由
        if self.y_axis_sources['target']: self.ui.curve_target.setData(x_array, self.target_data)
        else: self.ui.curve_target.setData([], [])
        
        # Actual Force 路由
        if self.y_axis_sources['actual']: self.ui.curve_actual.setData(x_array, self.actual_data)
        else: self.ui.curve_actual.setData([], [])
        
        # Angle 路由
        if self.y_axis_sources['angle']: self.ui.curve_angle.setData(x_array, self.angle_data)
        else: self.ui.curve_angle.setData([], [])

        # 动态更新坐标轴 Label
        x_label = "Time" if self.x_axis_source == 'time' else self.x_axis_source.capitalize()
        x_unit = "s" if self.x_axis_source == 'time' else ("°" if self.x_axis_source == 'angle' else "N")
        self.ui.plot_widget.setLabel('bottom', x_label, units=x_unit)

    # ================= 串口启停逻辑 =================
    def toggle_serial(self):
        if not self.worker.is_running:
            port = self.ui.cb_port.currentText()
            baud = self.ui.cb_baud.currentText()
            data_b = self.ui.cb_data_bits.currentText()
            stop_b = self.ui.cb_stop_bits.currentText()
            parity = self.ui.cb_parity.currentText()
            
            if self.worker.open_port(port, baud, data_b, stop_b, parity):
                self.ui.btn_open_serial.setText("关闭串口")
                self.ui.btn_open_serial.setStyleSheet("background-color: #ffcccc;")
                self.worker.start()
                self.start_time = time.time() 
        else:
            self.worker.close_port()
            self.ui.btn_open_serial.setText("打开串口")
            self.ui.btn_open_serial.setStyleSheet("")
            
    # ================= 状态解析与界面渲染 =================
    @pyqtSlot(float, float, float)
    def update_status_and_plot(self, angle, target, actual):
        if self.logger.is_recording:
            self.logger.log_data(target, actual)
            
        if not self.is_paused:
            self.ui.lbl_angle.setText(f"{angle:05.2f}")
            self.ui.lbl_target.setText(f"{target/9.8:.3f} / {target:.3f}")
            self.ui.lbl_actual.setText(f"{actual/9.8:.3f} / {actual:.3f}")
            
            error = actual - target
            error_kg = error / 9.8
            sign = "+" if error >= 0 else ""
            self.ui.lbl_error.setText(f"{sign}{error_kg:.3f} / {sign}{error:.3f}")
        
            dt_sec = self.ui.sb_dt.value() / 1000.0
            current_time = 0.0 if not self.time_data else self.time_data[-1] + dt_sec           
            
            self.time_data.append(current_time)
            self.target_data.append(target)
            self.actual_data.append(actual)
            self.angle_data.append(angle)
            
            if len(self.time_data) > self.max_data_points:
                self.time_data.pop(0)
                self.target_data.pop(0)
                self.actual_data.pop(0)
                self.angle_data.pop(0)
                
            self.update_plot_display()
            self.refresh_all_annotations() # 驱动游标随动
    # 删除这上方的 @pyqtSlot(float, float, float)
    def update_homing_data(self, b1, b2, zero):
        self.ui.le_bound1.setText(f"{b1:.3f}")
        self.ui.le_bound2.setText(f"{b2:.3f}")
        self.ui.le_zero.setText(f"{zero:.3f}")
        
        # 获取成功后，背景变浅绿，字体变深绿加粗，视觉提示非常清晰
        success_style = "background-color: #F0F9EB; color: #67C23A; font-weight: bold;"
        self.ui.le_bound1.setStyleSheet(success_style)
        self.ui.le_bound2.setStyleSheet(success_style)
        self.ui.le_zero.setStyleSheet(success_style)

    # 删除这上方的 @pyqtSlot(float)
    def update_resolution_data(self, gain):
        self.ui.le_gain.setText(f"{gain:.0f}") # 增益通常显示整数
        
        success_style = "background-color: #F0F9EB; color: #67C23A; font-weight: bold;"
        self.ui.le_gain.setStyleSheet(success_style) 
    # ================= 终端日志与自由收发逻辑 =================         
    @pyqtSlot(str)
    def append_log(self, msg):
        self.ui.txt_recv.append(msg)
        
    @pyqtSlot(bytes, bool)
    def append_raw_data(self, data, is_recv):
        direction = "RX" if is_recv else "TX"
        is_hex = self.ui.chk_hex_show.isChecked() if is_recv else self.ui.chk_hex_send.isChecked()
            
        if is_hex:
            text = ' '.join([f"{b:02X}" for b in data])
        else:
            encoding = self.ui.cb_term_encoding.currentText().lower()
            try:
                text = data.decode(encoding)
            except Exception:
                text = f"[解码异常: 原始HEX为 {data.hex()}]"
                
        self.ui.txt_recv.append(f"[{direction}] {text}")
        
    def send_terminal_data(self):
        text = self.ui.le_send.text()
        if not text: return
        
        if self.ui.chk_hex_send.isChecked():
            try:
                payload = bytes.fromhex(text.replace(' ', ''))
            except ValueError:
                self.append_log("[错误] 包含非法的十六进制字符")
                return
        else:
            if self.ui.chk_newline.isChecked(): text += '\r\n'
            payload = text.encode(self.ui.cb_term_encoding.currentText().lower())
            
        self.worker.send_raw(payload)  
        
    # ================= 调参配置指令封包下发 =================
    def send_pid_params(self):
        try:
            kp = float(self.ui.widget_kp.le.text())
            ki = float(self.ui.widget_ki.le.text())
            kd = float(self.ui.widget_kd.le.text())
            
            payload = struct.pack('<fff', kp, ki, kd)
            self.worker.send_cmd(0x13, payload)
            self.append_log(f"[系统指令] 下发 PID 成功 (Kp={kp}, Ki={ki}, Kd={kd})")
        except ValueError:
            self.append_log("[错误] PID 参数输入框内存在非法数值")
            
    # ================= 波形控制、交互与保存 =================
    # ================= 波形控制、交互与保存 =================
    def toggle_pause_plot(self):
        self.is_paused = not self.is_paused
        # 【修复与优化】：增加暂停按钮的颜色和文字状态反馈，避免因为不知道是否暂停而引发“盲操作冲突”
        if self.is_paused:
            self.ui.btn_pause_plot.setText("继续波形 ▶")
            self.ui.btn_pause_plot.setStyleSheet("background-color: #E6A23C; color: white;") # 橙色警示
        else:
            self.ui.btn_pause_plot.setText("暂停波形 ⏸")
            self.ui.btn_pause_plot.setStyleSheet("") # 恢复原本样式
        
    def clear_plot(self):
        # 清空内部数据缓存
        self.time_data.clear()
        self.target_data.clear()
        self.actual_data.clear()
        self.angle_data.clear()
        self.update_plot_display()
        
        # 移除所有用户标记
        for c in self.cursors:
            self.ui.plot_widget.removeItem(c['line'])
            self.ui.plot_widget.removeItem(c['text'])
        self.cursors.clear()
        
        for a in self.annotations:
            self.ui.plot_widget.removeItem(a['arrow'])
            self.ui.plot_widget.removeItem(a['text'])
        self.annotations.clear()
        
        # 【修复BUG】：强制隐藏悬浮十字光标，避免波形没了光标还飘在空中的“幽灵现象”
        self.ui.v_line.hide()
        self.ui.h_line.hide()
        self.ui.text_tooltip.hide()
        
    def trigger_auto_range(self):
        # 【修复BUG】：之前的针对单条曲线的 AutoRange 不够强力。
        # 现在的代码：针对整个图表控件底层的 ViewBox 强制重启 XY 双轴自动缩放。
        self.ui.plot_widget.plotItem.vb.enableAutoRange(axis=pg.ViewBox.XYAxes)  
    def recalculate_time_axis(self):
        """当修改 Δt 步长时，重新计算 X 轴的时间数据并刷新波形"""
        if not self.time_data: 
            return
            
        # 获取当前 UI 面板上的步长并转为秒
        dt_sec = self.ui.sb_dt.value() / 1000.0
        
        # 重新生成时间序列
        self.time_data = [i * dt_sec for i in range(len(self.target_data))]
        
        # 刷新波形和所有标记点
        self.update_plot_display()
        self.refresh_all_annotations()
    # ================= 动态鼠标坐标交互系 =================
    def on_mouse_moved(self, pos):
        """处理悬浮十字追踪光标与数据吸附"""
        view_box = self.ui.plot_widget.plotItem.vb
        scene_rect = view_box.sceneBoundingRect()
        x_array = self.get_current_x_array()
        
        if pos.x() < scene_rect.left() or pos.x() > scene_rect.right() or not x_array:
            self.ui.v_line.hide()
            self.ui.h_line.hide()
            self.ui.text_tooltip.hide()
            return
            
        mouse_point = view_box.mapSceneToView(pos)
        click_x, click_y = mouse_point.x(), mouse_point.y()
        
        # X 轴区间悬浮
        if pos.y() > scene_rect.bottom():
            self.ui.v_line.setPos(click_x)
            x_label = "Time" if self.x_axis_source == 'time' else self.x_axis_source.capitalize()
            x_unit = "s" if self.x_axis_source == 'time' else ("°" if self.x_axis_source == 'angle' else "N")
            self.ui.text_tooltip.setText(f"{x_label}: {click_x:.{self.x_decimals}f} {x_unit}")
            self.ui.text_tooltip.setPos(click_x, view_box.viewRange()[1][0])
            self.ui.v_line.show()
            self.ui.h_line.hide() 
            self.ui.text_tooltip.show()
            return

        # 视窗内部数据吸附
        if scene_rect.contains(pos):
            distances = [abs(t - click_x) for t in x_array]
            min_idx = distances.index(min(distances))
            
            dist_dict = {}
            if self.y_axis_sources['target']: dist_dict['target'] = abs(click_y - self.target_data[min_idx])
            if self.y_axis_sources['actual']: dist_dict['actual'] = abs(click_y - self.actual_data[min_idx])
            if self.y_axis_sources['angle']: dist_dict['angle'] = abs(click_y - self.angle_data[min_idx])
            
            if not dist_dict:
                self.ui.v_line.hide()
                self.ui.h_line.hide()
                self.ui.text_tooltip.hide()
                return
                
            closest_curve = min(dist_dict, key=dist_dict.get)
            min_dist = dist_dict[closest_curve]
            
            view_y_range = view_box.viewRange()[1]
            threshold = (view_y_range[1] - view_y_range[0]) * 0.15 
            
            if min_dist < threshold:
                val = getattr(self, f"{closest_curve}_data")[min_idx]
                real_x = x_array[min_idx]
                
                self.ui.v_line.setPos(real_x)
                self.ui.h_line.setPos(val)
                
                label = "Target" if closest_curve == 'target' else ("Actual" if closest_curve == 'actual' else "Angle")
                y_unit = "°" if closest_curve == 'angle' else "N"
                self.ui.text_tooltip.setText(f"{label}: {val:.{self.y_decimals}f} {y_unit}")
                self.ui.text_tooltip.setPos(real_x, val)
                
                self.ui.v_line.show()
                self.ui.h_line.show()
                self.ui.text_tooltip.show()
            else:
                self.ui.v_line.hide()
                self.ui.h_line.hide()
                self.ui.text_tooltip.hide()

    def on_mouse_clicked(self, event):
        pos = event.scenePos()
        view_box = self.ui.plot_widget.plotItem.vb
        scene_rect = view_box.sceneBoundingRect()
        
        # === 右键删除标记 ===
        if event.button() == Qt.RightButton and scene_rect.contains(pos):
            mouse_point = view_box.mapSceneToView(pos)
            mouse_x, mouse_y = mouse_point.x(), mouse_point.y()
            
            view_x_range = view_box.viewRange()[0]
            view_y_range = view_box.viewRange()[1]
            x_th = (view_x_range[1] - view_x_range[0]) * 0.02
            y_th = (view_y_range[1] - view_y_range[0]) * 0.1
            
            for cursor in self.cursors[:]:
                if abs(mouse_x - cursor['line'].value()) < x_th:
                    self.ui.plot_widget.removeItem(cursor['line'])
                    self.ui.plot_widget.removeItem(cursor['text'])
                    self.cursors.remove(cursor)
                    event.accept()
                    return
                    
            for a in self.annotations[:]:
                if abs(mouse_x - a['text'].pos().x()) < x_th and abs(mouse_y - a['text'].pos().y()) < y_th:
                    self.ui.plot_widget.removeItem(a['arrow'])
                    self.ui.plot_widget.removeItem(a['text'])
                    self.annotations.remove(a)
                    event.accept()
                    return

        # === 左键双击生成标记 ===
        if event.double() and event.button() == Qt.LeftButton:
            if pos.y() > scene_rect.bottom() and scene_rect.left() <= pos.x() <= scene_rect.right():
                mouse_point = view_box.mapSceneToView(pos)
                self.add_vertical_cursor(mouse_point.x())
                return
            if scene_rect.contains(pos):
                mouse_point = view_box.mapSceneToView(pos)
                self.add_curve_annotation(mouse_point.x(), mouse_point.y())

    # ================= 数据标记与刷新适配器 =================
    def refresh_all_annotations(self):
        """遍历所有标记物，根据当前的小数设置与坐标轴状态重新绘制"""
        for c in self.cursors: c['update_func']()
        for a in self.annotations: self.update_single_annotation(a)

    def get_index_by_timestamp(self, t):
        if not self.time_data: return -1
        distances = [abs(x - t) for x in self.time_data]
        return distances.index(min(distances))

    def add_vertical_cursor(self, x_val):
        v_line = pg.InfiniteLine(pos=x_val, angle=90, movable=True, pen=pg.mkPen('b', width=2))
        text_item = pg.TextItem(text="", color='b', fill=pg.mkBrush(255, 255, 255, 220))
        self.ui.plot_widget.addItem(v_line)
        self.ui.plot_widget.addItem(text_item)
        
        cursor_dict = {'line': v_line, 'text': text_item}
        
        def update_cursor_text():
            current_x = v_line.value()
            x_array = self.get_current_x_array()
            if not x_array: return
            
            distances = [abs(t - current_x) for t in x_array]
            min_idx = distances.index(min(distances))
            real_x = x_array[min_idx]
            
            lines, active_vals = [], []
            if self.y_axis_sources['target']:
                val = self.target_data[min_idx]
                lines.append(f"Target: {val:.{self.y_decimals}f} N")
                active_vals.append(val)
            if self.y_axis_sources['actual']:
                val = self.actual_data[min_idx]
                lines.append(f"Actual: {val:.{self.y_decimals}f} N")
                active_vals.append(val)
            if self.y_axis_sources['angle']:
                val = self.angle_data[min_idx]
                lines.append(f"Angle: {val:.{self.y_decimals}f} °")
                active_vals.append(val)
                
            if self.y_axis_sources['target'] and self.y_axis_sources['actual']:
                diff = self.actual_data[min_idx] - self.target_data[min_idx]
                lines.append(f"Diff: {diff:.{self.y_decimals}f} N")
                
            x_label = "Time" if self.x_axis_source == 'time' else self.x_axis_source.capitalize()
            x_unit = "s" if self.x_axis_source == 'time' else ("°" if self.x_axis_source == 'angle' else "N")
            lines.append(f"{x_label}: {real_x:.{self.x_decimals}f} {x_unit}")
            
            text_item.setText("\n".join(lines))
            if active_vals:
                view_y_range = self.ui.plot_widget.plotItem.vb.viewRange()[1]
                offset = (view_y_range[1] - view_y_range[0]) * 0.05
                text_item.setPos(current_x, max(active_vals) + offset) 
                
        v_line.sigPositionChanged.connect(update_cursor_text)
        cursor_dict['update_func'] = update_cursor_text
        self.cursors.append(cursor_dict)
        update_cursor_text()

    def add_curve_annotation(self, click_x, click_y):
        x_array = self.get_current_x_array()
        if not x_array: return
        
        distances = [abs(t - click_x) for t in x_array]
        min_idx = distances.index(min(distances))
        
        dist_dict = {}
        if self.y_axis_sources['target']: dist_dict['target'] = abs(click_y - self.target_data[min_idx])
        if self.y_axis_sources['actual']: dist_dict['actual'] = abs(click_y - self.actual_data[min_idx])
        if self.y_axis_sources['angle']: dist_dict['angle'] = abs(click_y - self.angle_data[min_idx])
        
        if not dist_dict: return
        closest_curve = min(dist_dict, key=dist_dict.get)
        min_dist = dist_dict[closest_curve]
        
        view_y_range = self.ui.plot_widget.plotItem.vb.viewRange()[1]
        if min_dist >= (view_y_range[1] - view_y_range[0]) * 0.15: return
        
        color = 'g' if closest_curve == 'target' else ('r' if closest_curve == 'actual' else 'b')
        arrow = pg.ArrowItem(pos=(0, 0), angle=-45, brush=color, pen=color)
        text = pg.TextItem("", color=color, fill=pg.mkBrush(255, 255, 255, 220))
        
        self.ui.plot_widget.addItem(arrow)
        self.ui.plot_widget.addItem(text)
        
        anno_dict = {'arrow': arrow, 'text': text, 'timestamp': self.time_data[min_idx], 'curve_type': closest_curve}
        self.annotations.append(anno_dict)
        self.update_single_annotation(anno_dict)

    def update_single_annotation(self, anno_dict):
        arrow, text = anno_dict['arrow'], anno_dict['text']
        t, curve_type = anno_dict['timestamp'], anno_dict['curve_type']
        
        idx = self.get_index_by_timestamp(t)
        if idx == -1 or not self.y_axis_sources.get(curve_type, False):
            arrow.hide(); text.hide()
            return
            
        arrow.show(); text.show()
        x_array = self.get_current_x_array()
        real_x = x_array[idx]
        val = getattr(self, f"{curve_type}_data")[idx]
        
        arrow.setPos(real_x, val)
        text.setPos(real_x, val)
        
        label = "Target" if curve_type == 'target' else ("Actual" if curve_type == 'actual' else "Angle")
        y_unit = "°" if curve_type == 'angle' else "N"
        x_label = "Time" if self.x_axis_source == 'time' else self.x_axis_source.capitalize()
        x_unit = "s" if self.x_axis_source == 'time' else ("°" if self.x_axis_source == 'angle' else "N")
        
        text.setText(f"{label}: {val:.{self.y_decimals}f} {y_unit}\n{x_label}: {real_x:.{self.x_decimals}f} {x_unit}")

    # ================= 录制保存逻辑 =================
    def toggle_recording(self):
        if not self.logger.is_recording:
            success, msg = self.logger.start_recording()
            self.append_log(f"[系统] {msg}")
            if success:
                self.ui.btn_record_data.setText("停止录制")
                self.ui.btn_record_data.setStyleSheet("background-color: #ffcccc;")
        else:
            success, msg = self.logger.stop_recording()
            self.append_log(f"[系统] {msg}")
            self.ui.btn_record_data.setText("开始录制数据")
            self.ui.btn_record_data.setStyleSheet("")
            
            if success and len(self.logger.buffer) > 0:
                reply = QMessageBox.question(self.ui, '保存确认', f"已录制 {len(self.logger.buffer)} 条数据，是否需要保存至本地？", QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.Yes:
                    filepath, _ = QFileDialog.getSaveFileName(self.ui, "保存录制数据", time.strftime("Log_%Y%m%d_%H%M%S.csv"), "CSV Files (*.csv)")
                    if filepath:
                        save_success, save_msg = self.logger.save_to_file(filepath)
                        self.append_log(f"[系统] {save_msg}")
                    else:
                        self.append_log("[系统] 用户取消保存")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_app = MainApp()
    main_app.ui.show()
    sys.exit(app.exec_())