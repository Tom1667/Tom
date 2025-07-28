# --- START OF CORRECTED backend_gui.py ---

import os
import traceback
import asyncio
import re
import aiofiles
import httpx
import winreg
import vdf
import json
import zipfile
import shutil
import struct
import zlib
from pathlib import Path
from typing import Tuple, List, Dict, Literal
from urllib.parse import quote

# --- GLOBAL CONFIG ---
DEFAULT_CONFIG = {
    "Github_Personal_Token": "",
    "Custom_Steam_Path": "",
    "steamtools_only_lua": False,
    "steam_path_mode": "auto",  # auto 或 manual
    "unlocker_mode": "auto",  # auto 或 manual
    "manual_unlocker": "steamtools",  # steamtools 或 greenluma
    "QA1": "温馨提示: Github_Personal_Token(个人访问令牌)可在Github设置的最底下开发者选项中找到, 详情请看教程。",
    "QA2": "温馨提示: 勾选'使用SteamTools进行清单更新'后，对于ST用户，程序将仅下载和更新LUA脚本，而不再下载清单文件(.manifest)。"
}


class STConverter:
    def __init__(self, logger):
        self.logger = logger

    def convert_file(self, st_path: str) -> str:
        try:
            content, _ = self.parse_st_file(st_path)
            return content
        except Exception as e:
            self.logger.error(f'ST文件转换失败: {st_path} - {e}')
            raise

    def parse_st_file(self, st_file_path: str) -> Tuple[str, dict]:
        with open(st_file_path, 'rb') as stfile:
            content = stfile.read()
        if len(content) < 12: raise ValueError("文件头长度不足")
        header = content[:12]
        xorkey, size, _ = struct.unpack('III', header)
        xorkey ^= 0xFFFEA4C8
        xorkey &= 0xFF
        encrypted_data = content[12:12 + size]
        if len(encrypted_data) < size: raise ValueError(f"数据长度不足")
        data = bytearray(encrypted_data)
        for i in range(len(data)): data[i] ^= xorkey
        decompressed_data = zlib.decompress(data)
        content_str = decompressed_data[512:].decode('utf-8')
        metadata = {'original_xorkey': xorkey, 'size': size}
        return content_str, metadata


class GuiBackend:
    def __init__(self, logger):
        self.log = logger
        self.st_converter = STConverter(self.log)
        self.app_config = {}
        self.steam_path = Path()
        self.unlocker_type = None
        self.temp_dir = Path('./temp_cai_install')
        self.st_lock_manifest_version = False

    def stack_error(self, e: Exception) -> str:
        return ''.join(traceback.format_exception(type(e), e, e.__traceback__))

    def load_config(self):
        config_path = Path('./config.json')
        if not config_path.exists():
            self.gen_config_file()
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)
            self.app_config = DEFAULT_CONFIG.copy()
            self.app_config.update(loaded_config)
        except Exception as e:
            self.log.error(f"配置文件加载失败，将重置: {self.stack_error(e)}")
            if config_path.exists(): os.remove(config_path)
            self.gen_config_file()
            self.app_config = DEFAULT_CONFIG.copy()

    def gen_config_file(self):
        try:
            with open("./config.json", mode="w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            self.log.info('首次启动或配置重置，已生成config.json，请在"设置"中填写。')
            self.app_config = DEFAULT_CONFIG.copy()
        except Exception as e:
            self.log.error(f'配置文件生成失败: {self.stack_error(e)}')

    def save_config(self):
        try:
            with open("./config.json", mode="w", encoding="utf-8") as f:
                config_to_save = DEFAULT_CONFIG.copy()
                config_to_save.update(self.app_config)
                json.dump(config_to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log.error(f'保存配置失败: {self.stack_error(e)}')

    def detect_steam_path(self) -> Path:
        try:
            # 检查是否为手动模式
            if self.app_config.get("steam_path_mode", "auto") == "manual":
                custom_path = self.app_config.get("Custom_Steam_Path", "").strip()
                if custom_path:
                    self.steam_path = Path(custom_path)
                    return self.steam_path

            # 自动模式
            custom_path = self.app_config.get("Custom_Steam_Path", "").strip()
            if custom_path and Path(custom_path).exists():
                self.steam_path = Path(custom_path)
                self.log.info(f"使用配置的Steam路径: {self.steam_path}")
            else:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
                self.steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
                self.log.info(f"自动检测到Steam路径: {self.steam_path}")
            return self.steam_path
        except Exception:
            self.log.error('Steam路径获取失败，请检查Steam是否安装或在设置中指定路径。')
            self.steam_path = Path()
            return self.steam_path

    def detect_unlocker(self) -> Literal["steamtools", "greenluma", "conflict", "none"]:
        if not self.steam_path.exists(): return "none"
        is_steamtools = (self.steam_path / 'config' / 'stplug-in').is_dir()
        is_greenluma = any(
            (self.steam_path / dll).exists() for dll in ['GreenLuma_2025_x86.dll', 'GreenLuma_2025_x64.dll'])
        if is_steamtools and is_greenluma:
            self.log.error("环境冲突：同时检测到SteamTools和GreenLuma！")
            return "conflict"
        elif is_steamtools:
            self.log.info("检测到解锁工具: SteamTools");
            self.unlocker_type = "steamtools";
            return "steamtools"
        elif is_greenluma:
            self.log.info("检测到解锁工具: GreenLuma");
            self.unlocker_type = "greenluma";
            return "greenluma"
        else:
            self.log.warning("未能自动检测到解锁工具。");
            return "none"

    def is_steamtools(self):
        return self.unlocker_type == "steamtools"

    def get_github_headers(self):
        return {'Authorization': f'Bearer {token}'} if (
            token := self.app_config.get("Github_Personal_Token", "")) else {}

    async def check_github_api_rate_limit(self, client: httpx.AsyncClient, headers: dict):
        if headers:
            self.log.info("已配置Github Token。")
        else:
            self.log.warning("未配置Github Token，API请求次数有限，建议在设置中添加。")
        try:
            r = await client.get('https://api.github.com/rate_limit', headers=headers);
            r.raise_for_status()
            rate = r.json().get('resources', {}).get('core', {})
            remaining = rate.get('remaining', 0)
            if remaining == 0:
                import time
                reset_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rate.get('reset', 0)))
                self.log.warning(f"GitHub API请求数已用尽，将在 {reset_time} 重置。")
                return False
            self.log.info(f'GitHub API 剩余请求次数: {remaining}')
            return True
        except Exception as e:
            self.log.error(f'检查GitHub API速率时出错: {e}')
            return False

    async def checkcn(self, client: httpx.AsyncClient):
        try:
            r = await client.get('https://mips.kugou.com/check/iscn?&format=json')
            if not bool(r.json().get('flag')):
                self.log.info(f"检测到您在非中国大陆地区 ({r.json().get('country')})，将使用GitHub官方下载源。")
                os.environ['IS_CN'] = 'no'
            else:
                os.environ['IS_CN'] = 'yes'
                self.log.info("检测到您在中国大陆地区，将使用国内镜像。")
        except Exception:
            os.environ['IS_CN'] = 'yes';
            self.log.warning('检查服务器位置失败，将默认使用国内加速CDN。')

    async def fetch_branch_info(self, client: httpx.AsyncClient, url: str, headers: dict):
        try:
            r = await client.get(url, headers=headers);
            r.raise_for_status();
            return r.json()
        except httpx.HTTPStatusError as e:
            self.log.error(f'获取信息失败: {e.request.url} - 状态码 {e.response.status_code}')
            if e.response.status_code == 404:
                self.log.error("404 Not Found: 请检查AppID是否正确，以及该清单是否存在于所选仓库中。")
            elif e.response.status_code == 403:
                self.log.error("403 Forbidden: GitHub API速率限制，请在设置中添加Token或稍后再试。")
            return None
        except Exception as e:
            self.log.error(f'获取信息失败: {self.stack_error(e)}');
            return None

    async def get_from_url(self, client: httpx.AsyncClient, sha: str, path: str, repo: str):
        urls = [f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}',
                f'https://raw.gitmirror.com/{repo}/{sha}/{path}'] if os.environ.get('IS_CN') == 'yes' else [
            f'https://raw.githubusercontent.com/{repo}/{sha}/{path}']
        for url in urls:
            try:
                self.log.info(f"尝试下载: {path} from {url.split('/')[2]}")
                r = await client.get(url, timeout=30)
                if r.status_code == 200: return r.content
                self.log.warning(f"下载失败 (状态码 {r.status_code}) from {url.split('/')[2]}，尝试下一个源...")
            except Exception as e:
                self.log.warning(f"下载时连接错误 from {url.split('/')[2]}: {e}，尝试下一个源...")
        raise Exception(f'所有下载源均失败: {path}')

    def extract_app_id(self, user_input: str):
        for p in [r"store\.steampowered\.com/app/(\d+)", r"steamdb\.info/app/(\d+)"]:
            if m := re.search(p, user_input): return m.group(1)
        return user_input if user_input.isdigit() else None

    async def search_all_repos(self, client: httpx.AsyncClient, app_id: str, repos: List[str]):
        # 确保 app_id 是字符串类型
        app_id = str(app_id)

        results = []
        for repo in repos:
            self.log.info(f"搜索仓库: {repo}")
            headers = self.get_github_headers()
            branch_url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
            if r1 := await self.fetch_branch_info(client, branch_url, headers):
                if 'commit' in r1 and (
                r2 := await self.fetch_branch_info(client, r1['commit']['commit']['tree']['url'], headers)):
                    if 'tree' in r2:
                        results.append({'repo': repo, 'sha': r1['commit']['sha'], 'tree': r2['tree'],
                                        'update_date': r1["commit"]["commit"]["author"]["date"]})
                        self.log.info(f"在仓库 {repo} 中找到清单。")
        return results

    async def get_manifest_from_github(self, client: httpx.AsyncClient, sha: str, path: str, repo: str, app_id: str,
                                       all_manifests: List[str]):
        # 确保 app_id 是字符串类型
        app_id = str(app_id)

        is_st_auto_update_mode = self.is_steamtools() and self.app_config.get("steamtools_only_lua", False)

        if path.endswith('.manifest') and is_st_auto_update_mode:
            self.log.info(f"ST自动更新模式: 已跳过清单文件下载: {path}");
            return []

        content = await self.get_from_url(client, sha, path, repo)
        depots = []
        stplug = self.steam_path / 'config' / 'stplug-in'

        if path.endswith('.manifest') and not is_st_auto_update_mode:
            depot_cache = self.steam_path / 'depotcache'
            cfg_depot_cache = self.steam_path / 'config' / 'depotcache'
            for p in [depot_cache, cfg_depot_cache, stplug]: p.mkdir(parents=True, exist_ok=True)
            for p in [depot_cache, cfg_depot_cache]: (p / Path(path).name).write_bytes(content)
            self.log.info(f'清单已保存: {path}')
        elif "key.vdf" in path.lower():
            depots_cfg = vdf.loads(content.decode('utf-8'))
            depots = [(depot_id, info['DecryptionKey']) for depot_id, info in depots_cfg.get('depots', {}).items()]
            if self.is_steamtools() and app_id:
                lua_path = stplug / f"{app_id}.lua"
                self.log.info(f'为SteamTools创建Lua脚本: {lua_path}')

                is_floating_version = is_st_auto_update_mode and not self.st_lock_manifest_version

                with open(lua_path, "w", encoding="utf-8") as f:
                    f.write(f'addappid({app_id}, 1, "None")\n')
                    for depot_id, key in depots: f.write(f'addappid({depot_id}, 1, "{key}")\n')

                    for mf_path in all_manifests:
                        if m := re.search(r'(\d+)_(\w+)\.manifest', mf_path):
                            line = f'setManifestid({m.group(1)}, "{m.group(2)}")\n'
                            if is_floating_version:
                                f.write('--' + line)
                            else:
                                f.write(line)
                self.log.info('Lua脚本创建成功。')
        return depots

    async def depotkey_merge(self, depots_config: dict):
        config_path = self.steam_path / 'config' / 'config.vdf'
        if not config_path.exists(): self.log.error('Steam默认配置(config.vdf)不存在'); return False
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = vdf.loads(f.read())
            steam = (config.get('InstallConfigStore', {}).get('Software', {}).get('Valve') or config.get(
                'InstallConfigStore', {}).get('Software', {}).get('valve'))
            if not steam: self.log.error('找不到Steam配置节'); return False
            steam.setdefault('depots', {}).update(depots_config.get('depots', {}))
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(vdf.dumps(config, pretty=True))
            self.log.info('密钥成功合并到 config.vdf。');
            return True
        except Exception as e:
            self.log.error(f'合并密钥失败: {self.stack_error(e)}');
            return False

    async def greenluma_add(self, depot_id_list: List[str]):
        try:
            app_list_path = self.steam_path / 'AppList'
            app_list_path.mkdir(parents=True, exist_ok=True)

            # 确保所有 ID 都是字符串
            depot_id_list = [str(appid) for appid in depot_id_list]

            for appid in depot_id_list:
                (app_list_path / f'{appid}.txt').write_text(str(appid), encoding='utf-8')

            self.log.info(f"已为GreenLuma添加AppID: {', '.join(depot_id_list)}")
            return True
        except Exception as e:
            self.log.error(f'为GreenLuma添加解锁文件时出错: {e}')
            return False

    async def _process_zip_based_manifest(self, client: httpx.AsyncClient, app_id: str, download_url: str,
                                          source_name: str):
        # 确保 app_id 是字符串类型
        app_id = str(app_id)

        try:
            self.temp_dir.mkdir(exist_ok=True)
            self.log.info(f'[{source_name}] 正在下载清单文件: {download_url}')
            async with client.stream("GET", download_url, timeout=60) as r:
                if r.status_code != 200:
                    self.log.error(f'[{source_name}] 下载失败: 状态码 {r.status_code}');
                    return False
                zip_path = self.temp_dir / f'{app_id}.zip'
                async with aiofiles.open(zip_path, 'wb') as f:
                    async for chunk in r.aiter_bytes(): await f.write(chunk)

            self.log.info(f'[{source_name}] 正在解压文件...')
            extract_path = self.temp_dir / app_id
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_path)

            manifest_files = list(extract_path.glob('*.manifest'))
            lua_files = list(extract_path.glob('*.lua'))
            st_files = list(extract_path.glob('*.st'))

            for st_file in st_files:
                try:
                    lua_path = st_file.with_suffix('.lua')
                    lua_content = self.st_converter.convert_file(str(st_file))
                    async with aiofiles.open(lua_path, 'w', encoding='utf-8') as f:
                        await f.write(lua_content)
                    lua_files.append(lua_path)
                    self.log.info(f'已转换ST文件: {st_file.name}')
                except Exception as e:
                    self.log.error(f'转换ST文件失败: {e} - {self.stack_error(e)}')

            is_st_auto_update_mode = self.is_steamtools() and self.app_config.get("steamtools_only_lua", False)
            is_floating_version = is_st_auto_update_mode and not self.st_lock_manifest_version

            if self.is_steamtools():
                st_plug = self.steam_path / 'config' / 'stplug-in';
                st_plug.mkdir(parents=True, exist_ok=True)

                if not is_st_auto_update_mode:
                    self.log.info(f'[{source_name}] 按SteamTools标准模式安装清单文件。')
                    # 定义两个目标路径
                    st_depot_path = self.steam_path / 'config' / 'depotcache'
                    gl_depot_path = self.steam_path / 'depotcache'

                    # 确保两个目录都存在
                    st_depot_path.mkdir(parents=True, exist_ok=True)
                    gl_depot_path.mkdir(parents=True, exist_ok=True)

                    if manifest_files:
                        for f in manifest_files:
                            # 复制到第一个位置
                            shutil.copy2(f, st_depot_path)
                            # 复制到第二个位置
                            shutil.copy2(f, gl_depot_path)
                        self.log.info(
                            f"[{source_name}] 已复制 {len(manifest_files)} 个清单到 config/depotcache 和 depotcache 两个目录。")
                    else:
                        self.log.info(f"[{source_name}] 未找到 .manifest 文件。")
                else:
                    self.log.info(f"[{source_name}] ST自动更新模式: 已跳过.manifest 文件。")

                lua_filename = f"{app_id}.lua"
                lua_filepath = st_plug / lua_filename
                all_depots = {}
                for lua_f in lua_files:
                    with open(lua_f, 'r', encoding='utf-8') as f_in:
                        for m in re.finditer(r'addappid\((\d+),\s*1,\s*"([^"]+)"\)', f_in.read()):
                            all_depots[m.group(1)] = m.group(2)

                async with aiofiles.open(lua_filepath, 'w', encoding='utf-8') as f:
                    await f.write(f'addappid({app_id}, 1, "None")\n')
                    for depot_id, key in all_depots.items():
                        await f.write(f'addappid({depot_id}, 1, "{key}")\n')

                    for manifest_f in manifest_files:
                        m = re.search(r'(\d+)_(\w+)\.manifest', manifest_f.name)
                        if m:
                            line = f'setManifestid({m.group(1)}, "{m.group(2)}")\n'
                            if is_floating_version:
                                await f.write('--' + line)
                            else:
                                await f.write(line)
                self.log.info(f'[{source_name}] 已为SteamTools生成解锁脚本: {lua_filename}')
                return True
            else:  # GreenLuma
                self.log.info(f'[{source_name}] 按GreenLuma/标准模式安装。')
                gl_depot = self.steam_path / 'depotcache';
                gl_depot.mkdir(parents=True, exist_ok=True)
                if not manifest_files: self.log.warning(
                    f"[{source_name}] 在GreenLuma/标准模式下未找到可安装的 .manifest 文件。"); return False

                for f in manifest_files: shutil.copy2(f, gl_depot)
                self.log.info(f"已复制 {len(manifest_files)} 个清单到Steam depotcache目录。")

                all_depots = {}
                for lua_f in lua_files:
                    with open(lua_f, 'r', encoding='utf-8') as f_in:
                        for m in re.finditer(r'addappid\((\d+),\s*"([^"]+)"\)', f_in.read()):
                            all_depots[m.group(1)] = {'DecryptionKey': m.group(2)}

                if all_depots:
                    await self.depotkey_merge({'depots': all_depots})
                    await self.greenluma_add([app_id] + list(all_depots.keys()))
                else:
                    await self.greenluma_add([app_id])
                return True
        except Exception as e:
            self.log.error(f'[{source_name}] 处理清单时出错: {self.stack_error(e)}');
            return False
        finally:
            if self.temp_dir.exists(): shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def cleanup_temp_files(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.log.info('临时文件清理完成。')

    async def search_games_by_name(self, client: httpx.AsyncClient, game_name: str) -> List[Dict]:
        try:
            self.log.info(f"通过API搜索游戏: '{game_name}'")
            r = await client.get(f'https://steamui.com/api/loadGames.php?page=1&search={game_name}&sort=update')
            r.raise_for_status()
            all_games = r.json().get('games', [])
            filtered_games = [game for game in all_games if game.get("type") in ["Game", "Application"]]
            self.log.info(f"找到 {len(filtered_games)} 个匹配的游戏。")
            return filtered_games
        except Exception as e:
            self.log.error(f"通过游戏名搜索AppID时出错: {e}")
            return []

    # ===== 新增DLC相关方法 =====

    async def _get_steamcmd_api_data(self, client: httpx.AsyncClient, appid: str) -> Dict:
        """从 steamcmd API 获取数据"""
        try:
            resp = await client.get(f"https://api.steamcmd.net/v1/info/{appid}", timeout=20)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log.error(f"从 api.steamcmd.net 获取 AppID {appid} 数据失败: {e}")
            return {}

    async def _get_dlc_ids(self, client: httpx.AsyncClient, appid: str) -> List[str]:
        """获取游戏的所有DLC ID"""
        data = await self._get_steamcmd_api_data(client, appid)
        if not data: return []
        info = data.get("data", {}).get(str(appid), {})
        dlc_str = (info.get("common", {}).get("listofdlc", "") or info.get("extended", {}).get("listofdlc", ""))
        dlc_dict = info.get("dlc", {})
        ids = set()
        if isinstance(dlc_str, str) and dlc_str.strip():
            ids.update(filter(str.isdigit, map(str.strip, dlc_str.split(","))))
        if isinstance(dlc_dict, dict):
            ids.update(dlc_dict.keys())
        return sorted(list(ids), key=int)

    async def _get_depots(self, client: httpx.AsyncClient, appid: str) -> List[Dict]:
        """获取AppID的所有depot信息"""
        data = await self._get_steamcmd_api_data(client, appid)
        if not data: return []
        info = data.get("data", {}).get(str(appid), {})
        depots = info.get("depots", {})
        out = []
        for depot_id, depot_info in depots.items():
            if not isinstance(depot_info, dict): continue
            manifest_info = depot_info.get("manifests", {}).get("public")
            if not isinstance(manifest_info, dict): continue
            out.append({
                "depot_id": depot_id,
                "size": int(manifest_info.get("download", 0)),
                "dlc_appid": depot_info.get("dlcappid")
            })
        return out

    async def get_game_dlcs(self, client: httpx.AsyncClient, app_id: str, progress_callback=None) -> Dict:
        """获取游戏的所有DLC信息（包括免费和付费）"""
        app_id = str(app_id)
        self.log.info(f"开始查找 AppID {app_id} 的所有DLC...")

        try:
            # 获取所有DLC ID
            all_dlc_ids = await self._get_dlc_ids(client, app_id)
            if not all_dlc_ids:
                self.log.info(f"AppID {app_id} 未找到任何DLC。")
                return {"free": [], "paid": [], "total": 0}

            self.log.info(f"找到 {len(all_dlc_ids)} 个DLC，正在分析...")

            # 获取DLC信息
            free_dlcs = []
            paid_dlcs = []

            # 获取主游戏名称
            game_name = await self._get_game_name(client, app_id)

            # 创建并发任务批次
            batch_size = 10  # 每批处理10个DLC
            processed_count = 0

            for batch_start in range(0, len(all_dlc_ids), batch_size):
                batch_end = min(batch_start + batch_size, len(all_dlc_ids))
                batch_dlc_ids = all_dlc_ids[batch_start:batch_end]

                # 创建当前批次的并发任务
                tasks = []
                for dlc_id in batch_dlc_ids:
                    task = self._analyze_single_dlc(client, dlc_id)
                    tasks.append(task)

                # 并发执行当前批次
                try:
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 处理结果
                    for i, result in enumerate(batch_results):
                        processed_count += 1

                        # 更新进度
                        if progress_callback:
                            progress_callback(processed_count, len(all_dlc_ids))

                        if isinstance(result, Exception):
                            self.log.error(f"分析DLC时出错: {result}")
                            continue

                        if result:
                            if result["has_depots"]:
                                paid_dlcs.append(result)
                            else:
                                free_dlcs.append(result)

                except Exception as e:
                    self.log.error(f"批次处理出错: {e}")

                # 批次之间短暂延迟，避免请求过于密集
                if batch_end < len(all_dlc_ids):
                    await asyncio.sleep(0.5)

            self.log.info(f"分析完成: {len(free_dlcs)} 个免费DLC, {len(paid_dlcs)} 个付费DLC")

            return {
                "game_name": game_name,
                "free": free_dlcs,
                "paid": paid_dlcs,
                "total": len(all_dlc_ids)
            }

        except Exception as e:
            self.log.error(f"获取DLC信息时出错: {self.stack_error(e)}")
            return {"free": [], "paid": [], "total": 0}

    async def _analyze_single_dlc(self, client: httpx.AsyncClient, dlc_id: str) -> Dict:
        """分析单个DLC（用于并发执行）"""
        try:
            # 并发获取depot信息和名称
            depot_task = self._get_depots(client, dlc_id)
            name_task = self._get_game_name(client, dlc_id)

            # 同时等待两个任务完成
            dlc_depots, dlc_name = await asyncio.gather(depot_task, name_task)

            return {
                "appid": dlc_id,
                "name": dlc_name,
                "has_depots": len(dlc_depots) > 0
            }
        except Exception as e:
            self.log.error(f"分析DLC {dlc_id} 时出错: {e}")
            raise

            self.log.info(f"找到 {len(all_dlc_ids)} 个DLC，正在分析...")

            # 获取DLC信息
            free_dlcs = []
            paid_dlcs = []

            # 获取主游戏名称
            game_name = await self._get_game_name(client, app_id)

            for i, dlc_id in enumerate(all_dlc_ids):
                if progress_callback:
                    progress_callback(i + 1, len(all_dlc_ids))

                # 获取DLC的depot信息
                dlc_depots = await self._get_depots(client, dlc_id)

                # 获取DLC名称
                dlc_name = await self._get_game_name(client, dlc_id)

                dlc_info = {
                    "appid": dlc_id,
                    "name": dlc_name,
                    "has_depots": len(dlc_depots) > 0
                }

                if not dlc_depots:
                    # 没有depot的通常是免费DLC
                    free_dlcs.append(dlc_info)
                else:
                    # 有depot的通常是付费DLC
                    paid_dlcs.append(dlc_info)

                # 避免请求过快
                await asyncio.sleep(0.1)

            self.log.info(f"分析完成: {len(free_dlcs)} 个免费DLC, {len(paid_dlcs)} 个付费DLC")

            return {
                "game_name": game_name,
                "free": free_dlcs,
                "paid": paid_dlcs,
                "total": len(all_dlc_ids)
            }

        except Exception as e:
            self.log.error(f"获取DLC信息时出错: {self.stack_error(e)}")
            return {"free": [], "paid": [], "total": 0}

    async def _get_game_name(self, client: httpx.AsyncClient, appid: str) -> str:
        """获取游戏/DLC名称"""
        try:
            # 先尝试Steam Store API
            r = await client.get(f"https://store.steampowered.com/api/appdetails?appids={appid}&l=schinese&cc=CN")
            if r.status_code == 200:
                data = r.json()
                if str(appid) in data and data[str(appid)].get('success'):
                    return data[str(appid)]['data'].get('name', f'DLC {appid}')
        except:
            pass

        # 如果失败，返回默认名称
        return f'DLC {appid}'

    async def process_dlcs(self, client: httpx.AsyncClient, app_id: str, dlcs: Dict, selected_repos: List[str]) -> Dict:
        """处理DLC入库"""
        app_id = str(app_id)
        result = {
            "success": [],
            "failed": [],
            "total": len(dlcs["free"]) + len(dlcs["paid"])
        }

        # 先处理免费DLC
        if dlcs["free"]:
            self.log.info(f"正在处理 {len(dlcs['free'])} 个免费DLC...")
            if self.is_steamtools():
                # 对于SteamTools，将免费DLC添加到lua文件
                lua_path = self.steam_path / 'config' / 'stplug-in' / f"{app_id}.lua"
                if lua_path.exists():
                    # 读取现有内容
                    existing_lines = []
                    with open(lua_path, 'r', encoding='utf-8') as f:
                        existing_lines = [line.strip() for line in f.readlines()]

                    # 获取已存在的AppID
                    existing_appids = set()
                    for line in existing_lines:
                        if match := re.search(r'addappid\((\d+)', line):
                            existing_appids.add(match.group(1))

                    # 添加新的免费DLC
                    new_lines = []
                    for dlc in dlcs["free"]:
                        if dlc["appid"] not in existing_appids:
                            new_lines.append(f"addappid({dlc['appid']})")
                            result["success"].append(dlc)

                    if new_lines:
                        # 合并并排序
                        all_lines = existing_lines + new_lines

                        # 分离不同类型的行
                        addappid_lines = []
                        setmanifestid_lines = []
                        other_lines = []

                        for line in all_lines:
                            if line.startswith("addappid"):
                                addappid_lines.append(line)
                            elif line.startswith("setManifestid") or line.startswith("--setManifestid"):
                                setmanifestid_lines.append(line)
                            else:
                                other_lines.append(line)

                        # 排序addappid行
                        def get_appid_from_line(line):
                            match = re.search(r'addappid\((\d+)', line)
                            return int(match.group(1)) if match else 0

                        addappid_lines.sort(key=get_appid_from_line)

                        # 写回文件
                        with open(lua_path, 'w', encoding='utf-8') as f:
                            for line in addappid_lines:
                                f.write(line + '\n')
                            for line in setmanifestid_lines:
                                f.write(line + '\n')
                            for line in other_lines:
                                if line:  # 跳过空行
                                    f.write(line + '\n')

                        self.log.info(f"成功添加 {len(new_lines)} 个免费DLC到lua文件")
            else:
                # GreenLuma模式
                dlc_ids = [dlc["appid"] for dlc in dlcs["free"]]
                await self.greenluma_add(dlc_ids)
                result["success"].extend(dlcs["free"])

        # 处理付费DLC
        if dlcs["paid"]:
            self.log.info(f"正在处理 {len(dlcs['paid'])} 个付费DLC...")

            # 按顺序尝试所有选中的仓库
            for dlc in dlcs["paid"]:
                dlc_id = dlc["appid"]
                found = False

                for repo_value in selected_repos:
                    self.log.info(f"尝试从 {repo_value} 获取DLC {dlc_id} 的密钥...")

                    try:
                        if repo_value == "swa":
                            success = await self._process_dlc_from_zip(
                                client, dlc_id, f'https://api.printedwaste.com/gfk/download/{dlc_id}', "SWA V2")
                        elif repo_value == "cysaw":
                            success = await self._process_dlc_from_zip(
                                client, dlc_id, f'https://cysaw.top/uploads/{dlc_id}.zip', "Cysaw")
                        elif repo_value == "furcate":
                            success = await self._process_dlc_from_zip(
                                client, dlc_id, f'https://furcate.eu/files/{dlc_id}.zip', "Furcate")
                        elif repo_value == "cngs":
                            success = await self._process_dlc_from_zip(
                                client, dlc_id, f'https://assiw.cngames.site/qindan/{dlc_id}.zip', "CNGS")
                        elif repo_value == "steamdatabase":
                            success = await self._process_dlc_from_zip(
                                client, dlc_id, f'https://steamdatabase.s3.eu-north-1.amazonaws.com/{dlc_id}.zip',
                                "SteamDatabase")
                        else:
                            # GitHub仓库
                            success = await self._process_dlc_from_github(client, dlc_id, repo_value)

                        if success:
                            self.log.info(f"成功从 {repo_value} 获取DLC {dlc_id}")
                            result["success"].append(dlc)
                            found = True
                            break
                    except Exception as e:
                        self.log.warning(f"从 {repo_value} 获取DLC {dlc_id} 失败: {str(e)}")
                        continue

                if not found:
                    self.log.warning(f"无法从任何源获取DLC {dlc_id} 的密钥")
                    result["failed"].append(dlc)

        # 如果是SteamTools，合并到主游戏的lua文件中
        if self.is_steamtools() and result["success"]:
            await self._merge_dlcs_to_main_lua(app_id)

        return result

    async def _process_dlc_from_zip(self, client: httpx.AsyncClient, dlc_id: str, download_url: str,
                                    source_name: str) -> bool:
        """从ZIP源处理DLC"""
        try:
            # 使用现有的ZIP处理方法
            return await self._process_zip_based_manifest(client, dlc_id, download_url, source_name)
        except Exception as e:
            self.log.error(f"处理ZIP源DLC失败: {str(e)}")
            return False

    async def _process_dlc_from_github(self, client: httpx.AsyncClient, dlc_id: str, repo: str) -> bool:
        """从GitHub处理DLC"""
        try:
            # 检查分支是否存在
            headers = self.get_github_headers()
            branch_url = f'https://api.github.com/repos/{repo}/branches/{dlc_id}'
            branch_info = await self.fetch_branch_info(client, branch_url, headers)

            if not branch_info:
                return False

            # 获取文件树
            sha = branch_info['commit']['sha']
            tree_url = branch_info['commit']['commit']['tree']['url']
            tree_info = await self.fetch_branch_info(client, tree_url, headers)

            if not tree_info:
                return False

            tree = tree_info['tree']
            all_manifests = [item['path'] for item in tree if item['path'].endswith('.manifest')]

            # 下载并处理文件
            tasks = []
            for item in tree:
                task = self.get_manifest_from_github(
                    client, sha, item['path'], repo, dlc_id, all_manifests)
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)
            return True

        except Exception as e:
            self.log.error(f"处理GitHub源DLC失败: {str(e)}")
            return False

    async def _merge_dlcs_to_main_lua(self, app_id: str):
        """将DLC合并到主游戏的lua文件中"""
        try:
            main_lua_path = self.steam_path / 'config' / 'stplug-in' / f"{app_id}.lua"
            if not main_lua_path.exists():
                self.log.warning(f"主游戏lua文件不存在: {main_lua_path}")
                return

            # 查找所有DLC的lua文件并合并
            stplug_dir = self.steam_path / 'config' / 'stplug-in'
            dlc_pattern = re.compile(r'^(\d+)\.lua$')

            for lua_file in stplug_dir.glob('*.lua'):
                match = dlc_pattern.match(lua_file.name)
                if match and match.group(1) != app_id:
                    # 检查是否是该游戏的DLC（这里简化处理，实际可能需要更精确的判断）
                    # 暂时跳过合并，因为DLC已经有自己的lua文件
                    pass

            self.log.info("DLC处理完成")

        except Exception as e:
            self.log.error(f"合并DLC到主lua文件失败: {str(e)}")