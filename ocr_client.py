#!/usr/bin/env python3
"""
OCR远程服务 - 客户端脚本
在小伙伴的电脑上运行，连接你的电脑进行OCR处理
"""

import os
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urljoin

def get_server_url():
    """获取服务端地址"""
    print("\n" + "="*60)
    print("📡 DeepSeek OCR 客户端")
    print("="*60)
    print("\n请输入服务端地址（例如：http://192.168.1.100:5000）")
    print("注意：需要和服务端在同一WiFi网络下")
    print()

    server_url = input("服务端地址: ").strip()

    if not server_url:
        print("❌ 未输入服务端地址")
        return None

    if not server_url.startswith('http'):
        server_url = 'http://' + server_url

    return server_url.rstrip('/')

def test_connection(server_url):
    """测试连接"""
    try:
        response = requests.get(server_url, timeout=10)
        if response.status_code == 200:
            return True, "连接成功"
        else:
            return False, f"连接失败: HTTP {response.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "连接失败：无法连接到服务器，请检查地址是否正确"
    except requests.exceptions.Timeout:
        return False, "连接超时"
    except Exception as e:
        return False, f"连接失败: {str(e)}"

def select_pdf_file():
    """选择PDF文件"""
    print("\n" + "="*60)
    print("📂 选择要处理的PDF文件")
    print("="*60)

    pdf_path = input("请输入PDF文件路径（或拖拽文件到此处）: ").strip().strip('"')

    if not pdf_path:
        print("❌ 未选择文件")
        return None

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return None

    if not pdf_path.is_file():
        print(f"❌ 路径不是文件: {pdf_path}")
        return None

    if pdf_path.suffix.lower() != '.pdf':
        print(f"❌ 不是PDF文件: {pdf_path}")
        return None

    size_mb = pdf_path.stat().st_size / 1024 / 1024
    print(f"\n✅ 已选择文件: {pdf_path.name}")
    print(f"   文件大小: {size_mb:.2f} MB")

    return str(pdf_path)

def upload_and_process(server_url, pdf_path):
    """上传文件并处理"""
    pdf_path = Path(pdf_path)

    print("\n" + "="*60)
    print("📤 正在上传文件...")
    print("="*60)

    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdf_path.name, f, 'application/pdf')}
            response = requests.post(
                f"{server_url}/upload",
                files=files,
                timeout=300
            )

        if response.status_code != 200:
            print(f"❌ 上传失败: {response.text}")
            return None

        result = response.json()
        task_id = result.get('task_id')

        print(f"✅ 文件上传成功!")
        print(f"   任务ID: {task_id}")
        print(f"\n⏳ 正在处理OCR，请稍候...")
        print("   （处理时间取决于PDF页数和网络速度）")

        return task_id

    except requests.exceptions.Timeout:
        print("❌ 上传超时")
        return None
    except Exception as e:
        print(f"❌ 上传失败: {str(e)}")
        return None

def wait_for_completion(server_url, task_id, check_interval=5):
    """等待处理完成"""
    print("\n" + "="*60)
    print("🔄 等待OCR处理完成")
    print("="*60)
    print(f"   任务ID: {task_id}")
    print(f"   检查间隔: {check_interval}秒")
    print()

    start_time = time.time()
    last_status = None

    while True:
        try:
            response = requests.get(f"{server_url}/status/{task_id}", timeout=30)

            if response.status_code != 200:
                print(f"❌ 检查状态失败: {response.text}")
                return False

            result = response.json()
            status = result.get('status', 'unknown')

            if status != last_status:
                if status == 'processing':
                    elapsed = int(time.time() - start_time)
                    print(f"   ⏳ 处理中... (已等待 {elapsed} 秒)")
                elif status == 'completed':
                    elapsed = int(time.time() - start_time)
                    print(f"\n✅ 处理完成! (总耗时: {elapsed} 秒)")
                    return True
                last_status = status

            if status == 'completed':
                return True

            time.sleep(check_interval)

        except requests.exceptions.Timeout:
            print("⚠️  检查超时，继续等待...")
            time.sleep(check_interval)
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
            return False
        except Exception as e:
            print(f"⚠️  检查状态出错: {str(e)}")
            time.sleep(check_interval)

def download_results(server_url, task_id):
    """下载结果"""
    print("\n" + "="*60)
    print("📥 下载处理结果")
    print("="*60)

    output_dir = Path('ocr_results') / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        print("\n📥 下载文本结果...")
        response = requests.get(f"{server_url}/download/{task_id}", timeout=300)

        if response.status_code == 200:
            text_file = output_dir / 'result.md'
            with open(text_file, 'wb') as f:
                f.write(response.content)
            print(f"   ✅ 文本已保存: {text_file}")
        else:
            print(f"   ❌ 下载失败: {response.text}")

    except Exception as e:
        print(f"   ❌ 下载文本出错: {str(e)}")

    try:
        print("\n📥 下载图片（如有）...")
        response = requests.get(f"{server_url}/download_images/{task_id}", timeout=300)

        if response.status_code == 200:
            zip_file = output_dir / 'images.zip'
            with open(zip_file, 'wb') as f:
                f.write(response.content)

            import zipfile
            images_dir = output_dir / 'images'
            images_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(zip_file, 'r') as zf:
                zf.extractall(images_dir)

            zip_file.unlink()
            print(f"   ✅ 图片已保存: {images_dir}")
        else:
            if '没有图片' not in response.text:
                print(f"   ⚠️  下载图片失败: {response.text}")
            else:
                print(f"   ℹ️  没有提取到图片")

    except Exception as e:
        print(f"   ⚠️  下载图片出错: {str(e)}")

    print(f"\n📁 结果保存位置: {output_dir.absolute()}")
    return output_dir

def cleanup_server(server_url, task_id):
    """清理服务端临时文件"""
    try:
        requests.post(f"{server_url}/cleanup/{task_id}", timeout=30)
    except:
        pass

def main():
    print("\n" + "="*60)
    print("🔗 DeepSeek OCR 远程服务 - 客户端")
    print("="*60)
    print("\n此客户端用于连接运行在你朋友电脑上的OCR服务")
    print("你需要：")
    print("  1. 确保与服务端在同一WiFi网络下")
    print("  2. 让服务端先运行 ocr_server.py")
    print("  3. 获取服务端的局域网IP地址")
    print()

    server_url = get_server_url()
    if not server_url:
        return 1

    success, message = test_connection(server_url)
    if not success:
        print(f"\n❌ {message}")
        print("\n请检查：")
        print("  1. 服务端是否已启动")
        print("  2. IP地址是否正确")
        print("  3. 是否在同一WiFi网络下")
        print("  4. 防火墙是否阻止了5000端口")
        return 1

    print(f"\n✅ {message}")

    pdf_path = select_pdf_file()
    if not pdf_path:
        return 1

    task_id = upload_and_process(server_url, pdf_path)
    if not task_id:
        return 1

    if not wait_for_completion(server_url, task_id):
        print("\n⚠️  处理未完成")
        return 1

    output_dir = download_results(server_url, task_id)

    cleanup_server(server_url, task_id)

    print("\n" + "="*60)
    print("🎉 处理完成!")
    print("="*60)
    print(f"\n📁 结果保存在: {output_dir}")
    print("\n你可以打开 result.md 查看OCR提取的文字内容")

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
        sys.exit(0)