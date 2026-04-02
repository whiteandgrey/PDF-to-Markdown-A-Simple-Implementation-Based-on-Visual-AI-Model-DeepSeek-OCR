#!/usr/bin/env python3
"""
OCR远程服务 - 客户端GUI版本 (tkinter)
在小伙伴的电脑上运行，连接服务端的电脑进行OCR处理
"""

import os
import sys
import re
import time
import json
import threading
import requests
import zipfile
import shutil
from pathlib import Path


def normalize_filename(filename, max_length=100):
    """
    规范化文件名
    
    Args:
        filename: 原始文件名（不带扩展名）
        max_length: 最大长度限制
    
    Returns:
        str: 规范化后的文件名
    """
    illegal_chars = r'[,#^\[\]|\\/:*?"<>]'
    normalized = re.sub(illegal_chars, '_', filename)
    normalized = normalized.strip(' _')
    
    if len(normalized) > max_length:
        normalized = normalized[:50].strip(' _')
    
    if not normalized:
        normalized = "document"
    
    return normalized
try:
    import ctypes
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass
except ImportError:
    print("错误: 需要安装 tkinter")
    sys.exit(1)


class ConfigManager:
    """配置管理器 - 保存和加载用户配置"""
    
    def __init__(self):
        self.config_dir = Path.home() / '.deepseek_ocr_client'
        self.config_file = self.config_dir / 'config.json'
        self.default_config = {
            'server_url': 'http://192.168.1.100:5000',
            'save_dir': os.path.expanduser("~/Documents/OCR_Results"),
            'pdf_dir': os.path.expanduser("~/Documents"),
            'timeout': 300
        }
    
    def load_config(self):
        """加载配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return {**self.default_config, **json.load(f)}
        except Exception:
            pass
        return self.default_config.copy()
    
    def save_config(self, config):
        """保存配置"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class OCRClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek OCR 客户端")
        self.root.geometry("600x600")
        self.root.resizable(False, False)

        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        self.server_url = None
        self.pdf_path = None
        self.task_id = None
        self.save_dir = self.config.get('save_dir', os.path.expanduser("~/Documents/OCR_Results"))
        self.timeout = self.config.get('timeout', 300)

        self.setup_ui()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="📡 DeepSeek OCR 远程服务", font=("微软雅黑", 18, "bold"))
        title_label.pack(pady=(0, 20))

        server_frame = ttk.LabelFrame(main_frame, text="服务端配置", padding="10")
        server_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(server_frame, text="服务端地址:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.server_entry = ttk.Entry(server_frame, width=35)
        self.server_entry.grid(row=0, column=1, padx=5, pady=5)
        self.server_entry.insert(0, self.config.get('server_url', "http://192.168.1.100:5000"))

        self.test_btn = ttk.Button(server_frame, text="测试连接", command=self.test_connection)
        self.test_btn.grid(row=0, column=2, pady=5)

        ttk.Label(server_frame, text="超时时间(秒):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.timeout_entry = ttk.Entry(server_frame, width=10)
        self.timeout_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.timeout_entry.insert(0, str(self.config.get('timeout', 300)))

        file_frame = ttk.LabelFrame(main_frame, text="选择PDF文件", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))

        self.file_entry = ttk.Entry(file_frame, width=45)
        self.file_entry.grid(row=0, column=0, padx=5, pady=5)

        self.browse_btn = ttk.Button(file_frame, text="浏览...", command=self.browse_file)
        self.browse_btn.grid(row=0, column=1, pady=5)

        save_frame = ttk.LabelFrame(main_frame, text="保存位置", padding="10")
        save_frame.pack(fill=tk.X, pady=(0, 15))

        self.save_entry = ttk.Entry(save_frame, width=45)
        self.save_entry.grid(row=0, column=0, padx=5, pady=5)
        self.save_entry.insert(0, self.save_dir)

        self.save_btn = ttk.Button(save_frame, text="选择...", command=self.browse_save_dir)
        self.save_btn.grid(row=0, column=1, pady=5)

        action_frame = ttk.Frame(main_frame)
        action_frame.pack(pady=(0, 15))

        self.start_btn = ttk.Button(action_frame, text="开始处理", command=self.start_processing, state=tk.DISABLED)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = ttk.Button(action_frame, text="重置", command=self.reset)
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(main_frame, text="处理日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, width=60, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(10, 0))

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def test_connection(self):
        server_url = self.server_entry.get().strip()
        if not server_url:
            messagebox.showwarning("警告", "请输入服务端地址")
            return

        if not server_url.startswith('http'):
            server_url = 'http://' + server_url
            self.server_entry.delete(0, tk.END)
            self.server_entry.insert(0, server_url)

        self.log(f"🔗 正在连接 {server_url}...")
        self.test_btn.config(state=tk.DISABLED)

        def test():
            try:
                response = requests.get(server_url, timeout=10)
                if response.status_code == 200:
                    self.root.after(0, lambda: messagebox.showinfo("成功", "连接成功!"))
                    self.root.after(0, lambda: self.log("✅ 连接成功"))
                    self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                    self.server_url = server_url
                    self.config['server_url'] = server_url
                    self._save_config()
                else:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"连接失败: HTTP {response.status_code}"))
            except requests.exceptions.ConnectionError:
                self.root.after(0, lambda: messagebox.showerror("错误", "连接失败：无法连接到服务器\n请检查：\n1. 服务端是否已启动\n2. IP地址是否正确\n3. 是否在同一WiFi网络下"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"连接失败: {str(e)}"))
            finally:
                self.root.after(0, lambda: self.test_btn.config(state=tk.NORMAL))

        threading.Thread(target=test, daemon=True).start()

    def browse_file(self):
        initial_dir = self.config.get('pdf_dir', os.path.expanduser("~/Documents"))
        file_path = filedialog.askopenfilename(
            title="选择PDF文件",
            filetypes=[("PDF文件", "*.pdf")],
            initialdir=initial_dir
        )
        if file_path:
            self.pdf_path = file_path
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)
            
            self.config['pdf_dir'] = str(Path(file_path).parent)
            self._save_config()

            size_mb = Path(file_path).stat().st_size / 1024 / 1024
            self.log(f"📄 已选择: {Path(file_path).name} ({size_mb:.2f} MB)")

    def browse_save_dir(self):
        initial_dir = self.config.get('save_dir', os.path.expanduser("~/Documents/OCR_Results"))
        save_path = filedialog.askdirectory(
            title="选择保存位置",
            initialdir=initial_dir
        )
        if save_path:
            self.save_dir = save_path
            self.save_entry.delete(0, tk.END)
            self.save_entry.insert(0, save_path)
            self.config['save_dir'] = save_path
            self._save_config()
            self.log(f"📁 保存位置: {save_path}")

    def _save_config(self):
        """保存当前配置"""
        try:
            self.config['timeout'] = int(self.timeout_entry.get())
        except ValueError:
            pass
        self.config_manager.save_config(self.config)
    
    def start_processing(self):
        if not self.server_url:
            messagebox.showwarning("警告", "请先测试连接")
            return

        if not self.pdf_path:
            messagebox.showwarning("警告", "请选择PDF文件")
            return

        try:
            self.timeout = int(self.timeout_entry.get())
            if self.timeout < 60:
                messagebox.showwarning("警告", "超时时间至少60秒")
                return
            self.config['timeout'] = self.timeout
            self._save_config()
        except ValueError:
            messagebox.showwarning("警告", "超时时间必须是数字")
            return

        self.start_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.save_btn.config(state=tk.DISABLED)
        self.server_entry.config(state=tk.DISABLED)
        self.timeout_entry.config(state=tk.DISABLED)
        self.progress.start(10)

        def process():
            try:
                self.log("\n" + "="*50)
                self.log("📤 正在上传文件...")

                with open(self.pdf_path, 'rb') as f:
                    files = {'file': (Path(self.pdf_path).name, f, 'application/pdf')}
                    response = requests.post(f"{self.server_url}/upload", files=files, timeout=300)

                if response.status_code != 200:
                    self.root.after(0, lambda: messagebox.showerror("错误", f"上传失败: {response.text}"))
                    return

                result = response.json()
                self.task_id = result.get('task_id')
                self.log(f"✅ 文件上传成功! 任务ID: {self.task_id}")
                self.log("⏳ 等待处理完成...")

                self.wait_for_completion()

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"处理失败: {str(e)}"))
                self.log(f"❌ 错误: {str(e)}")
            finally:
                self.root.after(0, lambda: self.progress.stop())
                self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.browse_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.save_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.server_entry.config(state=tk.NORMAL))
                self.root.after(0, lambda: self.timeout_entry.config(state=tk.NORMAL))

        threading.Thread(target=process, daemon=True).start()

    def wait_for_completion(self):
        check_count = 0
        status_timeout = 60
        while True:
            try:
                response = requests.get(f"{self.server_url}/status/{self.task_id}", timeout=status_timeout)
                if response.status_code != 200:
                    self.log(f"⚠️ 服务端返回错误: HTTP {response.status_code}")
                    break

                result = response.json()
                status = result.get('status', 'unknown')
                filename = result.get('filename', 'result.md')
                current = result.get('current', 0)
                total = result.get('total', 0)

                if status == 'completed':
                    self.log("✅ 处理完成!")
                    self.download_results(filename)
                    self.task_id = None
                    self.root.after(0, lambda: messagebox.showinfo("成功", "处理完成!\n结果已保存到指定文件夹"))
                    return
                elif status == 'error':
                    self.log("❌ 服务端处理出错")
                    self.task_id = None
                    self.root.after(0, lambda: messagebox.showerror("错误", "服务端处理出错"))
                    return
                elif status == 'not_found':
                    self.log("❌ 任务不存在")
                    self.task_id = None
                    self.root.after(0, lambda: messagebox.showerror("错误", "任务不存在"))
                    return

                if total > 0 and current > 0:
                    self.root.after(0, lambda: self.log(f"⏳ 处理中: 第 {current}/{total} 页"))
                elif check_count % 6 == 0:
                    self.root.after(0, lambda: self.log("⏳ 处理中..."))

                check_count += 1
                time.sleep(3)

            except requests.exceptions.Timeout:
                self.log(f"⚠️ 请求超时，继续等待...")
                time.sleep(5)
            except requests.exceptions.ConnectionError as e:
                self.log(f"⚠️ 连接错误: {str(e)[:50]}...")
                time.sleep(5)
            except Exception as e:
                self.log(f"⚠️ 检查状态出错: {str(e)[:50]}...")
                time.sleep(5)

    def download_results(self, filename='result.md'):
        self.log("\n📥 下载结果...")

        save_dir = Path(self.save_entry.get()) if self.save_entry.get() else Path(self.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        self.log(f"🔍 PDF路径: {self.pdf_path}")
        pdf_name = Path(self.pdf_path).stem if self.pdf_path else 'unknown'
        self.log(f"🔍 PDF stem: {pdf_name}")
        pdf_name = normalize_filename(pdf_name)
        self.log(f"🔍 规范化后: {pdf_name}")
        output_dir = save_dir / pdf_name
        self.log(f"🔍 输出目录: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            response = requests.get(f"{self.server_url}/download/{self.task_id}?version=marked", timeout=300)
            self.log(f"📥 marked版本下载: HTTP {response.status_code}")
            if response.status_code == 200:
                marked_file = output_dir / f'{pdf_name}_ocr_result.md'
                with open(marked_file, 'wb') as f:
                    f.write(response.content)
                self.log(f"✅ 带分页标记版已保存: {marked_file}")
            else:
                self.log(f"❌ 下载失败: {response.text[:100]}")
        except Exception as e:
            self.log(f"❌ 下载带分页版失败: {str(e)}")

        try:
            response = requests.get(f"{self.server_url}/download/{self.task_id}?version=clean", timeout=300)
            self.log(f"📥 clean版本下载: HTTP {response.status_code}")
            if response.status_code == 200:
                clean_file = output_dir / f'{pdf_name}_ocr_result_clean.md'
                with open(clean_file, 'wb') as f:
                    f.write(response.content)
                self.log(f"✅ 纯净版已保存: {clean_file}")
            else:
                self.log(f"❌ 下载失败: {response.text[:100]}")
        except Exception as e:
            self.log(f"❌ 下载纯净版失败: {str(e)}")

        try:
            response = requests.get(f"{self.server_url}/download_images/{self.task_id}", timeout=300)
            if response.status_code == 200:
                zip_temp = output_dir / 'images.zip.tmp'
                with open(zip_temp, 'wb') as f:
                    f.write(response.content)

                images_dir = output_dir / 'images'
                images_dir.mkdir(exist_ok=True)
                with zipfile.ZipFile(zip_temp, 'r') as zf:
                    zf.extractall(images_dir)
                zip_temp.unlink()
                self.log(f"✅ 图片已保存: {images_dir}")
        except Exception as e:
            self.log(f"⚠️ 下载图片失败: {str(e)}")

        try:
            requests.post(f"{self.server_url}/cleanup/{self.task_id}", timeout=30)
        except:
            pass

        self.log(f"\n📁 结果保存位置: {output_dir}")

    def reset(self):
        self.server_url = None
        self.pdf_path = None
        self.task_id = None
        self.server_entry.delete(0, tk.END)
        self.server_entry.insert(0, self.config.get('server_url', "http://192.168.1.100:5000"))
        self.file_entry.delete(0, tk.END)
        self.save_entry.delete(0, tk.END)
        self.save_entry.insert(0, self.save_dir)
        self.timeout_entry.delete(0, tk.END)
        self.timeout_entry.insert(0, str(self.config.get('timeout', 300)))
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.start_btn.config(state=tk.DISABLED)
    
    def on_closing(self):
        """处理窗口关闭事件"""
        if self.task_id is not None:
            result = messagebox.askyesnocancel(
                "确认退出",
                "任务正在进行中！\n\n确定要退出吗？\n\n选择'是'将放弃当前任务并退出。",
                icon='warning'
            )
            if result:
                self.root.destroy()
            elif result is None:
                return
        else:
            self.root.destroy()


def main():
    root = tk.Tk()
    app = OCRClientGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
