import sys
import time
import struct
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox
from PyQt5.QtCore import pyqtSlot, QObject, Qt  # 引入 Qt 用于按键和线型判断
import pyqtgraph as pg  # 引入 pyqtgraph 用于动态创建游标和图元

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
        self.max_data_points = 500 
        self.time_data = []
        self.target_data = []
        self.actual_data = []
        self.start_time = 0
        self.is_paused = False
        
        # ================= 新增：图元收集器，用于管理生成的标注和游标 =================
        self.annotations = [] 
        self.cursors = []     
        
        self.bind_signals()
        
    def bind_signals(self):
        # 1. 后台通信线程 -> UI 界面更新
        self.worker.sig_status_data.connect(self.update_status_and_plot)
        self.worker.sig_log_msg.connect(self.append_log)
        self.worker.sig_raw_data.connect(self.append_raw_data)
        
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
        
        # 5. 绑定鼠标交互事件
        self.ui.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)    # 悬浮十字光标
        self.ui.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_clicked) # 双击游标与标注

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
            if not self.time_data:
                current_time = 0.0
            else:
                current_time = self.time_data[-1] + dt_sec           
            self.time_data.append(current_time)
            self.target_data.append(target)
            self.actual_data.append(actual)
            
            if len(self.time_data) > self.max_data_points:
                self.time_data.pop(0)
                self.target_data.pop(0)
                self.actual_data.pop(0)
                
            self.ui.curve_target.setData(self.time_data, self.target_data)
            self.ui.curve_actual.setData(self.time_data, self.actual_data)
            
    # ================= 终端日志与自由收发逻辑 =================         
    @pyqtSlot(str)
    def append_log(self, msg):
        self.ui.txt_recv.append(msg)
        
    @pyqtSlot(bytes, bool)
    def append_raw_data(self, data, is_recv):
        direction = "RX" if is_recv else "TX"
        
        if is_recv:
            is_hex = self.ui.chk_hex_show.isChecked()
        else:
            is_hex = self.ui.chk_hex_send.isChecked()
            
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
        
        is_hex = self.ui.chk_hex_send.isChecked()
        encoding = self.ui.cb_term_encoding.currentText().lower()
        
        if is_hex:
            try:
                hex_str = text.replace(' ', '')
                payload = bytes.fromhex(hex_str)
            except ValueError:
                self.append_log("[错误] 包含非法的十六进制字符")
                return
        else:
            if self.ui.chk_newline.isChecked():
                text += '\r\n'
            payload = text.encode(encoding)
            
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
    def toggle_pause_plot(self):
        self.is_paused = not self.is_paused
        
    def clear_plot(self):
        self.time_data.clear()
        self.target_data.clear()
        self.actual_data.clear()
        self.ui.curve_target.setData([], [])
        self.ui.curve_actual.setData([], [])
        
        # 清空图表时，同时清理所有的游标和标注
        for arrow, text in self.annotations:
            self.ui.plot_widget.removeItem(arrow)
            self.ui.plot_widget.removeItem(text)
        self.annotations.clear()
        
        for cursor in self.cursors:
            self.ui.plot_widget.removeItem(cursor['line'])
            self.ui.plot_widget.removeItem(cursor['text'])
        self.cursors.clear()
        
    def recalculate_time_axis(self):
        if not self.time_data:
            return
            
        dt_sec = self.ui.sb_dt.value() / 1000.0
        new_time_data = []
        
        for i in range(len(self.target_data)):
            new_time_data.append(i * dt_sec)
            
        self.time_data = new_time_data
        
        self.ui.curve_target.setData(self.time_data, self.target_data)
        self.ui.curve_actual.setData(self.time_data, self.actual_data)   
        
    def trigger_auto_range(self):
        self.ui.curve_target.getViewBox().enableAutoRange()  
        
    def on_mouse_moved(self, pos):
        """处理悬浮十字追踪光标"""
        if self.ui.plot_widget.sceneBoundingRect().contains(pos):
            mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()
            
            self.ui.v_line.setPos(x_val)
            self.ui.h_line.setPos(y_val)
            
            self.ui.text_tooltip.setText(f"X (Time): {x_val:.3f} s\nY (Force): {y_val:.3f} N")
            self.ui.text_tooltip.setPos(x_val, y_val)
            
            self.ui.v_line.show()
            self.ui.h_line.show()
            self.ui.text_tooltip.show()
        else:
            self.ui.v_line.hide()
            self.ui.h_line.hide()
            self.ui.text_tooltip.hide()

    # ================= 新增：双击生成游标与标注的核心逻辑 =================
    def on_mouse_clicked(self, event):
        """处理鼠标双击事件的分发"""
        if event.double() and event.button() == Qt.LeftButton:
            pos = event.scenePos()
            
            # 1. 判断是否双击在底部的 X 轴刻度区域 -> 添加垂直动态游标
            bottom_axis = self.ui.plot_widget.getAxis('bottom')
            if bottom_axis.sceneBoundingRect().contains(pos):
                mouse_point = self.ui.plot_widget.plotItem.vb.mapSceneToView(pos)
                self.add_vertical_cursor(mouse_point.x())
                return
                
            # 2. 判断是否双击在绘图视图内 -> 添加静态曲线标注
            view_box = self.ui.plot_widget.plotItem.vb
            if view_box.sceneBoundingRect().contains(pos):
                mouse_point = view_box.mapSceneToView(pos)
                self.add_curve_annotation(mouse_point.x(), mouse_point.y())

    def add_vertical_cursor(self, x_val):
        """在指定 X 坐标生成可拖动的测量游标"""
        # 创建可拖动的垂线，颜色为醒目的蓝色
        v_line = pg.InfiniteLine(pos=x_val, angle=90, movable=True, pen=pg.mkPen('b', width=2))
        # 创建附带的数据标签，背景半透明
        text_item = pg.TextItem(text="", color='b', fill=pg.mkBrush(255, 255, 255, 220))
        
        self.ui.plot_widget.addItem(v_line)
        self.ui.plot_widget.addItem(text_item)
        self.cursors.append({'line': v_line, 'text': text_item})
        
        # 定义拖动时的动态更新回调函数
        def update_cursor_text():
            current_x = v_line.value()
            if not self.time_data: return
            
            # 查找缓冲池中距离游标 X 坐标最近的数据点
            distances = [abs(t - current_x) for t in self.time_data]
            if not distances: return
            min_idx = distances.index(min(distances))
            
            real_x = self.time_data[min_idx]
            t_y = self.target_data[min_idx]
            a_y = self.actual_data[min_idx]
            
            # 渲染游标的文字内容
            text_item.setText(f"X: {real_x:.3f} s\nTarget: {t_y:.3f} N\nActual: {a_y:.3f} N")
            # 标签悬浮在较高的那条曲线上方
            text_item.setPos(current_x, max(t_y, a_y) + 0.5) 
            
        v_line.sigPositionChanged.connect(update_cursor_text)
        update_cursor_text() # 立即执行一次初始化显示

    def add_curve_annotation(self, click_x, click_y):
        """双击曲线附近生成带颜色的永久标注"""
        if not self.time_data: return
        
        # 寻找 X 轴最近点
        distances = [abs(t - click_x) for t in self.time_data]
        min_idx = distances.index(min(distances))
        
        real_x = self.time_data[min_idx]
        t_y = self.target_data[min_idx]
        a_y = self.actual_data[min_idx]
        
        # 计算鼠标 Y 坐标距离 Target 和 Actual 的距离
        dist_to_target = abs(click_y - t_y)
        dist_to_actual = abs(click_y - a_y)
        
        # 设置容错阈值（防止乱点空白处也生成标注）
        view_y_range = self.ui.plot_widget.plotItem.vb.viewRange()[1]
        threshold = (view_y_range[1] - view_y_range[0]) * 0.1 # 10% 视窗高度作为吸附范围
        
        if dist_to_target < dist_to_actual and dist_to_target < threshold:
            color = 'g' # 绿色目标力
            val = t_y
        elif dist_to_actual <= dist_to_target and dist_to_actual < threshold:
            color = 'r' # 红色实际力
            val = a_y
        else:
            return # 距离两条曲线都太远，不触发
            
        # 生成箭头和文本框
        arrow = pg.ArrowItem(pos=(real_x, val), angle=-45, brush=color, pen=color)
        text = pg.TextItem(f"{val:.3f} N", color=color, fill=pg.mkBrush(255, 255, 255, 200))
        text.setPos(real_x, val)
        
        self.ui.plot_widget.addItem(arrow)
        self.ui.plot_widget.addItem(text)
        self.annotations.append((arrow, text))

    # =======================================================
               
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
                reply = QMessageBox.question(self.ui, '保存确认', 
                                             f"已录制 {len(self.logger.buffer)} 条数据，是否需要保存至本地？",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                
                if reply == QMessageBox.Yes:
                    default_name = time.strftime("Log_%Y%m%d_%H%M%S.csv")
                    filepath, _ = QFileDialog.getSaveFileName(self.ui, "保存录制数据", default_name, "CSV Files (*.csv)")
                    
                    if filepath:
                        save_success, save_msg = self.logger.save_to_file(filepath)
                        self.append_log(f"[系统] {save_msg}")
                    else:
                        self.append_log("[系统] 用户取消保存，数据已释放")
                else:
                    self.append_log("[系统] 用户选择不保存，数据已释放")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_app = MainApp()
    main_app.ui.show()
    sys.exit(app.exec_())