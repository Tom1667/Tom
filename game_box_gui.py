# game_box_gui_improved.py - 改进版游戏盒子GUI主程序

import sys
import os
import logging
import asyncio
import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
from pathlib import Path
import json
import threading
from typing import List, Dict, Optional, Set
import httpx
import subprocess
from PIL import Image, ImageTk
import io
import re
import time
from datetime import datetime
import pickle
import weakref
import webbrowser

# 确保ttkbootstrap正确导入
try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *

    # 设置默认主题，避免初始化问题
    ttk.Style.instance = None
except ImportError:
    messagebox.showerror("依赖缺失",
                         "错误: ttkbootstrap 库未安装。\n请在命令行中使用 'pip install ttkbootstrap' 命令安装后重试。")
    sys.exit(1)

# Import the backend
try:
    from backend_gui import GuiBackend
except ImportError as e:
    print(f"导入backend_gui失败: {e}")
    messagebox.showerror("文件缺失",
                         f"错误: backend_gui.py 文件缺失或有错误。\n{str(e)}\n请确保主程序和后端文件在同一个目录下。")
    sys.exit(1)


# Cache Manager Class
class CacheManager:
    """缓存管理器，用于保存和加载游戏信息、图片等"""

    def __init__(self, base_path: Path):
        self.cache_dir = base_path / "cache"
        self.cache_dir.mkdir(exist_ok=True)

        # 打印缓存目录位置，方便调试
        print(f"缓存目录: {self.cache_dir.absolute()}")

        self.images_dir = self.cache_dir / "images"
        self.images_dir.mkdir(exist_ok=True)

        self.game_info_file = self.cache_dir / "game_info.json"
        self.settings_file = self.cache_dir / "settings.json"
        self.installed_games_file = self.cache_dir / "installed_games.json"
        self.game_list_file = self.cache_dir / "game_list.json"
        self.custom_repos_file = self.cache_dir / "custom_repos.json"
        self.repo_config_file = self.cache_dir / "repo_config.json"  # 新增：仓库配置文件

        self.game_info_cache = self.load_game_info()
        self.settings_cache = self.load_settings()
        self.installed_games_cache = self.load_installed_games()
        self.game_list_cache = self.load_game_list()
        self.custom_repos_cache = self.load_custom_repos()
        self.repo_config = self.load_repo_config()  # 新增：加载仓库配置

    def load_repo_config(self) -> Dict:
        """加载仓库配置（哪些仓库被选中）"""
        if self.repo_config_file.exists():
            try:
                with open(self.repo_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保包含所有仓库列表
                    if 'all_repos' not in config:
                        config['all_repos'] = self.get_default_repos()
                    return config
            except:
                pass
        # 默认配置
        return {
            "selected_repos": ["swa"],
            "all_repos": self.get_default_repos()
        }

    def get_default_repos(self) -> List[Dict]:
        """获取默认仓库列表"""
        return [
            {"name": "SWA V2库", "path": "swa", "type": "zip"},
            {"name": "Cysaw库", "path": "cysaw", "type": "zip"},
            {"name": "Furcate库", "path": "furcate", "type": "zip"},
            {"name": "CNGS库", "path": "cngs", "type": "zip"},
            {"name": "SteamDatabase库", "path": "steamdatabase", "type": "zip"},
            {"name": "Auiowu/ManifestAutoUpdate", "path": "Auiowu/ManifestAutoUpdate", "type": "github"},
            {"name": "SteamAutoCracks/ManifestHub", "path": "SteamAutoCracks/ManifestHub", "type": "github"}
        ]

    def save_repo_config(self, config: Dict):
        """保存仓库配置"""
        try:
            with open(self.repo_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_game_info(self) -> Dict:
        """加载游戏信息缓存"""
        if self.game_info_file.exists():
            try:
                with open(self.game_info_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_game_info(self):
        """保存游戏信息缓存"""
        try:
            with open(self.game_info_file, 'w', encoding='utf-8') as f:
                json.dump(self.game_info_cache, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_settings(self) -> Dict:
        """加载设置缓存"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_settings(self, settings: Dict):
        """保存设置缓存"""
        try:
            self.settings_cache = settings
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_installed_games(self) -> Dict:
        """加载已安装游戏缓存"""
        if self.installed_games_file.exists():
            try:
                with open(self.installed_games_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception as e:
                print(f"加载已安装游戏缓存失败: {str(e)}")
                return {}
        return {}

    def save_installed_games(self):
        """保存已安装游戏缓存"""
        try:
            with open(self.installed_games_file, 'w', encoding='utf-8') as f:
                json.dump(self.installed_games_cache, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"保存已安装游戏缓存失败: {str(e)}")

    def load_game_list(self) -> List[Dict]:
        """加载完整游戏列表缓存"""
        if self.game_list_file.exists():
            try:
                with open(self.game_list_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_game_list(self, game_list: List[Dict]):
        """保存完整游戏列表缓存"""
        try:
            with open(self.game_list_file, 'w', encoding='utf-8') as f:
                json.dump(game_list, f, ensure_ascii=False, indent=2)
        except:
            pass

    def load_custom_repos(self) -> List[Dict]:
        """加载自定义仓库列表（已废弃，保留兼容性）"""
        return []

    def save_custom_repos(self, repos: List[Dict]):
        """保存自定义仓库列表（已废弃，保留兼容性）"""
        pass

    def set_game_info(self, app_id: str, info: Dict):
        """设置游戏信息缓存"""
        app_id = str(app_id)
        self.game_info_cache[app_id] = info
        self.save_game_info()

    def get_installed_game_name(self, app_id: str) -> Optional[str]:
        """获取已安装游戏的名称"""
        return self.installed_games_cache.get(str(app_id))

    def set_installed_game_name(self, app_id: str, name: str):
        """设置已安装游戏的名称"""
        app_id = str(app_id)
        self.installed_games_cache[app_id] = name
        self.save_installed_games()

    def remove_installed_game(self, app_id: str):
        """移除已安装游戏"""
        app_id = str(app_id)
        if app_id in self.installed_games_cache:
            del self.installed_games_cache[app_id]
            self.save_installed_games()

    def get_game_info(self, app_id: str) -> Optional[Dict]:
        """获取游戏信息缓存"""
        return self.game_info_cache.get(str(app_id))

    def get_image_path(self, app_id: str) -> Path:
        """获取图片缓存路径"""
        return self.images_dir / f"{str(app_id)}.jpg"

    def has_image(self, app_id: str) -> bool:
        """检查是否有图片缓存"""
        return self.get_image_path(str(app_id)).exists()

    def save_image(self, app_id: str, image_data: bytes):
        """保存图片缓存"""
        try:
            image_path = self.get_image_path(str(app_id))
            with open(image_path, 'wb') as f:
                f.write(image_data)
        except:
            pass

    def load_image(self, app_id: str) -> Optional[bytes]:
        """加载图片缓存"""
        try:
            image_path = self.get_image_path(str(app_id))
            if image_path.exists():
                with open(image_path, 'rb') as f:
                    return f.read()
        except:
            pass
        return None


# Steam API Helper Class
class SteamAPIHelper:
    """Steam API 辅助类，用于获取游戏信息和图片"""

    @staticmethod
    async def get_game_info(client: httpx.AsyncClient, app_id: str) -> Dict:
        """获取游戏详细信息"""
        app_id = str(app_id)

        apis = [
            # Steam Store API with Chinese support
            {
                'url': f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=schinese&cc=CN",
                'parser': lambda data: {
                    'name': data[app_id]['data']['name'] if app_id in data and data[app_id].get('success') else None,
                    'name_cn': data[app_id]['data'].get('name', '') if app_id in data and data[app_id].get(
                        'success') else '',
                    'header_image': data[app_id]['data']['header_image'] if app_id in data and data[app_id].get(
                        'success') else None,
                    'short_description': data[app_id]['data'].get('short_description', '') if app_id in data and data[
                        app_id].get('success') else '',
                    'genres': [g['description'] for g in data[app_id]['data'].get('genres', [])] if app_id in data and
                                                                                                    data[app_id].get(
                                                                                                        'success') else [],
                    'all_images': {
                        'header': data[app_id]['data'].get('header_image'),
                        'capsule': data[app_id]['data'].get('capsule_image'),
                        'capsule_v5': data[app_id]['data'].get('capsule_imagev5'),
                        'page': data[app_id]['data'].get('page_image')
                    } if app_id in data and data[app_id].get('success') else {}
                }
            },
            # Store Search API
            {
                'url': f"https://store.steampowered.com/api/storesearch/?term={app_id}&l=schinese&cc=CN",
                'parser': lambda data: {
                    'name': data['items'][0]['name'] if data.get('items') else None,
                    'name_cn': data['items'][0]['name'] if data.get('items') else None,
                    'header_image': f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
                    'short_description': '',
                    'genres': [],
                    'all_images': {}
                } if data.get('items') and str(data['items'][0]['id']) == app_id else None
            }
        ]

        for api in apis:
            try:
                response = await client.get(api['url'], timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    result = api['parser'](data)
                    if result and result['name']:
                        return result
            except:
                continue

        # 默认返回
        return {
            'name': f'游戏 {app_id}',
            'name_cn': f'游戏 {app_id}',
            'header_image': f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
            'short_description': '',
            'genres': [],
            'all_images': {}
        }

    @staticmethod
    @staticmethod
    async def get_game_image(client: httpx.AsyncClient, app_id: str) -> Optional[bytes]:
        """获取游戏图片 - 综合5种方式"""
        app_id = str(app_id)

        # 方式1：直接尝试CDN（最快） - 并行请求
        cdn_urls = [
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header.jpg",
            f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_616x353.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{app_id}/capsule_231x87.jpg"
        ]

        # 创建并行请求任务
        async def fetch_image(url):
            try:
                response = await client.get(url, timeout=5)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    if 'image' in content_type:
                        return response.content
            except:
                pass
            return None

        # 并行执行所有CDN请求
        tasks = [fetch_image(url) for url in cdn_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 返回第一个成功的结果
        for result in results:
            if isinstance(result, bytes) and result:
                return result

        # 方式2：Steam Store API（最准确）
        try:
            store_api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=CN&l=schinese"
            response = await client.get(store_api_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if app_id in data and data[app_id].get('success'):
                    app_data = data[app_id]['data']

                    image_fields = [
                        'header_image',
                        'capsule_image',
                        'capsule_imagev5',
                        'page_image'
                    ]

                    for field in image_fields:
                        image_url = app_data.get(field)
                        if image_url:
                            try:
                                img_response = await client.get(image_url, timeout=10)
                                if img_response.status_code == 200:
                                    return img_response.content
                            except:
                                continue
        except:
            pass

        # 方式3：Steam Web API
        try:
            schema_url = f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?appid={app_id}"
            response = await client.get(schema_url, timeout=10)

            if response.status_code == 200:
                possible_urls = [
                    f"https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/{app_id}/header.jpg",
                    f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/header_292x136.jpg"
                ]

                for url in possible_urls:
                    try:
                        img_response = await client.get(url, timeout=10)
                        if img_response.status_code == 200:
                            return img_response.content
                    except:
                        continue
        except:
            pass

        # 方式4：Steam Community
        try:
            community_urls = [
                f"https://steamcommunity.com/app/{app_id}",
                f"https://steamcommunity.com/games/{app_id}"
            ]

            for community_url in community_urls:
                try:
                    response = await client.get(community_url, timeout=10, follow_redirects=True)

                    if response.status_code == 200:
                        content = response.text

                        import re
                        patterns = [
                            rf'https://[^"]+/apps/{app_id}/header[^"]+\.jpg',
                            rf'https://[^"]+/apps/{app_id}/capsule[^"]+\.jpg',
                            rf'"image"\s*:\s*"([^"]+apps/{app_id}[^"]+)"'
                        ]

                        for pattern in patterns:
                            matches = re.findall(pattern, content)
                            if matches:
                                for img_url in matches[:2]:  # 只尝试前2个匹配
                                    if not img_url.startswith('http'):
                                        img_url = 'https:' + img_url

                                    try:
                                        img_response = await client.get(img_url, timeout=10)
                                        if img_response.status_code == 200:
                                            return img_response.content
                                    except:
                                        continue
                except:
                    continue
        except:
            pass

        # 方式5：使用备用CDN
        try:
            backup_urls = [
                f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/library_600x900.jpg",
                f"https://steamcdn-a.akamaihd.net/steam/apps/{app_id}/library_hero.jpg"
            ]

            for url in backup_urls:
                try:
                    response = await client.get(url, timeout=5)
                    if response.status_code == 200:
                        return response.content
                except:
                    continue
        except:
            pass

        return None


# Game Card Widget
class GameCard(ttk.Frame):
    """游戏卡片组件"""

    def __init__(self, parent, app_id: str, game_name: str, game_info: Dict, image_data: Optional[bytes],
                 add_callback, delete_callback=None, is_installed=False, main_gui=None):
        super().__init__(parent, relief="solid", borderwidth=1)
        self.parent = parent  # 添加这一行
        self.app_id = app_id
        self.game_name = game_name
        self.game_info = game_info
        self.add_callback = add_callback
        self.delete_callback = delete_callback
        self.is_installed = is_installed
        self.image_data = image_data
        self.original_image = None
        self._resize_timer = None
        self.main_gui = main_gui

        self.setup_ui(image_data)

        # 绑定大小改变事件
        self.bind("<Configure>", self.on_resize)

    def setup_ui(self, image_data):
        # 不设置固定大小，让卡片根据网格自适应
        self.grid_propagate(False)

        # 初始化计时器
        self._resize_timer = None

        # 图片显示 - 让图片完全填满分配的空间
        self.image_label = ttk.Label(self, text="", anchor="center")
        self.image_label.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=0, pady=0)

        if image_data:
            try:
                self.original_image = Image.open(io.BytesIO(image_data))
                # 延迟更新图片，等待窗口完全初始化
                self.after(50, self.update_image)
                # 再次延迟更新，确保布局完成
                self.after(200, self.update_image)
            except:
                self.image_label.configure(text="[无图片]", font=("Arial", 12))
        else:
            self.image_label.configure(text="[加载中...]", font=("Arial", 12))

        # 游戏名称
        self.name_label = ttk.Label(self,
                                    text=self.game_name[:30] + "..." if len(self.game_name) > 30 else self.game_name,
                                    font=("Arial", 10, "bold"))
        self.name_label.grid(row=1, column=0, columnspan=3, padx=5, pady=(1, 1), sticky="ew")

        # App ID
        self.id_label = ttk.Label(self, text=f"ID: {self.app_id}", font=("Arial", 9), foreground="gray")
        self.id_label.grid(row=2, column=0, padx=5, pady=(0, 3), sticky="w")

        # 操作按钮
        if self.is_installed:
            # 已入库，显示DLC、启动和删除按钮
            # 创建按钮容器
            button_frame = ttk.Frame(self)
            button_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=(0, 3), sticky="ew")

            # DLC按钮
            self.dlc_btn = ttk.Button(button_frame, text="DLC",
                                      command=lambda: self.main_gui.show_dlc_dialog(self.app_id,
                                                                                    self.game_name) if self.main_gui else None,
                                      style="warning.TButton", width=5)
            self.dlc_btn.pack(side=LEFT, padx=2)

            # 启动按钮
            self.launch_btn = ttk.Button(button_frame, text="启动",
                                         command=lambda: self.launch_steam_game(self.app_id),
                                         style="primary.TButton", width=6)
            self.launch_btn.pack(side=LEFT, padx=2)

            # 删除按钮
            self.delete_btn = ttk.Button(button_frame, text="删除",
                                         command=lambda: self.delete_callback(self.app_id, self.game_name),
                                         style="danger.TButton", width=6)
            self.delete_btn.pack(side=LEFT, padx=2)
        else:
            # 未入库，显示入库按钮
            self.action_btn = ttk.Button(self, text="入库",
                                         command=lambda: self.add_callback(self.app_id, self.game_name),
                                         style="success.TButton", width=6)
            self.action_btn.grid(row=2, column=1, padx=5, pady=(0, 3), sticky="e")

            # 如果有删除回调，也显示删除按钮（用于搜索结果中已入库的游戏）
            if self.delete_callback:
                self.delete_btn = ttk.Button(self, text="删除",
                                             command=lambda: self.delete_callback(self.app_id, self.game_name),
                                             style="danger.TButton", width=6)
                self.delete_btn.grid(row=2, column=2, padx=5, pady=(0, 3), sticky="e")

        # 配置行列权重 - 让图片占据最大空间
        self.grid_rowconfigure(0, weight=10)  # 图片占绝大部分空间
        self.grid_rowconfigure(1, weight=1)  # 游戏名称
        self.grid_rowconfigure(2, weight=1)  # 按钮行
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # 绑定销毁事件
        self.bind("<Destroy>", self._on_destroy)

    def _on_destroy(self, event):
        """卡片销毁时的清理"""
        if event.widget == self:
            # 取消任何未完成的计时器
            if hasattr(self, '_resize_timer') and self._resize_timer:
                try:
                    self.after_cancel(self._resize_timer)
                    self._resize_timer = None
                except:
                    pass

    def on_resize(self, event):
        """窗口大小改变时更新图片"""
        if self.original_image and event.widget == self:
            # 使用延迟调用避免过于频繁的更新
            if hasattr(self, '_resize_timer') and self._resize_timer:
                try:
                    self.after_cancel(self._resize_timer)
                    self._resize_timer = None
                except:
                    pass
            # 增加延迟时间，确保布局完成
            self._resize_timer = self.after(150, lambda: self._delayed_update_image())

    def _delayed_update_image(self):
        """延迟更新图片的回调函数"""
        self._resize_timer = None
        self.update_image()

    def launch_steam_game(self, app_id: str):
        """启动Steam游戏"""
        try:
            # 获取游戏名称
            game_name = self.game_name if hasattr(self, 'game_name') else f"游戏 {app_id}"

            # 创建一个标志来跟踪是否应该启动游戏
            should_launch = {'value': True}

            # 创建进度窗口
            progress_window = tk.Toplevel(self.winfo_toplevel())
            progress_window.title("启动游戏")
            progress_window.geometry("300x100")
            progress_window.resizable(False, False)
            progress_window.transient(self.winfo_toplevel())

            # 设置窗口图标
            try:
                if getattr(sys, 'frozen', False):
                    icon_path = os.path.join(sys._MEIPASS, '图标.ico')
                else:
                    icon_path = '图标.ico'
                if os.path.exists(icon_path):
                    progress_window.iconbitmap(icon_path)
            except:
                pass

            # 居中显示
            progress_window.update_idletasks()
            x = (progress_window.winfo_screenwidth() - 400) // 2
            y = (progress_window.winfo_screenheight() - 100) // 2
            progress_window.geometry(f"400x100+{x}+{y}")

            # 添加标签
            ttk.Label(progress_window,
                      text=f"正在启动 请在steam中查看: {game_name}",
                      font=("Arial", 10)).pack(pady=15)

            # 添加进度条
            progress_bar = ttk.Progressbar(progress_window,
                                           mode='indeterminate',
                                           length=250)
            progress_bar.pack(pady=10)
            progress_bar.start(10)

            # 定义关闭窗口时的处理函数
            def on_close():
                should_launch['value'] = False
                progress_window.destroy()

            # 绑定关闭事件
            progress_window.protocol("WM_DELETE_WINDOW", on_close)

            # 更新窗口
            progress_window.update()

            # 定义启动游戏的函数
            def launch_game():
                if should_launch['value']:
                    # 构建Steam URL并启动
                    steam_url = f"steam://run/{app_id}"
                    import webbrowser
                    webbrowser.open(steam_url)

            # 500毫秒后启动游戏（给用户反应时间）
            progress_window.after(500, launch_game)

            # 10秒后自动关闭进度窗口
            def auto_close():
                try:
                    if progress_window.winfo_exists():
                        progress_window.destroy()
                except:
                    pass

            progress_window.after(10000, auto_close)

        except Exception as e:
            # 如果出错，关闭进度窗口
            try:
                progress_window.destroy()
            except:
                pass
            messagebox.showerror("启动失败", f"无法启动游戏: {str(e)}")

    def update_image(self):
        """根据当前卡片大小更新图片 - 完全铺满图片框"""
        if not self.original_image:
            return

        try:
            # 检查组件是否仍然存在
            if not self.winfo_exists():
                return

            # 更新窗口以获取正确的尺寸
            self.update_idletasks()

            # 获取图片标签的实际大小
            if hasattr(self, 'image_label') and self.image_label.winfo_exists():
                label_width = self.image_label.winfo_width()
                label_height = self.image_label.winfo_height()

                if label_width > 1 and label_height > 1:
                    # 直接使用标签的尺寸
                    resized_img = self.original_image.resize((label_width, label_height), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(resized_img)
                    self.image_label.configure(image=photo)
                    self.image_label.image = photo

                    # 更新文字换行宽度
                    if hasattr(self, 'name_label') and self.name_label.winfo_exists():
                        self.name_label.configure(wraplength=self.winfo_width() - 10)
        except (tk.TclError, AttributeError):
            # 组件已被销毁，忽略错误
            pass

    def set_image(self, image_data: bytes):
        """设置新图片"""
        if image_data:
            try:
                # 检查组件是否仍然存在
                if self.winfo_exists():
                    self.image_data = image_data
                    self.original_image = Image.open(io.BytesIO(image_data))
                    # 延迟更新图片
                    self.after(50, self.update_image)
                    # 再次延迟更新，确保布局完成
                    self.after(200, self.update_image)
            except (tk.TclError, AttributeError):
                # 组件已被销毁，忽略错误
                pass
            except Exception:
                # 其他错误（如图片格式问题）
                pass

    def update_name(self, name: str):
        """更新游戏名称"""
        try:
            # 检查组件是否仍然存在
            if self.winfo_exists() and hasattr(self, 'name_label'):
                self.game_name = name
                self.name_label.configure(text=name[:30] + "..." if len(name) > 30 else name)
        except tk.TclError:
            # 组件已被销毁，忽略错误
            pass


# Gradient Background Canvas
class GradientCanvas(tk.Canvas):
    """渐变背景画布"""

    def __init__(self, parent, start_color="#1a1a2e", end_color="#16213e", **kwargs):
        super().__init__(parent, **kwargs)
        self.start_color = start_color
        self.end_color = end_color
        self.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        """画布大小改变时重绘渐变"""
        self.draw_gradient()

    def draw_gradient(self):
        """绘制渐变背景"""
        self.delete("gradient")
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            return

        # 解析颜色
        start_r = int(self.start_color[1:3], 16)
        start_g = int(self.start_color[3:5], 16)
        start_b = int(self.start_color[5:7], 16)

        end_r = int(self.end_color[1:3], 16)
        end_g = int(self.end_color[3:5], 16)
        end_b = int(self.end_color[5:7], 16)

        # 创建渐变
        steps = height
        for i in range(steps):
            ratio = i / steps
            r = int(start_r + (end_r - start_r) * ratio)
            g = int(start_g + (end_g - start_g) * ratio)
            b = int(start_b + (end_b - start_b) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"

            self.create_line(0, i, width, i, fill=color, tags="gradient")


# Main Game Box GUI - 改进版本
class GameBoxGUI:
    def __init__(self):
        try:
            # 先创建主窗口，确保它不会被提前销毁
            self.root = ttk.Window(themename="darkly")
            self.root.title("Steam游戏盒子")
            self.root.geometry("1400x800")
            self.root.minsize(1200, 700)

            # 设置窗口图标
            try:
                if getattr(sys, 'frozen', False):
                    # 如果是打包后的exe
                    icon_path = os.path.join(sys._MEIPASS, '图标.ico')
                else:
                    # 如果是python脚本
                    icon_path = '图标.ico'

                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
                    # 确保任务栏也显示图标
                    self.root.wm_iconbitmap(icon_path)
            except Exception as e:
                print(f"设置图标失败: {e}")

            # 保持对style的引用，防止被垃圾回收
            self.style = ttk.Style()

            self.processing_lock = threading.Lock()
            self.game_cards = []
            self.current_games = []
            self.http_client = None
            self.log = None  # 初始化为None
            self._resize_timer = None
            self._search_timer = None  # 添加搜索计时器
            self.last_search_text = ""  # 记录上次搜索内容
            self.clearing_display = False  # 清理显示标记
            self.search_cancelled = False  # 搜索中断标志
            self.selected_repos = set()  # 选中的仓库集合

            # 初始化缓存管理器 - 使用exe所在目录
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                base_path = Path(sys.executable).parent
            else:
                # 如果是python脚本
                base_path = Path(os.path.dirname(os.path.abspath(__file__)))

            self.cache_manager = CacheManager(base_path)

            # 预加载仓库配置（在创建UI之前）
            self.pre_load_repo_config()

            # 创建UI（必须在设置日志之前）
            self.create_widgets()
            self.create_menu()

            # 设置日志（在UI创建之后）
            self.log = self.setup_logging()

            # 创建backend
            try:
                self.backend = GuiBackend(self.log)

                # 先加载backend的配置
                self.backend.load_config()

                # 然后从缓存覆盖设置
                self.load_cached_settings()

            except Exception as e:
                messagebox.showerror("初始化错误", f"创建后端失败:\n{str(e)}\n\n请确保 backend_gui.py 文件存在且正确。")
                sys.exit(1)

            # 从缓存加载设置（在创建backend之后）
            self.load_cached_settings()

            # 初始化
            self.root.after(100, self.initialize_app)

            # 窗口关闭处理
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        except Exception as e:
            import traceback
            error_msg = f"初始化窗口失败:\n{str(e)}\n\n{traceback.format_exc()}"
            print(error_msg)
            try:
                messagebox.showerror("初始化错误", error_msg)
            except:
                pass
            sys.exit(1)

    def pre_load_repo_config(self):
        """预加载仓库配置（在创建UI之前）"""
        # 加载仓库配置
        repo_config = self.cache_manager.repo_config
        self.selected_repos = set(repo_config.get('selected_repos', ["swa"]))

        # 加载所有仓库列表
        self.all_repos = repo_config.get('all_repos', self.cache_manager.get_default_repos())
        self.repo_options = [(repo['name'], repo['path']) for repo in self.all_repos]

    def load_cached_settings(self):
        """从缓存加载设置"""
        cached_settings = self.cache_manager.settings_cache
        if cached_settings:
            # 恢复搜索模式
            if 'search_all' in cached_settings:
                self.search_all_var.set(cached_settings['search_all'])

            # 恢复Steam路径和解锁工具设置到backend配置
            if hasattr(self, 'backend'):
                if 'steam_path_mode' in cached_settings:
                    self.backend.app_config['steam_path_mode'] = cached_settings['steam_path_mode']
                if 'Custom_Steam_Path' in cached_settings:
                    self.backend.app_config['Custom_Steam_Path'] = cached_settings['Custom_Steam_Path']
                if 'unlocker_mode' in cached_settings:
                    self.backend.app_config['unlocker_mode'] = cached_settings['unlocker_mode']
                if 'manual_unlocker' in cached_settings:
                    self.backend.app_config['manual_unlocker'] = cached_settings['manual_unlocker']
                if 'Github_Personal_Token' in cached_settings:
                    self.backend.app_config['Github_Personal_Token'] = cached_settings['Github_Personal_Token']
                if 'steamtools_only_lua' in cached_settings:
                    self.backend.app_config['steamtools_only_lua'] = cached_settings['steamtools_only_lua']

        # 更新复选框状态（UI已经创建）
        for repo_value, cb_var in self.repo_checkbuttons.items():
            cb_var.set(repo_value in self.selected_repos)

    def save_settings_to_cache(self):
        """保存设置到缓存"""
        settings = {
            'search_all': self.search_all_var.get()
        }

        # 保存backend的所有配置
        if hasattr(self, 'backend') and hasattr(self.backend, 'app_config'):
            settings.update({
                'steam_path_mode': self.backend.app_config.get('steam_path_mode', 'auto'),
                'Custom_Steam_Path': self.backend.app_config.get('Custom_Steam_Path', ''),
                'unlocker_mode': self.backend.app_config.get('unlocker_mode', 'auto'),
                'manual_unlocker': self.backend.app_config.get('manual_unlocker', 'steamtools'),
                'Github_Personal_Token': self.backend.app_config.get('Github_Personal_Token', ''),
                'steamtools_only_lua': self.backend.app_config.get('steamtools_only_lua', False)
            })

        self.cache_manager.save_settings(settings)

        # 保存仓库配置
        repo_config = {
            'selected_repos': list(self.selected_repos),
            'all_repos': self.all_repos
        }
        self.cache_manager.save_repo_config(repo_config)

    def on_closing(self):
        """窗口关闭"""
        # 保存设置到缓存
        self.save_settings_to_cache()

        # 保存当前游戏列表到缓存
        if hasattr(self, 'current_games') and self.current_games:
            self.cache_manager.save_game_list(self.current_games)

        # 取消任何未完成的计时器
        if hasattr(self, '_resize_timer') and self._resize_timer:
            try:
                self.root.after_cancel(self._resize_timer)
            except:
                pass

        if hasattr(self, '_search_timer') and self._search_timer:
            try:
                self.root.after_cancel(self._search_timer)
            except:
                pass

        if self.processing_lock.locked():
            if messagebox.askyesno("确认", "正在处理任务，确定要退出吗？"):
                os._exit(0)
        else:
            self.root.destroy()

    def setup_logging(self):
        """设置日志系统"""
        logger = logging.getLogger('GameBoxGUI')
        logger.setLevel(logging.INFO)
        if logger.hasHandlers():
            logger.handlers.clear()

        class GuiHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

            def emit(self, record):
                msg = self.format(record)
                level = record.levelname
                self.text_widget.after(0, self.update_log_text, msg, level)

            def update_log_text(self, msg, level):
                try:
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg + '\n', level.upper())
                    self.text_widget.configure(state='disabled')
                    self.text_widget.see(tk.END)
                except tk.TclError:
                    pass

        gui_handler = GuiHandler(self.log_text)
        logger.addHandler(gui_handler)
        return logger

    def create_menu(self):
        """创建菜单栏"""
        try:
            menu_bar = ttk.Menu(self.root)
            self.root.config(menu=menu_bar)

            # 设置菜单
            settings_menu = ttk.Menu(menu_bar, tearoff=False)
            menu_bar.add_cascade(label="设置", menu=settings_menu)
            settings_menu.add_command(label="编辑配置", command=self.show_settings_dialog)
            settings_menu.add_separator()
            settings_menu.add_command(label="退出", command=self.on_closing)

            # 工具菜单
            tools_menu = ttk.Menu(menu_bar, tearoff=False)
            menu_bar.add_cascade(label="工具", menu=tools_menu)
            tools_menu.add_command(label="清理缓存", command=self.cleanup_cache)

            # 入库管理菜单
            manage_menu = ttk.Menu(menu_bar, tearoff=False)
            menu_bar.add_cascade(label="入库管理", menu=manage_menu)
            manage_menu.add_command(label="查看已入库游戏", command=self.show_installed_games)
            manage_menu.add_separator()
            manage_menu.add_command(label="GitHub仓库管理", command=self.show_repo_manager)
        except Exception as e:
            print(f"创建菜单失败: {e}")
            import traceback
            traceback.print_exc()

    def create_widgets(self):
        """创建主界面组件"""
        # 主容器 - 直接使用Frame，铺满整个窗口
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # 左侧面板
        left_panel = ttk.Frame(main_container, width=350)
        left_panel.pack(side=LEFT, fill=Y, padx=(0, 5))
        left_panel.pack_propagate(False)

        # 搜索区域
        search_frame = ttk.Labelframe(left_panel, text="游戏搜索", padding=10)
        search_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(search_frame, text="输入游戏名称或AppID:").pack(anchor=W)

        search_input_frame = ttk.Frame(search_frame)
        search_input_frame.pack(fill=X, pady=(5, 0))

        self.search_entry = ttk.Entry(search_input_frame, font=("Arial", 11))
        self.search_entry.pack(side=LEFT, fill=X, expand=True)
        self.search_entry.bind("<Return>", lambda e: self.search_games())
        self.search_entry.bind("<KeyRelease>", self.on_search_key_release)

        self.search_btn = ttk.Button(search_input_frame, text="搜索", command=self.search_games,
                                     style="info.TButton", width=8)
        self.search_btn.pack(side=LEFT, padx=(5, 0))

        # 清单源选择
        source_frame = ttk.Labelframe(left_panel, text="清单源设置", padding=10)
        source_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(source_frame, text="选择清单库（支持多选）:").pack(anchor=W, pady=(0, 5))

        # 创建一个可滚动的容器
        scroll_container = ttk.Frame(source_frame)
        scroll_container.pack(fill=BOTH, expand=True, pady=(0, 10))

        # 创建Canvas和Scrollbar
        self.repo_canvas = tk.Canvas(scroll_container, height=120, highlightthickness=0)
        repo_scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=self.repo_canvas.yview)
        self.repo_canvas.configure(yscrollcommand=repo_scrollbar.set)

        # 设置Canvas背景色以匹配主题
        if hasattr(self, 'style') and hasattr(self.style, 'colors'):
            self.repo_canvas.configure(bg=self.style.colors.bg)

        # 创建内部Frame来放置复选框
        self.repo_inner_frame = ttk.Frame(self.repo_canvas)
        self.repo_canvas_window = self.repo_canvas.create_window((0, 0), window=self.repo_inner_frame, anchor="nw")

        # 添加所有复选框到内部Frame
        self.repo_checkbuttons = {}
        for i, (name, value) in enumerate(self.repo_options):
            var = tk.BooleanVar(value=value in self.selected_repos)
            cb = ttk.Checkbutton(self.repo_inner_frame, text=name, variable=var,
                                 command=lambda v=value, var=var: self.on_repo_toggle(v, var))
            cb.pack(anchor=W, padx=5, pady=2)
            self.repo_checkbuttons[value] = var

        # 布局Canvas和Scrollbar
        repo_scrollbar.pack(side=RIGHT, fill=Y)
        self.repo_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        # 配置滚动区域
        def configure_scroll_region(event=None):
            self.repo_canvas.configure(scrollregion=self.repo_canvas.bbox("all"))
            # 调整Canvas窗口宽度以匹配Canvas宽度
            canvas_width = self.repo_canvas.winfo_width()
            if canvas_width > 1:
                self.repo_canvas.itemconfig(self.repo_canvas_window, width=canvas_width)

        self.repo_inner_frame.bind("<Configure>", configure_scroll_region)
        self.repo_canvas.bind("<Configure>", lambda e: configure_scroll_region())

        # 鼠标滚轮支持
        def on_repo_mousewheel(event):
            # 检查Canvas是否需要滚动
            if self.repo_canvas.winfo_height() < self.repo_inner_frame.winfo_height():
                self.repo_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # 鼠标进入和离开事件
        def on_enter_canvas(event):
            # 只在内容超出显示区域时绑定滚轮
            if self.repo_canvas.winfo_height() < self.repo_inner_frame.winfo_height():
                self.repo_canvas.bind_all("<MouseWheel>", on_repo_mousewheel)

        def on_leave_canvas(event):
            self.repo_canvas.unbind_all("<MouseWheel>")

        self.repo_canvas.bind("<Enter>", on_enter_canvas)
        self.repo_canvas.bind("<Leave>", on_leave_canvas)

        # 搜索模式（初始化变量）
        self.search_all_var = tk.BooleanVar(value=False)

        # 搜索模式复选框
        ttk.Checkbutton(source_frame, text="搜索所有GitHub库",
                        variable=self.search_all_var, command=self.save_settings_to_cache).pack(anchor=W, pady=(10, 0))

        # 日志区域
        log_frame = ttk.Labelframe(left_panel, text="操作日志", padding=5)
        log_frame.pack(fill=BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10,
                                                  font=("Consolas", 9), state='disabled')
        self.log_text.pack(fill=BOTH, expand=True)

        # 配置日志标签颜色
        self.log_text.tag_config('INFO', foreground='lightblue')
        self.log_text.tag_config('WARNING', foreground='yellow')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('CRITICAL', foreground='purple')

        # 右侧游戏展示区
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=LEFT, fill=BOTH, expand=True)

        # 工具栏
        toolbar = ttk.Frame(right_panel)
        toolbar.pack(fill=X, pady=(0, 10))

        ttk.Label(toolbar, text="游戏列表", font=("Arial", 14, "bold")).pack(side=LEFT)

        # 添加搜索已入库游戏按钮
        self.filter_entry = ttk.Entry(toolbar, font=("Arial", 10), width=20)
        self.filter_entry.pack(side=LEFT, padx=(20, 5))
        self.filter_entry.bind("<KeyRelease>", self.on_filter_key_release)

        self.filter_btn = ttk.Button(toolbar, text="搜索", command=self.filter_installed_games,
                                     style="secondary.TButton", width=8)
        self.filter_btn.pack(side=LEFT)

        # 添加主页按钮
        self.home_btn = ttk.Button(toolbar, text="主页", command=self.go_home,
                                   style="primary.TButton", width=8)
        self.home_btn.pack(side=LEFT, padx=(5, 0))

        self.status_label = ttk.Label(toolbar, text="就绪", font=("Arial", 10))
        self.status_label.pack(side=RIGHT)

        # 游戏卡片滚动区域
        self.create_game_display_area(right_panel)

        # 底部状态栏（在渐变背景之上）
        status_bar = ttk.Frame(self.root)
        status_bar.pack(side=BOTTOM, fill=X, padx=10, pady=5)

        self.unlocker_status = ttk.Label(status_bar, text="正在检测解锁工具...",
                                         font=("Arial", 9))
        self.unlocker_status.pack(side=LEFT)

        self.progress_bar = ttk.Progressbar(status_bar, mode='indeterminate', length=200)
        self.progress_bar.pack(side=RIGHT)

    def on_repo_toggle(self, repo_value: str, var: tk.BooleanVar):
        """仓库复选框切换事件"""
        if var.get():
            self.selected_repos.add(repo_value)
        else:
            self.selected_repos.discard(repo_value)

        # 至少要选中一个仓库
        if not self.selected_repos:
            messagebox.showwarning("提示", "至少需要选择一个清单源")
            var.set(True)
            self.selected_repos.add(repo_value)

        # 保存设置
        self.save_settings_to_cache()

    def go_home(self):
        """返回主页"""
        # 设置搜索中断标志
        self.search_cancelled = True

        # 如果正在搜索，停止进度条
        if self.progress_bar['mode'] == 'indeterminate':
            self.progress_bar.stop()

        # 清空搜索框
        self.search_entry.delete(0, tk.END)
        self.filter_entry.delete(0, tk.END)

        # 更新状态
        self.status_label.configure(text="就绪")

        # 滚动到顶部
        self.game_canvas.yview_moveto(0)

        # 显示已入库游戏
        self.show_installed_games_on_main()

    def filter_installed_games(self):
        """搜索主界面已入库的游戏"""
        filter_text = self.filter_entry.get().strip().lower()
        if not filter_text:
            # 如果搜索框为空，显示所有已入库游戏
            self.show_installed_games_on_main()
            return

        # 过滤当前显示的游戏卡片
        filtered_games = []
        for game in self.current_games:
            if game.get('is_installed'):
                if filter_text in game['appid'].lower() or filter_text in game['name'].lower():
                    filtered_games.append(game)

        # 重新显示过滤后的游戏
        self.display_installed_games(filtered_games)

    def on_filter_key_release(self, event):
        """过滤框按键释放事件"""
        if event.keysym == "Return":
            self.filter_installed_games()

    def create_game_display_area(self, parent):
        """创建游戏展示区域"""
        # 创建Canvas和Scrollbar
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=BOTH, expand=True)

        self.game_canvas = tk.Canvas(canvas_frame, bg=self.style.colors.bg)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.game_canvas.yview)

        self.game_canvas.configure(yscrollcommand=v_scrollbar.set)

        # 创建内部Frame
        self.game_frame = ttk.Frame(self.game_canvas)
        self.game_canvas_window = self.game_canvas.create_window((0, 0), window=self.game_frame, anchor="nw")

        # 布局
        self.game_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        v_scrollbar.pack(side=RIGHT, fill=Y)

        # 绑定事件
        self.game_frame.bind("<Configure>", self.on_frame_configure)
        self.game_canvas.bind("<Configure>", self.on_canvas_configure)

        # 鼠标滚轮支持
        self.game_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def on_frame_configure(self, event):
        """更新Canvas滚动区域"""
        self.game_canvas.configure(scrollregion=self.game_canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """Canvas大小改变时调整内部Frame宽度"""
        canvas_width = event.width
        self.game_canvas.itemconfig(self.game_canvas_window, width=canvas_width)

        # 使用延迟调用避免过于频繁的重新布局
        if hasattr(self, '_resize_timer') and self._resize_timer:
            try:
                self.root.after_cancel(self._resize_timer)
                self._resize_timer = None
            except:
                pass
        self._resize_timer = self.root.after(300, lambda: self._delayed_relayout())

    def _delayed_relayout(self):
        """延迟重新布局的回调函数"""
        self._resize_timer = None
        self.relayout_game_cards()

    def relayout_game_cards(self):
        """重新布局游戏卡片以适应窗口大小"""
        if not self.game_cards:
            return

        # 获取Canvas宽度来决定列数和卡片大小
        canvas_width = self.game_canvas.winfo_width()
        if canvas_width <= 1:  # Canvas还未完全初始化
            return

        min_card_width = 280  # 最小卡片宽度
        max_card_width = 400  # 最大卡片宽度
        padding = 20  # 卡片之间的间距

        # 计算最佳列数
        cols = max(1, canvas_width // (min_card_width + padding))
        # 计算实际卡片宽度
        available_width = canvas_width - (cols + 1) * padding
        card_width = min(max_card_width, max(min_card_width, available_width // cols))
        card_height = int(card_width * 0.7)  # 高度是宽度的70%

        # 重新布局
        for i, card in enumerate(self.game_cards):
            row = i // cols
            col = i % cols
            card.grid(row=row, column=col, padx=padding // 2, pady=padding // 2, sticky="nsew")
            card.configure(width=card_width, height=card_height)
            # 延迟触发卡片更新图片，确保布局完成
            card.after(100, card.update_image)

        # 配置列权重
        for i in range(cols):
            self.game_frame.columnconfigure(i, weight=1, minsize=card_width)

        # 配置行权重
        rows = (len(self.game_cards) + cols - 1) // cols
        for i in range(rows):
            self.game_frame.rowconfigure(i, weight=1, minsize=card_height)

    def on_mousewheel(self, event):
        """鼠标滚轮事件处理"""
        self.game_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def initialize_app(self):
        """初始化应用"""
        try:
            self.log.info("Steam游戏盒子启动")
            self.log.info("正在初始化...")

            # 显示缓存目录位置
            self.log.info(f"缓存目录: {self.cache_manager.cache_dir.absolute()}")

            # 加载配置
            self.backend.load_config()

            # 检测Steam和解锁工具
            self.detect_environment()

            # 不再需要创建全局的 HTTP 客户端
            # 每个异步操作会创建自己的客户端

            self.log.info("初始化完成")
            self.status_label.configure(text="就绪")

            # 清空搜索框，确保不显示之前的搜索
            self.search_entry.delete(0, tk.END)
            self.filter_entry.delete(0, tk.END)

            # 清空当前游戏列表，强制重新加载已入库游戏
            self.current_games = []
            self.cache_manager.game_list_cache = []

            # 确保滚动条在顶部
            self.game_canvas.yview_moveto(0)

            # 延迟显示已入库的游戏，确保窗口完全初始化
            self.root.after(500, self.show_installed_games_on_main)

        except Exception as e:
            import traceback
            error_msg = f"初始化应用失败:\n{str(e)}\n\n{traceback.format_exc()}"
            self.log.error(error_msg) if self.log else print(error_msg)
            messagebox.showerror("初始化错误", error_msg)

    def on_search_key_release(self, event):
        """搜索框按键释放事件"""
        current_text = self.search_entry.get().strip()

        # 取消之前的定时器
        if hasattr(self, '_search_timer') and self._search_timer:
            try:
                self.root.after_cancel(self._search_timer)
                self._search_timer = None
            except:
                pass

        # 如果搜索框被清空且之前有内容，显示已入库的游戏
        if not current_text and self.last_search_text:
            self.last_search_text = current_text
            self._search_timer = self.root.after(300, self.show_installed_games_on_main)
        else:
            self.last_search_text = current_text

    def detect_environment(self):
        """检测运行环境"""
        # 先从缓存同步设置到backend（确保使用最新的设置）
        cached_settings = self.cache_manager.settings_cache
        if cached_settings:
            if 'steam_path_mode' in cached_settings:
                self.backend.app_config['steam_path_mode'] = cached_settings['steam_path_mode']
            if 'Custom_Steam_Path' in cached_settings:
                self.backend.app_config['Custom_Steam_Path'] = cached_settings['Custom_Steam_Path']
            if 'unlocker_mode' in cached_settings:
                self.backend.app_config['unlocker_mode'] = cached_settings['unlocker_mode']
            if 'manual_unlocker' in cached_settings:
                self.backend.app_config['manual_unlocker'] = cached_settings['manual_unlocker']

        # Steam路径处理
        steam_mode = self.backend.app_config.get("steam_path_mode", "auto")

        if steam_mode == "manual":
            # 手动模式 - 使用配置的路径
            custom_path = self.backend.app_config.get("Custom_Steam_Path", "")
            if custom_path:
                self.backend.steam_path = Path(custom_path)
                if self.backend.steam_path.exists():
                    self.log.info(f"使用手动设置的Steam路径: {self.backend.steam_path}")
                else:
                    self.log.error(f"手动设置的Steam路径不存在: {custom_path}")
                    self.unlocker_status.configure(text="Steam路径无效", foreground="red")
                    messagebox.showerror("错误", f"手动设置的Steam路径不存在:\n{custom_path}\n\n请在设置中修改。")
            else:
                self.log.error("未设置Steam路径")
                self.unlocker_status.configure(text="未设置Steam路径", foreground="red")
                messagebox.showerror("错误", "请在设置中配置Steam路径")
        else:
            # 自动模式 - 自动检测
            steam_path = self.backend.detect_steam_path()
            if not steam_path.exists():
                self.log.error("未找到Steam安装路径")
                self.unlocker_status.configure(text="Steam未找到", foreground="red")
                messagebox.showerror("错误", "未找到Steam安装路径！\n程序将尝试使用默认路径。")
            else:
                self.log.info(f"自动检测到Steam路径: {steam_path}")

        # 解锁工具处理
        unlocker_mode = self.backend.app_config.get("unlocker_mode", "auto")

        if unlocker_mode == "manual":
            # 手动模式 - 使用配置的解锁工具
            manual_unlocker = self.backend.app_config.get("manual_unlocker", "steamtools")
            self.backend.unlocker_type = manual_unlocker
            self.log.info(f"使用手动设置的解锁工具: {manual_unlocker}")
            self.unlocker_status.configure(text=f"解锁工具: {manual_unlocker.title()}", foreground="green")
        else:
            # 自动模式 - 自动检测
            status = self.backend.detect_unlocker()
            if status == "conflict":
                self.log.error("检测到环境冲突")
                self.unlocker_status.configure(text="环境冲突", foreground="red")
                messagebox.showerror("环境冲突", "同时检测到SteamTools和GreenLuma！\n请卸载其中一个。")
            elif status == "none":
                self.log.warning("未检测到解锁工具")
                self.unlocker_status.configure(text="未检测到解锁工具", foreground="orange")
                self.handle_manual_unlocker_selection()
            else:
                self.log.info(f"自动检测到解锁工具: {status}")
                self.unlocker_status.configure(text=f"解锁工具: {status.title()}", foreground="green")

    def handle_manual_unlocker_selection(self):
        """手动选择解锁工具"""
        dialog = UnlockerSelectionDialog(self.root)
        self.root.wait_window(dialog)

        if dialog.result:
            self.backend.unlocker_type = dialog.result
            self.log.info(f"手动选择解锁工具: {dialog.result}")
            self.unlocker_status.configure(text=f"解锁工具: {dialog.result.title()}", foreground="green")

    def search_games(self):
        """搜索游戏"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("提示", "请输入搜索内容")
            return

        if not self.processing_lock.acquire(blocking=False):
            self.log.warning("正在处理中，请稍候...")
            return

        # 重置搜索中断标志
        self.search_cancelled = False

        # 清空当前显示
        self.clear_game_display()
        self.status_label.configure(text="搜索中...")
        self.progress_bar.start()

        # 异步搜索
        thread = threading.Thread(target=self.search_games_thread, args=(search_term,), daemon=True)
        thread.start()

    def search_games_thread(self, search_term):
        """搜索游戏线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 如果已经被中断，直接返回
            if self.search_cancelled:
                return

            # 创建专用的 HTTP 客户端
            async def search_with_client():
                # 检查是否被中断
                if self.search_cancelled:
                    return []

                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    # 判断是否是AppID
                    if search_term.isdigit() or self.backend.extract_app_id(search_term):
                        app_id = str(self.backend.extract_app_id(search_term) or search_term)

                        # 先从缓存获取
                        cached_info = self.cache_manager.get_game_info(app_id)
                        installed_name = self.cache_manager.get_installed_game_name(app_id)

                        if installed_name:
                            # 如果有入库时保存的名称，优先使用
                            games = [{'appid': app_id, 'name': installed_name, 'type': 'Game'}]
                        elif cached_info:
                            games = [
                                {'appid': app_id,
                                 'name': cached_info.get('name_cn', cached_info.get('name', f'游戏 {app_id}')),
                                 'type': 'Game'}]
                        else:
                            # 直接使用AppID
                            games = [{'appid': app_id, 'name': f'游戏 {app_id}', 'type': 'Game'}]
                            # 异步获取游戏信息
                            game_info = await SteamAPIHelper.get_game_info(client, app_id)
                            if game_info and game_info['name'] != f'游戏 {app_id}':
                                games[0]['name'] = game_info.get('name_cn', game_info['name'])
                                games[0]['schinese_name'] = game_info.get('name_cn', game_info['name'])
                                # 保存到缓存
                                self.cache_manager.set_game_info(app_id, game_info)
                    else:
                        # 搜索游戏名称
                        try:
                            games = await self.backend.search_games_by_name(client, search_term)
                        except Exception as e:
                            self.log.error(f"搜索游戏名称时出错: {str(e)}")
                            games = []

                        # 对搜索结果，也尝试从缓存获取更准确的名称
                        for game in games:
                            # 确保 appid 是字符串
                            game['appid'] = str(game['appid'])
                            installed_name = self.cache_manager.get_installed_game_name(game['appid'])
                            if installed_name:
                                # 如果有入库时保存的名称，优先使用
                                game['name'] = installed_name
                                game['schinese_name'] = installed_name
                            else:
                                cached_info = self.cache_manager.get_game_info(game['appid'])
                                if cached_info:
                                    game['name'] = cached_info.get('name_cn', cached_info.get('name', game['name']))
                                    game['schinese_name'] = cached_info.get('name_cn', cached_info.get('name',
                                                                                                       game.get(
                                                                                                           'schinese_name',
                                                                                                           game[
                                                                                                               'name'])))
                    return games

            games = loop.run_until_complete(search_with_client())

            # 再次检查是否被中断
            if not self.search_cancelled:
                self.current_games = games
                self.root.after(0, self.display_search_results, games)
            else:
                # 如果被中断，只更新UI状态
                self.root.after(0, self.search_complete)

        except Exception as e:
            if not self.search_cancelled:
                self.log.error(f"搜索失败: {str(e)}")
            self.root.after(0, self.search_complete)
        finally:
            try:
                loop.close()
            except:
                pass
            self.processing_lock.release()

    def display_search_results(self, games):
        """显示搜索结果"""
        # 如果搜索已被中断，不显示结果
        if self.search_cancelled:
            self.search_complete()
            return

        self.clear_game_display()

        if not games:
            self.log.warning("未找到匹配的游戏")
            self.status_label.configure(text="未找到游戏")
            # 如果没有搜索结果，显示已入库的游戏
            self.show_installed_games_on_main()
            return

        self.log.info(f"找到 {len(games)} 个游戏")
        self.status_label.configure(text=f"找到 {len(games)} 个游戏")

        # 获取已入库游戏列表
        installed_games = set()
        if self.backend.steam_path.exists():
            stplug_dir = self.backend.steam_path / "config" / "stplug-in"
            if stplug_dir.exists():
                for lua_file in stplug_dir.glob("*.lua"):
                    match = re.search(r'(\d+)', lua_file.stem)
                    if match:
                        installed_games.add(match.group(1))

        # 获取Canvas宽度来决定列数和卡片大小
        canvas_width = self.game_canvas.winfo_width()
        if canvas_width <= 1:  # Canvas还未完全初始化
            canvas_width = 1000  # 使用默认宽度

        min_card_width = 280  # 最小卡片宽度
        max_card_width = 400  # 最大卡片宽度
        padding = 20  # 卡片之间的间距

        # 计算最佳列数
        cols = max(1, canvas_width // (min_card_width + padding))
        # 计算实际卡片宽度
        available_width = canvas_width - (cols + 1) * padding
        card_width = min(max_card_width, max(min_card_width, available_width // cols))
        card_height = int(card_width * 0.7)  # 高度是宽度的70%

        # 创建游戏卡片
        for i, game in enumerate(games[:20]):  # 限制显示20个
            app_id = str(game['appid'])  # 确保是字符串

            # 获取游戏名称（优先级：已入库名称 > 缓存名称 > API返回名称）
            installed_name = self.cache_manager.get_installed_game_name(app_id)
            if installed_name:
                name = installed_name
            else:
                cached_info = self.cache_manager.get_game_info(app_id)
                if cached_info:
                    name = cached_info.get('name_cn', cached_info.get('name', f'游戏 {app_id}'))
                else:
                    name = game.get('schinese_name') or game.get('name', f'游戏 {app_id}')

            # 创建卡片
            row = i // cols
            col = i % cols

            # 优先从缓存加载图片
            cached_image = self.cache_manager.load_image(app_id)

            # 检查游戏是否已入库
            is_installed = app_id in installed_games

            # 如果游戏已入库，只显示删除按钮
            if is_installed:
                card = GameCard(self.game_frame, app_id, name, {}, cached_image,
                                None, self.on_game_delete, is_installed=True, main_gui=self)
            else:
                card = GameCard(self.game_frame, app_id, name, {}, cached_image,
                                self.on_game_selected, None, is_installed=False, main_gui=self)

            card.grid(row=row, column=col, padx=padding // 2, pady=padding // 2, sticky="nsew")
            card.configure(width=card_width, height=card_height)
            self.game_cards.append(card)

            # 确保图片正确显示
            if cached_image:
                card.after(100, card.update_image)

            # 确保图片正确显示
            if cached_image:
                card.after(100, card.update_image)

            # 如果没有缓存图片，异步加载
            if not cached_image:
                threading.Thread(target=self.load_game_image, args=(card, app_id), daemon=True).start()

        # 配置列权重和行权重
        for i in range(cols):
            self.game_frame.columnconfigure(i, weight=1, minsize=card_width)

            # 配置行权重
            rows = (len(games[:20]) + cols - 1) // cols
            for i in range(rows):
                self.game_frame.rowconfigure(i, weight=1, minsize=card_height)

            # 滚动到顶部
            self.game_canvas.yview_moveto(0)

            self.search_complete()

    def load_game_image(self, card: GameCard, app_id: str):
        """异步加载游戏图片"""
        # 确保 app_id 是字符串
        app_id = str(app_id)

        # 保存卡片的弱引用，避免循环引用
        card_ref = weakref.ref(card)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 先尝试从缓存获取
            cached_image = self.cache_manager.load_image(app_id)
            if cached_image:
                card_obj = card_ref()
                if card_obj:  # 检查卡片是否仍然存在
                    self.root.after(0, self.update_card_image, card_obj, cached_image)
                    return  # 缓存命中，直接返回

            # 创建专用的 HTTP 客户端来加载图片
            async def load_with_client():
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    # 从网络加载
                    image_data = await SteamAPIHelper.get_game_image(client, app_id)
                    if image_data:
                        # 保存到缓存
                        self.cache_manager.save_image(app_id, image_data)
                        return image_data

                    # 如果图片获取失败，尝试获取游戏信息
                    if not self.cache_manager.get_game_info(app_id):
                        game_info = await SteamAPIHelper.get_game_info(client, app_id)
                        if game_info:
                            self.cache_manager.set_game_info(app_id, game_info)

                            # 如果游戏信息中有额外的图片URL，再尝试一次
                            all_images = game_info.get('all_images', {})
                            for img_type, img_url in all_images.items():
                                if img_url:
                                    try:
                                        response = await client.get(img_url, timeout=10)
                                        if response.status_code == 200:
                                            image_data = response.content
                                            self.cache_manager.save_image(app_id, image_data)
                                            return image_data
                                    except:
                                        continue
                    return None

            result = loop.run_until_complete(load_with_client())

            if isinstance(result, bytes):  # 图片数据
                card_obj = card_ref()
                if card_obj:
                    self.root.after(0, self.update_card_image, card_obj, result)
            else:
                # 如果还是没有获取到图片，记录日志
                self.log.warning(f"无法获取游戏图片: {app_id}")
        except:
            pass
        finally:
            try:
                loop.close()
            except:
                pass

    def update_card_name(self, card: GameCard, name: str):
        """更新卡片的游戏名称"""
        try:
            # 检查卡片是否仍然存在
            if card.winfo_exists():
                card.update_name(name)
        except tk.TclError:
            # 卡片已被销毁，忽略错误
            pass

    def update_card_image(self, card: GameCard, image_data: bytes):
        """更新卡片图片"""
        try:
            # 检查卡片是否仍然存在
            if card.winfo_exists():
                card.set_image(image_data)
        except tk.TclError:
            # 卡片已被销毁，忽略错误
            pass

    def clear_game_display(self):
        """清空游戏显示区域"""
        # 设置清理标记
        self.clearing_display = True

        for card in self.game_cards:
            # 取消卡片的计时器
            if hasattr(card, '_resize_timer') and card._resize_timer:
                try:
                    card.after_cancel(card._resize_timer)
                except:
                    pass
            try:
                card.destroy()
            except:
                pass
        self.game_cards.clear()

        # 滚动到顶部
        self.game_canvas.yview_moveto(0)

        # 清理完成
        self.clearing_display = False

    def search_complete(self):
        """搜索完成"""
        self.progress_bar.stop()

    def on_game_delete(self, app_id: str, game_name: str):
        """删除已入库的游戏"""
        # 确保 app_id 是字符串
        app_id = str(app_id)

        result = messagebox.askyesno("确认删除",
                                     f"确定要删除以下游戏吗？\n\n"
                                     f"游戏: {game_name}\n"
                                     f"App ID: {app_id}")

        if result:
            try:
                # 删除相关文件
                stplug_dir = self.backend.steam_path / "config" / "stplug-in"
                depot_dir = self.backend.steam_path / "depotcache"

                deleted = False

                # 删除lua文件
                if stplug_dir.exists():
                    for f in stplug_dir.glob(f"*{app_id}*.lua"):
                        f.unlink()
                        deleted = True

                # 删除manifest文件
                if depot_dir.exists():
                    for f in depot_dir.glob(f"*{app_id}*.manifest"):
                        f.unlink()
                        deleted = True

                if deleted:
                    # 从已安装缓存中移除
                    self.cache_manager.remove_installed_game(app_id)
                    # 立即保存缓存
                    self.cache_manager.save_installed_games()

                    self.log.info(f"已删除游戏: {game_name} (ID: {app_id})")
                    messagebox.showinfo("成功", f"游戏 {game_name} 已成功删除")

                    # 刷新显示
                    if self.search_entry.get().strip():
                        # 如果有搜索内容，重新搜索
                        self.search_games()
                    else:
                        # 否则显示已入库游戏
                        self.show_installed_games_on_main()
                else:
                    self.log.warning(f"未找到游戏文件: {game_name} (ID: {app_id})")
                    messagebox.showwarning("提示", "未找到该游戏的相关文件")

            except Exception as e:
                self.log.error(f"删除游戏失败: {str(e)}")
                messagebox.showerror("错误", f"删除游戏时出错:\n{str(e)}")

    def show_dlc_dialog(self, app_id: str, game_name: str):
        """显示DLC对话框"""
        DLCDialog(self.root, app_id, game_name, self.backend, self.selected_repos, self.cache_manager)

    def on_game_selected(self, app_id: str, game_name: str):
        """游戏被选中"""
        if not self.processing_lock.acquire(blocking=False):
            self.log.warning("正在处理中，请稍候...")
            return

        # 确保 app_id 是字符串
        app_id = str(app_id)

        self.log.info(f"选择游戏: {game_name} (ID: {app_id})")

        # 获取选中的仓库列表
        selected_repo_names = []
        for (name, value) in self.repo_options:
            if value in self.selected_repos:
                selected_repo_names.append(name)

        if not selected_repo_names:
            messagebox.showwarning("提示", "请至少选择一个清单源")
            self.processing_lock.release()
            return

        # 确认对话框 - 显示所有选中的仓库
        repo_list_str = "\n".join([f"  • {name}" for name in selected_repo_names])
        result = messagebox.askyesno("确认",
                                     f"确定要为以下游戏下载并安装清单吗？\n\n"
                                     f"游戏: {game_name}\n"
                                     f"App ID: {app_id}\n\n"
                                     f"选中的清单源:\n{repo_list_str}\n\n"
                                     f"将按顺序尝试，直到成功为止。")

        if result:
            self.process_game(app_id, game_name)
        else:
            self.processing_lock.release()

    def process_game(self, app_id: str, game_name: str):
        """处理游戏"""
        self.status_label.configure(text=f"正在处理: {game_name}")
        self.progress_bar.start()

        thread = threading.Thread(target=self.process_game_thread, args=(app_id, game_name), daemon=True)
        thread.start()

    def process_game_thread(self, app_id: str, game_name: str):
        """处理游戏线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 确保 app_id 是字符串
            app_id = str(app_id)

            self.log.info(f"开始处理: {game_name} (ID: {app_id})")

            success = False
            failed_repos = []

            # 创建专用的 HTTP 客户端
            async def process_with_client():
                async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
                    # 按顺序尝试所有选中的仓库（转换为列表）
                    selected_repos_list = list(self.selected_repos)
                    for repo_value in selected_repos_list:
                        # 找到仓库名称
                        repo_name = None
                        for name, value in self.repo_options:
                            if value == repo_value:
                                repo_name = name
                                break

                        if not repo_name:
                            continue

                        self.log.info(f"尝试从 {repo_name} 下载清单...")

                        try:
                            if self.search_all_var.get():
                                # 搜索所有GitHub库模式
                                github_repos = [val for _, val in self.repo_options if
                                                val not in ["swa", "cysaw", "furcate", "cngs", "steamdatabase"]]
                                results = await self.backend.search_all_repos(client, app_id, github_repos)

                                if results:
                                    # 使用最新的
                                    results.sort(key=lambda x: x['update_date'], reverse=True)
                                    selected = results[0]
                                    result = await self.process_from_github_with_client(client, app_id,
                                                                                        selected['repo'],
                                                                                        selected)
                                    if result:
                                        self.log.info(f"从 {selected['repo']} 下载成功")
                                        return True
                                else:
                                    self.log.error("在所有GitHub库中都未找到清单")
                                    return False
                            else:
                                # 使用指定的库
                                if repo_value == "swa":
                                    result = await self.backend._process_zip_based_manifest(
                                        client, app_id, f'https://api.printedwaste.com/gfk/download/{app_id}', "SWA V2")
                                elif repo_value == "cysaw":
                                    result = await self.backend._process_zip_based_manifest(
                                        client, app_id, f'https://cysaw.top/uploads/{app_id}.zip', "Cysaw")
                                elif repo_value == "furcate":
                                    result = await self.backend._process_zip_based_manifest(
                                        client, app_id, f'https://furcate.eu/files/{app_id}.zip', "Furcate")
                                elif repo_value == "cngs":
                                    result = await self.backend._process_zip_based_manifest(
                                        client, app_id, f'https://assiw.cngames.site/qindan/{app_id}.zip', "CNGS")
                                elif repo_value == "steamdatabase":
                                    result = await self.backend._process_zip_based_manifest(
                                        client, app_id,
                                        f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{app_id}.zip',
                                        "SteamDatabase")
                                else:
                                    # GitHub库
                                    result = await self.process_from_github_with_client(client, app_id, repo_value)

                                if result:
                                    self.log.info(f"从 {repo_name} 下载成功")
                                    return True
                                else:
                                    failed_repos.append(repo_name)
                                    self.log.warning(f"从 {repo_name} 下载失败，尝试下一个源...")

                        except Exception as e:
                            failed_repos.append(repo_name)
                            self.log.error(f"从 {repo_name} 下载时出错: {str(e)}")
                            continue

                    return False

            success = loop.run_until_complete(process_with_client())

            if success:
                # 保存入库时的游戏名称
                self.cache_manager.set_installed_game_name(app_id, game_name)
                # 立即保存到文件
                self.cache_manager.save_installed_games()

                self.log.info(f"处理成功: {game_name}")
                self.root.after(0, lambda: messagebox.showinfo("成功",
                                                               f"游戏 {game_name} 的清单已成功下载并安装！\n\n"
                                                               f"请重启Steam客户端以使更改生效。"))
                # 延迟一下再刷新，确保文件已保存
                self.root.after(100, lambda: self.refresh_game_display())
            else:
                self.log.error(f"处理失败: {game_name}")
                failed_msg = "\n".join([f"  • {repo}" for repo in failed_repos])
                self.root.after(0,
                                lambda: messagebox.showerror("失败",
                                                             f"处理游戏 {game_name} 时出错！\n\n"
                                                             f"以下清单源都尝试失败:\n{failed_msg}\n\n"
                                                             f"请查看日志了解详情。"))

        except Exception as e:
            self.log.error(f"处理出错: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误:\n{str(e)}"))
        finally:
            self.root.after(0, self.process_complete)
            self.processing_lock.release()
            # 确保事件循环正确关闭
            try:
                # 给一点时间让任务完成
                loop.run_until_complete(asyncio.sleep(0.1))
                # 停止事件循环
                loop.stop()
                # 关闭事件循环
                loop.close()
            except:
                pass

    async def process_from_github_with_client(self, client: httpx.AsyncClient, app_id: str, repo: str,
                                              existing_data: Dict = None):
        """从GitHub处理（使用传入的客户端）"""
        try:
            # 确保 app_id 是字符串
            app_id = str(app_id)

            # 检查CN
            await self.backend.checkcn(client)

            # 检查API限制
            headers = self.backend.get_github_headers()
            if not await self.backend.check_github_api_rate_limit(client, headers):
                return False

            # 获取分支信息
            if existing_data:
                sha = existing_data['sha']
                tree = existing_data['tree']
                date = existing_data['update_date']
            else:
                branch_url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
                branch_info = await self.backend.fetch_branch_info(client, branch_url, headers)
                if not branch_info:
                    return False

                sha = branch_info['commit']['sha']
                date = branch_info["commit"]["commit"]["author"]["date"]

                tree_url = branch_info['commit']['commit']['tree']['url']
                tree_info = await self.backend.fetch_branch_info(client, tree_url, headers)
                if not tree_info:
                    return False

                tree = tree_info['tree']

            # 获取所有清单文件
            all_manifests = [item['path'] for item in tree if item['path'].endswith('.manifest')]

            # 下载并处理文件
            tasks = []
            for item in tree:
                task = self.backend.get_manifest_from_github(
                    client, sha, item['path'], repo, app_id, all_manifests)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 收集depot
            collected_depots = []
            for res in results:
                if isinstance(res, Exception):
                    self.log.error(f"下载文件出错: {res}")
                    continue
                if res:
                    collected_depots.extend(res)

            # 处理结果
            if self.backend.is_steamtools():
                self.log.info('检测到SteamTools，已生成解锁文件')
            elif collected_depots:
                await self.backend.greenluma_add([app_id] + [depot_id for depot_id, _ in collected_depots])
                await self.backend.depotkey_merge(
                    {'depots': {depot_id: {'DecryptionKey': key} for depot_id, key in collected_depots}})

            self.log.info(f'清单更新时间: {date}')
            return True

        except Exception as e:
            self.log.error(f"GitHub处理失败: {str(e)}")
            return False

    def refresh_game_display(self):
        """刷新游戏显示"""
        # 清除游戏列表缓存，强制重新扫描
        self.cache_manager.game_list_cache = []

        # 重新加载缓存以获取最新数据
        self.cache_manager.installed_games_cache = self.cache_manager.load_installed_games()

        # 清空搜索框
        self.search_entry.delete(0, tk.END)

        # 显示已入库游戏
        self.show_installed_games_on_main()

    def process_complete(self):
        """处理完成"""
        self.status_label.configure(text="就绪")
        self.progress_bar.stop()

    def show_settings_dialog(self):
        """显示设置对话框"""
        # 先从缓存同步设置到backend，确保显示最新的设置
        cached_settings = self.cache_manager.settings_cache
        if cached_settings:
            print(f"从缓存加载的设置: {cached_settings}")
            for key in ['steam_path_mode', 'Custom_Steam_Path', 'unlocker_mode',
                        'manual_unlocker', 'Github_Personal_Token', 'steamtools_only_lua']:
                if key in cached_settings:
                    self.backend.app_config[key] = cached_settings[key]

        print(f"传递给对话框的配置: {self.backend.app_config}")

        dialog = SettingsDialog(self.root, self.backend.app_config)
        self.root.wait_window(dialog)

        if dialog.result:
            print(f"对话框返回的结果: {dialog.result}")

            # 更新backend配置
            self.backend.app_config.update(dialog.result)

            # 保存到config.json
            self.backend.save_config()

            # 同步到缓存
            self.save_settings_to_cache()

            # 再次保存config.json确保写入
            self.backend.save_config()

            self.log.info("配置已保存")
            print(f"保存后的backend配置: {self.backend.app_config}")
            print(f"保存后的缓存: {self.cache_manager.settings_cache}")

            # 重新检测环境
            self.detect_environment()

    def show_installed_games(self):
        """显示已安装游戏"""
        dialog = InstalledGamesDialog(self.root, self.backend, self.cache_manager)
        dialog.parent_gui = self  # 设置主窗口引用

    def show_repo_manager(self):
        """显示GitHub仓库管理"""
        dialog = GitHubRepoManager(self.root, self.cache_manager, self)
        self.root.wait_window(dialog)

        # 刷新清单源列表
        self.refresh_repo_options()

    def refresh_repo_options(self):
        """刷新清单源选项列表"""
        # 保存当前选中的仓库
        current_selected = self.selected_repos.copy()

        # 从缓存加载所有仓库
        repo_config = self.cache_manager.repo_config
        self.all_repos = repo_config.get('all_repos', self.cache_manager.get_default_repos())
        self.repo_options = [(repo['name'], repo['path']) for repo in self.all_repos]

        # 清除旧的复选框
        if hasattr(self, 'repo_inner_frame'):
            for widget in self.repo_inner_frame.winfo_children():
                widget.destroy()

            # 清空选中的仓库集合，准备重建
            self.selected_repos.clear()

            # 创建新的复选框
            self.repo_checkbuttons = {}
            for i, (name, value) in enumerate(self.repo_options):
                # 检查这个仓库是否应该被选中
                if value in current_selected:
                    var = tk.BooleanVar(value=True)
                    self.selected_repos.add(value)
                else:
                    var = tk.BooleanVar(value=False)

                cb = ttk.Checkbutton(self.repo_inner_frame, text=name, variable=var,
                                     command=lambda v=value, var=var: self.on_repo_toggle(v, var))
                cb.pack(anchor=W, pady=2)
                self.repo_checkbuttons[value] = var

            # 确保至少有一个被选中
            if not self.selected_repos and self.repo_options:
                first_value = self.repo_options[0][1]
                self.selected_repos.add(first_value)
                self.repo_checkbuttons[first_value].set(True)

            # 更新Canvas滚动区域
            if hasattr(self, 'repo_canvas'):
                self.repo_canvas.configure(scrollregion=self.repo_canvas.bbox("all"))

            # 保存设置
            self.save_settings_to_cache()

    def cleanup_cache(self):
        """清理缓存"""
        cache_size = 0
        file_count = 0

        # 计算缓存大小
        if self.cache_manager.cache_dir.exists():
            for file in self.cache_manager.cache_dir.rglob('*'):
                if file.is_file():
                    cache_size += file.stat().st_size
                    file_count += 1

        # 转换为易读格式
        if cache_size > 1024 * 1024:
            size_str = f"{cache_size / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{cache_size / 1024:.2f} KB"

        result = messagebox.askyesno("确认清理",
                                     f"缓存目录: {self.cache_manager.cache_dir.absolute()}\n"
                                     f"缓存大小: {size_str} ({file_count} 个文件)\n\n"
                                     f"确定要清理所有缓存吗？\n\n"
                                     f"这将删除：\n"
                                     f"• 游戏信息缓存\n"
                                     f"• 游戏图片缓存\n"
                                     f"• 已安装游戏名称记录\n\n"
                                     f"清理后需要重新获取游戏信息。")

        if result:
            try:
                # 清理缓存目录
                if self.cache_manager.cache_dir.exists():
                    import shutil
                    shutil.rmtree(self.cache_manager.cache_dir)
                    self.cache_manager.cache_dir.mkdir(exist_ok=True)
                    self.cache_manager.images_dir.mkdir(exist_ok=True)

                    # 重新初始化缓存
                    self.cache_manager.game_info_cache = {}
                    self.cache_manager.installed_games_cache = {}
                    self.cache_manager.game_list_cache = []  # 清除游戏列表缓存
                    self.cache_manager.settings_cache = self.cache_manager.load_settings()

                    self.log.info("缓存已清理")
                    messagebox.showinfo("成功", "缓存清理完成")

                    # 刷新显示
                    self.show_installed_games_on_main()
                else:
                    messagebox.showinfo("提示", "没有需要清理的缓存")
            except Exception as e:
                self.log.error(f"清理缓存失败: {str(e)}")
                messagebox.showerror("错误", f"清理缓存失败:\n{str(e)}")

    def show_installed_games_on_main(self):
        """在主界面显示已入库的游戏"""
        try:
            if not self.processing_lock.acquire(blocking=False):
                return

            # 清空当前显示
            self.clear_game_display()
            self.status_label.configure(text="加载已入库游戏...")
            self.progress_bar.start()

            # 异步加载
            thread = threading.Thread(target=self.load_installed_games_thread, daemon=True)
            thread.start()
        except Exception as e:
            import traceback
            self.log.error(f"显示已入库游戏失败: {str(e)}\n{traceback.format_exc()}")
            self.processing_lock.release()

    def load_installed_games_thread(self):
        """加载已入库游戏的线程"""
        try:
            # 首先尝试从缓存加载
            cached_games = self.cache_manager.game_list_cache
            if cached_games:
                # 直接使用缓存的游戏列表
                self.current_games = cached_games
                self.root.after(0, self.display_installed_games, cached_games)
                return

            # 如果没有缓存，则扫描文件系统（只在首次运行或缓存丢失时）
            games = []

            if self.backend.steam_path.exists():
                stplug_dir = self.backend.steam_path / "config" / "stplug-in"
                if stplug_dir.exists():
                    for lua_file in stplug_dir.glob("*.lua"):
                        match = re.search(r'(\d+)', lua_file.stem)
                        if match:
                            app_id = match.group(1)

                            # 从已保存的名称获取（优先级最高）
                            installed_name = self.cache_manager.get_installed_game_name(app_id)
                            if installed_name:
                                name = installed_name
                            else:
                                # 其次使用缓存的游戏信息
                                cached_info = self.cache_manager.get_game_info(app_id)
                                if cached_info:
                                    name = cached_info.get('name_cn', cached_info.get('name', f'游戏 {app_id}'))
                                else:
                                    # 最后使用默认名称
                                    name = f'游戏 {app_id}'

                            games.append({
                                'appid': app_id,
                                'name': name,
                                'is_installed': True
                            })

            # 保存到缓存
            self.cache_manager.save_game_list(games)
            self.current_games = games
            self.root.after(0, self.display_installed_games, games)

        except Exception as e:
            self.log.error(f"加载已入库游戏失败: {str(e)}")
            self.root.after(0, self.search_complete)
        finally:
            self.processing_lock.release()

    def display_installed_games(self, games):
        """显示已入库的游戏"""
        self.clear_game_display()

        if not games:
            self.log.info("没有已入库的游戏")
            self.status_label.configure(text="没有已入库的游戏")
            self.search_complete()
            return

        self.log.info(f"找到 {len(games)} 个已入库游戏")
        self.status_label.configure(text=f"已入库游戏: {len(games)} 个")

        # 获取Canvas宽度来决定列数和卡片大小
        canvas_width = self.game_canvas.winfo_width()
        if canvas_width <= 1:  # Canvas还未完全初始化
            canvas_width = 1000  # 使用默认宽度

        min_card_width = 280  # 最小卡片宽度
        max_card_width = 400  # 最大卡片宽度
        padding = 20  # 卡片之间的间距

        # 计算最佳列数
        cols = max(1, canvas_width // (min_card_width + padding))
        # 计算实际卡片宽度
        available_width = canvas_width - (cols + 1) * padding
        card_width = min(max_card_width, max(min_card_width, available_width // cols))
        card_height = int(card_width * 0.7)  # 高度是宽度的70%

        # 创建游戏卡片
        for i, game in enumerate(games):
            app_id = str(game['appid'])  # 确保是字符串
            name = game['name']

            # 如果名称是默认的"游戏 XXXXX"格式，尝试从缓存获取更好的名称
            if name.startswith('游戏 ') and app_id in name:
                # 再次尝试从缓存获取
                installed_name = self.cache_manager.get_installed_game_name(app_id)
                if installed_name:
                    name = installed_name
                else:
                    cached_info = self.cache_manager.get_game_info(app_id)
                    if cached_info:
                        name = cached_info.get('name_cn', cached_info.get('name', name))

            # 创建卡片
            row = i // cols
            col = i % cols

            # 优先从缓存加载图片
            cached_image = self.cache_manager.load_image(app_id)

            card = GameCard(self.game_frame, app_id, name, {}, cached_image,
                            self.on_game_selected, self.on_game_delete, is_installed=True, main_gui=self)
            card.grid(row=row, column=col, padx=padding // 2, pady=padding // 2, sticky="nsew")
            card.configure(width=card_width, height=card_height)
            self.game_cards.append(card)

            # 如果没有缓存图片，异步加载
            if not cached_image:
                threading.Thread(target=self.load_game_image, args=(card, app_id), daemon=True).start()

        # 配置列权重和行权重
        for i in range(cols):
            self.game_frame.columnconfigure(i, weight=1, minsize=card_width)

            # 配置行权重
            rows = (len(games) + cols - 1) // cols
            for i in range(rows):
                self.game_frame.rowconfigure(i, weight=1, minsize=card_height)

            # 滚动到顶部
            self.game_canvas.yview_moveto(0)

            self.search_complete()

    def mainloop(self):
        """运行主循环"""
        self.root.mainloop()


# Dialog Classes
class UnlockerSelectionDialog(tk.Toplevel):
    """解锁工具选择对话框"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("选择解锁工具")
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None

        # 设置图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, '图标.ico')
            else:
                icon_path = '图标.ico'
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 400) // 2
        y = (self.winfo_screenheight() - 200) // 2
        self.geometry(f"400x200+{x}+{y}")

        # 创建UI
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill=BOTH, expand=True)

        ttk.Label(frame, text="未能自动检测到解锁工具\n请选择您使用的解锁工具:",
                  font=("Arial", 11), justify=CENTER).pack(pady=(0, 20))

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()

        ttk.Button(btn_frame, text="SteamTools", command=lambda: self.select("steamtools"),
                   style="info.TButton", width=15).pack(side=LEFT, padx=10)

        ttk.Button(btn_frame, text="GreenLuma", command=lambda: self.select("greenluma"),
                   style="success.TButton", width=15).pack(side=LEFT, padx=10)

        ttk.Button(frame, text="取消", command=self.destroy,
                   style="secondary.TButton", width=10).pack(pady=(20, 0))

    def select(self, tool):
        self.result = tool
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """设置对话框"""

    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("设置")
        self.geometry("600x500")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.result = None
        self.config = config.copy()

        # 设置图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, '图标.ico')
            else:
                icon_path = '图标.ico'
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 600) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"600x500+{x}+{y}")

        # 创建UI
        notebook = ttk.Notebook(self, padding=10)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # 基本设置
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="基本设置")
        self.create_basic_settings(basic_frame)

        # 高级设置
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="高级设置")
        self.create_advanced_settings(advanced_frame)

        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=X, side=BOTTOM, padx=10, pady=10)  # 添加 side=BOTTOM

        ttk.Button(btn_frame, text="取消", command=self.destroy,
                   style="secondary.TButton").pack(side=RIGHT, padx=(0, 5))

        ttk.Button(btn_frame, text="保存", command=self.save,
                   style="success.TButton").pack(side=RIGHT)

    def on_steam_mode_change(self):
        """Steam路径模式改变时的处理"""
        if self.steam_mode_var.get() == "auto":
            self.steam_path_entry.configure(state="disabled")
            self.browse_btn.configure(state="disabled")
        else:
            self.steam_path_entry.configure(state="normal")
            self.browse_btn.configure(state="normal")

    def on_unlocker_mode_change(self):
        """解锁工具模式改变时的处理"""
        if self.unlocker_mode_var.get() == "auto":
            self.unlocker_combo.configure(state="disabled")
        else:
            self.unlocker_combo.configure(state="readonly")

    def browse_steam_path(self):
        """浏览选择Steam路径"""
        from tkinter import filedialog
        path = filedialog.askdirectory(title="选择Steam安装目录")
        if path:
            self.steam_path_var.set(path)

    def create_basic_settings(self, parent):
        """创建基本设置"""
        frame = ttk.Frame(parent, padding=20)
        frame.pack(fill=BOTH, expand=True)

        # Steam路径设置
        ttk.Label(frame, text="Steam路径设置:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=W,
                                                                                 pady=(0, 10), columnspan=2)

        # Steam路径模式选择
        self.steam_mode_var = tk.StringVar(value=self.config.get("steam_path_mode", "auto"))
        ttk.Radiobutton(frame, text="自动检测", variable=self.steam_mode_var, value="auto",
                        command=self.on_steam_mode_change).grid(row=1, column=0, sticky=W, padx=20)
        ttk.Radiobutton(frame, text="手动设置", variable=self.steam_mode_var, value="manual",
                        command=self.on_steam_mode_change).grid(row=1, column=1, sticky=W)

        # Steam路径输入框
        ttk.Label(frame, text="Steam路径:", font=("Arial", 10)).grid(row=2, column=0, sticky=W, pady=(10, 0))
        self.steam_path_var = tk.StringVar(value=self.config.get("Custom_Steam_Path", ""))
        self.steam_path_entry = ttk.Entry(frame, textvariable=self.steam_path_var, width=40)
        self.steam_path_entry.grid(row=2, column=1, padx=10, pady=(10, 0))

        # 浏览按钮
        self.browse_btn = ttk.Button(frame, text="浏览", command=self.browse_steam_path, width=8)
        self.browse_btn.grid(row=2, column=2, pady=(10, 0))

        # 初始化Steam路径输入框状态
        self.on_steam_mode_change()

        # 解锁工具设置
        ttk.Label(frame, text="解锁工具设置:", font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=W,
                                                                                pady=(20, 10), columnspan=2)

        # 解锁工具模式选择
        self.unlocker_mode_var = tk.StringVar(value=self.config.get("unlocker_mode", "auto"))
        ttk.Radiobutton(frame, text="自动检测", variable=self.unlocker_mode_var, value="auto",
                        command=self.on_unlocker_mode_change).grid(row=4, column=0, sticky=W, padx=20)
        ttk.Radiobutton(frame, text="手动选择", variable=self.unlocker_mode_var, value="manual",
                        command=self.on_unlocker_mode_change).grid(row=4, column=1, sticky=W)

        # 解锁工具选择
        ttk.Label(frame, text="解锁工具:", font=("Arial", 10)).grid(row=5, column=0, sticky=W, pady=(10, 0))
        self.unlocker_var = tk.StringVar(value=self.config.get("manual_unlocker", "steamtools"))
        self.unlocker_combo = ttk.Combobox(frame, textvariable=self.unlocker_var,
                                           values=["steamtools", "greenluma"],
                                           state="readonly", width=37)
        self.unlocker_combo.grid(row=5, column=1, padx=10, pady=(10, 0))

        # 初始化解锁工具选择框状态
        self.on_unlocker_mode_change()

        # GitHub Token
        ttk.Label(frame, text="GitHub Token:", font=("Arial", 10, "bold")).grid(row=6, column=0, sticky=W,
                                                                                pady=(20, 10))

        self.token_var = tk.StringVar(value=self.config.get("Github_Personal_Token", ""))
        token_entry = ttk.Entry(frame, textvariable=self.token_var, width=40, show="*")
        token_entry.grid(row=7, column=0, columnspan=2, padx=(20, 0), sticky=W)

        # 说明
        info_text = ("GitHub Token用于提高API请求限制\n"
                     "可在GitHub设置->Developer settings->Personal access tokens中创建")
        ttk.Label(frame, text=info_text, font=("Arial", 9), foreground="gray").grid(row=8, column=0, columnspan=3,
                                                                                    pady=(10, 0))

    def create_advanced_settings(self, parent):
        """创建高级设置"""
        frame = ttk.Frame(parent, padding=20)
        frame.pack(fill=BOTH, expand=True)

        # SteamTools设置
        self.st_lua_var = tk.BooleanVar(value=self.config.get("steamtools_only_lua", False))
        ttk.Checkbutton(frame, text="使用SteamTools自动更新模式（仅下载LUA文件）",
                        variable=self.st_lua_var).pack(anchor=W, pady=10)

        ttk.Label(frame, text="启用此选项后，SteamTools将自动获取最新清单版本",
                  font=("Arial", 9), foreground="gray").pack(anchor=W, padx=20)

    def save(self):
        """保存设置"""
        # 获取所有设置值
        self.result = {
            "Github_Personal_Token": self.token_var.get(),
            "steamtools_only_lua": self.st_lua_var.get(),
            "steam_path_mode": self.steam_mode_var.get(),
            "Custom_Steam_Path": self.steam_path_var.get(),
            "unlocker_mode": self.unlocker_mode_var.get(),
            "manual_unlocker": self.unlocker_var.get()
        }

        # 打印调试信息
        print(f"[SettingsDialog] 保存的设置: {self.result}")
        print(f"[SettingsDialog] steam_path_mode = {self.steam_mode_var.get()}")

        # 显示保存成功提示
        messagebox.showinfo("成功", "设置已保存")

        self.destroy()


class InstalledGamesDialog(tk.Toplevel):
    """已安装游戏对话框"""

    def __init__(self, parent, backend, cache_manager):
        super().__init__(parent)
        self.title("入库管理")
        self.geometry("800x600")
        self.transient(parent)

        self.backend = backend
        self.cache_manager = cache_manager
        self.parent_gui = None  # 将由外部设置
        self.is_fetching = False  # 添加：是否正在获取游戏信息的标志
        self.total_to_fetch = 0  # 添加：需要获取的游戏总数
        self.fetch_progress = 0  # 添加：当前获取进度

        # 设置图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, '图标.ico')
            else:
                icon_path = '图标.ico'
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 800) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"800x600+{x}+{y}")

        # 创建UI
        self.create_ui()

        # 加载游戏列表
        self.refresh_list()

        # 窗口关闭时清理
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        """创建UI"""
        # 工具栏
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill=X)

        # 修改：将刷新按钮设为实例变量，以便控制其状态
        self.refresh_btn = ttk.Button(toolbar, text="刷新", command=self.refresh_list,
                                      style="info.TButton")
        self.refresh_btn.pack(side=LEFT, padx=5)

        ttk.Button(toolbar, text="全选", command=self.select_all,
                   style="primary.TButton").pack(side=LEFT, padx=5)

        ttk.Button(toolbar, text="删除选中", command=self.delete_selected,
                   style="danger.TButton").pack(side=LEFT, padx=5)

        ttk.Label(toolbar, text="|", font=("Arial", 10)).pack(side=LEFT, padx=10)

        ttk.Button(toolbar, text="GitHub仓库管理", command=self.open_repo_manager,
                   style="secondary.TButton").pack(side=LEFT, padx=5)

        # 修改：调整状态标签的字体大小
        self.status_label = ttk.Label(toolbar, text="", font=("Arial", 11, "bold"))
        self.status_label.pack(side=RIGHT, padx=10)

        # 列表
        list_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        list_frame.pack(fill=BOTH, expand=True)

        # Treeview
        columns = ("appid", "name", "date")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("appid", text="App ID")
        self.tree.heading("name", text="游戏名称")
        self.tree.heading("date", text="安装日期")

        self.tree.column("appid", width=100)
        self.tree.column("name", width=400)
        self.tree.column("date", width=200)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

    def refresh_list(self):
        """刷新列表"""
        # 添加：如果正在获取信息，不允许刷新
        if self.is_fetching:
            messagebox.showinfo("提示", "正在获取游戏信息，请稍候...")
            return

        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 获取已安装游戏
        if not self.backend.steam_path.exists():
            return

        stplug_dir = self.backend.steam_path / "config" / "stplug-in"
        if not stplug_dir.exists():
            return

        # 扫描lua文件
        import re
        from datetime import datetime

        # 收集所有游戏信息
        games_to_fetch = []
        temp_game_list = []

        for lua_file in stplug_dir.glob("*.lua"):
            # 提取AppID
            match = re.search(r'(\d+)', lua_file.stem)
            if match:
                app_id = match.group(1)

                # 优先使用入库时保存的名称
                installed_name = self.cache_manager.get_installed_game_name(app_id)
                if installed_name:
                    game_name = installed_name
                else:
                    # 否则从缓存获取游戏名称
                    cached_info = self.cache_manager.get_game_info(app_id)
                    if cached_info:
                        game_name = cached_info.get('name_cn', cached_info.get('name', f'游戏 {app_id}'))
                    else:
                        game_name = f"获取中... (ID: {app_id})"
                        games_to_fetch.append(app_id)

                # 获取修改时间
                mtime = datetime.fromtimestamp(lua_file.stat().st_mtime)
                date_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

                temp_game_list.append({
                    'app_id': app_id,
                    'name': game_name,
                    'date': date_str
                })

        # 先添加到列表（使用现有名称）
        for game in temp_game_list:
            self.tree.insert("", "end", values=(game['app_id'], game['name'], game['date']), tags=(game['app_id'],))

        # 如果有需要获取信息的游戏，显示提示
        if games_to_fetch:
            # 添加：设置获取标志，禁用刷新按钮
            self.is_fetching = True
            self.refresh_btn.configure(state="disabled")

            # 保存需要获取的游戏总数
            self.total_to_fetch = len(games_to_fetch)
            self.fetch_progress = 0

            # 修改：更新状态显示正在获取，使用更醒目的颜色
            self.status_label.configure(text=f"正在获取游戏信息... (0/{self.total_to_fetch})",
                                        foreground="#FF6B6B")  # 使用更醒目的红色

            # 异步获取未缓存的游戏信息
            threading.Thread(target=self.fetch_games_with_progress, args=(games_to_fetch,), daemon=True).start()
        else:
            self.status_label.configure(text="")
            # 同步到主界面
            self.sync_to_main_window()

    def fetch_games_with_progress(self, app_ids: List[str]):
        """带进度提示的游戏信息获取"""
        try:
            # 批量获取游戏信息
            self.fetch_multiple_game_info(app_ids)

            # 完成后的处理
            def on_complete():
                # 重置获取标志，启用刷新按钮
                self.is_fetching = False
                self.refresh_btn.configure(state="normal")

                # 更新状态
                self.status_label.configure(text="获取完成！", foreground="#51CF66")  # 绿色
                self.after(3000, lambda: self.status_label.configure(text=""))

            self.after(0, on_complete)
        except Exception as e:
            print(f"获取游戏信息时出错: {str(e)}")

            def on_error():
                # 重置获取标志，启用刷新按钮
                self.is_fetching = False
                self.refresh_btn.configure(state="normal")

                # 显示错误状态
                self.status_label.configure(text="获取失败", foreground="#FF6B6B")  # 红色
                self.after(3000, lambda: self.status_label.configure(text=""))

            self.after(0, on_error)

    def sync_to_main_window(self):
        """同步到主窗口"""
        try:
            # 清除主窗口的游戏列表缓存
            if self.parent_gui:
                self.parent_gui.cache_manager.game_list_cache = []
                # 直接调用主窗口的方法
                if hasattr(self.parent_gui, 'show_installed_games_on_main'):
                    self.parent_gui.show_installed_games_on_main()
        except Exception as e:
            print(f"同步到主窗口失败: {str(e)}")

    def fetch_multiple_game_info(self, app_ids: List[str]):
        """批量异步获取游戏信息"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            updated = False

            async def fetch_game_info_async():
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    # 创建批次
                    batch_size = 5  # 每批处理5个游戏

                    for batch_start in range(0, len(app_ids), batch_size):
                        batch_end = min(batch_start + batch_size, len(app_ids))
                        batch_app_ids = app_ids[batch_start:batch_end]

                        # 创建当前批次的并发任务
                        tasks = []
                        for app_id in batch_app_ids:
                            task = self._fetch_single_game_info(client, app_id)
                            tasks.append((app_id, task))

                        # 并发执行当前批次
                        try:
                            # 获取所有任务
                            task_list = [task for _, task in tasks]
                            results = await asyncio.gather(*task_list, return_exceptions=True)

                            # 处理结果
                            for (app_id, _), result in zip(tasks, results):
                                if isinstance(result, Exception):
                                    print(f"获取游戏信息失败 {app_id}: {result}")
                                    # 即使失败也要更新进度
                                    self.after(0, lambda: self.update_fetch_progress_only())
                                elif result:
                                    # 成功获取信息
                                    game_name = result['name']

                                    # 保存到缓存
                                    self.cache_manager.set_game_info(app_id, result)

                                    # 如果没有入库时保存的名称，保存当前获取的名称
                                    if not self.cache_manager.get_installed_game_name(app_id):
                                        self.cache_manager.set_installed_game_name(app_id, game_name)

                                    # 立即更新UI
                                    self.after(0, self.update_game_name, app_id, game_name)
                                    nonlocal updated
                                    updated = True
                                else:
                                    # 获取失败也要更新进度
                                    self.after(0, lambda: self.update_fetch_progress_only())

                        except Exception as e:
                            print(f"批次处理出错: {e}")
                            # 批次失败时，更新该批次的进度
                            for _ in batch_app_ids:
                                self.after(0, lambda: self.update_fetch_progress_only())

                        # 批次之间短暂延迟，避免请求过于密集
                        if batch_end < len(app_ids):
                            await asyncio.sleep(1)

                return updated

            # 执行异步获取
            updated = loop.run_until_complete(fetch_game_info_async())

        except Exception as e:
            print(f"批量获取游戏信息出错: {str(e)}")
        finally:
            try:
                loop.close()
            except:
                pass

    async def _fetch_single_game_info(self, client: httpx.AsyncClient, app_id: str) -> Optional[Dict]:
        """获取单个游戏信息（用于并发执行）"""
        try:
            # 先尝试通过主窗口的搜索逻辑获取
            if self.parent_gui and hasattr(self.parent_gui, 'backend'):
                # 使用backend的搜索功能
                games = await self.parent_gui.backend.search_games_by_name(client, app_id)

                # 在搜索结果中找到匹配的AppID
                for game in games:
                    if str(game.get('appid')) == str(app_id):
                        game_name = game.get('schinese_name', game.get('name', f'游戏 {app_id}'))

                        # 同时获取图片
                        image_task = SteamAPIHelper.get_game_image(client, app_id)

                        # 等待图片任务完成（不阻塞主要信息返回）
                        try:
                            image_data = await image_task
                            if image_data:
                                self.cache_manager.save_image(app_id, image_data)
                        except:
                            pass

                        return {
                            'name': game_name,
                            'name_cn': game_name,
                            'appid': app_id
                        }

                # 如果搜索结果中没找到，尝试直接通过Steam API获取
                game_info = await SteamAPIHelper.get_game_info(client, app_id)
                if game_info and game_info['name'] != f'游戏 {app_id}':
                    # 同时获取并缓存图片
                    image_task = SteamAPIHelper.get_game_image(client, app_id)

                    try:
                        image_data = await image_task
                        if image_data:
                            self.cache_manager.save_image(app_id, image_data)
                    except:
                        pass

                    return game_info

            return None

        except Exception as e:
            print(f"获取游戏信息失败 {app_id}: {str(e)}")
            raise

    def update_game_name(self, app_id: str, name: str):
        """更新游戏名称"""
        # 立即更新列表中的游戏名称
        for item in self.tree.get_children():
            if app_id in self.tree.item(item)["tags"]:
                values = list(self.tree.item(item)["values"])
                values[1] = name
                self.tree.item(item, values=values)
                break

        # 更新进度计数
        self.fetch_progress += 1

        # 更新进度显示
        if self.fetch_progress < self.total_to_fetch:
            self.status_label.configure(
                text=f"正在获取游戏信息... ({self.fetch_progress}/{self.total_to_fetch})",
                foreground="#FF6B6B"
            )
        else:
            # 获取完成
            self.is_fetching = False
            self.refresh_btn.configure(state="normal")
            self.status_label.configure(text="获取完成！", foreground="#51CF66")

            # 同步到主界面
            self.sync_to_main_window()

            # 延迟2秒后自动刷新
            self.after(2000, self.auto_refresh_after_fetch)

    def update_fetch_progress_only(self):
        """仅更新获取进度（用于获取失败的情况）"""
        self.fetch_progress += 1

        if self.fetch_progress < self.total_to_fetch:
            self.status_label.configure(
                text=f"正在获取游戏信息... ({self.fetch_progress}/{self.total_to_fetch})",
                foreground="#FF6B6B"
            )
        else:
            # 获取完成
            self.is_fetching = False
            self.refresh_btn.configure(state="normal")
            self.status_label.configure(text="获取完成！", foreground="#51CF66")

            # 同步到主界面
            self.sync_to_main_window()

            # 延迟2秒后自动刷新
            self.after(2000, self.auto_refresh_after_fetch)

    def auto_refresh_after_fetch(self):
        """获取完成后自动刷新"""
        # 检查窗口是否还存在
        try:
            if self.winfo_exists():
                # 重置获取标志，确保可以刷新
                self.is_fetching = False
                # 触发刷新
                self.refresh_list()
        except:
            pass

    def select_all(self):
        """全选所有项"""
        items = self.tree.get_children()
        self.tree.selection_set(items)

    def delete_selected(self):
        """删除选中项"""
        # 添加：如果正在获取信息，不允许删除
        if self.is_fetching:
            messagebox.showinfo("提示", "正在获取游戏信息，请稍候...")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择要删除的游戏")
            return

        if not messagebox.askyesno("确认", f"确定要删除选中的 {len(selected)} 个游戏吗？"):
            return

        # 删除文件
        for item in selected:
            values = self.tree.item(item)["values"]
            app_id = values[0]

            # 删除相关文件
            stplug_dir = self.backend.steam_path / "config" / "stplug-in"
            depot_dir = self.backend.steam_path / "depotcache"

            # 删除lua文件
            for f in stplug_dir.glob(f"*{app_id}*.lua"):
                f.unlink()

            # 删除manifest文件
            for f in depot_dir.glob(f"*{app_id}*.manifest"):
                f.unlink()

            # 从已安装缓存中移除
            self.cache_manager.remove_installed_game(app_id)

        # 刷新列表
        self.refresh_list()
        messagebox.showinfo("成功", "删除完成")

        # 同步到主界面
        self.sync_to_main_window()

    def on_closing(self):
        """窗口关闭时清理"""
        self.destroy()

    def open_repo_manager(self):
        """打开GitHub仓库管理器"""
        if self.parent_gui:
            self.parent_gui.show_repo_manager()


class GitHubRepoManager(tk.Toplevel):
    """GitHub仓库管理对话框"""

    def __init__(self, parent, cache_manager, parent_gui=None):
        super().__init__(parent)
        self.title("GitHub仓库管理")
        self.geometry("700x500")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.cache_manager = cache_manager
        self.parent_gui = parent_gui

        # 加载所有仓库
        repo_config = self.cache_manager.repo_config
        self.all_repos = repo_config.get('all_repos', self.cache_manager.get_default_repos())

        # 设置图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, '图标.ico')
            else:
                icon_path = '图标.ico'
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 700) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"700x500+{x}+{y}")

        # 创建UI
        self.create_ui()

        # 加载仓库列表
        self.refresh_list()

    def create_ui(self):
        """创建UI"""
        # 顶部说明
        info_frame = ttk.Frame(self, padding=10)
        info_frame.pack(fill=X)

        ttk.Label(info_frame, text="仓库管理",
                  font=("Arial", 12, "bold")).pack(anchor=W)
        ttk.Label(info_frame, text="可以添加、删除和管理所有仓库，格式: owner/repository",
                  font=("Arial", 9), foreground="gray").pack(anchor=W, pady=(5, 0))

        # 添加仓库区域
        add_frame = ttk.Frame(self, padding=(10, 5))
        add_frame.pack(fill=X)

        ttk.Label(add_frame, text="添加GitHub仓库:").pack(side=LEFT, padx=(0, 10))

        self.repo_entry = ttk.Entry(add_frame, width=30, font=("Arial", 10))
        self.repo_entry.pack(side=LEFT, padx=(0, 10))
        self.repo_entry.bind("<Return>", lambda e: self.add_repo())

        ttk.Button(add_frame, text="添加", command=self.add_repo,
                   style="success.TButton").pack(side=LEFT)

        # 仓库列表（使用Treeview以显示更多信息）
        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(fill=BOTH, expand=True)

        # 创建Treeview
        columns = ("type", "path", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=12)

        self.tree.heading("#0", text="仓库名称")
        self.tree.heading("type", text="类型")
        self.tree.heading("path", text="路径")
        self.tree.heading("status", text="状态")

        self.tree.column("#0", width=200)
        self.tree.column("type", width=80)
        self.tree.column("path", width=250)
        self.tree.column("status", width=80)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 说明文字
        note_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        note_frame.pack(fill=X)
        ttk.Label(note_frame, text="注意：仓库更改会自动同步到主界面",
                  font=("Arial", 9), foreground="blue").pack(anchor=W)

        # 底部按钮
        bottom_frame = ttk.Frame(self, padding=10)
        bottom_frame.pack(fill=X)

        ttk.Button(bottom_frame, text="删除选中", command=self.delete_selected,
                   style="danger.TButton").pack(side=LEFT, padx=5)

        ttk.Button(bottom_frame, text="验证选中", command=self.verify_selected,
                   style="info.TButton").pack(side=LEFT, padx=5)

        ttk.Button(bottom_frame, text="关闭", command=self.close_dialog,
                   style="secondary.TButton").pack(side=RIGHT)

    def refresh_list(self):
        """刷新仓库列表"""
        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 添加所有仓库
        for repo in self.all_repos:
            name = repo.get('name', repo['path'])
            repo_type = "ZIP源" if repo.get('type') == 'zip' else "GitHub"
            path = repo['path']
            status = "已验证" if repo.get('verified') else ""

            self.tree.insert("", "end", text=name, values=(repo_type, path, status))

    def add_repo(self):
        """添加新仓库"""
        repo_input = self.repo_entry.get().strip()
        if not repo_input:
            messagebox.showwarning("提示", "请输入仓库路径或名称")
            return

        # 判断是ZIP源还是GitHub仓库
        if '/' in repo_input:
            # GitHub仓库格式验证
            parts = repo_input.split('/')
            if len(parts) != 2:
                messagebox.showerror("格式错误", "GitHub仓库格式必须为: owner/repository")
                return

            owner, repo = parts

            # 验证owner和repository名称的合法性
            import re
            # GitHub用户名规则：字母数字、连字符，不能以连字符开头或结尾，长度1-39
            username_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,37}[a-zA-Z0-9])?$'
            # 仓库名规则：字母数字、连字符、下划线、点，长度1-100
            repo_pattern = r'^[a-zA-Z0-9][a-zA-Z0-9\-_.]{0,99}$'

            if not re.match(username_pattern, owner):
                messagebox.showerror("格式错误",
                                     f"无效的用户名格式: {owner}\n\n"
                                     "GitHub用户名规则：\n"
                                     "• 只能包含字母、数字、连字符\n"
                                     "• 不能以连字符开头或结尾\n"
                                     "• 长度1-39个字符")
                return

            if not re.match(repo_pattern, repo):
                messagebox.showerror("格式错误",
                                     f"无效的仓库名格式: {repo}\n\n"
                                     "仓库名规则：\n"
                                     "• 只能包含字母、数字、连字符、下划线、点\n"
                                     "• 必须以字母或数字开头\n"
                                     "• 长度1-100个字符")
                return

            # 检查是否是保留名称
            reserved_names = ['api', 'www', 'admin', 'help', 'support', 'blog', 'about',
                              'security', 'settings', 'account', 'explore', 'marketplace']
            if owner.lower() in reserved_names or repo.lower() in reserved_names:
                messagebox.showerror("格式错误", "用户名或仓库名包含GitHub保留字")
                return

            new_repo = {
                'name': f"{owner}/{repo}",  # 使用完整路径作为名称
                'path': repo_input,
                'type': 'github',
                'verified': False
            }
        else:
            # ZIP源验证
            valid_zip_sources = ['swa', 'cysaw', 'furcate', 'cngs', 'steamdatabase']
            if repo_input.lower() not in valid_zip_sources:
                messagebox.showerror("格式错误",
                                     f"无效的ZIP源名称: {repo_input}\n\n"
                                     f"有效的ZIP源包括: {', '.join(valid_zip_sources)}\n\n"
                                     "如果要添加GitHub仓库，请使用格式: owner/repository")
                return

            new_repo = {
                'name': repo_input,
                'path': repo_input.lower(),
                'type': 'zip',
                'verified': True
            }

        # 检查是否已存在
        for existing_repo in self.all_repos:
            if existing_repo['path'] == new_repo['path']:
                messagebox.showwarning("提示", "该仓库已存在")
                return

        # 添加到列表
        self.all_repos.append(new_repo)

        # 刷新显示
        self.refresh_list()
        self.repo_entry.delete(0, tk.END)

        # 保存
        self.save_repos()

        # 自动验证新添加的仓库（如果是GitHub仓库）
        if new_repo['type'] == 'github':
            self.tree.selection_set(self.tree.get_children()[-1])
            self.verify_selected()

    def delete_selected(self):
        """删除选中的仓库"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请选择要删除的仓库")
            return

        # 收集选中的仓库信息
        builtin_repos = []
        custom_repos = []
        all_selected_info = []

        for item in selection:
            name = self.tree.item(item)["text"]
            path = self.tree.item(item)["values"][1]
            all_selected_info.append((item, name, path))

            # 区分内置和自定义仓库
            if path in ['swa', 'cysaw', 'furcate', 'cngs', 'steamdatabase']:
                builtin_repos.append(name)
            else:
                custom_repos.append((item, name, path))

        # 构建确认消息
        msg = f"确定要删除选中的 {len(selection)} 个仓库吗？\n\n"

        if builtin_repos:
            msg += "⚠️ 警告：以下是内置仓库，删除后可能影响正常使用：\n"
            msg += "\n".join([f"  • {name}" for name in builtin_repos])
            msg += "\n\n"

        if custom_repos:
            msg += "自定义仓库：\n"
            msg += "\n".join([f"  • {name}" for _, name, _ in custom_repos])
            msg += "\n"

        msg += "\n删除后可以通过重新添加来恢复。"

        if messagebox.askyesno("确认删除", msg, icon='warning' if builtin_repos else 'question'):
            # 收集要删除的路径
            paths_to_delete = [path for _, _, path in all_selected_info]

            # 从列表中删除
            self.all_repos = [repo for repo in self.all_repos if repo['path'] not in paths_to_delete]

            # 确保至少保留一个仓库
            if not self.all_repos:
                # 如果全部删除了，至少恢复一个默认仓库
                self.all_repos.append({
                    "name": "SWA V2库",
                    "path": "swa",
                    "type": "zip",
                    "verified": True
                })
                messagebox.showinfo("提示", "已自动恢复SWA V2库，至少需要保留一个仓库源。")

            # 保存并刷新
            self.save_repos()
            self.refresh_list()

    def verify_selected(self):
        """验证选中的仓库是否存在"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请选择要验证的仓库")
            return

        # 创建进度窗口
        progress_window = tk.Toplevel(self)
        progress_window.title("验证中")
        progress_window.geometry("300x100")
        progress_window.transient(self)
        progress_window.grab_set()

        # 居中
        progress_window.update_idletasks()
        x = (progress_window.winfo_screenwidth() - 300) // 2
        y = (progress_window.winfo_screenheight() - 100) // 2
        progress_window.geometry(f"300x100+{x}+{y}")

        ttk.Label(progress_window, text="正在验证仓库...",
                  font=("Arial", 10)).pack(pady=20)
        progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
        progress_bar.pack(padx=20, fill=X)
        progress_bar.start()

        # 在线程中验证
        def verify_thread():
            results = []
            for item in selection:
                path = self.tree.item(item)["values"][1]
                repo_type = self.tree.item(item)["values"][0]

                # 查找对应的仓库
                repo = None
                for r in self.all_repos:
                    if r['path'] == path:
                        repo = r
                        break

                if not repo:
                    continue

                # ZIP源默认为已验证
                if repo_type == "ZIP源":
                    repo['verified'] = True
                    results.append((path, True))
                    continue

                # 使用GitHub API验证仓库是否存在
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    async def check_repo():
                        async with httpx.AsyncClient(verify=False, timeout=10) as client:
                            url = f"https://api.github.com/repos/{path}"
                            headers = {}
                            # 获取GitHub token（如果有的话）
                            if self.parent_gui and hasattr(self.parent_gui, 'backend'):
                                token = self.parent_gui.backend.app_config.get("Github_Personal_Token", "")
                                if token:
                                    headers['Authorization'] = f'Bearer {token}'

                            try:
                                response = await client.get(url, headers=headers)
                                return response.status_code == 200
                            except:
                                return False

                    exists = loop.run_until_complete(check_repo())
                    repo['verified'] = exists
                    results.append((path, exists))
                except Exception as e:
                    print(f"验证仓库 {path} 时出错: {str(e)}")
                    repo['verified'] = False
                    results.append((path, False))
                finally:
                    loop.close()

            # 更新UI
            self.after(0, lambda: self.show_verify_results(results, progress_window))

        threading.Thread(target=verify_thread, daemon=True).start()

    def show_verify_results(self, results, progress_window):
        """显示验证结果"""
        progress_window.destroy()

        # 保存验证结果
        self.save_repos()

        # 刷新列表显示
        self.refresh_list()

        # 显示结果
        success_count = sum(1 for _, exists in results if exists)
        fail_count = len(results) - success_count

        msg = f"验证完成！\n\n成功: {success_count} 个\n失败: {fail_count} 个"

        if fail_count > 0:
            msg += "\n\n失败的仓库:\n"
            for repo_path, exists in results:
                if not exists:
                    msg += f"• {repo_path}\n"

        messagebox.showinfo("验证结果", msg)

    def save_repos(self):  # 注意：这里的缩进要和 show_verify_results 对齐
        """保存仓库列表"""
        # 更新缓存中的仓库配置
        repo_config = self.cache_manager.repo_config
        repo_config['all_repos'] = self.all_repos
        self.cache_manager.save_repo_config(repo_config)

        # 如果有父窗口引用，通知刷新
        if self.parent_gui:
            self.parent_gui.refresh_repo_options()

    def close_dialog(self):  # 注意：这里的缩进要和 show_verify_results 对齐
        """关闭对话框"""
        self.save_repos()
        self.destroy()


class DLCDialog(tk.Toplevel):
    """DLC查找和安装对话框"""

    def __init__(self, parent, app_id: str, game_name: str, backend, selected_repos, cache_manager):
        super().__init__(parent)
        self.app_id = str(app_id)
        self.game_name = game_name
        self.backend = backend
        self.selected_repos = list(selected_repos)
        self.cache_manager = cache_manager
        self.dlc_data = None
        self.is_processing = False
        self.has_searched = False

        # 设置窗口
        self.title(f"DLC管理 - {game_name}")
        self.geometry("800x600")
        self.resizable(False, False)
        self.transient(parent)

        # 设置图标
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, '图标.ico')
            else:
                icon_path = '图标.ico'
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except:
            pass

        # 居中
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 800) // 2
        y = (self.winfo_screenheight() - 600) // 2
        self.geometry(f"800x600+{x}+{y}")

        # 创建UI
        self.create_ui()

        # 尝试从缓存加载DLC数据
        self.load_cached_dlc_data()

    def create_ui(self):
        """创建UI"""
        # 顶部信息栏
        info_frame = ttk.Frame(self, padding=10)
        info_frame.pack(fill=X)

        ttk.Label(info_frame, text=f"游戏: {self.game_name}",
                  font=("Arial", 12, "bold")).pack(anchor=W)
        ttk.Label(info_frame, text=f"App ID: {self.app_id}",
                  font=("Arial", 10)).pack(anchor=W)

        # 进度信息（右上角）
        self.progress_label = ttk.Label(info_frame, text="DLC列表",
                                        font=("Arial", 10))
        self.progress_label.pack(side=RIGHT)

        # 分隔线
        ttk.Separator(self, orient='horizontal').pack(fill=X, padx=10)

        # 主要内容区
        content_frame = ttk.Frame(self, padding=10)
        content_frame.pack(fill=BOTH, expand=True)

        # 创建DLC列表框架
        list_frame = ttk.LabelFrame(content_frame, text="DLC列表", padding=10)
        list_frame.pack(fill=BOTH, expand=True)

        # 创建Treeview
        columns = ("type", "name", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="tree headings", height=15)

        self.tree.heading("#0", text="App ID")
        self.tree.heading("type", text="类型")
        self.tree.heading("name", text="名称")
        self.tree.heading("status", text="状态")

        self.tree.column("#0", width=100)
        self.tree.column("type", width=80)
        self.tree.column("name", width=400)
        self.tree.column("status", width=100)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 底部进度条（左下角）
        progress_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        progress_frame.pack(fill=X)

        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=300)
        self.progress_bar.pack(side=LEFT)

        self.progress_text = ttk.Label(progress_frame, text="", font=("Arial", 9))
        self.progress_text.pack(side=LEFT, padx=(10, 0))

        # 底部按钮
        button_frame = ttk.Frame(progress_frame)
        button_frame.pack(side=RIGHT)

        # 添加"一键查找DLC"按钮
        self.find_dlc_btn = ttk.Button(button_frame, text="一键查找DLC",
                                       command=self.start_finding_dlcs,
                                       style="info.TButton")
        self.find_dlc_btn.pack(side=LEFT, padx=5)

        self.install_btn = ttk.Button(button_frame, text="入库所有DLC",
                                      command=self.install_dlcs,
                                      style="success.TButton", state="disabled")
        self.install_btn.pack(side=LEFT, padx=5)

        self.close_btn = ttk.Button(button_frame, text="关闭",
                                    command=self.close_dialog,
                                    style="secondary.TButton")
        self.close_btn.pack(side=LEFT)

    def load_cached_dlc_data(self):
        """从缓存加载DLC数据"""
        # 尝试从缓存获取DLC数据
        dlc_cache_key = f"dlc_data_{self.app_id}"
        cached_dlc = self.cache_manager.game_info_cache.get(dlc_cache_key)

        if cached_dlc:
            self.dlc_data = cached_dlc
            self.has_searched = True
            self.after(100, self.display_dlcs)
        else:
            # 如果没有缓存，显示提示信息
            self.tree.insert("", "end", text="",
                             values=("", '点击"一键查找DLC"开始查找', ""))
            self.progress_label.configure(text="未查找DLC")

    def save_dlc_data_to_cache(self):
        """保存DLC数据到缓存"""
        if self.dlc_data:
            dlc_cache_key = f"dlc_data_{self.app_id}"
            self.cache_manager.game_info_cache[dlc_cache_key] = self.dlc_data
            self.cache_manager.save_game_info()

    def start_finding_dlcs(self):
        """开始查找DLC"""
        if self.is_processing:
            messagebox.showinfo("提示", "正在处理中，请稍候...")
            return

        self.is_processing = True
        self.has_searched = True
        self.progress_label.configure(text="正在查找DLC...")
        self.find_dlc_btn.configure(state="disabled")

        # 清空现有列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 在线程中执行
        thread = threading.Thread(target=self.find_dlcs_thread, daemon=True)
        thread.start()

    def find_dlcs_thread(self):
        """查找DLC的线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            async def find_dlcs():
                async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                    # 进度回调
                    def progress_callback(current, total):
                        self.after(0, self.update_progress, current, total)

                    # 获取DLC信息
                    dlc_data = await self.backend.get_game_dlcs(client, self.app_id, progress_callback)
                    return dlc_data

            self.dlc_data = loop.run_until_complete(find_dlcs())

            # 保存到缓存
            self.save_dlc_data_to_cache()

            self.after(0, self.display_dlcs)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("错误", f"查找DLC时出错:\n{str(e)}"))
            self.after(0, lambda: self.find_dlc_btn.configure(state="normal"))
        finally:
            loop.close()
            self.is_processing = False

    def update_progress(self, current: int, total: int):
        """更新进度"""
        if total > 0:
            progress = (current / total) * 100
            self.progress_bar['value'] = progress
            self.progress_text.configure(text=f"{current}/{total}")
            self.progress_label.configure(text=f"正在分析DLC... ({current}/{total})")

    def display_dlcs(self):
        """显示DLC列表"""
        if not self.dlc_data:
            self.progress_label.configure(text="未找到DLC")
            self.find_dlc_btn.configure(state="normal")
            return

        # 清空列表
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 检查已安装的DLC
        installed_dlcs = set()
        if self.backend.steam_path.exists():
            stplug_dir = self.backend.steam_path / "config" / "stplug-in"
            depot_dir = self.backend.steam_path / "depotcache"

            # 1. 检查lua文件中的DLC
            if stplug_dir.exists():
                import re
                for lua_file in stplug_dir.glob("*.lua"):
                    try:
                        with open(lua_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                            # 查找 addappid 命令
                            addappid_matches = re.findall(r'addappid\s*\(\s*(\d+)', content)
                            for dlc_id in addappid_matches:
                                if dlc_id != self.app_id:
                                    installed_dlcs.add(dlc_id)

                            # 也查找 AddDLC 命令
                            adddlc_matches = re.findall(r'AddDLC\s*\(\s*(\d+)\s*\)', content)
                            for dlc_id in adddlc_matches:
                                installed_dlcs.add(dlc_id)

                    except Exception as e:
                        print(f"读取lua文件出错 {lua_file}: {e}")

            # 2. 检查manifest文件
            if depot_dir.exists():
                for manifest_file in depot_dir.glob("*.manifest"):
                    match = re.match(r'(\d+)_(\d+)_\d+\.manifest', manifest_file.name)
                    if match:
                        app_id = match.group(1)
                        for dlc in self.dlc_data.get("free", []) + self.dlc_data.get("paid", []):
                            if str(dlc["appid"]) == app_id:
                                installed_dlcs.add(app_id)
                                break

        print(f"检测到已安装的DLC: {installed_dlcs}")

        # 显示免费DLC
        if self.dlc_data.get("free"):
            free_parent = self.tree.insert("", "end", text="免费DLC",
                                           values=("", f"共 {len(self.dlc_data['free'])} 个", ""))
            installed_count = 0
            for dlc in self.dlc_data["free"]:
                # 检查是否已安装
                dlc_id = str(dlc["appid"])
                status = "已安装" if dlc_id in installed_dlcs else "待安装"
                if status == "已安装":
                    installed_count += 1
                self.tree.insert(free_parent, "end", text=dlc_id,
                                 values=("免费", dlc["name"], status))

            # 更新父节点显示已安装数量
            self.tree.item(free_parent,
                           values=("", f"共 {len(self.dlc_data['free'])} 个，已安装 {installed_count} 个", ""))
            self.tree.item(free_parent, open=True)

        # 显示付费DLC
        if self.dlc_data.get("paid"):
            paid_parent = self.tree.insert("", "end", text="付费DLC",
                                           values=("", f"共 {len(self.dlc_data['paid'])} 个", ""))
            installed_count = 0
            for dlc in self.dlc_data["paid"]:
                # 检查是否已安装
                dlc_id = str(dlc["appid"])
                status = "已安装" if dlc_id in installed_dlcs else "待安装"
                if status == "已安装":
                    installed_count += 1
                self.tree.insert(paid_parent, "end", text=dlc_id,
                                 values=("付费", dlc["name"], status))

            # 更新父节点显示已安装数量
            self.tree.item(paid_parent,
                           values=("", f"共 {len(self.dlc_data['paid'])} 个，已安装 {installed_count} 个", ""))
            self.tree.item(paid_parent, open=True)

        # 更新状态
        total = self.dlc_data.get("total", 0)
        self.progress_label.configure(text=f"找到 {total} 个DLC")
        self.progress_bar['value'] = 100
        self.progress_text.configure(text=f"{total}/{total}")

        # 启用按钮
        self.find_dlc_btn.configure(state="normal")
        if total > 0:
            self.install_btn.configure(state="normal")

    def update_installed_dlcs(self, new_installed_dlcs: List[str]):
        """更新已安装的DLC列表"""
        installed_dlcs_key = f"installed_dlcs_{self.app_id}"
        existing_installed = set(self.cache_manager.game_info_cache.get(installed_dlcs_key, []))

        # 添加新安装的DLC
        for dlc_id in new_installed_dlcs:
            existing_installed.add(str(dlc_id))

        # 保存到缓存
        self.cache_manager.game_info_cache[installed_dlcs_key] = list(existing_installed)
        self.cache_manager.save_game_info()

    def install_dlcs(self):
        """安装所有DLC"""
        if not self.dlc_data or self.is_processing:
            # 如果没有搜索过，提示用户先搜索
            if not self.has_searched:
                messagebox.showinfo("提示", '请先点击"一键查找DLC"来查找可用的DLC')
            return

        # 检查已安装的DLC (使用与display_dlcs相同的逻辑)
        installed_dlcs = set()
        if self.backend.steam_path.exists():
            stplug_dir = self.backend.steam_path / "config" / "stplug-in"
            depot_dir = self.backend.steam_path / "depotcache"

            # 1. 检查lua文件中的DLC
            if stplug_dir.exists():
                import re
                for lua_file in stplug_dir.glob("*.lua"):
                    try:
                        with open(lua_file, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                            # 查找 addappid 命令
                            addappid_matches = re.findall(r'addappid\s*\(\s*(\d+)', content)
                            for dlc_id in addappid_matches:
                                if dlc_id != self.app_id:
                                    installed_dlcs.add(dlc_id)

                            # 也查找 AddDLC 命令
                            adddlc_matches = re.findall(r'AddDLC\s*\(\s*(\d+)\s*\)', content)
                            for dlc_id in adddlc_matches:
                                installed_dlcs.add(dlc_id)

                    except Exception as e:
                        print(f"读取lua文件出错 {lua_file}: {e}")

            # 2. 检查manifest文件
            if depot_dir.exists():
                for manifest_file in depot_dir.glob("*.manifest"):
                    match = re.match(r'(\d+)_(\d+)_\d+\.manifest', manifest_file.name)
                    if match:
                        app_id = match.group(1)
                        for dlc in self.dlc_data.get("free", []) + self.dlc_data.get("paid", []):
                            if str(dlc["appid"]) == app_id:
                                installed_dlcs.add(app_id)
                                break

        # 过滤出未安装的DLC
        uninstalled_free = [dlc for dlc in self.dlc_data.get("free", []) if str(dlc["appid"]) not in installed_dlcs]
        uninstalled_paid = [dlc for dlc in self.dlc_data.get("paid", []) if str(dlc["appid"]) not in installed_dlcs]

        # 创建新的DLC数据，只包含未安装的
        filtered_dlc_data = {
            "free": uninstalled_free,
            "paid": uninstalled_paid,
            "total": len(uninstalled_free) + len(uninstalled_paid)
        }

        if filtered_dlc_data["total"] == 0:
            messagebox.showinfo("提示", "所有DLC都已安装！")
            return

        # 确认对话框
        total = filtered_dlc_data["total"]
        already_installed = self.dlc_data.get("total", 0) - filtered_dlc_data["total"]

        msg = f"找到 {self.dlc_data.get('total', 0)} 个DLC，其中 {already_installed} 个已安装。\n\n"
        msg += f"确定要入库剩余的 {total} 个DLC吗？\n\n"
        msg += f"待安装免费DLC: {len(uninstalled_free)} 个\n"
        msg += f"待安装付费DLC: {len(uninstalled_paid)} 个\n\n"
        msg += f"付费DLC将从已选择的清单源中查找密钥。"

        if not messagebox.askyesno("确认", msg):
            return

        # 保存原始数据
        self.original_dlc_data = self.dlc_data
        # 使用过滤后的数据进行安装
        self.dlc_data = filtered_dlc_data

        self.is_processing = True
        self.install_btn.configure(state="disabled")
        self.close_btn.configure(state="disabled")
        self.find_dlc_btn.configure(state="disabled")
        self.progress_label.configure(text="正在安装DLC...")
        self.progress_bar['value'] = 0

        # 在线程中执行
        thread = threading.Thread(target=self.install_dlcs_thread, daemon=True)
        thread.start()

    def install_dlcs_thread(self):
        """安装DLC的线程"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            async def install():
                async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
                    result = await self.backend.process_dlcs(
                        client, self.app_id, self.dlc_data, self.selected_repos)
                    return result

            result = loop.run_until_complete(install())
            self.after(0, self.show_install_result, result)

        except Exception as e:
            self.after(0, lambda: messagebox.showerror("错误", f"安装DLC时出错:\n{str(e)}"))
        finally:
            loop.close()
            self.is_processing = False
            # 恢复原始数据
            if hasattr(self, 'original_dlc_data'):
                self.dlc_data = self.original_dlc_data
            self.after(0, lambda: self.close_btn.configure(state="normal"))
            self.after(0, lambda: self.find_dlc_btn.configure(state="normal"))

    def show_install_result(self, result: Dict):
        """显示安装结果"""
        success_count = len(result["success"])
        failed_count = len(result["failed"])

        # 更新已安装的DLC列表
        if result["success"]:
            # 确保正确获取DLC ID
            successful_dlc_ids = []
            for dlc in result["success"]:
                # dlc 可能是字典对象，需要获取其 appid
                if isinstance(dlc, dict):
                    successful_dlc_ids.append(str(dlc.get("appid", "")))
                else:
                    # 如果是字符串，直接使用
                    successful_dlc_ids.append(str(dlc))

            # 打印调试信息
            print(f"成功安装的DLC IDs: {successful_dlc_ids}")

            self.update_installed_dlcs(successful_dlc_ids)

        # 重新显示DLC列表以更新状态
        self.display_dlcs()

        self.progress_label.configure(text=f"安装完成: 成功 {success_count} 个, 失败 {failed_count} 个")
        self.progress_bar['value'] = 100

        # 显示结果消息
        msg = f"DLC安装完成！\n\n成功: {success_count} 个\n失败: {failed_count} 个"
        if failed_count > 0:
            msg += "\n\n部分付费DLC可能因为清单源中没有相应文件而失败。"
        msg += "\n\n请重启Steam客户端以使更改生效。"

        messagebox.showinfo("安装完成", msg)

    def close_dialog(self):
        """关闭对话框"""
        if self.is_processing:
            if not messagebox.askyesno("确认", "正在处理中，确定要关闭吗？"):
                return
        self.destroy()

# 主程序入口
def main():
    """主程序入口"""
    try:  # 注意这里有4个空格的缩进
        # 设置DPI感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        # 检查依赖
        try:
            import PIL
        except ImportError:
            messagebox.showerror("依赖缺失", "错误: Pillow 库未安装。\n请使用 'pip install Pillow' 安装。")
            sys.exit(1)

        # 启动应用
        app = GameBoxGUI()
        app.mainloop()

    except Exception as e:
        # 捕获所有异常并显示
        import traceback
        error_msg = f"程序启动失败:\n{str(e)}\n\n详细错误:\n{traceback.format_exc()}"
        print(error_msg)
        try:
            messagebox.showerror("启动错误", error_msg)
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()