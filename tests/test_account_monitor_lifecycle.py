# -*- coding: utf-8 -*-
"""账户监控线程生命周期测试：切换设置不得重复创建实盘连接。"""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest import mock


# 导入应用编排模块只需要认证变量存在；测试不会使用这些占位值连接网络。
os.environ.setdefault("TQ_USER", "offline-test-user")
os.environ.setdefault("TQ_PASS", "offline-test-password")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from badge_app import app as app_module  # noqa: E402
from badge_app.backend import account as account_module  # noqa: E402


class _假信号:
    def __init__(self):
        self.槽 = []

    def connect(self, 槽):
        self.槽.append(槽)

    def disconnect(self, 槽):
        self.槽.remove(槽)


class _假账户线程:
    创建次数 = 0

    def __init__(self, **参数):
        type(self).创建次数 += 1
        self.参数 = 参数
        self.快照信号 = _假信号()
        self.状态信号 = _假信号()
        self.错误信号 = _假信号()
        self.持仓开关历史 = []
        self.委托开关历史 = []
        self.已启动 = False

    def 设置持仓行情监控(self, 开启):
        self.持仓开关历史.append(bool(开启))

    def 设置委托行情监控(self, 开启):
        self.委托开关历史.append(bool(开启))

    def start(self):
        self.已启动 = True


class _假悬浮牌:
    def __init__(self):
        self.设置请求 = _假信号()
        self.显示历史 = []
        self.状态历史 = []
        self.快照历史 = []
        self.自定义行情显示历史 = []
        self.价格历史 = []
        self.已显示 = False

    def 设置账户监控显示(self, **开关):
        self.显示历史.append(开关)

    def 更新账户状态(self, 状态):
        self.状态历史.append(状态)

    def 更新账户快照(self, 快照):
        self.快照历史.append(快照)

    def 设置自定义行情显示(self, 显示):
        self.自定义行情显示历史.append(bool(显示))

    def 更新价格文本(self, 文本):
        self.价格历史.append(文本)

    def 应用样式(self, **_样式):
        pass

    def 应用账户面板设置(self):
        pass

    def show(self):
        self.已显示 = True


class _假控制器:
    def __init__(self):
        self.悬浮牌 = _假悬浮牌()
        self.账户监控线程 = None
        self.行情线程 = None
        self._退役行情线程 = []
        self.当前合约 = "KQ.m@SHFE.cu"
        self._当前价格文本 = "…"
        self._行情错误文本 = ""
        self._账户状态文本 = ""
        self._自定义行情已开启 = True

    def _刷新托盘提示(self):
        pass

    def 处理账户快照(self, 快照):
        pass

    def 处理账户状态(self, 状态):
        pass

    def 处理账户错误(self, 错误):
        pass

    def 处理价格更新(self, 文本):
        pass

    def 处理错误(self, 信息):
        pass

    def _启动行情线程(self, 代码):
        self.行情线程 = ("new", 代码)

    def _清理退役行情线程(self, 线程):
        app_module.主控制._清理退役行情线程(self, 线程)

    def _等待后台线程退出(self):
        app_module.主控制._等待后台线程退出(self)


class _假运行线程:
    def __init__(self, 运行中=True):
        self.运行中 = 运行中

    def isRunning(self):
        return self.运行中


class _假行情线程:
    def __init__(self, 运行中=True):
        self.价格信号 = _假信号()
        self.错误信号 = _假信号()
        self.finished = _假信号()
        self.已停止 = False
        self.运行中 = 运行中

    def 停止(self):
        self.已停止 = True

    def isRunning(self):
        return self.运行中


class _状态检查时结束的行情线程(_假行情线程):
    def isRunning(self):
        # 模拟 isRunning 取得 True 后、调用方继续执行前，线程发出 finished。
        检查结果 = self.运行中
        self.运行中 = False
        for 槽 in list(self.finished.槽):
            槽()
        return 检查结果


class _假托盘:
    def __init__(self):
        self.隐藏次数 = 0

    def hide(self):
        self.隐藏次数 += 1


class _假应用:
    def __init__(self):
        self.退出次数 = 0

    def quit(self):
        self.退出次数 += 1


class 账户监控生命周期测试(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.应用 = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_启动时0条自定义行情在网络线程构造前生效(self):
        悬浮牌 = _假悬浮牌()
        构造行情线程 = mock.Mock(side_effect=AssertionError("0条时禁止构造自定义行情连接"))
        with (
            mock.patch.dict(app_module.state.配置, {"custom_quote_enabled": False}),
            mock.patch.object(app_module, "悬浮牌窗口", return_value=悬浮牌),
            mock.patch.object(app_module, "行情线程", 构造行情线程),
            mock.patch.object(app_module.state, "设置当前合约"),
            mock.patch.object(app_module.state, "保存配置"),
            mock.patch.object(app_module, "写入最近合约"),
            mock.patch.object(app_module.主控制, "_创建托盘"),
            mock.patch.object(app_module.主控制, "_应用账户监控设置"),
        ):
            控制器 = app_module.主控制(self.应用)

        构造行情线程.assert_not_called()
        self.assertIsNone(控制器.行情线程)
        self.assertEqual([False], 悬浮牌.自定义行情显示历史)

    def test_0条自定义行情不创建订阅而关开切换仅各执行一次(self):
        控制器 = _假控制器()
        控制器._自定义行情已开启 = False
        with mock.patch.dict(app_module.state.配置, {"custom_quote_enabled": False}):
            app_module.主控制._应用自定义行情设置(控制器)
        self.assertIsNone(控制器.行情线程)
        self.assertEqual([False], 控制器.悬浮牌.自定义行情显示历史)

        with mock.patch.dict(app_module.state.配置, {"custom_quote_enabled": True}):
            app_module.主控制._应用自定义行情设置(控制器)
            第一线程 = 控制器.行情线程
            app_module.主控制._应用自定义行情设置(控制器)
        self.assertEqual(("new", 控制器.当前合约), 第一线程)
        self.assertIs(第一线程, 控制器.行情线程)
        self.assertEqual([False, True, True], 控制器.悬浮牌.自定义行情显示历史)

    def test_关闭自定义行情会安全退役当前线程(self):
        控制器 = _假控制器()
        旧线程 = _假行情线程()
        旧线程.价格信号.connect(控制器.处理价格更新)
        旧线程.错误信号.connect(控制器.处理错误)
        控制器.行情线程 = 旧线程

        with mock.patch.dict(app_module.state.配置, {"custom_quote_enabled": False}):
            app_module.主控制._应用自定义行情设置(控制器)

        self.assertIsNone(控制器.行情线程)
        self.assertTrue(旧线程.已停止)
        self.assertIn(旧线程, 控制器._退役行情线程)
        for 槽 in list(旧线程.finished.槽):
            槽()
        self.assertNotIn(旧线程, 控制器._退役行情线程)

    def test_退役前已结束的行情线程不残留引用(self):
        控制器 = _假控制器()
        已结束线程 = _假行情线程(运行中=False)
        已结束线程.价格信号.connect(控制器.处理价格更新)
        已结束线程.错误信号.connect(控制器.处理错误)

        app_module.主控制._退役行情线程实例(控制器, 已结束线程)

        self.assertTrue(已结束线程.已停止)
        self.assertNotIn(已结束线程, 控制器._退役行情线程)

    def test_退役线程在状态检查期间结束也不会漏掉清理(self):
        控制器 = _假控制器()
        竞态线程 = _状态检查时结束的行情线程()
        竞态线程.价格信号.connect(控制器.处理价格更新)
        竞态线程.错误信号.connect(控制器.处理错误)

        app_module.主控制._退役行情线程实例(控制器, 竞态线程)

        self.assertTrue(竞态线程.已停止)
        self.assertNotIn(竞态线程, 控制器._退役行情线程)

    def test_0条时切换合约只保存不启动订阅(self):
        控制器 = _假控制器()
        控制器._自定义行情已开启 = False
        with (
            mock.patch.object(app_module.state, "保存配置"),
            mock.patch.object(app_module.state, "设置当前合约"),
            mock.patch.object(app_module, "写入最近合约"),
        ):
            app_module.主控制.切换合约订阅(控制器, "DCE.m2609")
        self.assertEqual("DCE.m2609", 控制器.当前合约)
        self.assertIsNone(控制器.行情线程)

    def test_主控制器每个账户快照只提交一次界面更新(self):
        控制器 = _假控制器()
        控制器._持仓数量 = 0
        控制器._委托数量 = 0
        快照 = {
            "positions": [{"symbol": "CZCE.PX609"}],
            "orders": [{"symbol": "DCE.m2609"}],
            "quotes": [
                {"symbol": "CZCE.PX609", "from_position": True, "from_order": False},
                {"symbol": "DCE.m2609", "from_position": False, "from_order": True},
                {"symbol": "SHFE.rb2610", "from_position": True, "from_order": True},
            ],
        }

        with mock.patch.dict(
            app_module.state.配置,
            {"monitor_position_quotes": True, "monitor_order_quotes": False},
        ):
            app_module.主控制.处理账户快照(控制器, 快照)

        self.assertEqual(1, len(控制器.悬浮牌.快照历史))
        提交 = 控制器.悬浮牌.快照历史[0]
        self.assertEqual(快照["positions"], 提交["positions"])
        self.assertEqual([], 提交["orders"])
        self.assertEqual(["CZCE.PX609", "SHFE.rb2610"], [项["symbol"] for 项 in 提交["quotes"]])
        self.assertEqual(1, 控制器._持仓数量)
        self.assertEqual(0, 控制器._委托数量)

    def test_单实例锁阻止同一启动脚本重复运行(self):
        with tempfile.TemporaryDirectory(prefix="tq-price-badge-test-") as 临时目录:
            锁路径 = os.path.join(临时目录, "instance.lock")
            第一把锁 = app_module._获取单实例锁(锁路径)
            self.assertIsNotNone(第一把锁)
            try:
                self.assertIsNone(app_module._获取单实例锁(锁路径))
            finally:
                第一把锁.unlock()

            重新获取 = app_module._获取单实例锁(锁路径)
            self.assertIsNotNone(重新获取)
            重新获取.unlock()

    def test_切换手工合约会等旧线程finished后再启动(self):
        控制器 = _假控制器()
        旧线程 = _假行情线程()
        旧线程.价格信号.connect(控制器.处理价格更新)
        旧线程.错误信号.connect(控制器.处理错误)
        控制器.行情线程 = 旧线程

        with (
            mock.patch.object(app_module.state, "保存配置"),
            mock.patch.object(app_module.state, "设置当前合约"),
            mock.patch.object(app_module, "写入最近合约"),
        ):
            app_module.主控制.切换合约订阅(控制器, "DCE.m2609")

        self.assertTrue(旧线程.已停止)
        self.assertIn(旧线程, 控制器._退役行情线程)
        self.assertIsNone(控制器.行情线程)
        self.assertEqual("DCE.m2609", 控制器._待启动自定义行情合约)
        self.assertFalse(旧线程.价格信号.槽)
        self.assertFalse(旧线程.错误信号.槽)

        for 槽 in list(旧线程.finished.槽):
            槽()
        self.assertNotIn(旧线程, 控制器._退役行情线程)
        self.assertEqual(("new", "DCE.m2609"), 控制器.行情线程)

    def test_连续切合约只在旧连接退出后启动最后一个(self):
        控制器 = _假控制器()
        旧线程 = _假行情线程()
        旧线程.价格信号.connect(控制器.处理价格更新)
        旧线程.错误信号.connect(控制器.处理错误)
        控制器.行情线程 = 旧线程

        with (
            mock.patch.object(app_module.state, "保存配置"),
            mock.patch.object(app_module.state, "设置当前合约"),
            mock.patch.object(app_module, "写入最近合约"),
        ):
            app_module.主控制.切换合约订阅(控制器, "DCE.m2609")
            app_module.主控制.切换合约订阅(控制器, "SHFE.rb2610")

        self.assertIsNone(控制器.行情线程)
        self.assertEqual("SHFE.rb2610", 控制器._待启动自定义行情合约)
        for 槽 in list(旧线程.finished.槽):
            槽()
        self.assertEqual(("new", "SHFE.rb2610"), 控制器.行情线程)

    def test_退出会等后台线程真正结束再关闭应用(self):
        运行线程 = _假运行线程(True)
        控制器 = _假控制器()
        控制器._退出等待线程 = [运行线程]
        控制器.托盘 = _假托盘()
        控制器.应用 = _假应用()
        延迟回调 = []

        with mock.patch.object(
            app_module.QtCore.QTimer,
            "singleShot",
            side_effect=lambda _毫秒, 回调: 延迟回调.append(回调),
        ):
            app_module.主控制._等待后台线程退出(控制器)
            self.assertEqual(0, 控制器.应用.退出次数)
            self.assertEqual(1, len(延迟回调))

            运行线程.运行中 = False
            延迟回调.pop()()

        self.assertEqual(1, 控制器.托盘.隐藏次数)
        self.assertEqual(1, 控制器.应用.退出次数)

    def test_两个开关关闭时不创建实盘账户线程(self):
        控制器 = _假控制器()
        构造 = mock.Mock(side_effect=AssertionError("关闭监控时禁止创建实盘连接"))
        with (
            mock.patch.object(app_module, "账户监控线程", 构造),
            mock.patch.dict(
                app_module.state.配置,
                {"monitor_position_quotes": False, "monitor_order_quotes": False},
            ),
        ):
            app_module.主控制._应用账户监控设置(控制器)

        构造.assert_not_called()
        self.assertIsNone(控制器.账户监控线程)

    def test_关闭再开启设置仍只创建一个账户线程(self):
        _假账户线程.创建次数 = 0
        控制器 = _假控制器()
        凭据 = {
            "broker_id": "G国信期货",
            "account_id": "offline-account",
            "account_password": "offline-password",
            "auth_user": "offline-auth",
            "auth_password": "offline-auth-password",
        }

        with (
            mock.patch.object(app_module, "账户监控线程", _假账户线程),
            mock.patch.object(app_module.state, "实盘账户凭据缺失项", return_value=[]),
            mock.patch.object(app_module.state, "读取实盘账户凭据", return_value=凭据),
            mock.patch.dict(
                app_module.state.配置,
                {"monitor_position_quotes": True, "monitor_order_quotes": False},
            ),
        ):
            app_module.主控制._应用账户监控设置(控制器)
            第一线程 = 控制器.账户监控线程
            self.assertTrue(第一线程.已启动)
            self.assertEqual(1, _假账户线程.创建次数)

            app_module.state.配置["monitor_position_quotes"] = False
            app_module.state.配置["monitor_order_quotes"] = False
            app_module.主控制._应用账户监控设置(控制器)

            app_module.state.配置["monitor_order_quotes"] = True
            app_module.主控制._应用账户监控设置(控制器)

        self.assertIs(第一线程, 控制器.账户监控线程)
        self.assertEqual(1, _假账户线程.创建次数)
        self.assertEqual([False, False], 第一线程.持仓开关历史)
        self.assertEqual([False, True], 第一线程.委托开关历史)

    def test_午休连续无更新不会重建API或重新登录(self):
        线程 = account_module.账户监控线程(
            "G国信期货",
            "offline-account",
            "offline-password",
            "offline-auth",
            "offline-auth-password",
        )
        假API = mock.Mock()
        假API.get_account.return_value = {}
        假API.get_position.return_value = {}
        假API.get_order.return_value = {}
        等待次数 = 0

        def 午休无更新(**_参数):
            nonlocal 等待次数
            等待次数 += 1
            if 等待次数 >= 3:
                线程._停止事件.set()
            return False

        假API.wait_update.side_effect = 午休无更新
        API构造 = mock.Mock(return_value=假API)

        with (
            mock.patch.object(account_module, "TqAccount", return_value=object()) as 账户构造,
            mock.patch.object(account_module, "TqAuth", return_value=object()) as 认证构造,
            mock.patch.object(account_module, "TqApi", API构造),
        ):
            # 直接调用 run，不启动 QThread；整个测试仅使用上面的离线替身。
            线程.run()

        self.assertEqual(3, 等待次数)
        self.assertEqual(1, 账户构造.call_count)
        self.assertEqual(1, 认证构造.call_count)
        self.assertEqual(1, API构造.call_count)
        假API.close.assert_called_once_with()

    def test_持仓行情订阅一次失败后会退避重试并恢复最新价(self):
        线程 = account_module.账户监控线程(
            "G国信期货",
            "offline-account",
            "offline-password",
            "offline-auth",
            "offline-auth-password",
            监控持仓行情=True,
        )
        假API = mock.Mock()
        假API.get_account.return_value = {}
        假API.get_position.return_value = {
            "SHFE.rb2610": {
                "exchange_id": "SHFE", "instrument_id": "rb2610",
                "pos_long": 1, "open_price_long": 3500, "float_profit_long": 10,
            }
        }
        假API.get_order.return_value = {}
        假API.get_quote_list.side_effect = [
            RuntimeError("临时行情订阅失败"),
            [{"last_price": 3510, "price_decs": 1}],
        ]
        更新次数 = 0

        def 两次处理后停止(**_参数):
            nonlocal 更新次数
            更新次数 += 1
            if 更新次数 >= 3:
                线程._停止事件.set()
            return True

        假API.wait_update.side_effect = 两次处理后停止
        快照历史 = []
        错误历史 = []
        线程.快照信号.connect(快照历史.append)
        线程.错误信号.connect(错误历史.append)
        时钟 = iter(float(值) for 值 in range(20))

        with (
            mock.patch.object(account_module, "TqAccount", return_value=object()),
            mock.patch.object(account_module, "TqAuth", return_value=object()),
            mock.patch.object(account_module, "TqApi", return_value=假API),
            mock.patch.object(account_module.time, "monotonic", side_effect=lambda: next(时钟)),
        ):
            线程.run()

        self.assertEqual(2, 假API.get_quote_list.call_count)
        self.assertEqual("quote_subscription_error", 错误历史[0]["type"])
        self.assertEqual(1.0, 错误历史[0]["retry_after_seconds"])
        self.assertTrue(
            any(快照["quotes"][0]["last_price"] == 3510 for 快照 in 快照历史),
            "退避重试成功后应将最新价写入快照",
        )
        假API.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
