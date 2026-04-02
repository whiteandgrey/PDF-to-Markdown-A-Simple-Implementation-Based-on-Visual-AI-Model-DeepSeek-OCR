# 脚本使用说明

本项目包含多个用于 OCR 处理的脚本，以下是每个脚本的详细使用说明。

---

## 📋 脚本列表

| 脚本文件名 | 说明 | 主要功能 |
|-----------|------|---------|
| [ocr_server.py](#ocr_serverpy) | OCR 服务端 | 提供 HTTP API 服务，供客户端调用 |
| [ocr_client.py](#ocr_clientpy) | 命令行客户端 | 通过命令行连接服务端进行 OCR 处理 |
| [ocr_client_gui.py](#ocr_client_guipy) | GUI 客户端 | 图形界面客户端，适合普通用户使用 |
| [build_client_exe.py](#build_client_exepy) | 打包工具 | 将 GUI 客户端打包成 Windows 可执行文件 |
| [pdf_ocr_auto_atomic_output.py](#pdf_ocr_auto_atomic_outputpy) | 本地 OCR 处理 | 在本地直接处理 PDF 文件 |
| [config.py](#configpy) | 配置文件 | 配置 OCR 处理参数和路径 |

---

## ocr_server.py

### 功能说明
提供 OCR 远程服务，让同一局域网内的其他电脑可以使用本机的 OCR 功能。

### 使用方法

```bash
python ocr_server.py
```

### 功能特性
- 自动获取本机局域网 IP 地址
- 提供 Web 界面显示服务信息
- 支持多任务并发处理
- 自动清理过期临时文件（2小时以上）
- 服务停止时自动清理临时文件

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务主页，显示服务信息 |
| `/upload` | POST | 上传 PDF 文件并开始处理 |
| `/status/<task_id>` | GET | 查询任务状态 |
| `/download/<task_id>` | GET | 下载 OCR 结果（支持 `?version=marked` 或 `?version=clean`） |
| `/download_images/<task_id>` | GET | 下载提取的图片（ZIP 格式） |
| `/cleanup/<task_id>` | POST | 清理服务端临时文件 |

---

## ocr_client.py

### 功能说明
命令行版本的 OCR 客户端，用于连接服务端进行 OCR 处理。

### 使用方法

```bash
python ocr_client.py
```

### 使用流程
1. 输入服务端地址（如 `http://192.168.1.100:5000`）
2. 输入 PDF 文件路径（或拖拽文件）
3. 等待处理完成
4. 结果自动下载到 `ocr_results/<task_id>/` 目录

### 输出文件
- `result.md` - OCR 提取的文本结果
- `images/` - 提取的图片目录（如果有）

---

## ocr_client_gui.py

### 功能说明
图形界面版本的 OCR 客户端，提供友好的用户交互界面。

### 使用方法

```bash
python ocr_client_gui.py
```

### 功能特性
- 图形化界面操作
- 自动保存配置（服务端地址、保存位置、超时时间、PDF选择位置）
- 实时显示处理进度和日志
- 任务进行时关闭窗口有确认提示
- Windows 高 DPI 支持

### 使用流程
1. 输入服务端地址
2. 点击"测试连接"确认连接成功
3. 点击"浏览..."选择 PDF 文件
4. 点击"选择..."设置保存位置
5. 点击"开始处理"
6. 等待处理完成，结果自动保存

### 配置保存
配置文件保存在：`~/.deepseek_ocr_client/config.json`

---

## build_client_exe.py

### 功能说明
将 GUI 客户端打包成独立的 Windows 可执行文件（.exe）。

### 使用方法

```bash
python build_client_exe.py
```

### 输出
- `dist/OCR_Client.exe` - 打包后的可执行文件
- 无需安装 Python 环境，双击即可运行

### 打包特性
- 单文件打包（`--onefile`）
- 无控制台窗口（`--windowed`）
- 自动清理临时文件

---

## pdf_ocr_auto_atomic_output.py

### 功能说明
在本地直接处理 PDF 文件，无需网络连接。

### 使用方法

```bash
# 使用配置文件中的默认 PDF
python pdf_ocr_auto_atomic_output.py

# 指定 PDF 文件
python pdf_ocr_auto_atomic_output.py document.pdf

# 指定 PDF 文件和输出目录
python pdf_ocr_auto_atomic_output.py document.pdf ./results
```

### 功能特性
- 原子式输出：任务开始时立即创建输出文件
- 实时写入：提取的文字实时写入文件
- 文件名规范化：处理非法字符、长度限制、同名文件
- 支持配置文件（config.py）

### 输出目录结构
```
输出目录/
├── text/
│   └── <文件名>.md          # OCR 文本结果
├── images/
│   ├── page_0001_img_001.jpg  # 提取的图片
│   └── ...
└── temp/                    # 临时文件（处理后自动清理）
```

---

## config.py

### 功能说明
配置文件，用于设置 OCR 处理的各种参数。

### 主要配置项

#### 模型配置
```python
MODEL_CONFIG = {
    'model_path': '路径/到/模型',
    'use_local_model': True,
}
```

#### 处理配置
```python
PROCESS_CONFIG = {
    'dpi': 300,
    'ocr_params': {
        'base_size': 1024,
        'image_size': 640,
        'crop_mode': True,
    },
}
```

#### 路径配置
```python
PATH_CONFIG = {
    'input_pdf': '默认PDF文件路径',
    'output_dir': '默认输出目录',
}
```

#### 系统配置
```python
SYSTEM_CONFIG = {
    'cuda_visible_devices': '0',
    'batch_size': 1,
    'timeout_per_page': 600,
}
```

---

## 📝 快速开始

### 场景 1：远程使用（推荐）
1. **服务端**：运行 `python ocr_server.py`
2. **客户端**：运行 `dist/OCR_Client.exe`（或 `python ocr_client_gui.py`）
3. 输入服务端地址，选择 PDF 文件，开始处理

### 场景 2：本地使用
1. 配置 `config.py` 中的模型路径
2. 运行 `python pdf_ocr_auto_atomic_output.py document.pdf`

---

## ⚠️ 注意事项

1. **远程使用**：服务端和客户端需要在同一局域网内
2. **GPU 要求**：本地 OCR 处理需要 NVIDIA GPU 和 CUDA
3. **防火墙**：确保服务端的 5000 端口未被防火墙阻止
4. **临时文件**：服务端会自动清理 2 小时以上的临时文件
