# 游戏存档自动备份与恢复工具

## 中文

这是一个使用 Python、Tkinter 和 watchdog 编写的桌面小工具，用来管理多个游戏的本地存档。它支持多游戏配置、手动备份、自动监控备份、历史备份查看、删除备份，以及恢复存档前自动创建保护备份。每个游戏都可以独立配置存档目录、备份目录和最大保留备份数。

项目主要文件包括：[gui.py]负责图形界面与监控控制，[backupFunc.py] 负责备份、恢复、配置和日志逻辑，[config.json]用于保存游戏配置。开发运行可直接执行 `gui.py`；如果需要打包为 Windows 程序，可以使用 PyInstaller 生成 `onedir` 或 `onefile` 版本。当前仓库内也包含已经整理好的打包输出目录，方便直接分发测试。

## English

This is a small desktop utility built with Python, Tkinter, and watchdog for managing local save files from multiple games. It supports multi-game configuration, manual backups, automatic monitored backups, backup history browsing, backup deletion, and protected restore flow that creates a safety backup before overwriting current saves. Each game can define its own save directory, backup directory, and maximum number of retained backups.

The main project files are `[gui.py]` for the GUI and monitoring flow, `[backupFunc.py]` for backup, restore, config, and logging logic, and `[config.json]` for stored game settings. For development, run `gui.py` directly. For Windows distribution, you can package it with PyInstaller in either `onedir` or `onefile` mode. This repository also contains prepared packaged output folders for quick sharing and testing.
