name: Build Release

on:
  push:
    tags: ['v*']

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install -r requirements.txt

      - run: python -m PyInstaller --onefile --windowed --uac-admin --collect-all rapidocr --name="MechaBreakAuto-${{ github.ref_name }}" --add-data="templates;templates" main.py

      - uses: softprops/action-gh-release@v2
        with:
          files: dist/MechaBreakAuto-${{ github.ref_name }}.exe
          name: "解限机路网补给助手 ${{ github.ref_name }}"
          body: |
            ## 更新内容

            IV级 / I~III级武装分区独立控制：将原来的混合模式拆分为两个独立分区，各自控制不同等级的武装购买策略。

            - **IV级武装**：3 种模式（全买 / 按勾选 / 不买），仅控制 4 级紫色武装
              - 「按勾选」时展示独立 21 武装复选框，旁带折叠按钮可收起列表
              - 「全买」「不买」时复选框自动隐藏
            - **I~III级武装**：2 种模式（购买勾选 / 不购买），仅控制 1~3 级武装
              - 「购买勾选」时展示独立 21 武装复选框，旁带折叠按钮
              - 「不购买」时复选框自动隐藏
            - 使用 Notebook 标签页切换两个分区，窗口高度不变
            - 默认勾选：蓄能爆破炮、分束机炮、六联导弹发射器

            ## ⚠ v1.0.7+ 重大变更（对比 v1.0.6）

            > v1.0.6 及之前使用模板匹配识别武装，v1.0.7 起更换为 ONNX 文字识别。

            - **检测方式**：模板匹配（cv2.matchTemplate）→ ONNX 文字识别（RapidOCR PP-OCRv4）
            - **识别流程**：投影分行 + 固定 ROI 裁切 → 单行纯文字 → rec 直连推理
            - **准确性**：216 张实测截图，名字全部正确，价格识别 95%+ 可用
            - **速度**：41ms/卡，6 卡约 260ms

            ## 参考数据

            设置：购买蓄爆分束六联 + 4级仅购买勾选  
            最终：62w蓝币刷新1400次（约每100轮耗时8分钟4w蓝币）  
            四级：六联11 蓄爆12 分束18  
            经验：
            - 六联 235×5+100×12+30×30=3275
            - 蓄爆 210×5+120×12+24×30=3210
            - 分束 227×5+125×12+30×30=3535

            ## 使用

            1. 下载 MechaBreakAuto-${{ github.ref_name }}.exe
            2. 游戏设置 720p 分辨率 + 窗口模式
            3. 打开路网补给页面 → 运行 EXE → 配置区域 → 选择 IV/I~III 策略 → 开始
            4. 按 F8 停止
