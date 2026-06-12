"""违规检测工具 v6.0 - flet 深色 Material Design 3 风格 GUI"""
import flet as ft
import threading
import time
import os
import sys
import re
import subprocess
from typing import List, Dict, Optional
from collections import defaultdict
from detector import DetectionResult, ScanProgress, get_available_drives, open_explorer_at

try:
    import pyperclip
except ImportError:
    pyperclip = None


# ── 颜色系统 (Material Design 3 Dark) ─────────────────────────────
class Colors:
    PRIMARY = "#a3c9ff"
    PRIMARY_CONTAINER = "#0078d4"
    ON_PRIMARY_CONTAINER = "#ffffff"
    SECONDARY = "#ffb597"
    TERTIARY = "#ffb3ac"
    TERTIARY_CONTAINER = "#ea1424"
    ERROR = "#ffb4ab"
    ERROR_CONTAINER = "#93000a"
    SURFACE = "#131313"
    SURFACE_DIM = "#131313"
    SURFACE_CONTAINER_LOWEST = "#0e0e0e"
    SURFACE_CONTAINER_LOW = "#1b1b1c"
    SURFACE_CONTAINER = "#202020"
    SURFACE_CONTAINER_HIGH = "#2a2a2a"
    SURFACE_CONTAINER_HIGHEST = "#353535"
    SURFACE_VARIANT = "#353535"
    SURFACE_BRIGHT = "#393939"
    ON_SURFACE = "#e5e2e1"
    ON_SURFACE_VARIANT = "#c0c7d4"
    OUTLINE = "#8a919e"
    OUTLINE_VARIANT = "#404752"
    TRANSPARENT = "transparent"


# ── 辅助函数 ──────────────────────────────────────────────────────
def border_all(width: int, color: str) -> ft.border.Border:
    """创建四边相同的边框"""
    return ft.border.Border(
        top=ft.BorderSide(width, color),
        right=ft.BorderSide(width, color),
        bottom=ft.BorderSide(width, color),
        left=ft.BorderSide(width, color)
    )


def border_bottom(width: int, color: str) -> ft.border.Border:
    """创建只有底部的边框"""
    return ft.border.Border(
        bottom=ft.BorderSide(width, color)
    )


def border_left(width: int, color: str) -> ft.border.Border:
    """创建只有左边的边框"""
    return ft.border.Border(
        left=ft.BorderSide(width, color)
    )


def border_left_bottom(left_w: int, left_c: str, bottom_w: int, bottom_c: str) -> ft.border.Border:
    """创建左边和底部的边框"""
    return ft.border.Border(
        left=ft.BorderSide(left_w, left_c),
        bottom=ft.BorderSide(bottom_w, bottom_c)
    )


def border_right(width: int, color: str) -> ft.border.Border:
    """创建只有右边的边框"""
    return ft.border.Border(
        right=ft.BorderSide(width, color)
    )


def border_radius_only(top_left: int = 0, top_right: int = 0, bottom_left: int = 0, bottom_right: int = 0):
    """创建指定角的圆角"""
    return ft.border_radius.BorderRadius(
        top_left=top_left,
        top_right=top_right,
        bottom_left=bottom_left,
        bottom_right=bottom_right
    )


# 常用对齐方式
alignment_center = ft.alignment.Alignment(0, 0)
alignment_center_right = ft.alignment.Alignment(1, 0)


class FletGUI:
    """违规检测工具 v6.0 - flet GUI"""

    def __init__(self, on_scan_callable, on_notify_callable,
                 on_cancel_callable=None, on_smartsheet_callable=None,
                 on_clean_registry_callable=None,
                 on_delete_callable=None):
        self.on_scan = on_scan_callable
        self.on_notify = on_notify_callable
        self.on_cancel = on_cancel_callable
        self.on_smartsheet = on_smartsheet_callable
        self.on_clean_registry = on_clean_registry_callable
        self.on_delete = on_delete_callable
        self._results: List[DetectionResult] = []
        self._scanning = False
        self._selected_items: set = set()
        self._cancel_requested = False

        # UI 组件引用
        self.page = None
        self.name_field = None
        self.start_btn = None
        self.start_btn_text = None
        self.cancel_btn = None
        self.tree_container = None
        self.status_text = None
        self.footer_status = None
        self.scanned_text = None
        self.found_text = None
        self.speed_text = None
        self.elapsed_text = None
        self.progress_segments = []
        self.stat_install = None
        self.stat_log = None
        self.stat_doc = None
        self.stat_registry = None
        self.header_checkbox = None
        self.log_list = None  # 日志列表控件
        self._last_progress_update = 0.0
        self._scan_phase = 0  # 当前扫描阶段: 0=未开始, 1=注册表, 2=固定路径, 3=全盘
        self._group_items = {}  # 分组行 → 子控件列表映射
        self._collapsed_groups = set()  # 已折叠的分组路径

    def run(self):
        ft.app(target=self._main)

    def _main(self, page: ft.Page):
        self.page = page

        # ── 页面配置 ─────────────────────────────────────────────
        page.title = "违规检测工具 v6.0"
        page.window.width = 1000
        page.window.height = 680
        page.window.resizable = True
        page.window.min_width = 800
        page.window.min_height = 500
        page.bgcolor = Colors.SURFACE
        page.theme_mode = ft.ThemeMode.DARK
        page.on_window_event = self._on_window_event
        page.on_keyboard_event = self._on_keyboard_event

        # ── 构建界面 ─────────────────────────────────────────────
        page.add(self._build_layout())
        page.update()

    def _build_layout(self) -> ft.Column:
        return ft.Column(
            spacing=0,
            controls=[
                self._build_top_app_bar(),
                ft.Row(
                    spacing=0,
                    controls=[
                        self._build_sidebar(),
                        self._build_main_content()
                    ],
                    expand=True
                ),
                self._build_footer()
            ],
            expand=True
        )

    # ── 顶部应用栏 ─────────────────────────────────────────────
    def _build_top_app_bar(self) -> ft.Container:
        self.name_field = ft.TextField(
            hint_text="请输入被检测人姓名",
            hint_style=ft.TextStyle(color=Colors.ON_SURFACE_VARIANT, size=12),
            text_style=ft.TextStyle(color=Colors.ON_SURFACE, size=12),
            bgcolor=Colors.SURFACE_CONTAINER,
            border_color=Colors.TERTIARY_CONTAINER,
            border_radius=8,
            focused_border_color=Colors.PRIMARY,
            width=250,
            height=36,
            content_padding=8,
            prefix_icon=ft.Icons.PERSON_SEARCH,
        )

        name_hint = ft.Text("姓名输入 (必填)", size=10, color=Colors.TERTIARY)

        # 操作工具组
        toolbar = ft.Container(
            bgcolor=Colors.SURFACE_CONTAINER,
            border=border_all(1, Colors.OUTLINE_VARIANT),
            border_radius=8,
            content=ft.Row(
                spacing=0,
                controls=[
                    self._toolbar_btn(ft.Icons.DELETE, "删除", self._delete_selected),
                    ft.VerticalDivider(width=1, color=Colors.OUTLINE_VARIANT),
                    self._toolbar_btn(ft.Icons.COPY, "复制", self._copy_paths),
                    ft.VerticalDivider(width=1, color=Colors.OUTLINE_VARIANT),
                    self._toolbar_btn(ft.Icons.CLEANING_SERVICES, "清理注册表", self._clean_registry),
                    ft.VerticalDivider(width=1, color=Colors.OUTLINE_VARIANT),
                    self._toolbar_btn(ft.Icons.SELECT_ALL, "全选", self._select_all),
                ]
            )
        )

        self.cancel_btn = ft.OutlinedButton(
            content=ft.Text("取消"),
            style=ft.ButtonStyle(
                color=Colors.ON_SURFACE,
                bgcolor=Colors.SURFACE,
                side=ft.BorderSide(1, Colors.OUTLINE_VARIANT),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            height=36,
            on_click=self._cancel_scan,
            disabled=True
        )

        self.start_btn_text = ft.Text("开始扫描")
        self.start_btn = ft.ElevatedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.PLAY_ARROW, size=16),
                self.start_btn_text
            ], spacing=4),
            style=ft.ButtonStyle(
                color=Colors.ON_PRIMARY_CONTAINER,
                bgcolor=Colors.PRIMARY_CONTAINER,
                side=ft.BorderSide(1, Colors.PRIMARY_CONTAINER),
                shape=ft.RoundedRectangleBorder(radius=8)
            ),
            height=36,
            on_click=self._start_scan
        )

        return ft.Container(
            bgcolor=Colors.SURFACE_CONTAINER_HIGH,
            border=border_bottom(1, Colors.OUTLINE_VARIANT),
            padding=ft.padding.Padding(12, 8, 12, 8),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=16,
                        controls=[
                            ft.Text(
                                "违规软件内容检测器",
                                size=18,
                                weight=ft.FontWeight.W_600,
                                color=Colors.PRIMARY
                            ),
                            ft.Column(
                                spacing=0,
                                controls=[
                                    self.name_field,
                                    name_hint
                                ]
                            )
                        ]
                    ),
                    ft.Row(
                        spacing=12,
                        controls=[
                            toolbar,
                            self.cancel_btn,
                            self.start_btn
                        ]
                    )
                ]
            ),
            height=64
        )

    def _toolbar_btn(self, icon: str, tooltip: str, on_click) -> ft.IconButton:
        return ft.IconButton(
            icon=icon,
            icon_size=18,
            icon_color=Colors.ON_SURFACE_VARIANT,
            tooltip=tooltip,
            on_click=on_click,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=0),
                padding=8
            )
        )

    # ── 侧边栏 ─────────────────────────────────────────────────
    def _build_sidebar(self) -> ft.Container:
        # 统计项数值引用
        self.stat_install = ft.Text("0", size=12, weight=ft.FontWeight.W_500, color=Colors.PRIMARY)
        self.stat_log = ft.Text("0", size=12, weight=ft.FontWeight.W_500, color=Colors.SECONDARY)
        self.stat_doc = ft.Text("0", size=12, weight=ft.FontWeight.W_500, color=Colors.ON_SURFACE)
        self.stat_registry = ft.Text("0", size=12, weight=ft.FontWeight.W_500, color=Colors.TERTIARY)

        # 日志列表
        self.log_list = ft.Column(
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=[
                ft.Text("> 系统就绪", size=10, color=Colors.ON_SURFACE_VARIANT, opacity=0.7)
            ]
        )

        return ft.Container(
            width=240,
            bgcolor=Colors.SURFACE_CONTAINER,
            border=border_right(1, Colors.OUTLINE_VARIANT),
            content=ft.Column(
                spacing=0,
                controls=[
                    # 统计面板
                    ft.Container(
                        padding=12,
                        border=border_bottom(1, Colors.OUTLINE_VARIANT),
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                ft.Text("[ 统计面板 ]", size=10, color=Colors.PRIMARY),
                                ft.Text("SUMMARY STATS", size=11, weight=ft.FontWeight.W_700,
                                        color=Colors.ON_SURFACE_VARIANT),
                                self._stat_item(ft.Icons.INSTALL_DESKTOP, "安装程序", self.stat_install),
                                self._stat_item(ft.Icons.HISTORY, "日志", self.stat_log),
                                self._stat_item(ft.Icons.DESCRIPTION, "文档", self.stat_doc),
                                self._stat_item(ft.Icons.DATA_OBJECT, "注册表", self.stat_registry),
                            ]
                        )
                    ),
                    # 日志面板
                    ft.Container(
                        padding=ft.padding.Padding(12, 8, 12, 8),
                        expand=True,
                        content=ft.Column(
                            spacing=4,
                            expand=True,
                            controls=[
                                ft.Text("[ 运行日志 ]", size=10, color=Colors.SECONDARY),
                                ft.Text("SYSTEM LOG", size=11, weight=ft.FontWeight.W_700,
                                        color=Colors.ON_SURFACE_VARIANT),
                                self.log_list,
                            ]
                        )
                    ),
                    # 操作提示
                    ft.Container(
                        padding=ft.padding.Padding(12, 8, 12, 8),
                        border=border_bottom(1, Colors.OUTLINE_VARIANT),
                        content=ft.Column(
                            spacing=4,
                            controls=[
                                ft.Text("快捷操作", size=10, color=Colors.ON_SURFACE_VARIANT),
                                ft.Text("Ctrl+A 全选  |  Ctrl+C 复制", size=10, color=Colors.ON_SURFACE_VARIANT, opacity=0.6),
                                ft.Text("Delete 删除所选", size=10, color=Colors.ON_SURFACE_VARIANT, opacity=0.6),
                            ]
                        )
                    )
                ]
            )
        )

    def _stat_item(self, icon: str, label: str, value_text: ft.Text) -> ft.Row:
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(icon, size=16, color=Colors.ON_SURFACE_VARIANT),
                        ft.Text(label, size=12, color=Colors.ON_SURFACE_VARIANT)
                    ]
                ),
                value_text
            ]
        )

    # ── 主内容区 ────────────────────────────────────────────────
    def _build_main_content(self) -> ft.Column:
        return ft.Column(
            spacing=0,
            expand=True,
            controls=[
                self._build_progress_section(),
                self._build_tree_view()
            ]
        )

    def _build_progress_section(self) -> ft.Container:
        # 统计文本
        self.scanned_text = ft.Text("0", size=14, weight=ft.FontWeight.W_500, color=Colors.ON_SURFACE)
        self.found_text = ft.Text("0", size=14, weight=ft.FontWeight.W_500, color=Colors.TERTIARY)
        self.speed_text = ft.Text("0/s", size=14, weight=ft.FontWeight.W_500, color=Colors.SECONDARY)
        self.elapsed_text = ft.Text("00:00", size=14, weight=ft.FontWeight.W_500, color=Colors.PRIMARY)

        # 进度条段落（支持阶段动画）
        self.progress_segments = [
            ft.Container(bgcolor=Colors.PRIMARY, height=6, expand=True, opacity=0.3,
                         border_radius=border_radius_only(top_left=3, bottom_left=3)),
            ft.Container(bgcolor=Colors.SECONDARY, height=6, expand=True, opacity=0.3),
            ft.Container(bgcolor=Colors.PRIMARY_CONTAINER, height=6, expand=True, opacity=0.3,
                         border_radius=border_radius_only(top_right=3, bottom_right=3))
        ]

        return ft.Container(
            bgcolor=Colors.SURFACE_CONTAINER_LOW,
            border=border_bottom(1, Colors.OUTLINE_VARIANT),
            padding=12,
            content=ft.Column(
                spacing=8,
                controls=[
                    # 统计行
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=24,
                                controls=[
                                    self._progress_stat("已扫描", self.scanned_text),
                                    self._progress_stat("发现数", self.found_text),
                                    self._progress_stat("速度", self.speed_text),
                                ]
                            ),
                            self._progress_stat("用时", self.elapsed_text)
                        ]
                    ),
                    # 三阶段进度条
                    ft.Row(
                        spacing=4,
                        controls=[
                            ft.Icon(ft.Icons.INFO, size=12, color=Colors.ON_SURFACE_VARIANT),
                            ft.Text("三阶段扫描进度 (注册表 -> 固定路径 -> 全盘)",
                                    size=10, color=Colors.ON_SURFACE_VARIANT)
                        ]
                    ),
                    ft.Row(
                        spacing=0,
                        controls=self.progress_segments
                    ),
                    # 阶段标签
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("注册表", size=10, color=Colors.ON_SURFACE_VARIANT),
                            ft.Text("固定路径", size=10, color=Colors.ON_SURFACE_VARIANT),
                            ft.Text("全盘扫描", size=10, color=Colors.ON_SURFACE_VARIANT),
                        ]
                    )
                ]
            )
        )

    def _progress_stat(self, label: str, value_text: ft.Text) -> ft.Column:
        return ft.Column(
            spacing=2,
            controls=[
                ft.Text(label, size=11, weight=ft.FontWeight.W_700,
                        color=Colors.ON_SURFACE_VARIANT),
                value_text
            ]
        )

    # ── 树形视图 ────────────────────────────────────────────────
    def _build_tree_view(self) -> ft.Container:
        self.tree_container = ft.Column(
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )

        return ft.Container(
            padding=16,
            expand=True,
            content=ft.Container(
                border=border_all(1, Colors.OUTLINE_VARIANT),
                border_radius=8,
                bgcolor=Colors.SURFACE_CONTAINER_LOWEST,
                content=ft.Column(
                    spacing=0,
                    controls=[
                        # 表头
                        ft.Container(
                            bgcolor=Colors.SURFACE_CONTAINER_HIGH,
                            border=border_bottom(1, Colors.OUTLINE_VARIANT),
                            padding=ft.padding.Padding(12, 8, 12, 8),
                            content=ft.Row(
                                controls=[
                                    ft.Container(
                                        width=32,
                                        content=ft.Checkbox(
                                            value=False,
                                            fill_color=Colors.PRIMARY,
                                            check_color=Colors.ON_PRIMARY_CONTAINER,
                                            on_change=self._toggle_all
                                        ),
                                        alignment=alignment_center
                                    ),
                                    ft.Container(
                                        width=60,
                                        content=ft.TextButton(
                                            "取消",
                                            style=ft.ButtonStyle(
                                                color=Colors.ON_SURFACE_VARIANT,
                                                padding=0,
                                                text_style=ft.TextStyle(size=9)
                                            ),
                                            on_click=lambda _: self._deselect_all(None),
                                            tooltip="取消全选"
                                        ),
                                        alignment=alignment_center
                                    ),
                                    ft.Container(
                                        expand=True,
                                        content=ft.Text("名称 / 目标", size=11, weight=ft.FontWeight.W_700,
                                                        color=Colors.ON_SURFACE_VARIANT)
                                    ),
                                    ft.Container(
                                        width=400,
                                        content=ft.Text("路径", size=11, weight=ft.FontWeight.W_700,
                                                        color=Colors.ON_SURFACE_VARIANT)
                                    ),
                                    ft.Container(
                                        width=96,
                                        alignment=alignment_center_right,
                                        content=ft.Text("大小", size=11, weight=ft.FontWeight.W_700,
                                                        color=Colors.ON_SURFACE_VARIANT)
                                    )
                                ]
                            )
                        ),
                        # 树形内容
                        self.tree_container
                    ]
                )
            )
        )

    def _build_tree_row(self, is_group: bool, name: str, path: str, size: str,
                        file_type: str = "", item_count: int = 0,
                        is_checked: bool = False, indent: int = 0,
                        result_id: str = "") -> ft.Container:
        # 图标
        if is_group:
            icon = ft.Icon(ft.Icons.KEYBOARD_ARROW_RIGHT, size=16, color=Colors.ON_SURFACE_VARIANT)
            type_icon = ft.Icon(ft.Icons.FOLDER, size=18, color=Colors.SECONDARY)
            name_color = Colors.ON_SURFACE
        else:
            icon = ft.Container(width=16)
            if file_type in ["exe", "msi"]:
                type_icon = ft.Icon(ft.Icons.INSTALL_DESKTOP, size=18, color=Colors.TERTIARY)
            elif file_type in ["log", "txt"]:
                type_icon = ft.Icon(ft.Icons.HISTORY, size=16, color=Colors.ON_SURFACE_VARIANT)
            else:
                type_icon = ft.Icon(ft.Icons.DESCRIPTION, size=18, color=Colors.ON_SURFACE_VARIANT)
            name_color = Colors.TERTIARY if file_type in ["exe", "msi"] else Colors.ON_SURFACE

        # 右键上下文菜单
        full_path = result_id or os.path.join(path, name)  # 完整文件路径
        ctx_menu = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT, icon_size=14,
            icon_color=Colors.ON_SURFACE_VARIANT,
            tooltip="更多操作",
            bgcolor=Colors.SURFACE_CONTAINER_HIGH,
            items=[
                ft.PopupMenuItem(
                    content="打开文件位置",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e, p=full_path: open_explorer_at(p),
                ),
                ft.PopupMenuItem(
                    content="复制路径",
                    icon=ft.Icons.COPY,
                    on_click=lambda e, p=full_path: self._copy_single_path(p),
                ),
            ]
        )

        # 复选框 - 绑定选择事件
        rid = result_id or path
        def _on_check(e, _rid=rid):
            if e.control.value:
                self._selected_items.add(_rid)
            else:
                self._selected_items.discard(_rid)

        checkbox = ft.Checkbox(
            value=is_checked,
            fill_color=Colors.PRIMARY,
            check_color=Colors.ON_PRIMARY_CONTAINER,
            data=rid,
            on_change=_on_check,
        )

        # 标签
        name_text = ft.Text(
            name,
            size=12,
            weight=ft.FontWeight.W_500,
            color=name_color
        )

        # 路径（可点击打开资源管理器）
        path_text = ft.Text(
            path,
            size=11,
            color=Colors.ON_SURFACE_VARIANT,
            overflow=ft.TextOverflow.ELLIPSIS,
            no_wrap=True,
            expand=True,
            selectable=True,
        )

        # 大小
        size_text = ft.Text(
            size,
            size=11,
            color=Colors.ON_SURFACE_VARIANT,
            text_align=ft.TextAlign.RIGHT
        )

        # 项目数量标签
        count_badge = ft.Container()
        if is_group and item_count > 0:
            count_badge = ft.Container(
                bgcolor=Colors.SURFACE_VARIANT,
                border_radius=4,
                padding=ft.padding.Padding(6, 2, 6, 2),
                content=ft.Text(f"{item_count} items", size=10, color=Colors.ON_SURFACE_VARIANT)
            )

        # 构建行
        left_indent = 12 + (indent * 24)
        is_child = indent > 0

        # 分组行点击折叠/展开
        row_on_click = None
        if is_group:
            def _group_click(e, _rid=rid, _icon=icon):
                self._toggle_group(_rid, _icon)
            row_on_click = _group_click

        row = ft.Container(
            bgcolor=Colors.SURFACE_VARIANT if is_child else Colors.SURFACE_CONTAINER_LOWEST,
            border=border_left_bottom(
                2, Colors.PRIMARY if is_child else Colors.TRANSPARENT,
                1, Colors.OUTLINE_VARIANT
            ),
            padding=ft.padding.Padding(left_indent, 8, 12, 8),
            on_hover=lambda e: self._on_row_hover(e, is_child),
            on_click=row_on_click,
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Container(width=32, content=checkbox, alignment=alignment_center),
                    ft.Row(
                        spacing=8,
                        controls=[icon, type_icon, name_text, count_badge],
                        expand=True
                    ),
                    ft.Container(
                        width=400,
                        content=path_text,
                        on_click=lambda e, p=full_path: open_explorer_at(p),
                        on_hover=lambda e: self._on_path_hover(e),
                        data=full_path,
                    ),
                    ft.Container(
                        width=96,
                        alignment=alignment_center_right,
                        content=size_text
                    ),
                    ft.Container(width=32, content=ctx_menu, alignment=alignment_center),
                ]
            )
        )

        return row

    def _on_row_hover(self, e, is_child: bool):
        if e.data == "true":
            e.control.bgcolor = Colors.SURFACE_VARIANT if is_child else Colors.SURFACE_CONTAINER_HIGHEST
        else:
            e.control.bgcolor = Colors.SURFACE_VARIANT if is_child else Colors.SURFACE_CONTAINER_LOWEST
        e.control.update()

    def _on_path_hover(self, e):
        """路径悬停时变色"""
        if e.data == "true":
            e.control.content.color = Colors.PRIMARY
        else:
            e.control.content.color = Colors.ON_SURFACE_VARIANT
        e.control.content.update()

    def _toggle_all(self, e):
        """表头复选框全选/取消全选"""
        checked = e.control.value
        self._selected_items.clear()
        if checked:
            for r in self._results:
                rid = os.path.join(r.path, r.filename)
                self._selected_items.add(rid)
        # 遍历 tree_container 中所有 checkbox 并同步状态
        for ctrl in self.tree_container.controls:
            self._sync_checkbox(ctrl, checked)
        self.tree_container.update()

    def _sync_checkbox(self, container, value):
        """递归同步复选框状态（只更新值，不单独调用 update）"""
        if hasattr(container, 'content'):
            content = container.content
            if isinstance(content, ft.Checkbox):
                content.value = value
                return
            if hasattr(content, 'controls'):
                for child in content.controls:
                    self._sync_checkbox(child, value)
        if hasattr(container, 'controls'):
            for child in container.controls:
                self._sync_checkbox(child, value)

    # ── 底部状态栏 ──────────────────────────────────────────────
    def _build_footer(self) -> ft.Container:
        self.status_text = ft.Text(
            "提示：点击路径可打开资源管理器。删除操作将移入回收站。",
            size=12,
            color=Colors.ON_SURFACE_VARIANT
        )
        self.footer_status = ft.Text(
            "系统版本 v6.0 | 运行状态：就绪",
            size=12,
            color=Colors.ON_SURFACE_VARIANT,
            opacity=0.5
        )

        return ft.Container(
            bgcolor=Colors.SURFACE_CONTAINER_LOW,
            border=border_bottom(1, Colors.OUTLINE_VARIANT),
            padding=ft.padding.Padding(12, 0, 12, 0),
            height=32,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.INFO, size=14, color=Colors.PRIMARY),
                            self.status_text
                        ]
                    ),
                    ft.Row(
                        spacing=16,
                        controls=[self.footer_status]
                    )
                ]
            )
        )

    # ── 扫描流程 ────────────────────────────────────────────────
    def _start_scan(self, e):
        name = self.name_field.value.strip() if self.name_field.value else ""
        if not name:
            self.name_field.border_color = Colors.TERTIARY_CONTAINER
            self.status_text.value = "请输入姓名"
            self.page.update()
            return

        self.name_field.border_color = Colors.OUTLINE_VARIANT

        self._scanning = True
        self._cancel_requested = False
        self._results = []
        self._selected_items.clear()
        self.tree_container.controls.clear()
        self._group_items.clear()
        self._collapsed_groups.clear()

        # 重置进度段
        self._scan_phase = 0
        self._scan_start_time = time.time()
        for seg in self.progress_segments:
            seg.opacity = 0.3

        self.start_btn_text.value = "扫描中..."
        self.start_btn.disabled = True
        self.cancel_btn.disabled = False

        self.status_text.value = "扫描中 - 正在检查注册表..."
        self.footer_status.value = "系统版本 v6.0 | 运行状态：扫描中"
        self.page.update()
        self._log("开始扫描")

        # 活动指示器
        self._scan_dots = 0
        self._scan_timer = None
        drives = get_available_drives()

        def _animate():
            """活动指示器 - 让用户知道程序还在运行"""
            if not self._scanning:
                return
            # 全盘扫描阶段有精确进度显示，停止动画定时器
            if "全盘扫描" in (self.status_text.value or ""):
                return
            self._scan_dots = (self._scan_dots + 1) % 4
            dots = "." * self._scan_dots
            current = self.status_text.value or "扫描中"
            # 从状态文本中提取已发现数量，追加到状态栏
            found_m = re.search(r'已发现 (\d+) 项', current)
            found_tag = f" | 已发现 {found_m.group(1)} 项" if found_m else ""
            # 计算已用时间
            elapsed = time.time() - self._scan_start_time
            elapsed_tag = f" | {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
            base = re.sub(r'\.+$', '', current).rstrip("。")
            self.status_text.value = f"{base}{dots}{found_tag}{elapsed_tag}"
            self.status_text.update()
            # 继续动画（1 秒间隔，提供清晰反馈）
            if self._scanning:
                self._scan_timer = threading.Timer(1.0, lambda: self.page.run_thread(_animate))
                self._scan_timer.daemon = True
                self._scan_timer.start()

        def _stage_update(stage_msg):
            """阶段回调 - 从工作线程调用"""
            self.page.run_thread(self._update_stage, stage_msg)

        def run():
            try:
                # 启动动画
                self.page.run_thread(_animate)

                # 调用 on_scan，传入进度回调和阶段回调
                results = self.on_scan(drives, self._update_progress, _stage_update)
                self._results = results
                if not self._cancel_requested:
                    self.page.run_thread(self._populate_tree, results)
            except Exception as ex:
                self.page.run_thread(self._show_error, str(ex))
            finally:
                # 停止动画定时器
                if self._scan_timer:
                    self._scan_timer.cancel()
                self.page.run_thread(self._scan_done)

        threading.Thread(target=run, daemon=True).start()

    def _cancel_scan(self, e):
        self._cancel_requested = True
        self._scanning = False
        if self.on_cancel:
            self.on_cancel()
        self.status_text.value = "已取消"
        self.footer_status.value = "系统版本 v6.0 | 运行状态：已取消"
        self.page.update()

    def _update_stage(self, stage_msg: str):
        """更新扫描阶段信息 - 在 UI 线程中执行"""
        try:
            # 提取已发现数量
            m = re.search(r'已发现 (\d+) 项', stage_msg)
            if m:
                self.found_text.value = m.group(1)
                # 更新已用时间
                elapsed = time.time() - self._scan_start_time
                self.elapsed_text.value = f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"

            self.status_text.value = f"扫描中 - {stage_msg}"
            self._log(stage_msg)
            # 更新进度条阶段指示
            if "注册表" in stage_msg:
                self._scan_phase = 1
            elif "固定路径" in stage_msg:
                self._scan_phase = 2
            elif "全盘扫描" in stage_msg:
                self._scan_phase = 3
            # 更新段落透明度：已完成=1.0, 当前=1.0, 未开始=0.3
            for i, seg in enumerate(self.progress_segments):
                if i < self._scan_phase:
                    seg.opacity = 1.0
                else:
                    seg.opacity = 0.3
            self.page.update()
        except Exception:
            pass

    def _update_progress(self, progress: ScanProgress):
        """从工作线程调用，将数据传到 UI 线程更新"""
        if not self._scanning:
            return
        # GUI 层节流：每秒刷新一次
        now = time.time()
        if now - self._last_progress_update < 1.0:
            return
        self._last_progress_update = now
        elapsed = now - progress.start_time
        data = {
            'scanned': f"{progress.scanned_count:,}",
            'found': str(progress.found_count),
            'speed': f"{progress.speed:,.0f}/s",
            'elapsed': f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        }
        self.page.run_thread(self._refresh_progress, data)

    def _refresh_progress(self, data):
        """在 UI 线程中更新进度显示 - 批量更新"""
        try:
            self.scanned_text.value = data['scanned']
            self.found_text.value = data['found']
            self.speed_text.value = data['speed']
            self.elapsed_text.value = data['elapsed']
            self.status_text.value = (
                f"全盘扫描中 - 已扫描 {data['scanned']} 个文件, "
                f"发现 {data['found']} 项 ({data['speed']})"
            )
            # 批量更新：1 次 page.update() 替代 5 次独立 control.update()
            self.page.update()
        except Exception:
            pass

    def _scan_done(self):
        self._scanning = False
        self.start_btn_text.value = "开始扫描"
        self.start_btn.disabled = False
        self.cancel_btn.disabled = True

        # 用户主动取消，不覆盖状态
        if self._cancel_requested:
            self.page.update()
            return

        total = len(self._results)
        groups = len(self._group_results(self._results))
        self.status_text.value = f"扫描完成, 发现 {total} 个违规文件 ({groups} 个目录)"
        self.footer_status.value = f"系统版本 v6.0 | 运行状态：已完成 (发现 {total} 项)"
        self._log(f"扫描完成，发现 {total} 项")
        self.page.update()

        if total:
            self._auto_notify()

    def _show_error(self, msg: str):
        self.status_text.value = f"扫描出错: {msg}"
        self.page.update()

    # ── 自动上报 ────────────────────────────────────────────────
    def _auto_notify(self):
        name = self.name_field.value.strip() if self.name_field.value else ""
        self.status_text.value = f"扫描完成, 发现 {len(self._results)} 个违规文件 - 正在上报..."
        self.page.update()

        def _send():
            result = self.on_notify(name, self._results, "")
            self.page.run_thread(self._notify_done, result)

        def _push():
            result = self.on_smartsheet(name, self._results, "") if self.on_smartsheet else {"success": True}
            self.page.run_thread(self._sheet_done, result)

        threading.Thread(target=_send, daemon=True).start()
        threading.Thread(target=_push, daemon=True).start()

    def _notify_done(self, r):
        tag = "报警已发送" if r.get("success") else f"报警失败: {r.get('message', '')}"
        current = self.status_text.value.split('-')[0].strip() if self.status_text.value else ""
        self.status_text.value = f"{current} - {tag}"
        self.page.update()

    def _sheet_done(self, r):
        tag = "智能表已同步" if r.get("success") else f"智能表失败: {r.get('message', '')}"
        current = self.status_text.value if self.status_text.value else ""
        self.status_text.value = f"{current} ; {tag}"
        self.page.update()

    # ── 结果填充 ────────────────────────────────────────────────
    def _group_results(self, results: List[DetectionResult]) -> Dict[str, List[DetectionResult]]:
        groups: Dict[str, List[DetectionResult]] = defaultdict(list)
        for r in results:
            groups[r.path].append(r)
        return groups

    def _populate_tree(self, results: List[DetectionResult]):
        self.tree_container.controls.clear()
        self._group_items.clear()
        self._collapsed_groups.clear()

        groups = self._group_results(results)

        for dir_path, items in sorted(groups.items()):
            if len(items) == 1:
                r = items[0]
                row = self._build_tree_row(
                    is_group=False,
                    name=r.filename,
                    path=r.path,  # 只显示目录路径
                    size=self._format_size(r.size),
                    file_type=r.file_type,
                    result_id=os.path.join(r.path, r.filename)
                )
                self.tree_container.controls.append(row)
            else:
                total_size = sum(i.size for i in items)
                dir_name = os.path.basename(dir_path) or dir_path

                # 分组行
                group_row = self._build_tree_row(
                    is_group=True,
                    name=dir_name,
                    path=dir_path,
                    size=self._format_size(total_size),
                    item_count=len(items),
                    result_id=dir_path
                )
                self.tree_container.controls.append(group_row)

                # 子项（默认折叠）
                child_rows = []
                for r in items:
                    child_row = self._build_tree_row(
                        is_group=False,
                        name=r.filename,
                        path=r.path,  # 只显示目录路径
                        size=self._format_size(r.size),
                        file_type=r.file_type,
                        indent=1,
                        result_id=os.path.join(r.path, r.filename)
                    )
                    child_row.visible = False  # 默认折叠
                    self.tree_container.controls.append(child_row)
                    child_rows.append(child_row)
                # 注册分组子项映射，并标记为已折叠
                self._group_items[dir_path] = child_rows
                self._collapsed_groups.add(dir_path)

        self.tree_container.update()

        # 更新侧边栏统计
        self._update_stats(results)

    def _format_size(self, size: int) -> str:
        if size == 0:
            return "-"
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _update_stats(self, results: List[DetectionResult]):
        """更新侧边栏统计面板"""
        install_count = 0
        log_count = 0
        doc_count = 0
        registry_count = 0
        for r in results:
            if r.source == "注册表":
                registry_count += 1
            elif r.file_type in ("安装程序", "安装目录", "安装本体"):
                install_count += 1
            elif "日志" in r.file_type:
                log_count += 1
            elif "文档" in r.file_type:
                doc_count += 1
        if self.stat_install:
            self.stat_install.value = str(install_count)
            self.stat_install.update()
        if self.stat_log:
            self.stat_log.value = str(log_count)
            self.stat_log.update()
        if self.stat_doc:
            self.stat_doc.value = str(doc_count)
            self.stat_doc.update()
        if self.stat_registry:
            self.stat_registry.value = str(registry_count)
            self.stat_registry.update()

    # ── 工具栏操作 ──────────────────────────────────────────────
    def _delete_selected(self, e):
        if not self.on_delete:
            self.status_text.value = "删除功能未启用"
            self.status_text.update()
            return

        # 确定待删除项
        if self._selected_items:
            targets = [r for r in self._results
                       if os.path.join(r.path, r.filename) in self._selected_items]
        else:
            self.status_text.value = "请先勾选要删除的文件"
            self.status_text.update()
            return

        if not targets:
            self.status_text.value = "无选中项可删除"
            self.status_text.update()
            return

        count = len(targets)

        # 确认对话框
        def _confirm_delete(dlg):
            self.page.pop_dialog()
            paths = [os.path.join(r.path, r.filename) for r in targets]

            def _do():
                errors = self.on_delete(paths)
                self.page.run_thread(self._delete_done, paths, errors)

            threading.Thread(target=_do, daemon=True).start()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认删除"),
            content=ft.Text(f"确定要将 {count} 个文件移入回收站吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("确定", on_click=lambda _: _confirm_delete(dialog)),
            ],
        )
        self.page.show_dialog(dialog)

    def _delete_done(self, file_paths, errors):
        # 只移除成功删除的文件
        error_paths = set()
        for err in errors:
            if ":" in err:
                error_paths.add(err.split(":")[0].strip())

        success_paths = [p for p in file_paths if p not in error_paths]
        deleted_set = set(success_paths)

        self._results = [r for r in self._results
                         if os.path.join(r.path, r.filename) not in deleted_set]
        self._selected_items.clear()
        self._populate_tree(self._results)

        success_count = len(success_paths)
        if errors:
            self.status_text.value = f"已删除 {success_count} 个文件, {len(errors)} 个失败"
            self._log(f"删除 {success_count} 成功, {len(errors)} 失败")
        else:
            self.status_text.value = f"已成功删除 {success_count} 个文件, 剩余 {len(self._results)} 个违规项"
            self._log(f"删除 {success_count} 个文件成功")
        self.page.update()

    def _select_all(self, e):
        """工具栏全选按钮"""
        self._selected_items.clear()
        for r in self._results:
            rid = os.path.join(r.path, r.filename)
            self._selected_items.add(rid)
        # 同步 UI 中的复选框状态
        for ctrl in self.tree_container.controls:
            self._sync_checkbox(ctrl, True)
        self.tree_container.update()
        self.status_text.value = f"已选择 {len(self._selected_items)} 项"
        self.page.update()

    def _copy_paths(self, e):
        # 优先复制选中项，否则复制全部
        if self._selected_items:
            items = [r for r in self._results
                     if os.path.join(r.path, r.filename) in self._selected_items]
        else:
            items = self._results

        if not items:
            self.status_text.value = "无结果可复制"
            self.status_text.update()
            return

        text = "\n".join(os.path.join(r.path, r.filename) for r in items)
        if pyperclip:
            try:
                pyperclip.copy(text)
                self.status_text.value = f"已复制 {len(items)} 条路径到剪贴板"
            except Exception:
                self.status_text.value = "复制失败，请手动复制"
        else:
            self.status_text.value = "复制功能不可用"
        self.page.update()

    def _clean_registry(self, e):
        if not self.on_clean_registry:
            self.status_text.value = "该功能未启用"
            self.status_text.update()
            return

        # 确认对话框
        def _confirm_clean(dlg):
            self.page.pop_dialog()

            def _do():
                deleted, errors = self.on_clean_registry()
                self.page.run_thread(self._clean_done, deleted, errors)

            threading.Thread(target=_do, daemon=True).start()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("确认清理注册表"),
            content=ft.Text("确定要删除钉钉相关的注册表项吗？"),
            actions=[
                ft.TextButton("取消", on_click=lambda _: self.page.pop_dialog()),
                ft.TextButton("确定", on_click=lambda _: _confirm_clean(dialog)),
            ],
        )
        self.page.show_dialog(dialog)

    def _clean_done(self, deleted, errors):
        msg = f"已删除 {deleted} 个相关注册表项。"
        if errors:
            msg += f" ({len(errors)} 个失败)"
        self.status_text.value = msg
        self.page.update()

    # ── 窗口事件 & 键盘快捷键 ──────────────────────────────

    def _on_window_event(self, e):
        """窗口关闭事件 - 停止扫描"""
        if e.type == "close":
            if self._scanning:
                self._cancel_requested = True
                self._scanning = False
                if self.on_cancel:
                    self.on_cancel()

    def _on_keyboard_event(self, e: ft.KeyboardEvent):
        """键盘快捷键"""
        # Delete 键删除选中项
        if e.key == "Delete" and not e.ctrl and not e.shift and not e.alt:
            self._delete_selected(None)
            return
        if not e.ctrl:
            return
        if e.key == "a" and not e.shift and not e.alt:
            # Ctrl+A 全选
            self._select_all(None)
        elif e.key == "c" and not e.shift and not e.alt:
            # Ctrl+C 复制路径
            self._copy_paths(None)
        elif e.key == "d" and not e.shift and not e.alt:
            # Ctrl+D 取消全选
            self._deselect_all(None)

    # ── 分组折叠/展开 ──────────────────────────────────────

    def _toggle_group(self, group_path: str, icon: ft.Icon):
        """切换分组行的折叠/展开状态"""
        if group_path in self._collapsed_groups:
            self._collapsed_groups.discard(group_path)
            icon.name = ft.Icons.KEYBOARD_ARROW_DOWN
        else:
            self._collapsed_groups.add(group_path)
            icon.name = ft.Icons.KEYBOARD_ARROW_RIGHT

        # 显示/隐藏子项
        children = self._group_items.get(group_path, [])
        for child in children:
            child.visible = group_path not in self._collapsed_groups
        self.page.update()

    def _deselect_all(self, e):
        """取消全选"""
        self._selected_items.clear()
        for ctrl in self.tree_container.controls:
            self._sync_checkbox(ctrl, False)
        self.tree_container.update()
        self.status_text.value = "已取消选择"
        self.page.update()

    def _copy_single_path(self, path: str):
        """复制单个路径到剪贴板"""
        if pyperclip:
            try:
                pyperclip.copy(path)
                self.status_text.value = f"已复制: {path}"
                self.page.update()
            except Exception:
                pass

    def _log(self, msg: str):
        """向日志面板追加一条记录"""
        if not self.log_list:
            return
        ts = time.strftime("%H:%M:%S")
        self.log_list.controls.append(
            ft.Text(f"> [{ts}] {msg}", size=10, color=Colors.ON_SURFACE_VARIANT, opacity=0.8)
        )
        # 最多保留 50 条日志
        if len(self.log_list.controls) > 50:
            self.log_list.controls.pop(0)
        try:
            self.log_list.update()
        except Exception:
            pass
