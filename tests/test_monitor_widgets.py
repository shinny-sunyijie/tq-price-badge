# -*- coding: utf-8 -*-
"""账户监控悬浮组件的纯离屏测试。

测试只向控件传入普通字典快照；不显示窗口、不启动事件循环、不构造账户或
行情线程，也不执行网络与鼠标操作。
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("TQ_USER", "offline-widget-test")
os.environ.setdefault("TQ_PASS", "offline-widget-test")

from PySide6 import QtWidgets

from badge_app.backend import state
from badge_app.frontend.widgets import 悬浮牌窗口


def _标签文本(部件: QtWidgets.QWidget) -> list[str]:
    return [标签.text() for 标签 in 部件.findChildren(QtWidgets.QLabel)]


def _合并文本(部件: QtWidgets.QWidget) -> str:
    return "|".join(_标签文本(部件))


class 账户监控悬浮组件测试(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.应用 = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self._原配置 = state.配置
        state.配置 = state.默认配置.copy()
        self.addCleanup(setattr, state, "配置", self._原配置)
        保存补丁 = mock.patch.object(state, "保存配置")
        保存补丁.start()
        self.addCleanup(保存补丁.stop)

        self.窗口 = 悬浮牌窗口()
        self.addCleanup(self.窗口.deleteLater)

    def test_自定义行情可在0与1条之间切换(self):
        self.窗口.更新价格文本("12345.6")
        self.assertFalse(self.窗口.价格标签.isHidden())
        self.assertFalse(self.窗口.小字标签.isHidden())
        显示高度 = self.窗口.height()

        self.窗口.设置自定义行情显示(False)
        self.assertTrue(self.窗口.价格标签.isHidden())
        self.assertTrue(self.窗口.小字标签.isHidden())
        self.assertFalse(self.窗口.锁按钮.isHidden())
        self.assertFalse(self.窗口.编辑按钮.isHidden())
        self.assertLess(self.窗口.height(), 显示高度)

        self.窗口.更新价格文本("54321.0")
        self.assertTrue(self.窗口.价格标签.isHidden())
        self.窗口.设置自定义行情显示(True)
        self.assertFalse(self.窗口.价格标签.isHidden())
        self.assertEqual("54321.0", self.窗口.价格标签.text())

    def test_两个账户开关独立控制显示(self):
        面板 = self.窗口.账户监控面板
        self.assertTrue(面板.isHidden())

        self.窗口.设置账户监控显示(持仓=True, 委托=False)
        self.assertFalse(面板.isHidden())
        self.assertFalse(面板.持仓区.isHidden())
        self.assertTrue(面板.委托区.isHidden())

        self.窗口.设置账户监控显示(持仓=False, 委托=True)
        self.assertTrue(面板.持仓区.isHidden())
        self.assertFalse(面板.委托区.isHidden())

        self.窗口.设置账户监控显示(持仓=False, 委托=False)
        self.assertTrue(面板.isHidden())

    def test_行情合并到每条委托和持仓且无独立表(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=True)
        self.窗口.更新账户快照(
            {
                "positions": [
                    {"symbol": "SHFE.rb2610", "long": {"volume": 2, "open_price": 3500, "float_profit": 20}}
                ],
                "orders": [
                    {
                        "symbol": "SHFE.rb2610", "direction": "BUY", "offset": "OPEN",
                        "volume_left": 2, "volume_orign": 5, "limit_price": 3475,
                    }
                ],
                "quotes": [{"symbol": "shfe.RB2610", "last_price": 3482, "price_decs": 1}],
            }
        )
        面板 = self.窗口.账户监控面板
        self.assertTrue(面板.自动行情区.isHidden())
        self.assertNotIn("自动行情", _合并文本(面板))

        持仓文本 = _合并文本(面板.持仓区)
        委托文本 = _合并文本(面板.委托区)
        self.assertIn("现3482.0", 持仓文本)
        self.assertIn("现3482.0", 委托文本)
        self.assertIn("rb2610 多2", 持仓文本)
        self.assertIn("rb2610 买开", 委托文本)
        self.assertNotIn("SHFE.", 持仓文本 + 委托文本)
        self.assertIn("余2/5", 委托文本)
        self.assertIn("委3475", 委托文本)

        # 模块标题与列表头均已删除。
        for 不应显示 in ("持仓 ·", "未成委托 ·", "合约", "方向", "手数", "最新价"):
            self.assertNotIn(不应显示, 持仓文本 + 委托文本)

    def test_锁仓展开多空两行且仅用quotes最新价(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=False)
        self.窗口.更新账户快照(
            {
                "positions": [
                    {
                        "symbol": "SHFE.rb2610",
                        "last_price": 999001,
                        "position_profit": 999002,
                        "long": {
                            "volume": 2, "open_price": 3500, "float_profit": 135.5,
                            "last_price": 999003, "position_profit": 999004,
                        },
                        "short": {
                            "volume": 1, "open_price": 3520, "float_profit": -45.25,
                            "last_price": 999005, "position_profit": 999006,
                        },
                    }
                ],
                "orders": [],
                "quotes": [{"symbol": "SHFE.rb2610", "last_price": 3510, "price_decs": 1}],
            }
        )
        文本 = _合并文本(self.窗口.账户监控面板.持仓区)
        self.assertIn("多2", 文本)
        self.assertIn("空1", 文本)
        self.assertEqual(2, 文本.count("现3510.0"))
        self.assertIn("开3500", 文本)
        self.assertIn("开3520", 文本)
        self.assertIn("浮+135.50", 文本)
        self.assertIn("浮-45.25", 文本)
        for 诱饵值 in ("999001", "999002", "999003", "999004", "999005", "999006"):
            self.assertNotIn(诱饵值, 文本)

    def test_还没收到首笔行情时每行保留现价占位(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=True)
        self.窗口.更新账户快照(
            {
                "positions": [{"symbol": "CZCE.PX609", "long": {"volume": 1}}],
                "orders": [{"symbol": "CZCE.PX609", "volume_left": 1, "volume_orign": 1}],
                "quotes": [{"symbol": "CZCE.PX609", "last_price": None, "price_decs": 0}],
            }
        )
        self.assertIn("现—", _合并文本(self.窗口.账户监控面板.持仓区))
        self.assertIn("现—", _合并文本(self.窗口.账户监控面板.委托区))

    def test_账户状态只显示简短状态与脱敏账号(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=False)
        self.窗口.更新账户状态(
            {
                "state": "connected", "message": "实盘账户只读监控已连接",
                "broker_id": "G国信期货", "account_id": "66***01",
            }
        )
        标签 = self.窗口.账户监控面板.账户状态标签
        self.assertEqual("已连接 66***01", 标签.text())
        self.assertNotIn("实盘", 标签.text())
        self.assertIn("实盘账户只读监控已连接", 标签.toolTip())

    def test_完整快照原子刷新且默认顺序无遮挡(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=True)
        快照 = {
            "positions": [
                {"symbol": "CZCE.PX609", "long": {"volume": 2, "open_price": 8120, "float_profit": 66}}
            ],
            "orders": [
                {
                    "symbol": "CZCE.PX609", "direction": "BUY", "offset": "OPEN",
                    "volume_left": 1, "volume_orign": 1, "limit_price": 8150,
                }
            ],
            "quotes": [{"symbol": "CZCE.PX609", "last_price": 8160, "price_decs": 0}],
        }
        面板 = self.窗口.账户监控面板
        尺寸信号 = []
        面板.内容尺寸变更.connect(lambda: 尺寸信号.append(True))

        self.窗口.更新账户快照(快照)
        self.assertEqual(1, len(尺寸信号))
        标签身份 = [id(标签) for 标签 in 面板.findChildren(QtWidgets.QLabel)]
        面板尺寸 = 面板.size()
        for _ in range(20):
            self.窗口.更新账户快照(快照)
        self.assertEqual(1, len(尺寸信号))
        self.assertEqual(标签身份, [id(标签) for 标签 in 面板.findChildren(QtWidgets.QLabel)])
        self.assertEqual(面板尺寸, 面板.size())

        模块 = [面板.账户状态标签, 面板.委托区, 面板.持仓区]
        self.assertLess(模块[0].y(), 模块[1].y())
        self.assertLess(模块[1].y(), 模块[2].y())
        self.assertGreaterEqual(模块[2].y() - (模块[1].y() + 模块[1].height()), 6)
        for 序号, 部件 in enumerate(模块):
            self.assertTrue(面板.rect().contains(部件.geometry()))
            for 其他部件 in 模块[序号 + 1:]:
                self.assertFalse(部件.geometry().intersects(其他部件.geometry()))
        self.assertTrue(self.窗口.rect().contains(面板.geometry()))
        for 手工组件 in (self.窗口.小字标签, self.窗口.价格标签):
            self.assertLessEqual(手工组件.geometry().bottom(), 面板.geometry().top())

        for 序号 in range(20):
            变化快照 = {
                "positions": 快照["positions"],
                "orders": 快照["orders"],
                "quotes": [{**快照["quotes"][0], "last_price": 8161 + 序号}],
            }
            self.窗口.更新账户快照(变化快照)
            self.assertEqual(标签身份, [id(标签) for 标签 in 面板.findChildren(QtWidgets.QLabel)])
            for 部件 in 模块:
                self.assertTrue(面板.rect().contains(部件.geometry()))
        self.assertIn("现8180", _合并文本(面板.委托区))
        self.assertIn("现8180", _合并文本(面板.持仓区))

    def test_账户面板与三模块字号位置可应用(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=True)
        self.窗口.更新账户快照(
            {
                "positions": [{"symbol": "CZCE.PX609", "long": {"volume": 1}}],
                "orders": [{"symbol": "CZCE.PX609", "volume_left": 1, "volume_orign": 1}],
                "quotes": [{"symbol": "CZCE.PX609", "last_price": 8160}],
            }
        )
        配置 = dict(state.默认配置)
        配置.update(
            {
                "account_panel_pos": {"x": 18, "y": 145},
                "account_status_font_size": 11,
                "account_position_font_size": 13,
                "account_order_font_size": 14,
                "account_status_pos": {"x": 3, "y": 4},
                "account_order_pos": {"x": 7, "y": 80},
                "account_position_pos": {"x": 9, "y": 190},
            }
        )
        self.窗口.应用账户面板设置(配置)

        面板 = self.窗口.账户监控面板
        self.assertEqual((18, 145), (面板.x(), 面板.y()))
        self.assertEqual((3, 4), (面板.账户状态标签.x(), 面板.账户状态标签.y()))
        self.assertEqual((7, 80), (面板.委托区.x(), 面板.委托区.y()))
        self.assertEqual((9, 190), (面板.持仓区.x(), 面板.持仓区.y()))
        self.assertEqual(11, 面板.账户状态标签.font().pointSize())
        self.assertEqual(14, 面板.委托区._字号)
        self.assertEqual(13, 面板.持仓区._字号)
        self.assertTrue(self.窗口.rect().contains(面板.geometry()))

    def test_自动模块会避让手工定位的委托模块(self):
        self.窗口.设置账户监控显示(持仓=True, 委托=True)
        self.窗口.更新账户快照(
            {
                "positions": [{"symbol": "CZCE.PX609", "long": {"volume": 2}}],
                "orders": [{"symbol": "CZCE.PX609", "volume_left": 1, "volume_orign": 1}],
                "quotes": [{"symbol": "CZCE.PX609", "last_price": 8160}],
            }
        )
        配置 = dict(state.默认配置)
        配置["account_order_pos"] = {"x": 0, "y": 35}
        self.窗口.应用账户面板设置(配置)

        面板 = self.窗口.账户监控面板
        模块 = [面板.账户状态标签, 面板.委托区, 面板.持仓区]
        self.assertEqual((0, 35), (面板.委托区.x(), 面板.委托区.y()))
        for 序号, 部件 in enumerate(模块):
            self.assertTrue(面板.rect().contains(部件.geometry()))
            for 其他部件 in 模块[序号 + 1:]:
                self.assertFalse(部件.geometry().intersects(其他部件.geometry()))


if __name__ == "__main__":
    unittest.main()
