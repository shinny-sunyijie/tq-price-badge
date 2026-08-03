# -*- coding: utf-8 -*-
from PySide6 import QtWidgets, QtGui, QtCore

from ..backend import state
from ..backend.market import 规范化合约代码, 合约代码合法, 在市期货合约加载线程
from .widgets import 悬浮牌预览


_在市期货合约缓存: list[str] | None = None
_在市期货合约加载中: 在市期货合约加载线程 | None = None


class 设置对话框(QtWidgets.QDialog):
    合约切换请求 = QtCore.Signal(str)

    def __init__(self, 当前合约: str, 父=None):
        super().__init__(父)
        self.当前合约 = 当前合约
        self.setWindowTitle("设置 - 悬浮牌样式")
        self.setModal(True)
        self.setMinimumSize(620, 650)
        self.resize(640, 680)
        self.setSizeGripEnabled(True)
        self._预览组件位置 = state.读取组件位置配置()
        self._在市期货合约: list[str] = []
        self._合约加载线程 = None
        self._初始化界面()
        self._恢复位置()

    def _初始化界面(self):
        外层布局 = QtWidgets.QVBoxLayout(self)
        self.设置页签 = QtWidgets.QTabWidget(self)
        外层布局.addWidget(self.设置页签, 1)

        行情页 = QtWidgets.QWidget(self.设置页签)
        self.设置页签.addTab(行情页, "行情与备注")
        布局 = QtWidgets.QGridLayout(行情页)
        布局.setColumnStretch(1, 1)
        行 = 0

        self.自定义行情显示开关 = QtWidgets.QCheckBox("显示这一条自定义行情（最多 1 条）", self)
        self.自定义行情显示开关.setChecked(bool(state.配置.get("custom_quote_enabled", True)))
        self.自定义行情显示开关.setToolTip("取消勾选后，合约备注和大号价格会一起隐藏")
        布局.addWidget(self.自定义行情显示开关, 行, 0, 1, 3)
        行 += 1

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
        self.合约输入.setMinimumWidth(300)
        self._刷新合约补全()
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
        布局.addWidget(self.预览组件, 行, 1, 1, 2, QtCore.Qt.AlignLeft)
        布局.setRowStretch(行, 1)

        self._自定义行情设置控件 = (
            self.字号变量,
            self.颜色按钮,
            self.备注字号变量,
            self.备注颜色按钮,
            self.合约输入,
            self.切换合约按钮,
            self.小字输入,
            self.预览组件,
        )
        self.自定义行情显示开关.toggled.connect(self._切换自定义行情设置)
        self._切换自定义行情设置(self.自定义行情显示开关.isChecked())
        # 只根据打开设置时已保存的配置加载合约目录。临时勾选后又
        # 取消对话框，不应产生一次未经保存的行情认证连接。
        if bool(state.配置.get("custom_quote_enabled", True)):
            self._加载在市期货合约()

        账户页 = QtWidgets.QWidget(self.设置页签)
        self.设置页签.addTab(账户页, "账户监控")
        账户页布局 = QtWidgets.QVBoxLayout(账户页)

        监控范围组 = QtWidgets.QGroupBox("监控范围", 账户页)
        账户监控布局 = QtWidgets.QVBoxLayout(监控范围组)
        self.持仓行情监控开关 = QtWidgets.QCheckBox("监控持仓，并显示持仓合约最新价", self)
        self.持仓行情监控开关.setChecked(bool(state.配置.get("monitor_position_quotes", False)))
        self.持仓行情监控开关.setToolTip("显示实盘持仓、浮动盈亏，并自动订阅持仓合约的最新价")
        账户监控布局.addWidget(self.持仓行情监控开关)
        self.委托行情监控开关 = QtWidgets.QCheckBox("监控未成委托，并显示委托合约最新价", self)
        self.委托行情监控开关.setChecked(bool(state.配置.get("monitor_order_quotes", False)))
        self.委托行情监控开关.setToolTip("显示仍有效的未成委托，并自动订阅这些委托合约的最新价")
        账户监控布局.addWidget(self.委托行情监控开关)
        账户监控提示 = QtWidgets.QLabel("只读监控，不提供下单或撤单操作；上方可选显示一条自定义行情。", self)
        账户监控提示.setStyleSheet("color:#888888;")
        账户监控提示.setWordWrap(True)
        账户监控布局.addWidget(账户监控提示)
        账户页布局.addWidget(监控范围组)

        显示设置组 = QtWidgets.QGroupBox("模块字号与位置", 账户页)
        显示设置布局 = QtWidgets.QGridLayout(显示设置组)
        显示设置布局.setHorizontalSpacing(12)
        显示设置布局.addWidget(QtWidgets.QLabel("模块"), 0, 0)
        显示设置布局.addWidget(QtWidgets.QLabel("字号"), 0, 1)
        显示设置布局.addWidget(QtWidgets.QLabel("位置"), 0, 2)
        显示设置布局.addWidget(QtWidgets.QLabel("X"), 0, 3)
        显示设置布局.addWidget(QtWidgets.QLabel("Y"), 0, 4)

        账户位置 = state.读取账户组件位置配置()
        显示设置布局.addWidget(QtWidgets.QLabel("整体账户区", self), 1, 0)
        显示设置布局.addWidget(QtWidgets.QLabel("—", self), 1, 1)
        (
            self.账户面板位置自动开关,
            self.账户面板X变量,
            self.账户面板Y变量,
        ) = self._添加账户位置设置控件(
            显示设置布局, 1, 账户位置["panel"], QtCore.QPoint(6, 108)
        )
        (
            self.账户状态字号变量,
            self.账户状态位置自动开关,
            self.账户状态X变量,
            self.账户状态Y变量,
        ) = self._添加账户显示设置行(
            显示设置布局, 2, "账户状态", "account_status_font_size",
            账户位置["status"], QtCore.QPoint(0, 0),
        )
        (
            self.委托字号变量,
            self.委托位置自动开关,
            self.委托X变量,
            self.委托Y变量,
        ) = self._添加账户显示设置行(
            显示设置布局, 3, "未成委托", "account_order_font_size",
            账户位置["order"], QtCore.QPoint(0, 24),
        )
        (
            self.持仓字号变量,
            self.持仓位置自动开关,
            self.持仓X变量,
            self.持仓Y变量,
        ) = self._添加账户显示设置行(
            显示设置布局, 4, "持仓", "account_position_font_size",
            账户位置["position"], QtCore.QPoint(0, 72),
        )

        self.账户全部自动排列按钮 = QtWidgets.QPushButton("全部恢复自动排列", 显示设置组)
        self.账户全部自动排列按钮.clicked.connect(self._账户全部恢复自动排列)
        显示设置布局.addWidget(self.账户全部自动排列按钮, 5, 0, 1, 5, QtCore.Qt.AlignLeft)
        账户位置提示 = QtWidgets.QLabel(
            "“整体账户区”的 X/Y 相对悬浮牌左上角；其余三项的 X/Y 相对整体账户区。"
            "自动排列会随字号和内容高度避让。",
            显示设置组,
        )
        账户位置提示.setWordWrap(True)
        账户位置提示.setStyleSheet("color:#888888;")
        显示设置布局.addWidget(账户位置提示, 6, 0, 1, 5)
        账户页布局.addWidget(显示设置组)
        账户页布局.addStretch(1)

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
        外层布局.addLayout(按钮框)

        self._预览()

    def _添加账户显示设置行(
        self,
        布局: QtWidgets.QGridLayout,
        行: int,
        名称: str,
        字号配置键: str,
        已保存位置: QtCore.QPoint | None,
        位置占位: QtCore.QPoint,
    ):
        布局.addWidget(QtWidgets.QLabel(名称, self), 行, 0)

        字号 = QtWidgets.QSpinBox(self)
        字号.setRange(6, 48)
        字号.setSingleStep(1)
        字号.setSuffix(" pt")
        字号.setValue(int(state.配置.get(字号配置键, 9)))
        布局.addWidget(字号, 行, 1)

        自动, x变量, y变量 = self._添加账户位置设置控件(
            布局, 行, 已保存位置, 位置占位
        )
        return 字号, 自动, x变量, y变量

    def _添加账户位置设置控件(
        self,
        布局: QtWidgets.QGridLayout,
        行: int,
        已保存位置: QtCore.QPoint | None,
        位置占位: QtCore.QPoint,
    ):
        自动 = QtWidgets.QCheckBox("自动", self)
        自动.setChecked(已保存位置 is None)
        自动.setToolTip("勾选后由悬浮牌根据其它模块的大小自动排列")
        布局.addWidget(自动, 行, 2)

        显示位置 = 已保存位置 if 已保存位置 is not None else 位置占位
        x变量 = QtWidgets.QSpinBox(self)
        x变量.setRange(0, 4000)
        x变量.setValue(显示位置.x())
        x变量.setToolTip("整体账户区相对悬浮牌；内容模块相对整体账户区")
        布局.addWidget(x变量, 行, 3)

        y变量 = QtWidgets.QSpinBox(self)
        y变量.setRange(0, 4000)
        y变量.setValue(显示位置.y())
        y变量.setToolTip("整体账户区相对悬浮牌；内容模块相对整体账户区")
        布局.addWidget(y变量, 行, 4)

        def 切换坐标编辑(使用自动: bool):
            x变量.setEnabled(not 使用自动)
            y变量.setEnabled(not 使用自动)

        自动.toggled.connect(切换坐标编辑)
        切换坐标编辑(自动.isChecked())
        return 自动, x变量, y变量

    def _账户全部恢复自动排列(self):
        for 开关 in (
            self.账户面板位置自动开关,
            self.账户状态位置自动开关,
            self.委托位置自动开关,
            self.持仓位置自动开关,
        ):
            开关.setChecked(True)

    def _切换自定义行情设置(self, 显示: bool):
        """关闭自定义行情时保留参数，但禁用编辑并隐藏整块预览。"""

        for 控件 in self._自定义行情设置控件:
            控件.setEnabled(显示)
        self.预览组件.setVisible(显示)

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
        global _在市期货合约加载中
        if _在市期货合约缓存 is not None:
            self._应用在市期货合约(_在市期货合约缓存)
            return
        if _在市期货合约加载中 is not None and _在市期货合约加载中.isFinished():
            _在市期货合约加载中 = None

        需要启动 = _在市期货合约加载中 is None
        if 需要启动:
            _在市期货合约加载中 = 在市期货合约加载线程(state.TQ_USER, state.TQ_PASS, self)
        self._合约加载线程 = _在市期货合约加载中
        self._合约加载线程.完成信号.connect(self._应用在市期货合约)
        self._合约加载线程.错误信号.connect(self._处理合约加载失败)
        self._合约加载线程.finished.connect(self._合约加载结束)
        if 需要启动:
            self._合约加载线程.start()

    def _应用在市期货合约(self, 合约列表: list[str]):
        global _在市期货合约缓存
        self._在市期货合约 = [规范化合约代码(x) for x in 合约列表 if str(x).strip()]
        _在市期货合约缓存 = list(self._在市期货合约)
        self._刷新合约补全()

    def _处理合约加载失败(self, 错误信息: str):
        print("加载在市期货合约失败:", 错误信息)

    def _合约加载结束(self):
        global _在市期货合约加载中
        完成线程 = self._合约加载线程
        self._合约加载线程 = None
        if _在市期货合约加载中 is 完成线程:
            _在市期货合约加载中 = None

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

    @staticmethod
    def _读取位置控件值(自动开关, x变量, y变量):
        if 自动开关.isChecked():
            return None
        return {"x": int(x变量.value()), "y": int(y变量.value())}

    def accept(self):
        字号 = self.字号变量.value()
        颜色 = self.颜色按钮.text()
        备注字号 = self.备注字号变量.value()
        备注颜色 = self.备注颜色按钮.text()
        小字原始 = (self.小字输入.text() or "").strip()
        位置 = self._预览组件位置
        state.配置["custom_quote_enabled"] = self.自定义行情显示开关.isChecked()
        state.配置["badge_font_size"] = 字号
        state.配置["badge_font_color"] = 颜色
        state.配置["subtitle_font_size"] = 备注字号
        state.配置["subtitle_font_color"] = 备注颜色
        state.配置["badge_subtitle"] = "" if (小字原始 == "" or 小字原始 == state.合约代码) else 小字原始
        state.配置["badge_subtitle_pos"] = {"x": int(位置["subtitle"].x()), "y": int(位置["subtitle"].y())}
        state.配置["badge_lock_pos"] = {"x": int(位置["lock"].x()), "y": int(位置["lock"].y())}
        state.配置["badge_edit_pos"] = {"x": int(位置["edit"].x()), "y": int(位置["edit"].y())}
        state.配置["badge_price_pos"] = {"x": int(位置["price"].x()), "y": int(位置["price"].y())}
        state.配置["monitor_position_quotes"] = self.持仓行情监控开关.isChecked()
        state.配置["monitor_order_quotes"] = self.委托行情监控开关.isChecked()
        state.配置["account_status_font_size"] = self.账户状态字号变量.value()
        state.配置["account_position_font_size"] = self.持仓字号变量.value()
        state.配置["account_order_font_size"] = self.委托字号变量.value()
        state.配置["account_panel_pos"] = self._读取位置控件值(
            self.账户面板位置自动开关, self.账户面板X变量, self.账户面板Y变量
        )
        state.配置["account_status_pos"] = self._读取位置控件值(
            self.账户状态位置自动开关, self.账户状态X变量, self.账户状态Y变量
        )
        state.配置["account_position_pos"] = self._读取位置控件值(
            self.持仓位置自动开关, self.持仓X变量, self.持仓Y变量
        )
        state.配置["account_order_pos"] = self._读取位置控件值(
            self.委托位置自动开关, self.委托X变量, self.委托Y变量
        )
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
        # 合约目录加载在线程间共享，关闭某一个设置窗口不应中断其它窗口的加载。
        # 应用退出时由主控制统一请求中断并等待线程真正结束。
        self._合约加载线程 = None

    def closeEvent(self, 事件: QtGui.QCloseEvent):
        self._停止合约加载线程()
        self._保存位置()
        super().closeEvent(事件)
