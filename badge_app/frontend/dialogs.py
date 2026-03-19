# -*- coding: utf-8 -*-
from PySide6 import QtWidgets, QtGui, QtCore

from ..backend import state
from ..backend.market import 规范化合约代码, 合约代码合法, 在市期货合约加载线程
from .widgets import 悬浮牌预览


class 设置对话框(QtWidgets.QDialog):
    合约切换请求 = QtCore.Signal(str)

    def __init__(self, 当前合约: str, 父=None):
        super().__init__(父)
        self.当前合约 = 当前合约
        self.setWindowTitle("设置 - 悬浮牌样式")
        self.setModal(True)
        self.setFixedSize(520, 560)
        self._预览组件位置 = state.读取组件位置配置()
        self._在市期货合约: list[str] = []
        self._合约加载线程 = None
        self._初始化界面()
        self._恢复位置()

    def _初始化界面(self):
        布局 = QtWidgets.QGridLayout(self)
        行 = 0

        布局.addWidget(QtWidgets.QLabel("行情字体大小："), 行, 0, QtCore.Qt.AlignRight)
        self.字号变量 = QtWidgets.QSpinBox(self)
        self.字号变量.setRange(1, 160)
        self.字号变量.setSingleStep(2)
        self.字号变量.setValue(state.配置["badge_font_size"])
        self.字号变量.valueChanged.connect(self._预览)
        布局.addWidget(self.字号变量, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("行情字体颜色："), 行, 0, QtCore.Qt.AlignRight)
        self.颜色按钮 = QtWidgets.QPushButton(state.配置["badge_font_color"], self)
        self.颜色按钮.clicked.connect(self._选择颜色)
        布局.addWidget(self.颜色按钮, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("备注字体大小："), 行, 0, QtCore.Qt.AlignRight)
        self.备注字号变量 = QtWidgets.QSpinBox(self)
        self.备注字号变量.setRange(10, 80)
        self.备注字号变量.setSingleStep(1)
        self.备注字号变量.setValue(state.配置["subtitle_font_size"])
        self.备注字号变量.valueChanged.connect(self._预览)
        布局.addWidget(self.备注字号变量, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("备注字体颜色："), 行, 0, QtCore.Qt.AlignRight)
        self.备注颜色按钮 = QtWidgets.QPushButton(state.配置["subtitle_font_color"], self)
        self.备注颜色按钮.clicked.connect(lambda: self._选择颜色(True))
        布局.addWidget(self.备注颜色按钮, 行, 1, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("订阅合约："), 行, 0, QtCore.Qt.AlignRight)
        self.合约输入 = QtWidgets.QLineEdit(self.当前合约, self)
        self.合约输入.setPlaceholderText("输入关键字模糊搜索在市期货合约（示例：SHFE.rb2501）")
        self.合约输入.editingFinished.connect(self._规范化合约输入)
        self.合约补全模型 = QtCore.QStringListModel(self)
        self.合约补全 = QtWidgets.QCompleter(self.合约补全模型, self)
        self.合约补全.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.合约补全.setFilterMode(QtCore.Qt.MatchContains)
        self.合约补全.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.合约输入.setCompleter(self.合约补全)
        self._刷新合约补全()
        self._加载在市期货合约()
        布局.addWidget(self.合约输入, 行, 1, QtCore.Qt.AlignLeft)
        self.切换合约按钮 = QtWidgets.QPushButton("切换", self)
        self.切换合约按钮.clicked.connect(self._切换合约)
        布局.addWidget(self.切换合约按钮, 行, 2, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("价格上方小字："), 行, 0, QtCore.Qt.AlignRight)
        self.小字输入 = QtWidgets.QLineEdit(state.配置.get("badge_subtitle") or state.合约代码, self)
        self.小字输入.textChanged.connect(self._预览)
        布局.addWidget(self.小字输入, 行, 1, QtCore.Qt.AlignLeft)
        提示标签 = QtWidgets.QLabel("（留空=跟随合约代码）", self)
        提示标签.setStyleSheet("color:#888888;")
        布局.addWidget(提示标签, 行, 2, QtCore.Qt.AlignLeft)
        行 += 1

        布局.addWidget(QtWidgets.QLabel("预览："), 行, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        self.预览组件 = 悬浮牌预览(self)
        self.预览组件.位置变更.connect(self._更新预览位置提示)
        self.预览组件.应用外部位置(self._预览组件位置)
        布局.addWidget(self.预览组件, 行, 1, 1, 2)
        行 += 1

        按钮框 = QtWidgets.QHBoxLayout()
        self.确定按钮 = QtWidgets.QPushButton("保存", self)
        self.确定按钮.setDefault(True)
        self.确定按钮.setAutoDefault(True)
        self.取消按钮 = QtWidgets.QPushButton("取消", self)
        self.确定按钮.clicked.connect(self.accept)
        self.取消按钮.clicked.connect(self.reject)
        按钮框.addStretch(1)
        按钮框.addWidget(self.确定按钮)
        按钮框.addWidget(self.取消按钮)
        布局.addLayout(按钮框, 行, 0, 1, 3)

        self._预览()

    def _候选合约列表(self) -> list[str]:
        候选 = [self.当前合约]
        候选.extend(self._在市期货合约)
        候选.extend(state.配置.get("recent_symbols", []))
        结果 = []
        for 项 in 候选:
            代码 = 规范化合约代码(str(项))
            if 代码 and 代码 not in 结果:
                结果.append(代码)
        return 结果

    def _刷新合约补全(self):
        self.合约补全模型.setStringList(self._候选合约列表())

    def _加载在市期货合约(self):
        self._合约加载线程 = 在市期货合约加载线程(state.TQ_USER, state.TQ_PASS, self)
        self._合约加载线程.完成信号.connect(self._应用在市期货合约)
        self._合约加载线程.错误信号.connect(self._处理合约加载失败)
        self._合约加载线程.finished.connect(self._合约加载结束)
        self._合约加载线程.start()

    def _应用在市期货合约(self, 合约列表: list[str]):
        self._在市期货合约 = [规范化合约代码(x) for x in 合约列表 if str(x).strip()]
        self._刷新合约补全()

    def _处理合约加载失败(self, 错误信息: str):
        print("加载在市期货合约失败:", 错误信息)

    def _合约加载结束(self):
        self._合约加载线程 = None

    def _规范化合约输入(self):
        self.合约输入.setText(规范化合约代码(self.合约输入.text()))

    def _切换合约(self):
        代码 = 规范化合约代码(self.合约输入.text())
        self.合约输入.setText(代码)
        if not 合约代码合法(代码):
            QtWidgets.QMessageBox.warning(
                self,
                "合约代码无效",
                "请输入天勤可识别的代码，例如：\n"
                "- KQ.m@SHFE.cu（主连）\n"
                "- SHFE.rb2501（具体合约）",
            )
            return
        self.合约切换请求.emit(代码)
        QtWidgets.QMessageBox.information(self, "已切换", f"已切换到合约：{代码}")
        self.当前合约 = 代码
        self._刷新合约补全()

    def _选择颜色(self, 用于备注=False):
        按钮 = self.备注颜色按钮 if 用于备注 else self.颜色按钮
        初始 = QtGui.QColor(按钮.text())
        颜色 = QtWidgets.QColorDialog.getColor(初始, self, "选择字体颜色")
        if 颜色.isValid():
            if (not 用于备注) and 颜色.name().lower() == "#00ff00":
                QtWidgets.QMessageBox.information(
                    self,
                    "提示",
                    "纯 #00FF00 绿在透明背景上会比较刺眼，建议用稍微偏灰一点的绿，例如 #A6E22E。",
                )
            按钮.setText(颜色.name())
            self._预览()

    def _预览(self):
        字号 = self.字号变量.value()
        颜色 = self.颜色按钮.text()
        备注字号 = self.备注字号变量.value()
        备注颜色 = self.备注颜色按钮.text()
        小字原始 = (self.小字输入.text() or "").strip()
        小字文本 = 小字原始 if 小字原始 else state.合约代码
        行情文本 = getattr(self.parent(), "当前价格文本", "12345.6")

        self.预览组件.更新样式(字号, 颜色, 备注字号, 备注颜色)
        self.预览组件.更新文本(小字文本, 行情文本)
        self.预览组件.应用外部位置(self._预览组件位置)

    def _更新预览位置提示(self, 位置: dict):
        self._预览组件位置 = 位置

    def accept(self):
        字号 = self.字号变量.value()
        颜色 = self.颜色按钮.text()
        备注字号 = self.备注字号变量.value()
        备注颜色 = self.备注颜色按钮.text()
        小字原始 = (self.小字输入.text() or "").strip()
        位置 = self._预览组件位置
        state.配置["badge_font_size"] = 字号
        state.配置["badge_font_color"] = 颜色
        state.配置["subtitle_font_size"] = 备注字号
        state.配置["subtitle_font_color"] = 备注颜色
        state.配置["badge_subtitle"] = "" if (小字原始 == "" or 小字原始 == state.合约代码) else 小字原始
        state.配置["badge_subtitle_pos"] = {"x": int(位置["subtitle"].x()), "y": int(位置["subtitle"].y())}
        state.配置["badge_lock_pos"] = {"x": int(位置["lock"].x()), "y": int(位置["lock"].y())}
        state.配置["badge_edit_pos"] = {"x": int(位置["edit"].x()), "y": int(位置["edit"].y())}
        state.配置["badge_price_pos"] = {"x": int(位置["price"].x()), "y": int(位置["price"].y())}
        state.保存配置()
        super().accept()

    def keyPressEvent(self, 事件: QtGui.QKeyEvent):
        if 事件.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.accept()
            return
        super().keyPressEvent(事件)

    def _恢复位置(self):
        记录 = state.配置.get("settings_pos") or {}
        if "x" in 记录 and "y" in 记录:
            目标 = QtCore.QPoint(int(记录["x"]), int(记录["y"]))
        else:
            目标 = self._默认位置()

        安全点 = state.计算安全坐标(目标, self.size())
        self.move(安全点)

    def _默认位置(self) -> QtCore.QPoint:
        父级 = self.parentWidget()
        if 父级:
            父矩形 = 父级.frameGeometry()
            return 父矩形.center() - QtCore.QPoint(self.width() // 2, self.height() // 2)

        屏幕 = QtGui.QGuiApplication.primaryScreen()
        if 屏幕:
            可用 = 屏幕.availableGeometry()
            return 可用.center() - QtCore.QPoint(self.width() // 2, self.height() // 2)
        return QtCore.QPoint(100, 100)

    def _保存位置(self):
        state.配置["settings_pos"] = {"x": int(self.x()), "y": int(self.y())}
        state.保存配置()

    def _停止合约加载线程(self):
        线程 = self._合约加载线程
        if 线程 and 线程.isRunning():
            线程.requestInterruption()
            线程.wait(1200)

    def closeEvent(self, 事件: QtGui.QCloseEvent):
        self._停止合约加载线程()
        self._保存位置()
        super().closeEvent(事件)
