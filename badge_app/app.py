# -*- coding: utf-8 -*-
import sys

from PySide6 import QtWidgets, QtCore

from .backend import state
from .backend.account import 账户监控线程
from .backend.market import 行情线程, 在市期货合约加载线程, 写入最近合约, 规范化合约代码
from .frontend.dialogs import 设置对话框
from .frontend.widgets import 悬浮牌窗口


def _获取单实例锁(锁路径: str | None = None):
    if 锁路径 is None:
        临时目录 = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.TempLocation)
        锁路径 = QtCore.QDir(临时目录).filePath("tq-price-badge.lock")
    锁 = QtCore.QLockFile(锁路径)
    锁.setStaleLockTime(30_000)
    return 锁 if 锁.tryLock(0) else None


class 主控制(QtCore.QObject):
    def __init__(self, 应用: QtWidgets.QApplication):
        super().__init__()
        self.应用 = 应用
        self._当前价格文本 = "…"
        self._行情错误文本 = ""
        self._账户状态文本 = ""
        self._持仓数量 = 0
        self._委托数量 = 0
        self._正在退出 = False
        self._退出等待线程 = []
        self.当前合约 = 规范化合约代码(state.合约代码)
        state.设置当前合约(self.当前合约)
        写入最近合约(self.当前合约)
        state.保存配置()
        self.悬浮牌 = 悬浮牌窗口()
        self.悬浮牌.设置请求.connect(self.打开设置)
        self._自定义行情已开启 = bool(state.配置.get("custom_quote_enabled", True))
        self.悬浮牌.设置自定义行情显示(self._自定义行情已开启)
        self.悬浮牌.应用账户面板设置()
        if state.显示大号价格默认:
            self.悬浮牌.show()

        self.行情线程 = None
        self._退役行情线程 = []
        self._待启动自定义行情合约 = None
        self.账户监控线程 = None
        if self._自定义行情已开启:
            self._启动行情线程(self.当前合约)
        self._创建托盘()
        self._应用账户监控设置()

    def _创建托盘(self):
        图标 = self.应用.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.托盘 = QtWidgets.QSystemTrayIcon(图标, self.应用)
        菜单 = QtWidgets.QMenu()

        self.显示动作 = 菜单.addAction("隐藏悬浮牌" if self.悬浮牌.isVisible() else "显示悬浮牌")
        self.锁定动作 = 菜单.addAction("解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌")
        菜单.addSeparator()
        self.设置动作 = 菜单.addAction("设置")
        菜单.addSeparator()
        self.退出动作 = 菜单.addAction("退出")

        self.显示动作.triggered.connect(self.切换悬浮牌可见)
        self.锁定动作.triggered.connect(self.切换锁定)
        self.设置动作.triggered.connect(self.打开设置)
        self.退出动作.triggered.connect(self.退出)

        self.托盘.setContextMenu(菜单)
        self._刷新托盘提示()
        self.托盘.show()

    def 切换悬浮牌可见(self):
        if self.悬浮牌.isVisible():
            self.悬浮牌.hide()
            self.显示动作.setText("显示悬浮牌")
        else:
            self.悬浮牌.show()
            self.显示动作.setText("隐藏悬浮牌")

    def 切换锁定(self):
        self.悬浮牌.切换锁定()
        self.锁定动作.setText("解锁悬浮牌" if self.悬浮牌.已锁定 else "锁定悬浮牌")

    def 打开设置(self):
        对话 = 设置对话框(self.当前合约, self.悬浮牌)
        对话.合约切换请求.connect(self.切换合约订阅)
        if 对话.exec() == QtWidgets.QDialog.Accepted:
            self.悬浮牌.应用样式(
                字号=state.配置["badge_font_size"],
                颜色=state.配置["badge_font_color"],
                小字=state.生效小字(),
                小字字号=state.配置["subtitle_font_size"],
                小字颜色=state.配置["subtitle_font_color"],
            )
            self.悬浮牌.更新组件位置(state.读取组件位置配置())
            self._应用自定义行情设置()
            self.悬浮牌.应用账户面板设置()
            self._应用账户监控设置()

    def _应用自定义行情设置(self):
        开启 = bool(state.配置.get("custom_quote_enabled", True))
        self.悬浮牌.设置自定义行情显示(开启)
        self._自定义行情已开启 = 开启

        if 开启:
            if self.行情线程 is None:
                self._当前价格文本 = "…"
                self._行情错误文本 = ""
                self.悬浮牌.更新价格文本(self._当前价格文本)
                主控制._请求启动自定义行情(self, self.当前合约)
        else:
            self._待启动自定义行情合约 = None
            if self.行情线程 is not None:
                旧线程 = self.行情线程
                self.行情线程 = None
                主控制._退役行情线程实例(self, 旧线程)

        self._刷新托盘提示()

    def _应用账户监控设置(self):
        监控持仓 = bool(state.配置.get("monitor_position_quotes", False))
        监控委托 = bool(state.配置.get("monitor_order_quotes", False))
        self.悬浮牌.设置账户监控显示(持仓=监控持仓, 委托=监控委托)

        if self.账户监控线程 is not None:
            self.账户监控线程.设置持仓行情监控(监控持仓)
            self.账户监控线程.设置委托行情监控(监控委托)
            self._刷新托盘提示()
            return
        if not (监控持仓 or 监控委托):
            self._账户状态文本 = ""
            self._刷新托盘提示()
            return

        缺失项 = state.实盘账户凭据缺失项()
        if 缺失项:
            信息 = f"缺少环境变量：{', '.join(缺失项)}；请重启应用以读取新配置"
            self._账户状态文本 = "配置缺失"
            self.悬浮牌.更新账户状态({"state": "error", "message": 信息})
            self._刷新托盘提示()
            return

        凭据 = state.读取实盘账户凭据()
        try:
            线程 = 账户监控线程(
                经纪公司=凭据["broker_id"],
                资金账号=凭据["account_id"],
                交易密码=凭据["account_password"],
                天勤用户=凭据["auth_user"],
                天勤密码=凭据["auth_password"],
                监控持仓行情=监控持仓,
                监控委托行情=监控委托,
            )
        except Exception as 异常:
            信息 = str(异常)
            self._账户状态文本 = "配置错误"
            self.悬浮牌.更新账户状态({"state": "error", "message": 信息})
            self._刷新托盘提示()
            return

        self.账户监控线程 = 线程
        线程.快照信号.connect(self.处理账户快照)
        线程.状态信号.connect(self.处理账户状态)
        线程.错误信号.connect(self.处理账户错误)
        线程.start()

    def _启动行情线程(self, 代码: str):
        self.行情线程 = 行情线程(代码, state.TQ_USER, state.TQ_PASS)
        self.行情线程.价格信号.connect(self.处理价格更新)
        self.行情线程.错误信号.connect(self.处理错误)
        self.行情线程.start()

    def _请求启动自定义行情(self, 代码: str):
        """串行化手工行情连接，避免快速关开或切合约时多个 TqApi 短暂并存。"""

        if not getattr(self, "_自定义行情已开启", True) or getattr(self, "_正在退出", False):
            self._待启动自定义行情合约 = None
            return
        if self.行情线程 is not None:
            return

        仍在退役 = []
        for 线程 in list(self._退役行情线程):
            try:
                运行中 = 线程.isRunning()
            except AttributeError:
                运行中 = True
            if 运行中:
                仍在退役.append(线程)
            else:
                self._退役行情线程.remove(线程)
        if 仍在退役:
            # 多次快速切换只保留最后一个目标；旧连接全部 finished 后再启动。
            self._待启动自定义行情合约 = 代码
            return

        self._待启动自定义行情合约 = None
        self._启动行情线程(代码)

    def 切换合约订阅(self, 新合约: str):
        新合约 = 规范化合约代码(新合约)
        if not 新合约 or 新合约 == self.当前合约:
            return
        旧线程 = self.行情线程
        self.当前合约 = 新合约
        state.设置当前合约(新合约)
        写入最近合约(新合约)
        state.保存配置()
        if 旧线程 is not None:
            self.行情线程 = None
            主控制._退役行情线程实例(self, 旧线程)
        if getattr(self, "_自定义行情已开启", True):
            主控制._请求启动自定义行情(self, self.当前合约)
        self.悬浮牌.应用样式(小字=state.生效小字())
        self._当前价格文本 = "…"
        self._行情错误文本 = ""
        self._刷新托盘提示()

    def _退役行情线程实例(self, 线程):
        """停止订阅但保留 QThread 引用，直到 finished 后再释放。"""

        try:
            线程.价格信号.disconnect(self.处理价格更新)
            线程.错误信号.disconnect(self.处理错误)
        except (RuntimeError, TypeError):
            pass
        if 线程 not in self._退役行情线程:
            # 必须先接住 finished 再请求停止，避免线程恰好在状态检查前后结束而漏掉清理。
            self._退役行情线程.append(线程)
            线程.finished.connect(lambda 完成线程=线程: self._清理退役行情线程(完成线程))
        线程.停止()
        try:
            if not 线程.isRunning():
                # 兼容连接 finished 前就已经结束的线程；清理函数可重复调用。
                主控制._清理退役行情线程(self, 线程)
        except AttributeError:
            pass

    def _清理退役行情线程(self, 线程):
        if 线程 in self._退役行情线程:
            self._退役行情线程.remove(线程)
        待启动 = getattr(self, "_待启动自定义行情合约", None)
        if 待启动:
            主控制._请求启动自定义行情(self, 待启动)

    def 退出(self):
        if self._正在退出:
            return
        self._正在退出 = True
        self._待启动自定义行情合约 = None
        if self.行情线程 is not None:
            self.行情线程.停止()
        for 线程 in self._退役行情线程:
            线程.停止()
        if self.账户监控线程 is not None:
            self.账户监控线程.停止()
        设置加载线程 = self.悬浮牌.findChildren(在市期货合约加载线程)
        for 线程 in 设置加载线程:
            线程.requestInterruption()
        self._退出等待线程 = [
            线程
            for 线程 in (
                self.行情线程,
                self.账户监控线程,
                *self._退役行情线程,
                *设置加载线程,
            )
            if 线程 is not None
        ]
        self.悬浮牌.hide()
        self.托盘.setToolTip("正在安全关闭后台连接…")
        self._等待后台线程退出()

    def _等待后台线程退出(self):
        if any(线程.isRunning() for 线程 in self._退出等待线程):
            QtCore.QTimer.singleShot(100, self._等待后台线程退出)
            return
        self.托盘.hide()
        self.应用.quit()

    def 处理价格更新(self, 文本):
        if not getattr(self, "_自定义行情已开启", True):
            return
        self._当前价格文本 = 文本
        self._行情错误文本 = ""
        self.悬浮牌.更新价格文本(文本)
        self._刷新托盘提示()

    def 处理错误(self, 信息):
        if not getattr(self, "_自定义行情已开启", True):
            return
        self._行情错误文本 = 信息
        self._刷新托盘提示()

    def 处理账户快照(self, 快照: dict):
        监控持仓 = bool(state.配置.get("monitor_position_quotes", False))
        监控委托 = bool(state.配置.get("monitor_order_quotes", False))
        持仓 = list(快照.get("positions") or []) if 监控持仓 else []
        委托 = list(快照.get("orders") or []) if 监控委托 else []
        行情 = [
            项 for 项 in list(快照.get("quotes") or [])
            if (监控持仓 and 项.get("from_position"))
            or (监控委托 and 项.get("from_order"))
        ]
        self._持仓数量 = len(持仓)
        self._委托数量 = len(委托)
        self.悬浮牌.更新账户快照(
            {"positions": 持仓, "orders": 委托, "quotes": 行情}
        )
        self._刷新托盘提示()

    def 处理账户状态(self, 状态: dict):
        状态映射 = {
            "connecting": "连接中",
            "connected": "在线",
            "error": "连接错误",
            "stopped": "已停止",
        }
        原始状态 = str(状态.get("state", ""))
        if 原始状态 == "stopped" and self._账户状态文本 == "连接错误":
            return
        self._账户状态文本 = 状态映射.get(原始状态, 原始状态)
        self.悬浮牌.更新账户状态(状态)
        self._刷新托盘提示()

    def 处理账户错误(self, 错误: dict):
        if 错误.get("fatal"):
            self._账户状态文本 = "连接错误"
            self.悬浮牌.更新账户状态({"state": "error", "message": str(错误.get("message", ""))})
            self._刷新托盘提示()

    def _刷新托盘提示(self):
        if not hasattr(self, "托盘"):
            return
        行 = []
        if getattr(self, "_自定义行情已开启", True):
            if self._行情错误文本:
                行.append(f"{self.当前合约} 出错: {self._行情错误文本}")
            else:
                行.append(f"{self.当前合约} {state.标题前缀}: {self._当前价格文本}")
        账户监控已开启 = bool(state.配置.get("monitor_position_quotes", False)) or bool(
            state.配置.get("monitor_order_quotes", False)
        )
        if self._账户状态文本 and 账户监控已开启:
            行.append(f"实盘{self._账户状态文本}｜持仓 {self._持仓数量}｜未成 {self._委托数量}")
        if not 行:
            行.append("监控悬浮牌")
        self.托盘.setToolTip("\n".join(行))


def main():
    state.读取配置()
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    单实例锁 = _获取单实例锁()
    if 单实例锁 is None:
        return
    # 锁必须和应用保持相同生命周期；重复启动会在创建任何网络线程前直接退出。
    app._tq_price_badge_single_instance_lock = 单实例锁
    控制 = 主控制(app)
    sys.exit(app.exec())
