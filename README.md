# 项目简介
这是一个基于 TqSdk + PySide6 的「期货行情透明悬浮牌」，带托盘图标和简单设置界面。
# 功能说明
 - 始终置顶透明悬浮牌显示某个合约最新价
 - 除价格外，悬浮牌可以显示一行备注小字
 - 托盘菜单：显示/隐藏、锁定、设置、退出
 - 自动记住上次样式配置
 - 设置中支持输入框补全切换订阅合约（支持 `KQ.m@交易所.品种` 与 `交易所.合约`），并自动复用单条行情线程以节约资源

# 目录结构
 - `tq_price_badge.py`：兼容原有启动方式的薄入口
 - `badge_app/frontend/`：Qt 界面层，负责悬浮牌、预览和设置对话框
 - `badge_app/backend/`：配置持久化、合约规范化、行情线程等后端逻辑
 - `badge_app/app.py`：应用编排层，负责把前后端串起来

项目基于天勤量化行情，登录信息需写在系统环境变量中
```chatinput
pip install -r requirements.txt
python tq_price_badge.py KQ.m@SHFE.cu
```
