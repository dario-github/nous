"""Nous — 热加载 (M2.6)

使用 watchfiles 监控 ontology/constraints/*.yaml，
变更触发重新解析 + sanity check + atomic swap。

失败回滚：解析失败不替换，保持旧规则，记录错误日志。

HotReloader class：
    start()           — 在后台线程启动文件监控
    stop()            — 停止监控线程
    reload()          — 手动触发重新加载（同步）
    get_constraints() — 获取当前内存中的约束列表
"""
import logging
import threading
import time
from pathlib import Path
from typing import Optional

from nous.constraint_parser import DEFAULT_CONSTRAINTS_DIR, load_constraints
from nous.schema import Constraint

logger = logging.getLogger("nous.hot_reload")


# ── sanity check ──────────────────────────────────────────────────────────────


def _sanity_check(constraints: list[Constraint]) -> tuple[bool, str]:
    """
    对加载的约束列表做基本合法性检查。

    1. 非空列表（至少有 1 条规则）
    2. 每条规则有合法的 id（非空字符串）
    3. 每条规则有合法的 verdict（已知枚举值）
    4. 类型正确（list[Constraint]）

    返回 (ok: bool, error_msg: str)
    """
    VALID_VERDICTS = {"block", "confirm", "require", "warn", "rewrite", "transform",
                      "delegate", "allow"}

    if not isinstance(constraints, list):
        return False, f"期望 list，得到 {type(constraints)}"

    if len(constraints) == 0:
        # 允许空目录（不报错）
        return True, ""

    for c in constraints:
        if not isinstance(c, Constraint):
            return False, f"列表元素不是 Constraint 类型: {type(c)}"
        if not c.id or not isinstance(c.id, str):
            return False, f"Constraint.id 非法: {c.id!r}"
        if c.verdict not in VALID_VERDICTS:
            return False, f"Constraint {c.id!r} verdict 非法: {c.verdict!r}"

    return True, ""


# ── HotReloader ───────────────────────────────────────────────────────────────


class HotReloader:
    """
    约束 YAML 热加载器。

    使用示例：
        reloader = HotReloader()
        reloader.start()
        constraints = reloader.get_constraints()
        reloader.stop()
    """

    def __init__(
        self,
        constraints_dir: Optional[Path] = None,
        debounce_ms: float = 200.0,
    ):
        self._constraints_dir = Path(constraints_dir or DEFAULT_CONSTRAINTS_DIR)
        self._debounce_ms = debounce_ms

        # 初始加载
        self._constraints: list[Constraint] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 初始化时同步加载一次
        self.reload()

    # ── 公开 API ──────────────────────────────────────────────────────────

    def get_constraints(self) -> list[Constraint]:
        """获取当前内存中的约束列表（线程安全）"""
        with self._lock:
            return list(self._constraints)

    def reload(self) -> bool:
        """
        手动触发重新加载（同步）。

        成功时 atomic swap 替换内存中的约束列表，返回 True。
        失败时保持旧规则，记录错误日志，返回 False。
        """
        try:
            new_constraints = load_constraints(self._constraints_dir)
        except Exception as e:
            logger.error("[hot_reload] 加载约束失败（解析异常），保持旧规则: %s", e)
            return False

        ok, err = _sanity_check(new_constraints)
        if not ok:
            logger.error("[hot_reload] sanity check 失败，保持旧规则: %s", err)
            return False

        # atomic swap
        with self._lock:
            old_count = len(self._constraints)
            self._constraints = new_constraints

        logger.info(
            "[hot_reload] 约束热加载成功: %d 条 (原 %d 条)",
            len(new_constraints),
            old_count,
        )
        return True

    def start(self) -> None:
        """在后台线程启动文件监控（幂等，重复调用无副作用）"""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            name="nous-hot-reload",
            daemon=True,
        )
        self._thread.start()
        logger.info("[hot_reload] 后台监控已启动: %s", self._constraints_dir)

    def stop(self) -> None:
        """停止监控线程（等待最多 3 秒）"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        logger.info("[hot_reload] 后台监控已停止")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── 内部监控循环 ──────────────────────────────────────────────────────

    def _watch_loop(self) -> None:
        """后台线程：使用 watchfiles.watch 监控目录变更"""
        try:
            from watchfiles import watch, Change
        except ImportError:
            logger.error(
                "[hot_reload] watchfiles 未安装，热加载功能不可用。"
                "请 pip install watchfiles"
            )
            return

        try:
            # watch() 是阻塞迭代器，每当文件变更时 yield 一个变更集合
            for changes in watch(
                str(self._constraints_dir),
                stop_event=self._stop_event,
                debounce=int(self._debounce_ms),
            ):
                if self._stop_event.is_set():
                    break

                # 只关注 .yaml 文件
                yaml_changes = [
                    (chg, path) for chg, path in changes
                    if path.endswith(".yaml")
                ]
                if not yaml_changes:
                    continue

                logger.info(
                    "[hot_reload] 检测到 %d 处 YAML 变更，触发重新加载...",
                    len(yaml_changes),
                )
                for chg, path in yaml_changes:
                    logger.debug("  %s: %s", chg.name, path)

                self.reload()

        except Exception as e:
            if not self._stop_event.is_set():
                logger.error("[hot_reload] 监控循环异常: %s", e)
