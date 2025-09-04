# -*- coding: utf-8 -*-
"""
Flow(Veo3) —— 修复版本
主要改进：
1) 更灵活的页面检测
2) 直接查找输入框元素
3) 增加调试信息输出
4) 改进等待和重试机制
"""

from typing import Dict, Any, Optional, List, Tuple, Callable
import re, time, requests, os, subprocess, base64

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# ===== 可调参数 =====
APP_READY_TOTAL_SECONDS = 60  # 增加等待时间
RETRY_INTERVAL_SECONDS = 2.0  # 增加重试间隔
SCAN_PORTS = list(range(9222, 9233))
PASTE_STABILIZE_SECONDS = 1.5  # 增加粘贴后等待时间

# 更全面的输入框识别策略
INPUT_SELECTORS = [
    "textarea",
    "div[contenteditable='true']",
    "div[role='textbox']",
    "input[type='text']",
    "input:not([type='button']):not([type='submit']):not([type='reset'])",
    "[placeholder*='prompt']",
    "[placeholder*='提示']",
    "[placeholder*='输入']",
    "[placeholder*='describe']",
    "[aria-label*='prompt']",
    "[aria-label*='input']",
    "[data-testid*='input']",
    "[data-testid*='prompt']"
]

# 发送按钮识别策略
SEND_BUTTON_SELECTORS = [
    "button[type='submit']",
    "button:has(svg)",  # 通常箭头按钮包含 SVG
    "button[aria-label*='send']",
    "button[aria-label*='submit']",
    "button[title*='send']",
    "button[title*='submit']",
    "[role='button'][aria-label*='send']",
    "[data-testid*='send']",
    "[data-testid*='submit']"
]


# 保留原有的端口检测和驱动管理函数
def _http_get_json_no_proxy(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout, proxies={"http": None, "https": None})
    r.raise_for_status()
    return r.json()


def _probe_devtools_json(port: int):
    for host in ("127.0.0.1", "localhost"):
        try:
            return _http_get_json_no_proxy(f"http://{host}:{port}/json/version", 1.2)
        except Exception:
            pass
    return None


def _parse_major(browser: str) -> Optional[str]:
    m = re.search(r"/(\d+)\.", browser or "")
    return m.group(1) if m else None


def _read_devtools_active_port_candidates() -> List[int]:
    paths = [
        os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "DevToolsActivePort"),
        r"C:\Users\MSI\chrome-remote-profile\DevToolsActivePort",
        r"C:\temp\chrome-debug-profile-final\DevToolsActivePort",
    ]
    out = []
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    line = f.readline().strip()
                    if line.isdigit():
                        out.append(int(line))
        except Exception:
            pass
    return out


def _find_debug_ports_from_processes() -> List[int]:
    ports = []
    try:
        import psutil
        for proc in psutil.process_iter(attrs=["name", "cmdline"]):
            try:
                if not (proc.info.get("name") or "").lower().startswith("chrome"):
                    continue
                cmd = " ".join(proc.info.get("cmdline") or [])
                m = re.search(r"--remote-debugging-port=(\d+)", cmd)
                if m:
                    ports.append(int(m.group(1)))
            except Exception:
                continue
    except Exception:
        pass
    seen = set()
    uniq = []
    for p in ports:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def _install_matching_chromedriver(major: str) -> str:
    try:
        return ChromeDriverManager(version=major).install()
    except Exception:
        return ChromeDriverManager().install()


def _attach_driver(port: int, driver_path: str) -> webdriver.Chrome:
    opts = webdriver.ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    service = ChromeService(executable_path=driver_path)
    drv = webdriver.Chrome(service=service, options=opts)

    # 确保窗口在前台
    try:
        drv.execute_cdp_cmd("Page.bringToFront", {})
        drv.maximize_window()  # 最大化窗口
    except Exception:
        pass

    # 移除 webdriver 标记
    try:
        drv.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    except Exception:
        pass

    return drv


def _choose_working_port(preferred: Optional[int]) -> Optional[int]:
    candidates = []
    if preferred and preferred > 0:
        candidates.append(preferred)

    for p in _read_devtools_active_port_candidates():
        if p not in candidates:
            candidates.append(p)

    for p in _find_debug_ports_from_processes():
        if p not in candidates:
            candidates.append(p)

    for p in SCAN_PORTS:
        if p not in candidates:
            candidates.append(p)

    for p in candidates:
        if _probe_devtools_json(p):
            return p

    return None


def _set_clipboard(text: str) -> bool:
    """设置系统剪贴板"""
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    try:
        b64 = base64.b64encode(text.encode("utf-16le")).decode("ascii")
        ps = ("$b='{b64}';$t=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($b));"
              "Set-Clipboard -Value $t").format(b64=b64)
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
        return True
    except Exception:
        pass

    try:
        p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
        p.communicate((text or "").encode("utf-8", errors="ignore"))
        return p.returncode == 0
    except Exception:
        return False


def _find_input_element(driver) -> Optional[Any]:
    """查找输入框元素"""
    print("🔍 正在查找输入框...")

    for selector in INPUT_SELECTORS:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                # 检查元素是否可见和可编辑
                if (element.is_displayed() and
                        element.is_enabled() and
                        not element.get_attribute("readonly")):
                    print(f"✅ 找到输入框: {selector}")
                    return element
        except Exception as e:
            print(f"⚠️ 选择器 {selector} 出错: {e}")
            continue

    print("❌ 未找到合适的输入框")
    return None


def _find_send_button(driver) -> Optional[Any]:
    """查找发送按钮"""
    print("🔍 正在查找发送按钮...")

    for selector in SEND_BUTTON_SELECTORS:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                if element.is_displayed() and element.is_enabled():
                    print(f"✅ 找到发送按钮: {selector}")
                    return element
        except Exception as e:
            print(f"⚠️ 选择器 {selector} 出错: {e}")
            continue

    # 通用按钮查找
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if (btn.is_displayed() and btn.is_enabled() and
                    any(keyword in (btn.text or "").lower() + (btn.get_attribute("aria-label") or "").lower()
                        for keyword in ["send", "submit", "generate", "create", "生成", "发送", "提交"])):
                print(f"✅ 找到通用发送按钮: {btn.text}")
                return btn
    except Exception as e:
        print(f"⚠️ 通用按钮查找出错: {e}")

    print("❌ 未找到合适的发送按钮")
    return None


def _input_and_submit(driver, prompt_text: str) -> Tuple[bool, str]:
    """输入文本并提交"""
    print(f"📝 开始输入文本: {prompt_text[:50]}...")

    # 查找输入框
    input_element = _find_input_element(driver)
    if not input_element:
        return False, "未找到输入框"

    try:
        # 聚焦到输入框
        print("🎯 聚焦输入框...")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_element)
        time.sleep(0.5)
        input_element.click()
        time.sleep(0.5)

        # 清空输入框
        print("🧹 清空输入框...")
        input_element.clear()
        time.sleep(0.3)

        # 方法1：直接输入
        try:
            # 方法2：使用剪贴板
            print("📋 方法2：使用剪贴板粘贴...")
            if _set_clipboard(prompt_text):
                input_element.send_keys(Keys.CONTROL, "v")
                time.sleep(PASTE_STABILIZE_SECONDS)
            else:
                return False, "设置剪贴板失败"
        except Exception as e:
            pass
        # 验证输入
        current_value = input_element.get_attribute("value") or input_element.text
        print(f"📋 当前输入框内容: {current_value[:50]}...")

        # 提交方法1：回车
        print("⏎ 尝试回车提交...")
        try:
            input_element.send_keys(Keys.ENTER)
            time.sleep(2.0)
            return True, "回车提交成功"
        except Exception as e:
            print(f"⚠️ 回车提交失败: {e}")

        # 提交方法2：点击发送按钮
        print("🖱️ 尝试点击发送按钮...")
        send_button = _find_send_button(driver)
        if send_button:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", send_button)
                time.sleep(0.5)
                send_button.click()
                time.sleep(2.0)
                return True, "按钮点击提交成功"
            except Exception as e:
                print(f"⚠️ 按钮点击失败: {e}")
                # 使用JavaScript点击
                try:
                    driver.execute_script("arguments[0].click();", send_button)
                    time.sleep(2.0)
                    return True, "JavaScript点击提交成功"
                except Exception as e2:
                    print(f"⚠️ JavaScript点击也失败: {e2}")

        return False, "所有提交方法都失败"

    except Exception as e:
        print(f"❌ 输入和提交过程出错: {e}")
        return False, f"输入提交异常: {e}"


def generate_video_in_flow(prompt_text: str,
                           debugging_port: Optional[int] = None,
                           flow_url: Optional[str] = None) -> Dict[str, Any]:
    """主函数：生成视频"""
    print("🚀 开始Flow视频生成流程...")

    # 选择工作端口
    port = _choose_working_port(debugging_port if debugging_port else None)
    if not port:
        return {"success": False, "message":
            "未检测到 DevTools 端口。请关闭所有 Chrome 后，用自定义目录启动："
            r' "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\MSI\chrome-remote-profile"'
                }

    print(f"🔌 使用端口: {port}")

    # 安装ChromeDriver
    try:
        info = _probe_devtools_json(port)
        major = _parse_major((info or {}).get("Browser", "")) or "latest"
        driver_path = _install_matching_chromedriver(major)
        print(f"🚗 ChromeDriver路径: {driver_path}")
    except Exception as e:
        return {"success": False, "message": f"安装匹配 ChromeDriver 失败：{e}"}

    # 连接到Chrome
    try:
        driver = _attach_driver(port, driver_path)
        print("✅ 成功连接到Chrome")
    except Exception as e:
        return {"success": False, "message": f"Selenium 附着失败（port={port}）：{e}"}

    try:
        # 查找或打开Flow页面
        print("🔍 查找Flow页面...")
        flow_handle = None

        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            current_url = (driver.current_url or "").lower()
            print(f"📄 检查标签页: {current_url}")

            # 更宽松的URL匹配
            if any(keyword in current_url for keyword in ["flow", "veo", "labs.google", "ai.google"]):
                flow_handle = handle
                print(f"✅ 找到Flow页面: {current_url}")
                break

        # 如果没找到Flow页面，尝试打开
        if not flow_handle and flow_url:
            print(f"🌐 打开新的Flow页面: {flow_url}")
            driver.switch_to.window(driver.window_handles[0])
            driver.execute_script(f"window.open('{flow_url}','_blank');")
            time.sleep(3.0)
            flow_handle = driver.window_handles[-1]
            driver.switch_to.window(flow_handle)

        if not flow_handle:
            return {"success": False, "message": "未找到 Flow 标签页，且未提供 flow_url。"}

        driver.switch_to.window(flow_handle)
        print(f"🎯 当前页面: {driver.current_url}")

        # 等待页面加载完成
        print("⏳ 等待页面加载...")
        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            print("✅ 页面加载完成")
        except TimeoutException:
            print("⚠️ 页面加载超时，但继续尝试...")

        # 额外等待JavaScript渲染
        time.sleep(3.0)

        # 多次尝试输入和提交
        print("🔄 开始尝试输入和提交...")
        start_time = time.time()
        attempt = 0

        while time.time() - start_time < APP_READY_TOTAL_SECONDS:
            attempt += 1
            print(f"\n🎯 第 {attempt} 次尝试...")

            success, reason = _input_and_submit(driver, prompt_text)
            if success:
                print(f"🎉 成功！原因: {reason}")
                return {"success": True, "message": f"已提交生成请求（{reason}）"}

            print(f"⚠️ 第 {attempt} 次尝试失败: {reason}")
            time.sleep(RETRY_INTERVAL_SECONDS)

        return {"success": False, "message": f"经过 {attempt} 次尝试后仍未成功。最后失败原因: {reason}"}

    except Exception as e:
        print(f"❌ 自动化过程异常: {e}")
        return {"success": False, "message": f"自动化异常：{e}"}

    finally:
        # 可选：关闭driver（如果你不需要保持连接）
        # driver.quit()
        pass


# 使用示例
if __name__ == "__main__":
    prompt = "一只可爱的小猫在花园里玩耍"
    result = generate_video_in_flow(prompt)
    print(f"\n最终结果: {result}")