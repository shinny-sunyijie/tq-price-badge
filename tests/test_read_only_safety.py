# -*- coding: utf-8 -*-
"""只读安全护栏：静态确认生产代码没有任何交易动作入口。

本测试只读取并解析 ``badge_app`` 下的 Python 源码；不会导入生产模块、
构造 TqApi、访问网络、创建 Qt 应用或显示窗口。
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


仓库根目录 = Path(__file__).resolve().parents[1]
生产代码目录 = 仓库根目录 / "badge_app"

# 这些公开接口会直接或间接产生委托、撤单或目标持仓交易。
禁止调用名称 = {
    "insert_order",
    "cancel_order",
    "set_target_volume",
}

# 导入或实例化这些类即意味着引入自动交易执行能力。
禁止交易类 = {
    "TargetPosTask",
    "TargetPosScheduler",
    "InsertOrderTask",
    "InsertOrderUntilAllTradedTask",
    "Twap",
    "TWAP",
}

# 应用不得绕过 TqSdk 公开 API，直接向交易通道发送协议包。
禁止私有发送成员 = {
    "_send_pack",
    "_send_chan",
    "_td_send_chan",
    "_trade_chan",
}

禁止交易协议 = {
    "insert_order",
    "cancel_order",
    "confirm_settlement",
}


def _属性全名(节点: ast.AST) -> str:
    """尽可能还原 ``obj.attr.method`` 形式的静态名称。"""

    部分: list[str] = []
    当前 = 节点
    while isinstance(当前, ast.Attribute):
        部分.append(当前.attr)
        当前 = 当前.value
    if isinstance(当前, ast.Name):
        部分.append(当前.id)
    return ".".join(reversed(部分))


def _位置(路径: Path, 节点: ast.AST, 原因: str) -> str:
    相对路径 = 路径.relative_to(仓库根目录)
    return f"{相对路径}:{getattr(节点, 'lineno', '?')}：{原因}"


class 只读安全扫描测试(unittest.TestCase):
    def test_生产代码不包含交易动作(self):
        问题: list[str] = []
        源文件 = sorted(生产代码目录.rglob("*.py"))
        self.assertTrue(源文件, "没有找到 badge_app 生产代码")

        for 路径 in 源文件:
            源码 = 路径.read_text(encoding="utf-8")
            try:
                语法树 = ast.parse(源码, filename=str(路径))
            except SyntaxError as 异常:
                self.fail(f"无法解析 {路径.relative_to(仓库根目录)}：{异常}")

            for 节点 in ast.walk(语法树):
                if isinstance(节点, ast.ImportFrom):
                    模块 = 节点.module or ""
                    if 模块 == "tqsdk.lib" or 模块.startswith("tqsdk.lib."):
                        问题.append(_位置(路径, 节点, f"禁止导入交易任务模块 {模块}"))
                    if 模块 == "tqsdk.algorithm" or 模块.startswith("tqsdk.algorithm."):
                        问题.append(_位置(路径, 节点, f"禁止导入算法交易模块 {模块}"))
                    for 别名 in 节点.names:
                        if 别名.name in 禁止交易类:
                            问题.append(_位置(路径, 节点, f"禁止导入交易类 {别名.name}"))

                elif isinstance(节点, ast.Import):
                    for 别名 in 节点.names:
                        模块 = 别名.name
                        if (
                            模块 == "tqsdk.lib"
                            or 模块.startswith("tqsdk.lib.")
                            or 模块 == "tqsdk.algorithm"
                            or 模块.startswith("tqsdk.algorithm.")
                        ):
                            问题.append(_位置(路径, 节点, f"禁止导入交易执行模块 {模块}"))

                elif isinstance(节点, ast.Attribute):
                    成员 = 节点.attr
                    小写成员 = 成员.casefold()
                    if (
                        成员 in 禁止调用名称
                        or 成员 in 禁止交易类
                        or "insert_order" in 小写成员
                        or "cancel_order" in 小写成员
                        or "target_volume" in 小写成员
                    ):
                        问题.append(_位置(路径, 节点, f"禁止访问交易接口 {_属性全名(节点)}"))
                    if 成员 in 禁止私有发送成员:
                        问题.append(_位置(路径, 节点, f"禁止访问私有发送通道 {_属性全名(节点)}"))
                    全名 = _属性全名(节点)
                    if 成员 in {"send", "send_nowait"} and any(
                        f".{私有成员}." in f".{全名}." for 私有成员 in 禁止私有发送成员
                    ):
                        问题.append(_位置(路径, 节点, f"禁止通过私有交易通道发送数据 {全名}"))

                elif isinstance(节点, ast.Name):
                    if (
                        节点.id in 禁止调用名称
                        or 节点.id in 禁止交易类
                        or 节点.id in 禁止私有发送成员
                    ):
                        问题.append(_位置(路径, 节点, f"禁止使用交易符号 {节点.id}"))

                elif isinstance(节点, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    名称 = 节点.name
                    小写名称 = 名称.casefold()
                    if (
                        名称 in 禁止调用名称
                        or 名称 in 禁止交易类
                        or 名称 in 禁止私有发送成员
                        or "insert_order" in 小写名称
                        or "cancel_order" in 小写名称
                        or "target_volume" in 小写名称
                    ):
                        问题.append(_位置(路径, 节点, f"禁止定义交易入口 {名称}"))

                elif isinstance(节点, ast.Constant) and isinstance(节点.value, str):
                    if 节点.value in 禁止交易协议 or 节点.value in 禁止调用名称:
                        问题.append(_位置(路径, 节点, f"禁止构造交易协议 {节点.value!r}"))
                    if 节点.value in 禁止交易类:
                        问题.append(_位置(路径, 节点, f"禁止动态访问交易类 {节点.value!r}"))
                    if 节点.value in 禁止私有发送成员:
                        问题.append(_位置(路径, 节点, f"禁止动态访问私有发送成员 {节点.value!r}"))

        self.assertFalse(问题, "发现可能产生交易动作的生产代码：\n" + "\n".join(问题))


if __name__ == "__main__":
    unittest.main()
