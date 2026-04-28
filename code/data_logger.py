# -*- coding: utf-8 -*-
import csv
import time

class CSVLogger:
    def __init__(self):
        """
        初始化数据记录器（改为内存缓存模式）
        """
        self.is_recording = False
        self.start_time = 0
        self.buffer = [] # 内存缓存列表

    def start_recording(self):
        """
        开始录制，清空之前的缓存并记录起始时间
        """
        if self.is_recording:
            return False, "已经在录制中"
         
        self.buffer.clear()
        self.start_time = time.time()
        self.is_recording = True
        return True, "开始在内存中缓存录制数据"

    def log_data(self, target, actual):
        """
        向内存中追加一行实时数据
        """
        if self.is_recording:
            current_time = time.time() - self.start_time
            self.buffer.append((current_time, target, actual))

    def stop_recording(self):
        """
        停止录制，保留内存数据等待保存
        """
        if not self.is_recording:
            return False, "未处于录制状态"
            
        self.is_recording = False
        data_count = len(self.buffer)
        return True, f"录制已停止，共获取 {data_count} 条数据"

    def save_to_file(self, filepath):
        """
        将内存中的缓存数据一次性写入指定的 CSV 文件
        """
        if not self.buffer:
            return False, "没有可保存的数据"
            
        try:
            with open(filepath, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Time(s)", "Target_Force(N)", "Actual_Force(N)"])
                
                for row in self.buffer:
                    writer.writerow([f"{row[0]:.3f}", f"{row[1]:.3f}", f"{row[2]:.3f}"])
            return True, "数据保存成功"
        except Exception as e:
            return False, f"文件保存失败: {str(e)}"
