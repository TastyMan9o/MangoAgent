# -*- coding: utf-8 -*-
"""
Flow(Veo3) 页面自动填写并提交提示词 —— Zero-Click 优先版（可直接替换原文件）
改动要点：
- 先“零点击聚焦（zero-click focus）”锁定真正的文本输入框，再考虑任何点击/Tab
- 候选输入框按：提示词匹配、靠近底部中部、尺寸与可编辑性 评分排序
- 失败才降级到极少量 XY 扫描、最后才使用 Tab 巡航（可通过开关禁用）
"""

from typing import Dict, Any, Optional, List, Tuple, Callable
import re, time, requests, os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# ===== 可调参数 =====
APP_READY_TOTAL_SECONDS = 40
RETRY_INTERVAL_SECONDS = 1.2
SCAN_PORTS = list(range(9222, 9233))
AFTER_INPUT_STABILIZE_SECONDS = 1.2  # 文本注入后等待 UI 就绪时间

# —— Zero-Click 策略开关 —— #
ZERO_CLICK_FIRST = True          # 优先使用零点击深度聚焦（推荐开启）
ENABLE_TAB_FALLBACK = False      # 是否允许最终使用 Tab 巡航（默认关闭以完全避免乱跳）

# 底部输入栏位置扫描（与原版一致，但会更少用到）
XY_SCAN_X_FACTORS = [0.50, 0.56, 0.44]   # 收敛到更少扫描点
XY_SCAN_Y_OFFSETS = [-90, -105]          # 收敛到更少扫描点

PROMPT_HINTS = [
    "使用文本生成视频","在提示框中输入","请输入提示","提示","文本","内容","描述",
    "prompt","idea","describe","caption","story","keywords","topic","text"
]
BUTTON_HINTS = [
    "生成","创建","提交","开始","运行","执行","启动","播放","下一步","继续",
    "generate","create","submit","start","run","make","play","next","continue"
]

# ---------- DevTools & Driver ----------
def _http_get_json_no_proxy(url: str, timeout: float = 2.0) -> Dict[str, Any]:
    r = requests.get(url, timeout=timeout, proxies={"http": None, "https": None})
    r.raise_for_status()
    return r.json()

def _tick_editor_after_programmatic_input(drv, el):
    """程序化设值后做一次真实键事件触发：Space → Backspace，避免“箭头不亮”"""
    try:
        drv.execute_script("""
            const el = arguments[0];
            el && el.focus && el.focus();
            if (el && el.isContentEditable) {
                const sel = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                sel.removeAllRanges(); sel.addRange(range);
            } else if (el && typeof el.selectionStart === 'number') {
                const len = (el.value || '').length;
                el.setSelectionRange(len, len);
            }
        """, el)

        drv.execute_cdp_cmd("Input.dispatchKeyEvent",
                            {"type":"keyDown","key":" ","code":"Space","windowsVirtualKeyCode":32})
        drv.execute_cdp_cmd("Input.dispatchKeyEvent",
                            {"type":"keyUp","key":" ","code":"Space","windowsVirtualKeyCode":32})
        drv.execute_cdp_cmd("Input.dispatchKeyEvent",
                            {"type":"keyDown","key":"Backspace","code":"Backspace","windowsVirtualKeyCode":8})
        drv.execute_cdp_cmd("Input.dispatchKeyEvent",
                            {"type":"keyUp","key":"Backspace","code":"Backspace","windowsVirtualKeyCode":8})
        return True
    except Exception:
        return False

def _probe_devtools_json(port: int):
    for host in ("127.0.0.1","localhost"):
        try:
            return _http_get_json_no_proxy(f"http://{host}:{port}/json/version", timeout=1.2)
        except Exception:
            pass
    return None

def _set_system_clipboard(text: str) -> bool:
    # 1) pyperclip
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass
    # 2) Windows PowerShell（Unicode 可靠）
    try:
        import base64, subprocess
        b64 = base64.b64encode(text.encode("utf-16le")).decode("ascii")
        ps  = ("$b='{b64}';$t=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($b));"
               "Set-Clipboard -Value $t").format(b64=b64)
        subprocess.run(["powershell","-NoProfile","-Command",ps], check=True)
        return True
    except Exception:
        pass
    # 3) clip 退路
    try:
        import subprocess
        p = subprocess.Popen("clip", stdin=subprocess.PIPE, shell=True)
        p.communicate((text or "").encode("utf-8", errors="ignore"))
        return p.returncode == 0
    except Exception:
        return False

def _get_editor_text(drv, el) -> str:
    try:
        return drv.execute_script("""
            const el=arguments[0];
            if(!el) return "";
            if (el.isContentEditable) return el.innerText || "";
            if (el.value !== undefined) return el.value || "";
            return el.textContent || "";
        """, el) or ""
    except Exception:
        return ""

def _parse_major(browser: str) -> Optional[str]:
    m = re.search(r"/(\d+)\.", browser or "")
    return m.group(1) if m else None

def _read_devtools_active_port_candidates() -> List[int]:
    paths = [
        os.path.join(os.getenv("LOCALAPPDATA",""),"Google","Chrome","User Data","DevToolsActivePort"),
        r"C:\Users\MSI\chrome-remote-profile\DevToolsActivePort",
        r"C:\temp\chrome-debug-profile-final\DevToolsActivePort",
    ]
    out=[]
    for p in paths:
        try:
            if os.path.exists(p):
                with open(p,"r",encoding="utf-8") as f:
                    line=f.readline().strip()
                    if line.isdigit(): out.append(int(line))
        except Exception:
            pass
    return out

def _find_debug_ports_from_processes() -> List[int]:
    ports=[]
    try:
        import psutil
        for proc in psutil.process_iter(attrs=["name","cmdline"]):
            try:
                if not (proc.info.get("name") or "").lower().startswith("chrome"): continue
                cmd=" ".join(proc.info.get("cmdline") or [])
                m=re.search(r"--remote-debugging-port=(\d+)",cmd)
                if m: ports.append(int(m.group(1)))
            except Exception:
                continue
    except Exception:
        pass
    seen=set(); uniq=[]
    for p in ports:
        if p not in seen: uniq.append(p); seen.add(p)
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
    return webdriver.Chrome(service=service, options=opts)

def _choose_working_port(preferred: Optional[int]) -> Optional[int]:
    candidates=[]
    if preferred and preferred>0: candidates.append(preferred)
    for p in _read_devtools_active_port_candidates():
        if p not in candidates: candidates.append(p)
    for p in _find_debug_ports_from_processes():
        if p not in candidates: candidates.append(p)
    for p in SCAN_PORTS:
        if p not in candidates: candidates.append(p)
    for p in candidates:
        if _probe_devtools_json(p): return p
    return None

# ---------- Deep finders (JS) ----------
_FIND_COMPOSER_JS = r'''
(function(hints){
  const contains=(s,subs)=>!!s && subs.some(k=> s.toLowerCase().includes(k.toLowerCase()));
  const vis=(el)=>{ if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el);
                    return r.width>0 && r.height>0 && st.visibility!=='hidden' && st.display!=='none'; };
  const roots=[]; const add=r=>{ if(r && !roots.includes(r)) roots.push(r); };
  add(document);
  for(let i=0;i<roots.length;i++){
    const r=roots[i]; const nodes=(r.querySelectorAll ? r.querySelectorAll('*') : []);
    for(const n of nodes){ if(n && n.shadowRoot) add(n.shadowRoot); }
  }
  const qsAllDeep=sel=>{ const out=[]; for(const r of roots){ try{ r.querySelectorAll(sel).forEach(e=>out.push(e)); }catch(e){} } return out; };

  let cands = [];
  ['textarea','input[type="text"]','input[type="search"]','[contenteditable="true"]','[role="textbox"]','div[aria-multiline="true"]']
  .forEach(sel=> qsAllDeep(sel).forEach(el=>{ if(vis(el)) cands.push(el); }));

  const isCapsuleLike = (el)=>{
    const role=(el.getAttribute('role')||'').toLowerCase();
    const hasPopup=(el.getAttribute('aria-haspopup')||'').toLowerCase();
    if (role==='combobox' || (hasPopup && hasPopup!=='false')) return true;
    const near=el.closest('[role="tablist"],[role="menu"],[role="menubar"],[role="toolbar"]');
    return !!near;
  };

  const isEditable = (el)=>{
    const tn=(el.tagName||'').toLowerCase();
    if (el.isContentEditable) return true;
    if (tn==='textarea') return true;
    if (tn==='input') {
      const t=(el.type||'text').toLowerCase();
      return !['button','checkbox','radio','submit','file','range','color','reset','hidden'].includes(t);
    }
    const role=(el.getAttribute('role')||'').toLowerCase();
    if (['textbox','searchbox'].includes(role)) return true;
    // combobox 常被用于模式胶囊，排除
    if (role==='combobox') return false;
    return false;
  };

  const score=(el)=>{
    let s=0;
    const r=el.getBoundingClientRect();
    const centerOK = (r.left > innerWidth*0.12) && (r.right < innerWidth*0.88);
    const bottomness = (r.top - innerHeight*0.55) / Math.max(1, innerHeight*0.45); // [-∞,1]
    s += Math.max(0, Math.min(10, Math.round(bottomness*12))); // 0~10:越靠下越高
    if (centerOK) s += 6;
    const area = r.width*r.height;
    s += Math.min(6, Math.round(area/40000)); // 面积越大，越像编辑器
    const al=(el.getAttribute('placeholder')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('data-placeholder')||'');
    if (contains(al,hints)) s += 14; // 提示词强信号
    if (isCapsuleLike(el)) s -= 12;  // 胶囊/菜单强惩罚
    if (isEditable(el)) s += 6;
    if (r.height >= 32) s += 2;
    return s;
  };

  cands = cands
    .filter(el=>isEditable(el))
    .map(el=>({el, sc:score(el)}))
    .sort((a,b)=>b.sc-a.sc)
    .map(x=>x.el);

  return cands[0] || null;
})(arguments[0]);
'''

# —— 新增：一次性返回“候选列表”，便于顺序聚焦（零点击） —— #
_FIND_COMPOSERS_LIST_JS = r'''
(function(hints){
  const contains=(s,subs)=>!!s && subs.some(k=> s.toLowerCase().includes(k.toLowerCase()));
  const vis=(el)=>{ if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el);
                    return r.width>0 && r.height>0 && st.visibility!=='hidden' && st.display!=='none'; };
  const roots=[]; const add=r=>{ if(r && !roots.includes(r)) roots.push(r); };
  add(document);
  for(let i=0;i<roots.length;i++){
    const r=roots[i]; const nodes=(r.querySelectorAll ? r.querySelectorAll('*') : []);
    for(const n of nodes){ if(n && n.shadowRoot) add(n.shadowRoot); }
  }
  const qsAllDeep=sel=>{ const out=[]; for(const r of roots){ try{ r.querySelectorAll(sel).forEach(e=>out.push(e)); }catch(e){} } return out; };

  let cands = [];
  ['textarea','input[type="text"]','input[type="search"]','[contenteditable="true"]','[role="textbox"]','div[aria-multiline="true"]']
    .forEach(sel=> qsAllDeep(sel).forEach(el=>{ if(vis(el)) cands.push(el); }));

  const isCapsuleLike = (el)=>{
    const role=(el.getAttribute('role')||'').toLowerCase();
    const hasPopup=(el.getAttribute('aria-haspopup')||'').toLowerCase();
    if (role==='combobox' || (hasPopup && hasPopup!=='false')) return true;
    const near=el.closest('[role="tablist"],[role="menu"],[role="menubar"],[role="toolbar"]');
    return !!near;
  };

  const isEditable = (el)=>{
    const tn=(el.tagName||'').toLowerCase();
    if (el.isContentEditable) return true;
    if (tn==='textarea') return true;
    if (tn==='input') {
      const t=(el.type||'text').toLowerCase();
      return !['button','checkbox','radio','submit','file','range','color','reset','hidden'].includes(t);
    }
    const role=(el.getAttribute('role')||'').toLowerCase();
    if (['textbox','searchbox'].includes(role)) return true;
    if (role==='combobox') return false;
    return false;
  };

  const score=(el)=>{
    let s=0;
    const r=el.getBoundingClientRect();
    const centerOK = (r.left > innerWidth*0.12) && (r.right < innerWidth*0.88);
    const bottomness = (r.top - innerHeight*0.55) / Math.max(1, innerHeight*0.45);
    s += Math.max(0, Math.min(10, Math.round(bottomness*12)));
    if (centerOK) s += 6;
    const area = r.width*r.height;
    s += Math.min(6, Math.round(area/40000));
    const al=(el.getAttribute('placeholder')||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('data-placeholder')||'');
    if (contains(al,hints)) s += 14;
    if (isCapsuleLike(el)) s -= 12;
    if (isEditable(el)) s += 6;
    if (r.height >= 32) s += 2;
    return s;
  };

  return cands
    .filter(el=>isEditable(el))
    .map(el=>({el, sc:score(el)}))
    .sort((a,b)=>b.sc-a.sc)
    .slice(0,6)           // 只取前6个候选，足够用且更快
    .map(x=>x.el);
})(arguments[0]);
'''

_FIND_SEND_BUTTON_JS = r'''
(function(anchor, hints){
  const contains=(s,subs)=>!!s && subs.some(k=> s.toLowerCase().includes(k.toLowerCase()));
  const vis=(el)=>{ if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el);
                    return r.width>0 && r.height>0 && st.visibility!=='hidden' && st.display!=='none'; };
  const disabledLike=(el)=>{ if(!el) return true; if(el.disabled) return true;
    const ad=el.getAttribute('aria-disabled'); if(ad && ad.toString().toLowerCase()==='true') return true;
    const cls=(el.getAttribute('class')||'').toLowerCase(); if(cls.includes('disabled')) return true;
    if(getComputedStyle(el).pointerEvents==='none') return true; return false; };

  function collectRoots(start){ const roots=[]; const add=r=>{ if(r && !roots.includes(r)) roots.push(r); };
    add(start||document); for(let i=0;i<roots.length;i++){ const r=roots[i];
      const nodes=(r.querySelectorAll?r.querySelectorAll('*'):[]); for(const n of nodes){ if(n && n.shadowRoot) add(n.shadowRoot); } }
    return roots; }

  const base = anchor ? (anchor.closest('section,div,form,main,article,footer')||document) : document;
  const roots = collectRoots(base);
  const out=[];
  for(const r of roots){ try{ r.querySelectorAll('button,[role="button"]').forEach(b=>{ if(vis(b) && !disabledLike(b)) out.push(b); }); }catch(e){} }

  function dist(a,b){ const ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();
    const ax=(ra.left+ra.right)/2, ay=(ra.top+ra.bottom)/2, bx=(rb.left+rb.right)/2, by=(rb.top+rb.bottom)/2;
    return Math.hypot(ax-bx, ay-by); }

  if(anchor) out.sort((a,b)=>dist(a,anchor)-dist(b,anchor));

  const isGen=(el)=>{ const t=(el.innerText||'').toLowerCase(); const al=(el.getAttribute('aria-label')||'').toLowerCase(); const ti=(el.getAttribute('title')||'').toLowerCase();
                      return contains(t,hints) || contains(al,hints) || contains(ti,hints); };
  for(const b of out){ if(isGen(b)) return b; }
  for(const b of out){ const w=b.offsetWidth, h=b.offsetHeight, txt=(b.innerText||'').trim();
    if(w>=36 && h>=36 && txt.length<=4) return b; }
  return null;
})(arguments[0], arguments[1]);
'''

_GUESS_INPUT_BY_ARROW_JS = r'''
(function(){
  function vis(el){ if(!el) return false; const r=el.getBoundingClientRect(); const st=getComputedStyle(el);
    return r.width>0 && r.height>0 && st.visibility!=='hidden' && st.display!=='none'; }
  const btns = Array.from(document.querySelectorAll('button,[role="button"]')).filter(vis);
  let arrow=null, best=0;
  for(const b of btns){
    const r=b.getBoundingClientRect();
    const roundScore = Math.min(r.width,r.height) / Math.max(r.width,r.height);
    const posScore = (r.top>window.innerHeight*0.6?1:0) + (r.left>window.innerWidth*0.6?1:0);
    const score = roundScore + posScore;
    if(score>best){ best=score; arrow=b; }
  }
  if(!arrow) return null;
  const br=arrow.getBoundingClientRect();
  const x=Math.max(10, br.left - Math.min(120, br.width*2));
  const y=Math.min(window.innerHeight-10, (br.top+br.bottom)/2);
  const el=document.elementFromPoint(x,y);
  return el || null;
})();
'''

def _deep_find_composer(driver):
    try:
        return driver.execute_script(_FIND_COMPOSER_JS, PROMPT_HINTS)
    except Exception:
        return None

def _deep_find_composers_list(driver) -> List:
    """返回多个候选，供 Zero-Click 顺序尝试"""
    try:
        lst = driver.execute_script(_FIND_COMPOSERS_LIST_JS, PROMPT_HINTS)
        return lst or []
    except Exception:
        return []

def _deep_find_send_button(driver, anchor):
    try:
        return driver.execute_script(_FIND_SEND_BUTTON_JS, anchor, BUTTON_HINTS)
    except Exception:
        return None

def _guess_input_by_arrow(driver):
    try:
        return driver.execute_script(_GUESS_INPUT_BY_ARROW_JS)
    except Exception:
        return None

# ---------- 坐标点击（仅作兜底） ----------
def _cdp_click_viewport_xy(driver, x: int, y: int) -> bool:
    try:
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type":"mouseMoved","x":int(x),"y":int(y),"buttons":1})
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type":"mousePressed","x":int(x),"y":int(y),"button":"left","clickCount":1})
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {"type":"mouseReleased","x":int(x),"y":int(y),"button":"left","clickCount":1})
        return True
    except Exception:
        return False

def _is_editable(driver, el) -> bool:
    try:
        return bool(driver.execute_script("""
          const el=arguments[0];
          if(!el) return false;
          const role=(el.getAttribute('role')||'').toLowerCase();
          const tn=(el.tagName||'').toLowerCase();
          const hasPopup=(el.getAttribute('aria-haspopup')||'').toLowerCase();
          if (['button','menu','menuitem','tab','tablist','switch','checkbox','radio'].includes(role)) return false;
          if (['button','a'].includes(tn)) return false;
          if (hasPopup && hasPopup !== 'false') return false;
          if (el.isContentEditable) return true;
          if (tn === 'textarea') return true;
          if (tn === 'input') {
            const t=(el.type||'text').toLowerCase();
            return !['button','checkbox','radio','submit','file','range','color','reset','hidden'].includes(t);
          }
          if (['textbox','searchbox'].includes(role)) return true;
          if (role==='combobox') return false;
          const r = el.getBoundingClientRect();
          const inBottom = r.top > window.innerHeight*0.55 && r.height >= 28;
          const inCenter = r.left > window.innerWidth*0.12 && r.right < window.innerWidth*0.88;
          return inBottom && inCenter;
        """, el))
    except Exception:
        return False

def _focus_prompt_bar_xy_scan(driver, dwell=0.12):
    """少量 XY 点击扫描（降级选项，点位收敛以减少误触）"""
    try:
        w,h = driver.execute_script("return [window.innerWidth, window.innerHeight];")
    except Exception:
        return None
    for xf in XY_SCAN_X_FACTORS:
        x = int(w * xf)
        for dy in XY_SCAN_Y_OFFSETS:
            y = int(h + dy)
            _cdp_click_viewport_xy(driver, x, y)
            time.sleep(dwell)
            el = driver.switch_to.active_element
            if el and _is_editable(driver, el):
                return el
    return None

def _tab_to_any_textbox(driver, max_steps=36):
    """不推荐；仅作为最后兜底，可关闭 ENABLE_TAB_FALLBACK 来完全禁用"""
    try:
        try:
            driver.find_element(By.TAG_NAME, "body").click()
        except Exception:
            pass
        for _ in range(max_steps):
            el = driver.switch_to.active_element
            if el and _is_editable(driver, el):
                ok = driver.execute_script("""
                  const r=arguments[0].getBoundingClientRect();
                  return (r.top > innerHeight*0.55) &&
                         (r.left > innerWidth*0.12) && (r.right < innerWidth*0.88) &&
                         (r.height >= 28);
                """, el)
                if ok:
                    return el
            ActionChains(driver).send_keys(Keys.TAB).perform()
            time.sleep(0.10)
    except Exception:
        return None
    return None

def _click_bottom_right_send(driver) -> bool:
    try:
        w,h = driver.execute_script("return [window.innerWidth, window.innerHeight];")
        return _cdp_click_viewport_xy(driver, int(w-40), int(h-40))
    except Exception:
        return False

# ---------- Zero-Click：不点任何按钮，顺序聚焦候选 ----------
def _zero_click_focus_bottom_textbox(driver):
    """
    1) 返回候选输入框列表（按评分排序）
    2) 逐个执行 scrollIntoView + focus（不做 click）
    3) 若是封闭 shadow host，尝试对 host 本身 focus；再看 activeElement 是否变为可编辑
    """
    try:
        candidates = _deep_find_composers_list(driver)
        for el in candidates[:4]:  # 尝试前4个足够稳
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'nearest'});", el)
                driver.execute_script("arguments[0].focus && arguments[0].focus();", el)
                time.sleep(0.05)
            except Exception:
                continue

            # 直接拿 activeElement
            try:
                active = driver.switch_to.active_element
                if active and _is_editable(driver, active):
                    return active
            except Exception:
                pass

            # 再次校验：elementFromPoint 只做 focus，不点
            try:
                x,y = driver.execute_script("""
                  const r = arguments[0].getBoundingClientRect();
                  return [ (r.left+r.right)/2, Math.min(window.innerHeight-5, (r.top+r.bottom)/2) ];
                """, el)
                host = driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", x, y)
                if host:
                    driver.execute_script("arguments[0].focus && arguments[0].focus();", host)
                    time.sleep(0.05)
                    active = driver.switch_to.active_element
                    if active and _is_editable(driver, active):
                        return active
            except Exception:
                pass
        return None
    except Exception:
        return None

# ---------- 文本输入 ----------
AFTER_INPUT_STABILIZE_SECONDS = globals().get("AFTER_INPUT_STABILIZE_SECONDS", 0.8)

def _clear_and_type(el, text: str) -> bool:
    try:
        try:
            el.click()
        except Exception:
            pass
        drv = el.parent

        try:
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            time.sleep(0.05)
        except Exception:
            try:
                drv.execute_script("""
                    if (arguments[0].isContentEditable) { arguments[0].innerText = ""; }
                    else if (arguments[0].value !== undefined) { arguments[0].value = ""; }
                    else { arguments[0].textContent = ""; }
                """, el)
            except Exception:
                pass

        if _set_system_clipboard(text):
            try:
                el.send_keys(Keys.CONTROL, "v")
                time.sleep(0.05)
                try:
                    _tick_editor_after_programmatic_input(drv, el)
                except Exception:
                    pass
                time.sleep(AFTER_INPUT_STABILIZE_SECONDS)
                cur = _get_editor_text(drv, el)
                if cur and (cur.strip()[:8] == (text.strip()[:8] if text else "")):
                    return True
            except Exception:
                pass

        try:
            drv.execute_script("arguments[0].focus && arguments[0].focus();", el)
        except Exception:
            pass

        try:
            try:
                drv.execute_script("""
                    if (arguments[0].isContentEditable) { arguments[0].innerText=''; }
                    else if (arguments[0].value !== undefined) { arguments[0].value=''; }
                    else { arguments[0].textContent=''; }
                """, el)
            except Exception:
                pass

            drv.execute_cdp_cmd("Input.insertText", {"text": text})
            time.sleep(0.05)
            try:
                drv.execute_script("arguments[0].dispatchEvent(new Event('input',  {bubbles:true}));", el)
                drv.execute_script("arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", el)
            except Exception:
                pass
            try:
                _tick_editor_after_programmatic_input(drv, el)
            except Exception:
                pass
            time.sleep(AFTER_INPUT_STABILIZE_SECONDS)
            return True
        except Exception:
            try:
                drv.execute_script("""
                    const el = arguments[0], val = arguments[1];
                    el.focus && el.focus();
                    if (el.isContentEditable) {
                        try { document.execCommand && document.execCommand('selectAll', false, null); } catch(e){}
                        try { document.execCommand && document.execCommand('insertText', false, val); }
                        catch(e){ el.innerText = val; }
                    } else if (el.value !== undefined) {
                        el.value = val;
                    } else {
                        el.textContent = val;
                    }
                    el.dispatchEvent && el.dispatchEvent(new Event('input',  { bubbles: true }));
                    el.dispatchEvent && el.dispatchEvent(new Event('change', { bubbles: true }));
                """, el, text)
                time.sleep(0.05)
                try:
                    _tick_editor_after_programmatic_input(drv, el)
                except Exception:
                    pass
                time.sleep(AFTER_INPUT_STABILIZE_SECONDS)
                return True
            except Exception:
                return False
    except Exception:
        try:
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(text)
            time.sleep(0.05)
            try:
                _tick_editor_after_programmatic_input(el.parent, el)
            except Exception:
                pass
            time.sleep(AFTER_INPUT_STABILIZE_SECONDS)
            return True
        except Exception:
            return False

# ---------- 执行一次“填充并触发” ----------
def _fill_then_click_here(driver, prompt_text: str) -> Tuple[bool, str]:
    # 1) 先“检测文本框”（深度 JS 查找，不做任何点击；避免误触下载/分享等控件）
    composer = _deep_find_composer(driver)

    # 2) 找不到再用 XY 扫描（会点击），只作为二级兜底
    if composer is None:
        composer = _focus_prompt_bar_xy_scan(driver)

    # 3) 仍找不到，最后才用 TAB 巡航（最容易把焦点游走到一堆可交互控件上）
    if composer is None:
        composer = _tab_to_any_textbox(driver)

    # 4) 还失败就退出
    if composer is None:
        return False, "no_composer"

    # 5) 输入
    if not _clear_and_type(composer, prompt_text):
        return False, "type_error"

    # 6) 发送（顺序不变：按钮→回车→右下角兜底；如果你之前已按我给的“回车优先”改过，也保留即可）
    btn = _deep_find_send_button(driver, composer)
    if btn is not None:
        try:
            btn.click()
            return True, "clicked"
        except WebDriverException:
            try:
                driver.execute_script("arguments[0].click();", btn)
                return True, "clicked(js)"
            except Exception:
                pass

    try:
        composer.send_keys(Keys.ENTER)
        time.sleep(0.3)
        return True, "enter"
    except Exception:
        pass

    if _click_bottom_right_send(driver):
        return True, "cdp_click"

    return False, "no_button"


def _with_each_frame(driver, fn: Callable[[], Tuple[bool,str]], depth=0, limit=3) -> Tuple[bool,str]:
    ok, reason = fn()
    if ok: return True, reason
    if depth >= limit: return False, reason
    frames = driver.find_elements(By.CSS_SELECTOR, "iframe")
    for f in frames:
        try:
            driver.switch_to.frame(f)
            ok2, r2 = _with_each_frame(driver, fn, depth+1, limit)
            driver.switch_to.default_content()
            if ok2: return True, r2
        except Exception:
            try: driver.switch_to.default_content()
            except Exception: pass
            continue
    return False, reason

# ---------- Public entry ----------
def generate_video_in_flow(prompt_text: str,
                           debugging_port: Optional[int] = None,
                           flow_url: Optional[str] = None) -> Dict[str, Any]:
    port = _choose_working_port(debugging_port if debugging_port else None)
    if not port:
        return {"success": False, "message":
            "未检测到 DevTools 端口。请关闭所有 Chrome 后，用自定义目录启动："
            r' "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\MSI\chrome-remote-profile"'
        }

    try:
        info = _probe_devtools_json(port)
        major = _parse_major((info or {}).get("Browser","")) or "latest"
        driver_path = _install_matching_chromedriver(major)
    except Exception as e:
        return {"success": False, "message": f"安装匹配 ChromeDriver 失败：{e}"}

    try:
        driver = _attach_driver(port, driver_path)
    except Exception as e:
        return {"success": False, "message": f"Selenium 附着失败（port={port}）：{e}"}

    try:
        handle=None
        for h in driver.window_handles:
            driver.switch_to.window(h)
            u=(driver.current_url or "").lower()
            if ("labs.google" in u and "/flow/" in u) or "flow" in u:
                handle=h; break
        if not handle and flow_url:
            driver.switch_to.window(driver.window_handles[0])
            driver.execute_script(f"window.open('{flow_url}','_blank');")
            time.sleep(0.6)
            handle=driver.window_handles[-1]
        if not handle:
            return {"success": False, "message": "未找到 Flow 标签页，且未提供 flow_url。"}
        driver.switch_to.window(handle)

        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            pass

        t0=time.time(); last_reason="unknown"
        while time.time()-t0 < APP_READY_TOTAL_SECONDS:
            ok, reason = _with_each_frame(driver, lambda: _fill_then_click_here(driver, prompt_text))
            if ok:
                time.sleep(1.0)
                return {"success": True, "message": f"已提交生成请求（port={port}, {reason}）。"}
            last_reason = reason
            time.sleep(RETRY_INTERVAL_SECONDS)

        return {"success": False, "message": f"未能触发生成（最后原因：{last_reason}）。请确认页面已加载/已登录。"}
    except Exception as e:
        return {"success": False, "message": f"自动化异常：{e}"}
