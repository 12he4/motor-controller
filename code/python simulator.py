import serial
import struct
import time
import math

class STM32Simulator:
    def __init__(self, port='COM2', baudrate=115200):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=0.01)
            print(f"[下位机模拟器] 成功启动，正在监听 {port}...")
            print("请在上位机中打开相连的另一个虚拟串口（如 COM1）\n")
        except Exception as e:
            print(f"[错误] 无法打开串口 {port}: {e}")
            print("请确认是否已使用 VSPD 等软件创建了虚拟串口对，且端口号对应。")
            exit(1)
            
        self.rx_buffer = bytearray()
        self.time_counter = 0.0
        
        # 初始物理状态
        self.angle = 45.0
        self.target = 4.0

    def run(self):
        last_send_time = time.time()
        
        while True:
            try:
                # 1. 非阻塞接收上位机数据
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting)
                    self.rx_buffer.extend(data)
                    self._parse_rx()
                
                # 2. 定时发送 0x20 状态数据包 (模拟 25Hz 采样率 -> 40ms)
                current_time = time.time()
                if current_time - last_send_time >= 0.04:
                    self._send_status()
                    last_send_time = current_time
                    
                time.sleep(0.005) # 释放 CPU
            except KeyboardInterrupt:
                print("\n[退出] 模拟器已关闭")
                self.ser.close()
                break

    def _send_status(self):
        """构造并发送 0x20 实时状态帧"""
        self.time_counter += 0.04
        
        # 模拟真实的物理力学波动 (正弦波噪声 + 目标值)
        actual = self.target + 0.5 * math.sin(2 * math.pi * 0.5 * self.time_counter)
        
        # 封包数据 (小端 3 个 float)
        payload = struct.pack('<fff', self.angle, self.target, actual)
        frame = self._build_frame(0x20, payload)
        self.ser.write(frame)

    def _parse_rx(self):
        """解析上位机发来的指令 (含 2 字节数据长度支持)"""
        while len(self.rx_buffer) >= 9:
            if self.rx_buffer[0] == 0xAA and self.rx_buffer[1] == 0x55:
                # 解析 2 字节长度
                data_len = self.rx_buffer[4] | (self.rx_buffer[5] << 8)
                frame_len = 9 + data_len
                
                if len(self.rx_buffer) < frame_len:
                    break
                    
                frame = self.rx_buffer[:frame_len]
                cmd = frame[3]
                
                # 命令分发处理
                if cmd == 0x10:
                    print("[收到指令] 回中校准 (0x10) -> 回复确认")
                    self.ser.write(self._build_frame(0x10)) # 返回 ACK
                elif cmd == 0x11:
                    print("[收到指令] 分辨率测试 (0x11) -> 回复确认")
                    self.ser.write(self._build_frame(0x11)) # 返回 ACK
                elif cmd == 0x13 and data_len == 12:
                    kp, ki, kd = struct.unpack('<fff', frame[6:18])
                    print(f"[收到指令] PID 参数下发 (0x13): Kp={kp}, Ki={ki}, Kd={kd}")
                else:
                    # 对于非协议的原始数据（收发区敲击的测试数据）
                    raw_hex = ' '.join([f"{b:02X}" for b in frame])
                    print(f"[收到未知/原始帧] HEX: {raw_hex}")
                    
                del self.rx_buffer[:frame_len]
            else:
                # 兼容上位机发送的纯字符串：如果头部不是 0xAA 0x55，就当成文本打印丢弃
                print(f"[收到非协议字符串]: {bytes(self.rx_buffer).decode('gbk', 'ignore')}")
                self.rx_buffer.clear()

    def _build_frame(self, cmd, payload=b''):
        """按照通信协议组装给上位机的数据帧"""
        data_len = len(payload)
        len_low = data_len & 0xFF
        len_high = (data_len >> 8) & 0xFF
        
        frame = bytearray([0xAA, 0x55, 0x01, cmd, len_low, len_high])
        frame.extend(payload)
        
        check_sum = sum(frame[2:]) & 0xFF
        frame.append(check_sum)
        frame.extend([0x00, 0x00])
        return bytes(frame)

if __name__ == "__main__":
    # 请确保此处填写的端口是被虚拟出来的，且与上位机选择的端口互通
    sim = STM32Simulator(port='COM2', baudrate=115200)
    sim.run()