import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from backupFunc import (
    create_backup,
    delete_backup,
    delete_backup_dir,
    list_backups,
    load_config,
    log_message,
    restore_backup,
    save_config,
)


WINDOW_TITLE = "游戏存档备份工具"
STATUS_NONE_SELECTED = "当前选中游戏状态：未选择"
STATUS_MONITORING = "当前选中游戏状态：{name} 监控中"
STATUS_NOT_MONITORING = "当前选中游戏状态：{name} 未监控"
MONITOR_TAG = " [监控中]"

ERROR_TITLE = "错误"
INFO_TITLE = "成功"
TIP_TITLE = "提示"
DELETE_CONFIRM_TITLE = "确认删除"
DELETE_BACKUP_CONFIRM_TITLE = "确认删除备份"
RESTORE_CONFIRM_TITLE = "确认恢复"
START_FAILED_TITLE = "启动失败"
BACKUP_FAILED_TITLE = "备份失败"
RESTORE_FAILED_TITLE = "恢复失败"
DELETE_FAILED_TITLE = "删除失败"


@dataclass
class GameConfig:
    name: str
    source_dir: str
    backup_dir: str
    max_backups: int

    @classmethod
    def from_dict(cls, data: dict) -> "GameConfig":
        return cls(
            name=str(data.get("name", "")),
            source_dir=str(data.get("source_dir", "")),
            backup_dir=str(data.get("backup_dir", "")),
            max_backups=int(data.get("max_backups", 5)),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source_dir": self.source_dir,
            "backup_dir": self.backup_dir,
            "max_backups": self.max_backups,
        }


class SaveChangeHandler(FileSystemEventHandler):
    def __init__(
        self,
        root: tk.Tk,
        game: GameConfig,
        refresh_callback: Callable[[], None],
        debounce_seconds: float = 3.0,
    ) -> None:
        self.root = root
        self.game = game
        self.refresh_callback = refresh_callback
        self.debounce_seconds = debounce_seconds
        self.last_backup_time = 0.0

    def _schedule_refresh(self) -> None:
        try:
            if self.root.winfo_exists():
                self.root.after(0, self.refresh_callback)
        except tk.TclError:
            pass

    def _try_backup(self, file_path: str) -> None:
        if file_path.endswith(".tmp"):
            return

        current_time = time.time()
        if current_time - self.last_backup_time < self.debounce_seconds:
            return

        try:
            new_backup_path = create_backup(
                self.game.name,
                self.game.source_dir,
                self.game.backup_dir,
                self.game.max_backups,
                "auto",
            )
            self.last_backup_time = current_time
            log_message(f"{self.game.name} 自动备份成功: {new_backup_path}")
            print(f"{self.game.name} 自动备份成功: {new_backup_path}")
            self._schedule_refresh()
        except Exception as error:
            error_message = f"{self.game.name} 自动备份失败: {error}"
            log_message(error_message)
            print(error_message)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._try_backup(event.src_path)

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._try_backup(event.src_path)

    def on_deleted(self, event) -> None:
        if event.is_directory:
            return
        self._try_backup(event.src_path)


class SaveBackupApp:
    def __init__(self) -> None:
        self.games = self._load_games()
        self.observers: dict[str, Observer] = {}

        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.geometry("780x780")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status_label: tk.Label
        self.game_listbox: tk.Listbox
        self.backup_listbox: tk.Listbox
        self.name_entry: tk.Entry
        self.source_entry: tk.Entry
        self.backup_entry: tk.Entry
        self.max_backups_entry: tk.Entry

        self._build_ui()
        self.refresh_game_list()
        self._select_initial_game()

    def run(self) -> None:
        self.root.mainloop()

    def _load_games(self) -> list[GameConfig]:
        config = load_config()
        games_data = config.get("games", [])

        if not isinstance(games_data, list):
            return []

        games: list[GameConfig] = []

        for item in games_data:
            try:
                games.append(GameConfig.from_dict(item))
            except (TypeError, ValueError):
                continue

        return games

    def _save_games(self) -> None:
        save_config({"games": [game.to_dict() for game in self.games]})

    def _build_ui(self) -> None:
        tk.Label(self.root, text=WINDOW_TITLE, font=("Arial", 16)).pack(pady=10)

        self.status_label = tk.Label(self.root, text=STATUS_NONE_SELECTED, fg="blue")
        self.status_label.pack(pady=5)

        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        tk.Label(left_frame, text="游戏列表").pack()

        self.game_listbox = tk.Listbox(
            left_frame,
            width=25,
            height=25,
            exportselection=False,
        )
        self.game_listbox.pack(pady=10)
        self.game_listbox.bind("<<ListboxSelect>>", self.on_game_selected)

        game_button_frame = tk.Frame(left_frame)
        game_button_frame.pack(pady=10)

        tk.Button(
            game_button_frame,
            text="新增配置",
            width=10,
            command=self.add_new_game,
        ).pack(pady=5)
        tk.Button(
            game_button_frame,
            text="保存配置",
            width=10,
            command=self.save_current_game,
        ).pack(pady=5)
        tk.Button(
            game_button_frame,
            text="删除配置",
            width=10,
            command=self.delete_current_game,
        ).pack(pady=5)

        self.name_entry = self._build_labeled_entry(
            right_frame,
            "游戏名称",
            width=60,
        )
        self.source_entry = self._build_folder_row(right_frame, "存档目录")
        self.backup_entry = self._build_folder_row(right_frame, "备份目录")
        self.max_backups_entry = self._build_labeled_entry(
            right_frame,
            "最大备份数",
            width=60,
        )

        action_button_frame = tk.Frame(right_frame)
        action_button_frame.pack(pady=15, anchor="w")

        tk.Button(
            action_button_frame,
            text="立即备份",
            command=self.run_backup,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            action_button_frame,
            text="刷新备份列表",
            command=self.refresh_backup_list,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            action_button_frame,
            text="恢复选中备份",
            command=self.run_restore,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            action_button_frame,
            text="删除选中备份",
            command=self.delete_selected_backup,
        ).pack(side=tk.LEFT, padx=5)

        monitor_button_frame = tk.Frame(right_frame)
        monitor_button_frame.pack(pady=10, anchor="w")

        tk.Button(
            monitor_button_frame,
            text="开始监控选中游戏",
            command=self.start_selected_monitoring,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            monitor_button_frame,
            text="停止监控选中游戏",
            command=self.stop_selected_monitoring,
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(right_frame, text="历史备份版本").pack(anchor="w")

        self.backup_listbox = tk.Listbox(
            right_frame,
            width=70,
            height=15,
            exportselection=False,
        )
        self.backup_listbox.pack(pady=10, anchor="w")

    def _build_labeled_entry(self, parent: tk.Widget, label_text: str, width: int) -> tk.Entry:
        tk.Label(parent, text=label_text).pack(anchor="w")

        entry = tk.Entry(parent, width=width)
        entry.pack(pady=5, anchor="w")
        return entry

    def _build_folder_row(self, parent: tk.Widget, label_text: str) -> tk.Entry:
        tk.Label(parent, text=label_text).pack(anchor="w")

        frame = tk.Frame(parent)
        frame.pack(pady=5, anchor="w")

        entry = tk.Entry(frame, width=48)
        entry.pack(side=tk.LEFT, padx=5)

        tk.Button(
            frame,
            text="浏览",
            command=lambda: self.choose_folder(entry),
        ).pack(side=tk.LEFT)

        return entry

    def choose_folder(self, entry: tk.Entry) -> None:
        folder_path = filedialog.askdirectory()
        if not folder_path:
            return

        entry.delete(0, tk.END)
        entry.insert(0, folder_path)

    def get_selected_game_index(self) -> int | None:
        selection = self.game_listbox.curselection()
        if not selection:
            return None

        selected_index = selection[0]
        if selected_index >= len(self.games):
            return None

        return selected_index

    def get_selected_game(self) -> GameConfig | None:
        selected_index = self.get_selected_game_index()
        if selected_index is None:
            return None

        return self.games[selected_index]

    def get_display_name(self, game_name: str) -> str:
        if game_name in self.observers:
            return f"{game_name}{MONITOR_TAG}"
        return game_name

    def refresh_game_list(self) -> None:
        selected_index = self.get_selected_game_index()

        self.game_listbox.delete(0, tk.END)

        for game in self.games:
            self.game_listbox.insert(tk.END, self.get_display_name(game.name))

        if selected_index is not None and selected_index < len(self.games):
            self.game_listbox.selection_set(selected_index)
            self.game_listbox.activate(selected_index)

    def select_game(self, index: int) -> None:
        if index < 0 or index >= len(self.games):
            return

        self.game_listbox.selection_clear(0, tk.END)
        self.game_listbox.selection_set(index)
        self.game_listbox.activate(index)
        self.load_selected_game_to_form()

    def _select_initial_game(self) -> None:
        if not self.games:
            self.clear_form()
            self.update_selected_game_status("")
            return

        self.select_game(0)

    def clear_form(self) -> None:
        for entry in (
            self.name_entry,
            self.source_entry,
            self.backup_entry,
            self.max_backups_entry,
        ):
            entry.delete(0, tk.END)

        self.backup_listbox.delete(0, tk.END)

    def read_form_data(self) -> GameConfig | None:
        game_name = self.name_entry.get().strip()
        source_dir = self.source_entry.get().strip()
        backup_dir = self.backup_entry.get().strip()
        max_backups_text = self.max_backups_entry.get().strip()

        if not game_name or not source_dir or not backup_dir or not max_backups_text:
            messagebox.showerror(ERROR_TITLE, "请填写所有字段")
            return None

        try:
            max_backups = int(max_backups_text)
        except ValueError:
            messagebox.showerror(ERROR_TITLE, "最大备份数必须是整数")
            return None

        if max_backups <= 0:
            messagebox.showerror(ERROR_TITLE, "最大备份数必须大于 0")
            return None

        return GameConfig(
            name=game_name,
            source_dir=source_dir,
            backup_dir=backup_dir,
            max_backups=max_backups,
        )

    def load_game_into_form(self, game: GameConfig) -> None:
        self.clear_form()
        self.name_entry.insert(0, game.name)
        self.source_entry.insert(0, game.source_dir)
        self.backup_entry.insert(0, game.backup_dir)
        self.max_backups_entry.insert(0, str(game.max_backups))
        self.refresh_backup_list()
        self.update_selected_game_status(game.name)

    def update_selected_game_status(self, game_name: str) -> None:
        if not game_name:
            self.status_label.config(text=STATUS_NONE_SELECTED)
            return

        if game_name in self.observers:
            self.status_label.config(text=STATUS_MONITORING.format(name=game_name))
            return

        self.status_label.config(text=STATUS_NOT_MONITORING.format(name=game_name))

    def on_game_selected(self, _event=None) -> None:
        self.load_selected_game_to_form()

    def load_selected_game_to_form(self) -> None:
        game = self.get_selected_game()
        if game is None:
            return

        self.load_game_into_form(game)

    def add_new_game(self) -> None:
        self.game_listbox.selection_clear(0, tk.END)
        self.clear_form()
        self.update_selected_game_status("")

    def _find_duplicate_name(self, name: str, ignore_index: int | None = None) -> int | None:
        for index, game in enumerate(self.games):
            if index == ignore_index:
                continue

            if game.name == name:
                return index

        return None

    def save_current_game(self) -> None:
        game = self.read_form_data()
        if game is None:
            return

        selected_index = self.get_selected_game_index()
        duplicate_index = self._find_duplicate_name(game.name, ignore_index=selected_index)

        if duplicate_index is not None:
            messagebox.showerror(ERROR_TITLE, "游戏名称不能重复")
            return

        if selected_index is None:
            self.games.append(game)
            target_index = len(self.games) - 1
        else:
            old_name = self.games[selected_index].name

            if old_name != game.name and old_name in self.observers:
                messagebox.showerror(
                    ERROR_TITLE,
                    "请先停止该游戏的监控，再修改游戏名称",
                )
                return

            self.games[selected_index] = game
            target_index = selected_index

        self._save_games()
        self.refresh_game_list()
        self.select_game(target_index)
        messagebox.showinfo(INFO_TITLE, "游戏配置已保存")

    def delete_current_game(self) -> None:
        selected_index = self.get_selected_game_index()
        if selected_index is None:
            messagebox.showerror(ERROR_TITLE, "请先选择一个游戏")
            return

        game = self.games[selected_index]
        if game.name in self.observers:
            messagebox.showerror(ERROR_TITLE, "请先停止该游戏的监控，再删除")
            return

        confirm = messagebox.askyesno(
            DELETE_CONFIRM_TITLE,
            (
                f"确定要删除游戏配置\n{game.name}\n吗？\n"
                "这会同时删除该游戏备份目录中的备份内容。"
            ),
        )
        if not confirm:
            return

        try:
            delete_backup_dir(game.backup_dir)
            del self.games[selected_index]
            self._save_games()
            self.refresh_game_list()
        except Exception as error:
            messagebox.showerror(DELETE_FAILED_TITLE, str(error))
            return

        if self.games:
            next_index = min(selected_index, len(self.games) - 1)
            self.select_game(next_index)
        else:
            self.clear_form()
            self.update_selected_game_status("")

        messagebox.showinfo(INFO_TITLE, "游戏配置已删除")

    def delete_selected_backup(self) -> None:
        game = self.read_form_data()
        if game is None:
            return

        selection = self.backup_listbox.curselection()
        if not selection:
            messagebox.showerror(ERROR_TITLE, "请先选择一个备份版本")
            return

        backup_name = self.backup_listbox.get(selection[0])
        backup_path = str(Path(game.backup_dir) / backup_name)

        confirm = messagebox.askyesno(
            DELETE_BACKUP_CONFIRM_TITLE,
            f"确定要删除备份\n{backup_name}\n吗？",
        )
        if not confirm:
            return

        try:
            delete_backup(backup_path)
            self.refresh_backup_list()
            messagebox.showinfo(INFO_TITLE, f"已删除备份\n{backup_name}")
        except Exception as error:
            messagebox.showerror(DELETE_FAILED_TITLE, str(error))

    def refresh_backup_list(self) -> None:
        backup_dir = self.backup_entry.get().strip()
        self.backup_listbox.delete(0, tk.END)

        if not backup_dir:
            return

        for backup_name in list_backups(backup_dir):
            self.backup_listbox.insert(tk.END, backup_name)

    def run_backup(self) -> None:
        game = self.read_form_data()
        if game is None:
            return

        try:
            new_backup_path = create_backup(
                game.name,
                game.source_dir,
                game.backup_dir,
                game.max_backups,
                "manual",
            )
            self.refresh_backup_list()
            messagebox.showinfo(INFO_TITLE, f"备份完成\n{new_backup_path}")
        except Exception as error:
            messagebox.showerror(BACKUP_FAILED_TITLE, str(error))

    def run_restore(self) -> None:
        game = self.read_form_data()
        if game is None:
            return

        selection = self.backup_listbox.curselection()
        if not selection:
            messagebox.showerror(ERROR_TITLE, "请先选择一个备份版本")
            return

        backup_name = self.backup_listbox.get(selection[0])
        source_backup_path = str(Path(game.backup_dir) / backup_name)

        confirm = messagebox.askyesno(
            RESTORE_CONFIRM_TITLE,
            (
                f"确定要恢复备份\n{backup_name}\n"
                "到存档目录吗？\n"
                "恢复前会先自动备份当前存档。"
            ),
        )
        if not confirm:
            return

        monitoring_was_running = game.name in self.observers

        try:
            if monitoring_was_running:
                self._stop_observer(game.name)

            protection_backup_path = create_backup(
                game.name,
                game.source_dir,
                game.backup_dir,
                game.max_backups,
                "protect",
            )
            restore_backup(source_backup_path, game.source_dir)
            self.refresh_backup_list()
            messagebox.showinfo(
                INFO_TITLE,
                (
                    f"已恢复备份\n{backup_name}\n\n"
                    f"恢复前保护备份已创建：\n{protection_backup_path}"
                ),
            )
        except Exception as error:
            messagebox.showerror(RESTORE_FAILED_TITLE, str(error))
        finally:
            if monitoring_was_running and game.name not in self.observers:
                try:
                    self._start_monitor_for_game(game)
                    self.refresh_game_list()
                    self.select_game(self.games.index(game))
                except Exception as error:
                    messagebox.showerror(START_FAILED_TITLE, f"恢复后重新启动监控失败：{error}")

    def _refresh_visible_backup_list(self, game_name: str) -> None:
        selected_game = self.get_selected_game()
        if selected_game is None:
            return

        if selected_game.name != game_name:
            return

        self.refresh_backup_list()

    def _start_monitor_for_game(self, game: GameConfig) -> None:
        observer = Observer()
        event_handler = SaveChangeHandler(
            root=self.root,
            game=game,
            refresh_callback=lambda: self._refresh_visible_backup_list(game.name),
            debounce_seconds=3.0,
        )
        observer.schedule(event_handler, game.source_dir, recursive=True)
        observer.start()
        self.observers[game.name] = observer

    def start_selected_monitoring(self) -> None:
        game = self.get_selected_game()
        if game is None:
            messagebox.showerror(ERROR_TITLE, "请先选择一个游戏")
            return

        if not game.name or not game.source_dir or not game.backup_dir:
            messagebox.showerror(ERROR_TITLE, "当前游戏配置不完整")
            return

        if game.name in self.observers:
            messagebox.showinfo(TIP_TITLE, f"{game.name} 已经在监控中")
            return

        try:
            self._start_monitor_for_game(game)
            self.refresh_game_list()
            self.select_game(self.games.index(game))
            self.update_selected_game_status(game.name)
            messagebox.showinfo(INFO_TITLE, f"已开始监控 {game.name}")
        except Exception as error:
            messagebox.showerror(START_FAILED_TITLE, str(error))

    def _stop_observer(self, game_name: str) -> bool:
        observer = self.observers.get(game_name)
        if observer is None:
            return False

        observer.stop()
        observer.join()
        del self.observers[game_name]
        return True

    def stop_selected_monitoring(self) -> None:
        game = self.get_selected_game()
        if game is None:
            messagebox.showerror(ERROR_TITLE, "请先选择一个游戏")
            return

        if not self._stop_observer(game.name):
            messagebox.showinfo(TIP_TITLE, f"{game.name} 当前未监控")
            return

        self.refresh_game_list()
        self.select_game(self.games.index(game))
        self.update_selected_game_status(game.name)
        messagebox.showinfo(INFO_TITLE, f"已停止监控 {game.name}")

    def stop_all_monitoring(self) -> None:
        for game_name in list(self.observers.keys()):
            self._stop_observer(game_name)

    def on_close(self) -> None:
        self.stop_all_monitoring()
        self.root.destroy()


def main() -> None:
    app = SaveBackupApp()
    app.run()


if __name__ == "__main__":
    main()
