from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


CONFIG_PATH = str(get_app_base_dir() / "config.json")
LOG_PATH = str(get_app_base_dir() / "backup.log")


def get_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def load_config(config_path: str = CONFIG_PATH) -> dict:
    config_file = Path(config_path)
    if not config_file.exists():
        return {"games": []}

    with config_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_config(config: dict, config_path: str = CONFIG_PATH) -> None:
    config_file = Path(config_path)

    with config_file.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=4)


def validate_source_dir(source_dir: str) -> bool:
    source_path = Path(source_dir)
    return source_path.exists() and source_path.is_dir()


def copy_save_folder(source_dir: str, target_dir: str) -> None:
    shutil.copytree(source_dir, target_dir)


def create_backup(
    game_name: str,
    source_dir: str,
    backup_dir: str,
    max_backups: int,
    backup_type: str = "manual",
) -> str:
    if not validate_source_dir(source_dir):
        raise FileNotFoundError(f"源存档目录不存在或不是文件夹: {source_dir}")

    ensure_dir(backup_dir)

    backup_name = f"{backup_type}_{get_timestamp()}"
    backup_path = str(Path(backup_dir) / backup_name)

    copy_save_folder(source_dir, backup_path)

    log_message(f"{game_name} 备份成功: {backup_path}")
    cleanup_old_backups(backup_dir, max_backups)

    return backup_path


def list_backups(backup_dir: str) -> list[str]:
    backup_path = Path(backup_dir)
    if not backup_path.exists() or not backup_path.is_dir():
        return []

    backups: list[str] = []

    for item in backup_path.iterdir():
        if item.is_dir():
            backups.append(item.name)

    backups.sort()
    return backups


def cleanup_old_backups(backup_dir: str, max_backups: int) -> None:
    backups = list_backups(backup_dir)
    if len(backups) <= max_backups:
        return

    delete_count = len(backups) - max_backups

    for backup_name in backups[:delete_count]:
        shutil.rmtree(Path(backup_dir) / backup_name)


def delete_backup(backup_path: str) -> None:
    target_path = Path(backup_path)

    if not target_path.exists() or not target_path.is_dir():
        raise FileNotFoundError(f"备份目录不存在或不是文件夹: {backup_path}")

    shutil.rmtree(target_path)


def delete_backup_dir(backup_dir: str) -> None:
    target_path = Path(backup_dir)

    if not target_path.exists():
        return

    if not target_path.is_dir():
        raise FileNotFoundError(f"备份目录不存在或不是文件夹: {backup_dir}")

    for item in target_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)


def restore_backup(source_backup_path: str, target_save_dir: str) -> None:
    source_path = Path(source_backup_path)
    target_path = Path(target_save_dir)

    if not source_path.exists() or not source_path.is_dir():
        raise FileNotFoundError(f"备份目录不存在或不是文件夹: {source_backup_path}")

    if target_path.exists():
        shutil.rmtree(target_path)

    shutil.copytree(source_path, target_path)


def log_message(message: str, log_file: str = LOG_PATH) -> None:
    timestamp = get_timestamp()

    with open(log_file, "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {message}\n")
