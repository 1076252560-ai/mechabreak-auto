# 解限机路网补给助手

![Downloads](https://img.shields.io/github/downloads/Coder-Sakura/mechabreak-auto/total?label=Downloads&cacheSeconds=3600) ![Release](https://badgen.net/github/release/Coder-Sakura/mechabreak-auto?label=Release)

自动刷新路网补给页面，按筛选条件自动购买武装。

## 功能

- IV 级独立设置：购买所有 / 仅勾选 / 不购买
- I/II/III 级独立设置：购买勾选 / 不购买
- ONNX 文字识别 + 紫色检测，准确率 > 95%
- 自动刷新循环

## 下载

从 [Releases](https://github.com/Coder-Sakura/mechabreak-auto/releases) 下载最新 EXE，放到文件夹双击运行。

## 使用

1. 打开游戏路网补给页面（建议 720p 分辨率 + 窗口模式）
2. 管理员运行 EXE → 点「配置区域」→ 参考图 → 框选卡片区域 → 预览确认
3. 同样框选刷新按钮 → 预览确认
4. 分别选择 IV 级和I/II/III 级要买的武装
5. 点「▶ 开始」
6. 按 F8 停止

### gif示例动画：

<img width="818" height="554" alt="动画" src="https://github.com/user-attachments/assets/dea63481-e69a-4c37-b819-ad1d71301e02" />

## 开发

```
pip install -r requirements.txt
python main.py          # 本地运行
build.bat               # 打包 EXE
```

## 技术栈

Python 3.11 + tkinter + RapidOCR ONNX + OpenCV + Win32 API


## 最后的话
本项目仅供个人学习相关技术使用
