#!/usr/bin/env python3
"""
OCR远程服务 - 服务端脚本
让同一WiFi下的其他电脑可以使用你电脑上的OCR功能
"""

import os
import sys
import shutil
import time
import socket
from pathlib import Path
from flask import Flask, request, send_file, jsonify, after_this_request
from werkzeug.utils import secure_filename
import threading
import uuid

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

TEMP_UPLOAD_DIR = PROJECT_ROOT / 'temp_remote_uploads'
TEMP_OUTPUT_DIR = PROJECT_ROOT / 'temp_remote_outputs'
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_local_ip():
    """获取本机局域网IP地址"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

def process_pdf_ocr(pdf_path, output_dir, task_id):
    """在后台线程中处理PDF OCR"""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        output_dir = Path(output_dir)

        import fitz
        from transformers import AutoModel, AutoTokenizer
        import torch
        import re

        model_path = 'C:/Users/WWWWG/Desktop/DeepSeek-OCR-main/huggingface/hub/models--deepseek-ai--DeepSeek-OCR/snapshots/9f30c71f441d010e5429c532364a86705536c53a'

        print(f"[{task_id}] 开始处理PDF...")

        pdf_path = Path(pdf_path)
        output_base = Path(output_dir)
        text_dir = output_base / 'text'
        images_dir = output_base / 'images'
        temp_dir = PROJECT_ROOT / f'temp_{task_id}'

        text_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        output_file = text_dir / 'ocr_result.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 文档OCR提取结果\n\n")
            f.write(f"**源文件:** {pdf_path.absolute()}\n")
            f.write(f"**处理开始时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**状态:** 处理中...\n\n")
            f.write("---\n")
            f.write("\n## 📝 OCR提取内容\n\n")
            f.write("> 开始提取文字内容...\n\n")

        print(f"[{task_id}] 原子式输出文件已创建: {output_file}")

        status_file = output_dir / 'status.txt'
        with open(status_file, 'w', encoding='utf-8') as f:
            f.write('processing|0|0')

        print(f"[{task_id}] PDF转图片...")
        pdf = fitz.open(str(pdf_path))
        total_pages = len(pdf)

        image_files = []
        for i in range(total_pages):
            page = pdf[i]
            zoom = 300 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_name = f'page_{i+1:04d}.png'
            img_path = temp_dir / img_name
            pix.save(str(img_path))
            image_files.append(img_path)
        pdf.close()
        print(f"[{task_id}] 转换完成: {total_pages} 张图片")

        print(f"[{task_id}] 加载OCR模型...")
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModel.from_pretrained(model_path, _attn_implementation='eager', trust_remote_code=True, use_safetensors=True)
        model = model.eval().cuda().to(torch.bfloat16)

        prompt = "<image>\n<|grounding|>Convert the document to markdown. "

        print(f"[{task_id}] 开始OCR处理...")
        for i, img_path in enumerate(image_files, 1):
            page_temp = temp_dir / f'page_{i:04d}'
            page_temp.mkdir(exist_ok=True)

            model.infer(
                tokenizer,
                prompt=prompt,
                image_file=str(img_path),
                output_path=str(page_temp),
                base_size=1024,
                image_size=640,
                crop_mode=True,
                save_results=True,
                test_compress=True
            )

            result_file = page_temp / 'result.mmd'
            if result_file.exists():
                with open(result_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                image_mapping = {}
                page_images = page_temp / 'images'
                if page_images.exists():
                    for img_idx, img in enumerate(page_images.iterdir(), 1):
                        if img.is_file():
                            ext = img.suffix.lower() if img.suffix else '.png'
                            new_name = f"page_{i:04d}_img_{img_idx:03d}{ext}"
                            shutil.copy2(img, images_dir / new_name)
                            image_mapping[img_idx] = new_name

                for img_idx, new_name in image_mapping.items():
                    content = content.replace(f'](images/{img_idx - 1}.jpg)', f'](images/{new_name})')
                    content = content.replace(f'](images/{img_idx - 1}.png)', f'](images/{new_name})')
                    content = content.replace(f'](images/{img_idx - 1})', f'](images/{new_name})')

                import re
                content = re.sub(r'<center>\s*(.*?)\s*</center>', r'>\1', content, flags=re.DOTALL)

                marked_content = f"\n\n{'='*60}\n## 📄 第 {i}/{total_pages} 页\n{'='*60}\n\n{content}"

                with open(output_file, 'r', encoding='utf-8') as f:
                    existing = f.read()
                marker = "> 开始提取文字内容...\n\n"
                if marker in existing:
                    progress_info = f"> 正在处理第 {i}/{total_pages} 页...\n\n"
                    new_content = existing.replace(marker, progress_info + marked_content + "\n\n" + marker)
                else:
                    new_content = existing + "\n\n" + marked_content
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)

            if i < total_pages:
                time.sleep(0.3)

            with open(status_file, 'w', encoding='utf-8') as f:
                f.write(f'processing|{i}|{total_pages}')

        with open(status_file, 'w', encoding='utf-8') as f:
            f.write(f'completed|{total_pages}|{total_pages}')

        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.split('\n')
        updated_lines = []
        for line in lines:
            if line.startswith("**状态:**"):
                updated_lines.append("**状态:** 完成")
            elif "> 开始提取文字内容..." in line or "> 正在处理第" in line:
                continue
            else:
                updated_lines.append(line)
        updated_lines.append(f"\n**处理完成时间:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
        updated_lines.append(f"\n**总页数:** {total_pages}")
        updated_lines.append("> OCR处理完成")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(updated_lines))

        clean_file = text_dir / 'ocr_result_clean.md'
        with open(output_file, 'r', encoding='utf-8') as f:
            clean_content = f.read()
        clean_content = re.sub(r'\n{3,}' + r'={60}' + r'\n## 📄 第 \d+/\d+ 页\n' + r'={60}' + r'\n{2,}', '\n\n', clean_content)
        with open(clean_file, 'w', encoding='utf-8') as f:
            f.write(clean_content)

        with open(status_file, 'w', encoding='utf-8') as f:
            f.write('completed')

        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print(f"[{task_id}] 处理完成!")
        if task_id in ACTIVE_TASKS:
            ACTIVE_TASKS.remove(task_id)

    except Exception as e:
        print(f"[{task_id}] 处理出错: {e}")
        import traceback
        traceback.print_exc()
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f"\n\n**错误:** {str(e)}\n")
            with open(status_file, 'w', encoding='utf-8') as f:
                f.write('error|-1|-1')
            if task_id in ACTIVE_TASKS:
                ACTIVE_TASKS.remove(task_id)
        except:
            pass

@app.route('/')
def index():
    local_ip = get_local_ip()
    port = 5000
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>DeepSeek OCR 远程服务</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
            .info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            .info h2 {{ margin-top: 0; color: #1976d2; }}
            .ip {{ font-size: 24px; font-weight: bold; color: #d32f2f; }}
            .instructions {{ background: #fff3e0; padding: 15px; border-radius: 8px; }}
            .instructions ol {{ line-height: 1.8; }}
        </style>
    </head>
    <body>
        <h1>📄 DeepSeek OCR 远程服务</h1>
        <div class="info">
            <h2>服务端信息</h2>
            <p>服务地址: <span class="ip">http://{local_ip}:{port}</span></p>
            <p>局域网IP: <span class="ip">{local_ip}</span></p>
        </div>
        <div class="instructions">
            <h2>使用方法</h2>
            <ol>
                <li>在你的电脑上运行此服务端脚本（已运行）</li>
                <li>让小伙伴在他的电脑上运行 <code>ocr_client.py</code></li>
                <li>输入服务地址: <code>http://{local_ip}:{port}</code></li>
                <li>选择PDF文件并提交处理</li>
                <li>处理完成后，结果会自动下载到他的电脑</li>
            </ol>
        </div>
    </body>
    </html>
    """

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': '只支持PDF文件'}), 400

    task_id = str(uuid.uuid4())[:8]
    filename = secure_filename(file.filename)
    upload_dir = TEMP_UPLOAD_DIR / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = upload_dir / filename
    file.save(str(pdf_path))

    output_dir = TEMP_OUTPUT_DIR / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    ACTIVE_TASKS.add(task_id)

    thread = threading.Thread(target=process_pdf_ocr, args=(str(pdf_path), str(output_dir), task_id))
    thread.start()

    return jsonify({
        'task_id': task_id,
        'message': '文件已接收，开始处理',
        'status': 'processing'
    })

@app.route('/status/<task_id>', methods=['GET'])
def check_status(task_id):
    output_dir = TEMP_OUTPUT_DIR / task_id
    if not output_dir.exists():
        return jsonify({'status': 'not_found'}), 404

    status_file = output_dir / 'status.txt'
    if status_file.exists():
        with open(status_file, 'r', encoding='utf-8') as f:
            status_line = f.read().strip()

        parts = status_line.split('|')
        status = parts[0]
        current = int(parts[1]) if len(parts) > 1 else 0
        total = int(parts[2]) if len(parts) > 2 else 0

        if status == 'completed':
            text_dir = output_dir / 'text'
            if text_dir.exists():
                md_file = text_dir / 'ocr_result.md'
                if md_file.exists():
                    return jsonify({
                        'status': 'completed',
                        'filename': md_file.name,
                        'current': current,
                        'total': total
                    })
            return jsonify({'status': 'completed', 'current': current, 'total': total})
        elif status == 'error':
            return jsonify({'status': 'error', 'current': current, 'total': total})
        else:
            return jsonify({'status': 'processing', 'current': current, 'total': total})

    return jsonify({'status': 'processing', 'current': 0, 'total': 0})

@app.route('/download/<task_id>', methods=['GET'])
def download_result(task_id):
    output_dir = TEMP_OUTPUT_DIR / task_id
    if not output_dir.exists():
        return jsonify({'error': '任务不存在'}), 404

    text_dir = output_dir / 'text'
    if not text_dir.exists():
        return jsonify({'error': '输出目录不存在'}), 404

    version = request.args.get('version', 'marked')
    if version == 'clean':
        md_file = text_dir / 'ocr_result_clean.md'
        download_name = 'ocr_result_clean.md'
    else:
        md_file = text_dir / 'ocr_result.md'
        download_name = 'ocr_result.md'

    if not md_file.exists():
        return jsonify({'error': '输出文件不存在'}), 404

    return send_file(md_file, as_attachment=True, download_name=download_name)

@app.route('/download_images/<task_id>', methods=['GET'])
def download_images(task_id):
    output_dir = TEMP_OUTPUT_DIR / task_id
    if not output_dir.exists():
        return jsonify({'error': '任务不存在'}), 404

    images_dir = output_dir / 'images'
    if not images_dir.exists():
        return jsonify({'error': '没有图片'}), 404

    zip_path = TEMP_OUTPUT_DIR / f"{task_id}_images.zip"

    if zip_path.exists():
        zip_path.unlink()

    shutil.make_archive(str(zip_path.with_suffix('')), 'zip', str(images_dir))

    return send_file(zip_path, as_attachment=True, download_name='ocr_images.zip')

@app.route('/cleanup/<task_id>', methods=['POST'])
def cleanup(task_id):
    try:
        upload_dir = TEMP_UPLOAD_DIR / task_id
        output_dir = TEMP_OUTPUT_DIR / task_id

        if upload_dir.exists():
            shutil.rmtree(upload_dir)

        if output_dir.exists():
            shutil.rmtree(output_dir)

        zip_files = list(TEMP_OUTPUT_DIR.glob(f"{task_id}_images.zip"))
        for zf in zip_files:
            zf.unlink()

        return jsonify({'message': '清理完成'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

ACTIVE_TASKS = set()

def cleanup_old_tasks():
    """定期清理过期的临时文件"""
    import threading
    import datetime

    def cleanup():
        while True:
            try:
                now = datetime.datetime.now()
                cleanup_age = 7200

                if TEMP_UPLOAD_DIR.exists():
                    for task_dir in TEMP_UPLOAD_DIR.iterdir():
                        if task_dir.is_dir() and task_dir.name not in ACTIVE_TASKS:
                            try:
                                mtime = datetime.datetime.fromtimestamp(task_dir.stat().st_mtime)
                                age = (now - mtime).total_seconds()
                                if age > cleanup_age:
                                    shutil.rmtree(task_dir, ignore_errors=True)
                                    print(f"🧹 已清理过期上传: {task_dir.name}")
                            except Exception:
                                pass

                if TEMP_OUTPUT_DIR.exists():
                    for task_dir in TEMP_OUTPUT_DIR.iterdir():
                        if task_dir.is_dir() and task_dir.name not in ACTIVE_TASKS:
                            try:
                                mtime = datetime.datetime.fromtimestamp(task_dir.stat().st_mtime)
                                age = (now - mtime).total_seconds()
                                if age > cleanup_age:
                                    shutil.rmtree(task_dir, ignore_errors=True)
                                    print(f"🧹 已清理过期输出: {task_dir.name}")
                            except Exception:
                                pass

                for zf in TEMP_OUTPUT_DIR.glob("*_images.zip"):
                    try:
                        mtime = datetime.datetime.fromtimestamp(zf.stat().st_mtime)
                        age = (now - mtime).total_seconds()
                        if age > cleanup_age:
                            zf.unlink(missing_ok=True)
                    except Exception:
                        pass

            except Exception as e:
                print(f"⚠️ 清理出错: {e}")

            time.sleep(300)

    cleanup_thread = threading.Thread(target=cleanup, daemon=True)
    cleanup_thread.start()
    print(f"🧹 后台清理线程已启动 (每5分钟检查一次, 2小时以上的临时文件会被清理)")

def main():
    local_ip = get_local_ip()
    port = 5000

    cleanup_old_tasks()

    print("\n" + "="*60)
    print("🚀 DeepSeek OCR 远程服务已启动")
    print("="*60)
    print(f"\n📍 服务地址: http://{local_ip}:{port}")
    print(f"📍 局域网IP: {local_ip}")
    print(f"\n📋 使用说明:")
    print(f"   1. 让小伙伴在他的电脑上运行 ocr_client.py")
    print(f"   2. 输入服务地址: http://{local_ip}:{port}")
    print(f"   3. 选择PDF文件并提交")
    print(f"   4. 结果会自动下载到他的电脑")
    print("\n" + "="*60)
    print("⚠️  按 Ctrl+C 停止服务")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def cleanup_on_exit():
    """服务停止时清理临时文件"""
    print("\n🧹 正在清理临时文件...")
    try:
        if TEMP_UPLOAD_DIR.exists():
            shutil.rmtree(TEMP_UPLOAD_DIR, ignore_errors=True)
            TEMP_UPLOAD_DIR.mkdir(exist_ok=True)
            print("✅ 上传临时目录已清理")
        if TEMP_OUTPUT_DIR.exists():
            shutil.rmtree(TEMP_OUTPUT_DIR, ignore_errors=True)
            TEMP_OUTPUT_DIR.mkdir(exist_ok=True)
            print("✅ 输出临时目录已清理")
    except Exception as e:
        print(f"⚠️ 清理出错: {e}")

import atexit
atexit.register(cleanup_on_exit)

if __name__ == '__main__':
    main()