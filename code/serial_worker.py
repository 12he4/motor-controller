import serial
import struct
from PyQt5.QtCore import QThread, pyqtSignal


class SerialWorker(QThread):
    # 定义 PyQt 信号，用于跨线程将数据安全地抛给 UI 主线程
    # 参数：(当前天顶角, 目标力, 实际力)
    sig_status_data = pyqtSignal(float, float, float)
    
    # 用于向 UI 的收发窗口打印文本日志或异常信息
    sig_log_msg = pyqtSignal(str)
    
    # 用于向 UI 抛出原始字节流，在收发窗口显示 (原始字节, 是否为下位机发送来的数据)
    sig_raw_data = pyqtSignal(bytes, bool)
    # 【新增】：回中校准数据信号 (边界1, 边界2, 零位) 和 分辨率测试信号 (增益)
    sig_homing_data = pyqtSignal(float, float, float)
    sig_resolution_data = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.serial_port = serial.Serial()
        self.is_running = False

    def open_port(self, port, baudrate, data_bits, stop_bits, parity):
        try:
            self.serial_port.port = port
            self.serial_port.baudrate = int(baudrate)
            
            # 数据位设置
            if data_bits == "8": self.serial_port.bytesize = serial.EIGHTBITS
            elif data_bits == "7": self.serial_port.bytesize = serial.SEVENBITS
            elif data_bits == "6": self.serial_port.bytesize = serial.SIXBITS
            elif data_bits == "5": self.serial_port.bytesize = serial.FIVEBITS
            
            # 停止位设置
            if stop_bits == "1": self.serial_port.stopbits = serial.STOPBITS_ONE
            elif stop_bits == "1.5": self.serial_port.stopbits = serial.STOPBITS_ONE_POINT_FIVE
            elif stop_bits == "2": self.serial_port.stopbits = serial.STOPBITS_TWO
            
            # 校验位设置
            parity_dict = {"None": serial.PARITY_NONE, "Even": serial.PARITY_EVEN, 
                           "Odd": serial.PARITY_ODD, "Mark": serial.PARITY_MARK, 
                           "Space": serial.PARITY_SPACE}
            self.serial_port.parity = parity_dict.get(parity, serial.PARITY_NONE)
            
            self.serial_port.timeout = 0.05 # 50ms 非阻塞超时读取
            self.serial_port.open()
            return True
        except Exception as e:
            self.sig_log_msg.emit(f"[错误] 串口打开失败: {str(e)}")
            return False

    def close_port(self):
        self.is_running = False
        self.wait() # 等待后台线程安全退出
        if self.serial_port.is_open:
            self.serial_port.close()

    def run(self):
        self.is_running = True
        rx_buffer = bytearray()
        
        while self.is_running:
            if not self.serial_port.is_open:
                self.msleep(100)
                continue
                
            try:
                waiting = self.serial_port.in_waiting
                if waiting > 0:
                    raw_data = self.serial_port.read(waiting)
                    self.sig_raw_data.emit(raw_data, True) # 抛出原始数据供 UI 终端回显
                    rx_buffer.extend(raw_data)
                    self._parse_data(rx_buffer)
                else:
                    self.msleep(10) # 释放 CPU 时间片，防止单核 100% 占用
            except Exception as e:
                self.sig_log_msg.emit(f"[异常] 串口读取错误: {str(e)}")
                self.msleep(500)

    def _parse_data(self, buffer):
        """
        状态机滑动窗口解包逻辑：
        帧格式: 帧头(2) + 目标地址(1) + CMD(1) + 数据长度N(2) + 数据(N) + 和校验(1) + 附加校验(2)
        最短有效帧长度 = 2 + 1 + 1 + 2 + 0 + 1 + 2 = 9 字节
        """
        # 【修改点1】：最短帧长度判断从 8 改为 9
        while len(buffer) >= 9:
            if buffer[0] == 0xAA and buffer[1] == 0x55:
                
                # 【修改点2】：将 buffer[4] 和 buffer[5] 拼接为 2 字节长度 (小端模式)
                data_len = buffer[4] | (buffer[5] << 8)
                
                # 【修改点3】：基础长度由 8 变为 9
                frame_len = 9 + data_len 
                
                if len(buffer) < frame_len:
                    break
                    
                frame = buffer[:frame_len]
                cmd = frame[3]
                
                if cmd == 0x20 and data_len == 12:
                    # 【修改点4】：数据起始索引从 5 往后推 1 位，变成 6:18
                    data_payload = frame[6:18]
                    try:
                        angle, target_f, actual_f = struct.unpack('<fff', data_payload)
                        self.sig_status_data.emit(angle, target_f, actual_f)
                    except Exception as e:
                        self.sig_log_msg.emit(f"[解包错误] {str(e)}")
                
                elif cmd == 0x10:
                    # 检查是否有 12 字节的负载 (3个 float)
                    if data_len == 12:
                        try:
                            data_payload = frame[6:18]
                            b1, b2, zero = struct.unpack('<fff', data_payload)
                            self.sig_homing_data.emit(b1, b2, zero)
                            self.sig_log_msg.emit(f"[系统通知] 收到回中校准结果: 边界A={b1:.3f}, 边界B={b2:.3f}, 零位={zero:.3f}")
                        except Exception as e:
                            self.sig_log_msg.emit(f"[解包错误] 回中数据异常: {str(e)}")
                    else:
                        self.sig_log_msg.emit("[系统通知] 下位机已确认回中校准 (无附加数据)")
                        
                elif cmd == 0x11:
                    # 检查是否有 4 字节的负载 (1个 float)
                    if data_len == 4:
                        try:
                            data_payload = frame[6:10]
                            gain = struct.unpack('<f', data_payload)[0]
                            self.sig_resolution_data.emit(gain)
                            self.sig_log_msg.emit(f"[系统通知] 收到分辨率测试结果: 增益={gain:.0f}")
                        except Exception as e:
                            self.sig_log_msg.emit(f"[解包错误] 分辨率数据异常: {str(e)}")
                    else:
                        self.sig_log_msg.emit("[系统通知] 下位机已确认分辨率测试 (无附加数据)")
                
                del buffer[:frame_len]
            else:
                del buffer[0:1]

    def send_raw(self, data_bytes):
        """提供给数据收发区，直接发送未经封包的原始字节流"""
        if not self.serial_port.is_open:
            self.sig_log_msg.emit("[发送失败] 串口未打开")
            return
        try:
            self.serial_port.write(data_bytes)
            self.sig_raw_data.emit(data_bytes, False) # 将发出的数据回显给 UI
        except Exception as e:
            self.sig_log_msg.emit(f"[发送异常] {str(e)}")

    def send_cmd(self, cmd, payload_bytes=b''):
        """按照自定义通讯协议，封包发送控制指令"""
        if not self.serial_port.is_open:
            self.sig_log_msg.emit("[发送失败] 串口未打开")
            return
            
        data_len = len(payload_bytes)
        
        # 【修改点5】：将 data_len 拆解为 2 个字节 (小端模式：低字节在前，高字节在后)
        len_low = data_len & 0xFF
        len_high = (data_len >> 8) & 0xFF
        
        # 组装头部: 帧头(2) + 目标地址(1) + CMD(1) + 长度低字节(1) + 长度高字节(1)
        frame = bytearray([0xAA, 0x55, 0x01, cmd, len_low, len_high])
        frame.extend(payload_bytes)
        
        # 计算和校验 (从目标地址到数据内容，所有字节累加和的低 8 位)
        # 注意：此处切片 frame[2:] 依然正确，因为目标地址依然在索引 2 的位置
        check_sum = sum(frame[2:]) & 0xFF
        frame.append(check_sum)
        
        # 附加校验 (暂以 0x00 0x00 占位)
        frame.extend([0x00, 0x00])
        
        try:
            self.serial_port.write(frame)
            self.sig_raw_data.emit(bytes(frame), False) # 此处将 bytearray 强制转换为 bytes
        except Exception as e:
            self.sig_log_msg.emit(f"[封包发送异常] {str(e)}")
