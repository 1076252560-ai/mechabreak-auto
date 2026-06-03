# 解限机路网补给助手

自动刷新路网补给页面，按筛选条件自动购买武装。

## 功能

- 全选模式：购买所有未售罄武装
- IV 级紫色全买 + 其他按勾选购买
- 指定武装模板匹配购买
- 自动刷新循环

## 下载

从 [Releases](https://github.com/Coder-Sakura/mechabreak-auto/releases) 下载最新 EXE，放到文件夹双击运行。

## 使用

1. 打开游戏路网补给页面（建议游戏显示改为窗口+720p分辨率，效果更佳）
2. 右键管理员权限运行 EXE → 点「配置区域」→ 框选 6 张卡片区域 → 框选刷新按钮
3. 选择 IV 级模式 + 勾选要买的武装
4. 点「▶ 开始」
5. 关闭窗口时自动保存勾选状态和参数
动画：
<img width="818" height="554" alt="动画" src="https://github.com/user-attachments/assets/dea63481-e69a-4c37-b819-ad1d71301e02" />

## 调整识别阈值

当某个武装被误识别时，编辑 EXE 同目录下的 `config.json`，找到 `arm_thresholds`：

```json
"arm_thresholds": {"_default": 0.90, "蓄能爆破炮": 0.92}
```

`_default` 为全局阈值，单独写武装名可覆盖。提高数值减少误匹配，降低数值放宽匹配。改完保存即生效。

## 开发

```
pip install -r requirements.txt
python main.py          # 本地运行
build.bat               # 打包 EXE
```

## 技术栈

Python 3.11 + tkinter + OpenCV + Win32 API
