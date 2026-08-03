# -*- coding: utf-8 -*-
"""账户快照纯函数的离线测试。

这里只使用普通字典模拟会原地更新的 TqSdk Entity；不构造账户线程、TqApi、
Qt 应用或窗口，也不执行任何网络操作。
"""

from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from badge_app.backend import account as account_module


def _持仓(
    合约: str,
    *,
    多头: int = 0,
    空头: int = 0,
    多头浮盈=0.0,
    空头浮盈=0.0,
    浮盈=0.0,
) -> dict:
    交易所, 品种 = 合约.split(".", 1)
    return {
        "exchange_id": 交易所,
        "instrument_id": 品种,
        "pos_long": 多头,
        "pos_short": 空头,
        "pos_long_today": 多头,
        "pos_long_his": 0,
        "pos_short_today": 空头,
        "pos_short_his": 0,
        "open_price_long": 3500.0,
        "open_price_short": 3520.0,
        "position_price_long": 3501.0,
        "position_price_short": 3519.0,
        "float_profit_long": 多头浮盈,
        "float_profit_short": 空头浮盈,
        "float_profit": 浮盈,
    }


def _委托(
    委托号: str,
    合约: str,
    *,
    状态: str = "ALIVE",
    原始手数=5,
    剩余手数=5,
    委托价=3510.0,
) -> dict:
    交易所, 品种 = 合约.split(".", 1)
    return {
        "order_id": 委托号,
        "exchange_order_id": f"EX-{委托号}",
        "exchange_id": 交易所,
        "instrument_id": 品种,
        "direction": "BUY",
        "offset": "OPEN",
        "volume_orign": 原始手数,
        "volume_left": 剩余手数,
        "limit_price": 委托价,
        "price_type": "LIMIT",
        "volume_condition": "ANY",
        "time_condition": "GFD",
        "insert_date_time": 1_700_000_000_000_000_000,
        "last_msg": "报单成功",
        "status": 状态,
        "is_dead": False,
        "is_online": True,
        "is_error": False,
        "trade_price": float("nan"),
    }


class 账户快照纯函数测试(unittest.TestCase):
    def setUp(self):
        # 即使未来纯函数被误改，这三道护栏也会阻止测试触发任何登录构造。
        self._登录护栏 = [
            mock.patch.object(account_module, "TqApi", side_effect=AssertionError("测试禁止构造 TqApi")),
            mock.patch.object(account_module, "TqAccount", side_effect=AssertionError("测试禁止构造 TqAccount")),
            mock.patch.object(account_module, "TqAuth", side_effect=AssertionError("测试禁止构造 TqAuth")),
        ]
        for 补丁 in self._登录护栏:
            补丁.start()
            self.addCleanup(补丁.stop)

    def test_双零历史持仓被过滤(self):
        全部持仓 = {
            "SHFE.cu2508": _持仓("SHFE.cu2508", 多头=0, 空头=0, 浮盈=9999.0),
            "SHFE.rb2610": _持仓("SHFE.rb2610", 多头=2, 浮盈=120.0),
        }

        快照 = account_module.转换持仓快照(全部持仓)

        self.assertEqual([项["symbol"] for 项 in 快照], ["SHFE.rb2610"])

    def test_锁仓保留多空两侧且使用浮动盈亏(self):
        持仓 = _持仓(
            "SHFE.rb2610",
            多头=2,
            空头=1,
            多头浮盈=135.5,
            空头浮盈=-45.25,
            浮盈=90.25,
        )
        # 特意放入完全不同的持仓盈亏，防止实现误用 position_profit。
        持仓.update(
            {
                "position_profit_long": 9991.0,
                "position_profit_short": 9992.0,
                "position_profit": 19983.0,
            }
        )

        项 = account_module.转换持仓快照({"SHFE.rb2610": 持仓})[0]

        self.assertEqual(项["pos_long"], 2)
        self.assertEqual(项["pos_short"], 1)
        self.assertEqual(项["long"]["volume"], 2)
        self.assertEqual(项["short"]["volume"], 1)
        self.assertEqual(项["long"]["float_profit"], 135.5)
        self.assertEqual(项["short"]["float_profit"], -45.25)
        self.assertEqual(项["float_profit"], 90.25)
        self.assertNotIn("position_profit", 项)
        self.assertNotIn("last_price", 项)
        self.assertNotIn("last_price", 项["long"])
        self.assertNotIn("last_price", 项["short"])

    def test_NaN和无穷值不会泄漏到快照(self):
        持仓 = _持仓(
            "SHFE.rb2610",
            多头=1,
            多头浮盈=float("inf"),
            空头浮盈=float("-inf"),
            浮盈=float("nan"),
        )
        持仓["open_price_long"] = float("nan")
        委托 = _委托("alive-non-finite", "SHFE.rb2610", 委托价=float("nan"))
        委托["trade_price"] = float("inf")
        行情 = {
            "SHFE.rb2610": {
                "last_price": float("-inf"),
                "price_decs": float("nan"),
                "datetime": "",
            }
        }

        快照 = account_module.构建只读快照(
            {"currency": "CNY", "balance": float("nan"), "available": float("inf")},
            {"SHFE.rb2610": 持仓},
            {"alive-non-finite": 委托},
            行情,
            监控持仓行情=True,
            监控委托行情=True,
        )

        self.assertIsNone(快照["account"]["balance"])
        self.assertIsNone(快照["account"]["available"])
        self.assertIsNone(快照["positions"][0]["long"]["open_price"])
        self.assertIsNone(快照["positions"][0]["long"]["float_profit"])
        self.assertIsNone(快照["positions"][0]["short"]["float_profit"])
        self.assertIsNone(快照["positions"][0]["float_profit"])
        self.assertIsNone(快照["orders"][0]["limit_price"])
        self.assertIsNone(快照["orders"][0]["trade_price"])
        self.assertIsNone(快照["quotes"][0]["last_price"])
        # allow_nan=False 会在任何嵌套位置仍含 NaN/inf 时直接失败。
        json.dumps(快照, ensure_ascii=False, allow_nan=False)

    def test_部分成交ALIVE保留而FINISHED过滤(self):
        全部委托 = {
            "partial": _委托("partial", "DCE.m2609", 原始手数=5, 剩余手数=2),
            "finished": _委托("finished", "SHFE.rb2610", 状态="FINISHED", 原始手数=5, 剩余手数=2),
            "filled-transition": _委托(
                "filled-transition", "CZCE.MA609", 状态="ALIVE", 原始手数=3, 剩余手数=0
            ),
        }

        快照 = account_module.转换活动委托快照(全部委托)

        self.assertEqual(len(快照), 1)
        self.assertEqual(快照[0]["order_id"], "partial")
        self.assertEqual(快照[0]["volume_orign"], 5)
        self.assertEqual(快照[0]["volume_left"], 2)
        self.assertEqual(快照[0]["volume_traded"], 3)
        self.assertEqual(快照[0]["status"], "ALIVE")

    def test_两个行情开关独立且同合约来源去重(self):
        全部持仓 = {
            "SHFE.rb2610": _持仓("SHFE.rb2610", 多头=2, 浮盈=120.0),
        }
        全部委托 = {
            "overlap": _委托("overlap", "SHFE.rb2610", 原始手数=2, 剩余手数=1),
            "order-only": _委托("order-only", "DCE.m2609", 原始手数=3, 剩余手数=3),
            "finished": _委托("finished", "CZCE.MA609", 状态="FINISHED", 剩余手数=1),
        }
        行情 = {
            "SHFE.rb2610": {"last_price": 3518.0, "price_decs": 0, "datetime": "t1"},
            "DCE.m2609": {"last_price": 3021.5, "price_decs": 1, "datetime": "t2"},
            "CZCE.MA609": {"last_price": 2500.0, "price_decs": 0, "datetime": "t3"},
        }

        都关闭 = account_module.构建只读快照({}, 全部持仓, 全部委托, 行情)
        仅持仓 = account_module.构建只读快照(
            {}, 全部持仓, 全部委托, 行情, 监控持仓行情=True
        )
        仅委托 = account_module.构建只读快照(
            {}, 全部持仓, 全部委托, 行情, 监控委托行情=True
        )
        都开启 = account_module.构建只读快照(
            {}, 全部持仓, 全部委托, 行情, 监控持仓行情=True, 监控委托行情=True
        )

        self.assertEqual(都关闭["quotes"], [])
        self.assertEqual([项["symbol"] for 项 in 仅持仓["quotes"]], ["SHFE.rb2610"])
        self.assertEqual(
            [项["symbol"] for 项 in 仅委托["quotes"]],
            ["DCE.m2609", "SHFE.rb2610"],
        )
        self.assertEqual(
            [项["symbol"] for 项 in 都开启["quotes"]],
            ["DCE.m2609", "SHFE.rb2610"],
        )
        重叠行情 = next(项 for 项 in 都开启["quotes"] if 项["symbol"] == "SHFE.rb2610")
        self.assertTrue(重叠行情["from_position"])
        self.assertTrue(重叠行情["from_order"])
        self.assertEqual(sum(项["symbol"] == "SHFE.rb2610" for 项 in 都开启["quotes"]), 1)
        self.assertNotIn("CZCE.MA609", {项["symbol"] for 项 in 都开启["quotes"]})

    def test_快照不受SDK风格原对象后续原地变更影响(self):
        账户 = {"currency": "CNY", "balance": 100000.0, "available": 80000.0}
        持仓 = _持仓("SHFE.rb2610", 多头=2, 多头浮盈=120.0, 浮盈=120.0)
        委托 = _委托("mutable", "SHFE.rb2610", 原始手数=4, 剩余手数=3)
        行情 = {"SHFE.rb2610": {"last_price": 3518.0, "price_decs": 0, "datetime": "before"}}
        全部持仓 = {"SHFE.rb2610": 持仓}
        全部委托 = {"mutable": 委托}

        快照 = account_module.构建只读快照(
            账户,
            全部持仓,
            全部委托,
            行情,
            监控持仓行情=True,
            监控委托行情=True,
        )
        原快照 = copy.deepcopy(快照)

        账户["balance"] = 1.0
        持仓["pos_long"] = 0
        持仓["float_profit_long"] = -999.0
        委托["status"] = "FINISHED"
        委托["volume_left"] = 0
        行情["SHFE.rb2610"]["last_price"] = 1.0
        行情["SHFE.rb2610"]["datetime"] = "after"
        全部持仓.clear()
        全部委托.clear()
        行情.clear()

        self.assertEqual(快照, 原快照)
        self.assertEqual(快照["account"]["balance"], 100000.0)
        self.assertEqual(快照["positions"][0]["pos_long"], 2)
        self.assertEqual(快照["orders"][0]["volume_left"], 3)
        self.assertEqual(快照["quotes"][0]["last_price"], 3518.0)


if __name__ == "__main__":
    unittest.main()
