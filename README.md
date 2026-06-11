# 解限机路网补给助手

![Downloads](https://gh-down-badges.linkof.link/Coder-Sakura/mechabreak-auto)![Release](https://badgen.net/github/release/Coder-Sakura/mechabreak-auto)

自动刷新路网补给页面，按筛选条件自动购买武装。

## 功能

- 全选模式：购买所有未售罄武装
- IV 级购买模式：购买所有 / 仅勾选 / 不购买
- I/II/III 级按勾选武装购买
- ONNX 文字识别 + 紫色检测，准确率 > 95%
- 自动刷新循环

## 下载

从 [Releases](https://github.com/Coder-Sakura/mechabreak-auto/releases) 下载最新 EXE，放到文件夹双击运行。

## 使用

1. 打开游戏路网补给页面（建议 720p 分辨率 + 窗口模式）
2. 管理员运行 EXE → 点「配置区域」→ 参考图 → 框选卡片区域 → 预览确认
3. 同样框选刷新按钮 → 预览确认
4. 选择 IV 模式 + 勾选要买的武装
5. 点「▶ 开始」
6. 按 F8 停止，关闭时自动保存设置

动画：
<img width="818" height="554" alt="动画" src="https://github.com/user-attachments/assets/dea63481-e69a-4c37-b819-ad1d71301e02" />

## config.json 默认配置

首次运行自动生成，用户无需手动编辑。

| 字段 | 默认值 | 说明 |
|---|---|---|
| `iv_mode` | `"all"` | 四级模式：`"all"`=全买, `"filter"`=仅勾选, `"none"`=不买 |
| `arms` | 21 武装全 `false` | 待用户勾选 |
| `refresh_delay` | `1.5` | 刷新间隔（秒） |
| `max_rounds` | `1` | 最大轮数（0=无限） |
| `action_delay` | `300` | 操作延迟（毫秒） |

## 开发

```
pip install -r requirements.txt
python main.py          # 本地运行
build.bat               # 打包 EXE
```

## 技术栈

Python 3.11 + tkinter + RapidOCR ONNX + OpenCV + Win32 API
