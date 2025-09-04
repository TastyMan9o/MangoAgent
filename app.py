# app.py (重构版 - 解决对话框位置、页面滚动和流式输出问题)
# -*- coding: utf-8 -*-
import streamlit as st
import requests, io, time, json, pandas as pd
from datetime import datetime
import qrcode
import os

# --- App Setup ---
st.set_page_config(page_title="MangoAgent 控制台", page_icon="🤖", layout="wide")

# --- 端口设置功能 ---
def get_api_base_url():
    """从session state获取API基础URL"""
    port = st.session_state.get('api_port', 8001)
    return f"http://127.0.0.1:{port}"

def get_proxy_settings():
    """获取代理设置"""
    proxy_enabled = st.session_state.get('proxy_enabled', False)
    proxy_host = st.session_state.get('proxy_host', '127.0.0.1')
    proxy_port = st.session_state.get('proxy_port', 7890)
    
    if proxy_enabled:
        return {
            "http": f"http://{proxy_host}:{proxy_port}",
            "https": f"http://{proxy_host}:{proxy_port}"
        }
    return {"http": None, "https": None}

API_BASE_URL = get_api_base_url()

# --- Reusable Functions ---
def display_prompt(prompt_content: dict):
    st.code(json.dumps(prompt_content, indent=2, ensure_ascii=False), language='json')

def refresh_prompt_list():
    try:
        resp = requests.get(f"{API_BASE_URL}/api/prompt/list", timeout=30, proxies=get_proxy_settings())
        resp.raise_for_status()
        st.session_state['prompt_files'] = resp.json()
        st.toast("Prompt 列表已刷新！")
    except Exception as e:
        st.error(f"获取Prompt列表失败: {e}")

def format_duration(seconds: int) -> str:
    if not isinstance(seconds, (int, float)): return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

# --- Session State Initialization ---
for key in ['cookie_str','hotspot_results','selected_prompt','refined_result','expansion_results','iteration_result']:
    st.session_state.setdefault(key, None)
st.session_state.setdefault('prompt_files', [])
st.session_state.setdefault("agent_messages", [{"role":"assistant","content":"你好！我是MangoAgent大脑，请问有什么可以帮您？"}])
st.session_state.setdefault('llm_provider', "Gemini")
st.session_state.setdefault('gemini_model', "gemini-2.5-flash")
st.session_state.setdefault('deepseek_model', "deepseek-chat")
st.session_state.setdefault('show_detailed_thinking', True)  # 新增：是否显示详细思考过程

# --- 主页面布局 ---
st.title("🤖 MangoAgent 控制台")
st.caption("您的自动化视频灵感助手")

# 创建两列布局：左侧功能，右侧对话
left_col, right_col = st.columns([2, 1])

# --- 左侧功能区域 ---
with left_col:
    # API密钥管理
    with st.expander("🔑 API 密钥管理 (API Key Management)"):
        try:
            response = requests.get(f"{API_BASE_URL}/api/keys/get", proxies=get_proxy_settings())
            if response.status_code == 200:
                current_keys = response.json()
            else:
                current_keys = {}
                st.error(f"加载API密钥状态失败: {response.status_code}")
        except Exception as e:
            st.error(f"无法连接后端加载API密钥状态: {e}")
            current_keys = {}
        
        # 显示当前密钥状态
        if current_keys:
            st.info("当前已保存的API密钥状态：")
            col1, col2, col3 = st.columns(3)
            with col1:
                if current_keys.get("deepseek_api_key"):
                    st.success(f"✅ DeepSeek: 已设置")
                else:
                    st.warning("❌ DeepSeek: 未设置")
            with col2:
                if current_keys.get("gemini_api_keys"):
                    key_count = len([k.strip() for k in current_keys.get("gemini_api_keys", "").split(',') if k.strip()])
                    st.success(f"✅ Gemini: 已设置 ({key_count} 个密钥)")
                else:
                    st.warning("❌ Gemini: 未设置")
            with col3:
                if current_keys.get("veo_api_key"):
                    st.success(f"✅ Veo: 已设置")
                else:
                    st.warning("❌ Veo: 未设置")
        
        with st.form("api_key_form"):
            st.info("在此处输入您的API密钥，将被安全地存储在项目的 .env 文件中。")
            deepseek_key = st.text_input("DeepSeek API Key", value=current_keys.get("deepseek_api_key", ""), type="password")
            gemini_keys_str = current_keys.get("gemini_api_keys", "")
            gemini_keys_display = "\n".join([k.strip() for k in gemini_keys_str.split(',') if k.strip()])
            gemini_keys_multiline = st.text_area("Gemini API Keys (每行一个，用于轮询)", value=gemini_keys_display, height=150, help="当一个Key达到速率限制时会自动切换到下一个。每行输入一个API密钥。")
            veo_key = st.text_input("Veo API Key", value=current_keys.get("veo_api_key", ""), type="password", help="输入您的Veo API密钥")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 保存所有密钥"):
                    with st.spinner("正在保存..."):
                        payload = {"deepseek_api_key": deepseek_key, "veo_api_key": veo_key, "gemini_api_keys": gemini_keys_multiline}
                        try:
                            response = requests.post(f"{API_BASE_URL}/api/keys/update", json=payload, proxies=get_proxy_settings())
                            response.raise_for_status()
                            st.success("✅ 保存成功！页面将重新加载以显示最新状态。")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ 保存失败: {e}")
            with col2:
                if st.form_submit_button("🔄 清空表单"):
                    st.rerun()

    # 端口设置
    with st.expander("⚙️ 端口设置 (Port Settings)"):
        st.info("在这里配置API端口和代理设置。")
        
        # 先处理代理启用状态
        proxy_enabled = st.checkbox("启用代理", value=st.session_state.get('proxy_enabled', False), help="是否启用HTTP代理（VPN）")
        
        with st.form("port_settings_form"):
            col1, col2 = st.columns(2)
            with col1:
                api_port = st.number_input("API端口", value=st.session_state.get('api_port', 8001), min_value=1024, max_value=65535, help="后端API服务端口（不是VPN端口）")
            with col2:
                # 显示当前代理状态
                if proxy_enabled:
                    st.success("✅ 代理已启用")
                else:
                    st.info("❌ 代理未启用")
            
            # 代理设置部分
            if proxy_enabled:
                st.markdown("**代理设置：**")
                col3, col4 = st.columns(2)
                with col3:
                    proxy_host = st.text_input("代理主机", value=st.session_state.get('proxy_host', '127.0.0.1'), help="代理服务器地址（通常是127.0.0.1）")
                with col4:
                    proxy_port = st.number_input("代理端口", value=st.session_state.get('proxy_port', 7890), min_value=1024, max_value=65535, help="VPN代理端口（如7890、1080等）")
            else:
                proxy_host = st.session_state.get('proxy_host', '127.0.0.1')
                proxy_port = st.session_state.get('proxy_port', 7890)
            
            if st.form_submit_button("保存端口设置"):
                st.session_state['api_port'] = api_port
                st.session_state['proxy_enabled'] = proxy_enabled
                if proxy_enabled:
                    st.session_state['proxy_host'] = proxy_host
                    st.session_state['proxy_port'] = proxy_port
                st.success("端口设置已保存！页面将重新加载以应用新设置。")
                time.sleep(1)
                st.rerun()

    # 刷新Prompt列表
    if not st.session_state['prompt_files']:
        refresh_prompt_list()

    # 功能标签页
    tab_login, tab_manage, tab_hotspot, tab_iterate, tab_refine, tab_expand, tab_generate = st.tabs(
        ["🔑 授权登录", "🗂️ Prompt 管理", "🔥 热点发现 & 生成", "🔁 单视频迭代", "✍️ 交互式优化", "💡 创意扩展", "🎬 视频生成"])

    # 授权登录标签页
    with tab_login:
        st.header("Bilibili 授权登录")
        if st.session_state.get('cookie_str'):
            st.success("🎉 您已登录成功！")
        else:
            st.info("为了使用B站相关功能，请先授权登录。")
            if st.button("1. 获取B站登录二维码"):
                try:
                    with st.spinner("请求二维码..."):
                        response = requests.get(f"{API_BASE_URL}/api/auth/get-qr-code", proxies=get_proxy_settings())
                        response.raise_for_status()
                        data = response.json()
                        st.session_state['qrcode_key'] = data.get("qrcode_key")
                        login_url = data.get("url")
                    qr = qrcode.QRCode(box_size=10, border=4)
                    qr.add_data(login_url)
                    img = qr.make_image(fill_color="black", back_color="white")
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    st.image(buf.getvalue(), caption="请在 2 分钟内使用手机B站APP扫描", width=250)
                    st.session_state['login_active'] = True
                except Exception as e:
                    st.error(f"连接后端服务失败: {e}")
            if st.session_state.get('login_active', False):
                status_placeholder = st.empty()
                status_placeholder.info("⏳ 等待扫码...")
                for i in range(60):
                    try:
                        poll_resp = requests.get(f"{API_BASE_URL}/api/auth/poll-qr-code", params={"qrcode_key": st.session_state['qrcode_key']}, proxies=get_proxy_settings())
                        poll_data = poll_resp.json()
                        code = poll_data.get("code")
                        if code == 86090: status_placeholder.info("👍 已扫码...")
                        elif code == 0:
                            st.session_state['cookie_str'] = poll_data.get("cookie_str")
                            st.session_state['login_active'] = False
                            status_placeholder.success("✅ 登录成功！页面即将刷新...")
                            time.sleep(2)
                            st.rerun()
                            break
                        elif code == 86038:
                            status_placeholder.error("❌ 二维码已过期。")
                            st.session_state['login_active'] = False
                            break
                        time.sleep(2)
                    except:
                        st.session_state['login_active'] = False
                        break

    # Prompt管理标签页
    with tab_manage:
        st.header("🗂️ Prompt 管理")
        st.markdown("在这里您可以查看、搜索和删除所有已生成的Prompt。")
        if st.button("🔄 刷新Prompt列表", key="refresh_btn_manage"):
            refresh_prompt_list()
            st.rerun()
        if not st.session_state.get('prompt_files', []):
            st.info("当前没有可管理的Prompt。")
        else:
            search_term = st.text_input("搜索Prompt文件名", placeholder="输入关键词过滤...", key="manage_search")
            filtered_prompts = [p for p in st.session_state['prompt_files'] if search_term.lower() in p.lower()]
            if not filtered_prompts:
                st.warning("未找到匹配的Prompt。")
            else:
                prompts_df = pd.DataFrame({"path": filtered_prompts})
                prompts_df["filename"] = prompts_df["path"].apply(os.path.basename)
                prompts_df["delete"] = False
                st.info("勾选您想删除的Prompt，然后点击下方的删除按钮。")
                edited_df = st.data_editor(
                    prompts_df[["delete", "filename"]],
                    column_config={"delete": st.column_config.CheckboxColumn("删除?", default=False),"filename": st.column_config.TextColumn("Prompt 文件名"),},
                    use_container_width=True,
                    hide_index=True,
                    key="manage_data_editor"
                )
                prompts_to_delete = edited_df[edited_df["delete"]]
                if not prompts_to_delete.empty:
                    if st.button(f"🗑️ 确认删除选中的 {len(prompts_to_delete)} 个Prompt", type="primary", key="confirm_delete_btn"):
                        deleted_count = 0
                        error_count = 0
                        progress_bar = st.progress(0, text="开始删除...")
                        merged_df = prompts_df.merge(prompts_to_delete, on="filename", how="inner")
                        for i, row in enumerate(merged_df.itertuples()):
                            full_path = row.path
                            filename = row.filename
                            progress_text = f"正在删除 ({i+1}/{len(merged_df)}): {filename}..."
                            progress_bar.progress((i + 1) / len(merged_df), text=progress_text)
                            try:
                                payload = {"prompt_path": full_path}
                                response = requests.delete(f"{API_BASE_URL}/api/prompt/delete", json=payload, proxies=get_proxy_settings())
                                response.raise_for_status()
                                deleted_count += 1
                            except Exception as e:
                                st.error(f"删除 '{filename}' 失败: {e}")
                                error_count += 1
                        progress_bar.empty()
                        st.success(f"操作完成！成功删除 {deleted_count} 个Prompt。")
                        if error_count > 0:
                            st.error(f"{error_count} 个Prompt删除失败。")
                        time.sleep(1)
                        refresh_prompt_list()
                        st.rerun()

    # 热点发现标签页
    with tab_hotspot:
        st.header("🔥 热点发现 & 生成")
        st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_hotspot")
        if not st.session_state.get('cookie_str'):
            st.warning("请先在'授权登录'标签页完成登录。")
        else:
            with st.expander("⚙️ 调整排序算法权重"):
                weights = {}
                c1, c2, c3 = st.columns(3)
                with c1:
                    weights['likes'] = st.slider("👍 点赞", 0.0, 2.0, 1.0, 0.05, key="w_likes")
                    weights['comments'] = st.slider("💬 评论", 0.0, 2.0, 0.8, 0.05, key="w_comments")
                with c2:
                    weights['danmaku'] = st.slider("🎞️ 弹幕", 0.0, 2.0, 0.5, 0.05, key="w_danmaku")
                    weights['gravity'] = st.slider("⏳ 时间衰减因子", 1.0, 2.5, 1.8, 0.05, key="w_gravity")
                with c3:
                    weights['duration_weight'] = st.slider("⏱️ 时长惩罚 (值越高越偏爱短视频)", 0.0, 1.0, 0.25, 0.05, key="w_duration")
                weights['views'] = 0.1
            c1, c2 = st.columns([2, 1])
            with c1:
                keywords_input = st.text_input("搜索关键词 (用逗号分隔)", placeholder="例如: 科技, AI, 游戏...", key="hotspot_keywords")
                if st.button("🔍 搜索热点视频"):
                    with st.spinner("正在搜索B站热点视频..."):
                        response = requests.post(f"{API_BASE_URL}/api/hotspot/search", json={"keywords": [k.strip() for k in keywords_input.split(",")], "weights": weights}, proxies=get_proxy_settings())
                        if response.status_code == 200: st.session_state['hotspot_results'] = response.json()
                        else: st.error(f"搜索失败: {response.text}")
            with c2:
                manual_url = st.text_input("或直接输入B站视频URL", key="manual_url_hotspot")
                if st.button("🎯 直接分析此链接"):
                    with st.spinner("正在处理手动链接..."):
                        try:
                            response = requests.post(f"{API_BASE_URL}/api/hotspot/generate-from-link", json={"video_url": manual_url}, proxies=get_proxy_settings())
                            response.raise_for_status()
                            result_data = response.json()
                            st.success("分析完成！")
                            for res in result_data.get("results", []):
                                st.subheader(f"生成结果: `{res.get('saved_path')}`")
                                st.info(f"🤖 **Gemini 视频摘要**: {res.get('video_summary')}")
                                display_prompt(res.get("prompt_content"))
                        except Exception as e:
                            st.error(f"处理链接失败: {e}")
            if st.session_state.get('hotspot_results'):
                st.subheader("搜索结果")
                df = pd.DataFrame(st.session_state['hotspot_results'])
                df['pubdate_str'] = pd.to_datetime(df['pubdate'], unit='s', errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
                df['duration_str'] = df['duration'].apply(format_duration)
                df['likes'] = df['stats'].apply(lambda x: x.get('likes', 0))
                df['comments'] = df['stats'].apply(lambda x: x.get('comments', 0))
                display_cols = {'title': '🎬 标题', 'score': '🔥 热度分', 'likes': '👍 点赞', 'comments': '💬 评论', 'duration_str': '⏱️ 时长', 'pubdate_str': '📅 发布时间', 'url': '🔗 链接'}
                df_display = df[list(display_cols.keys())].rename(columns=display_cols)
                df_display['select'] = False
                column_config = {"🔗 链接": st.column_config.LinkColumn("视频链接", display_text="跳转")}
                edited_df = st.data_editor(df_display, hide_index=True, column_order=('select', '🎬 标题', '🔥 热度分', '⏱️ 时长', '👍 点赞', '💬 评论', '📅 发布时间', '🔗 链接'), column_config=column_config, height=350, use_container_width=True)
                selected_rows = edited_df[edited_df.select]
                if not selected_rows.empty:
                    st.write("已选择的热点:")
                    st.dataframe(selected_rows[['🎬 标题', '🔥 热度分']], hide_index=True, use_container_width=True)
                    if st.button("🧠 对所选项进行Gemini分析"):
                        with st.spinner("正在下载视频并进行Gemini分析..."):
                            selected_urls = selected_rows['🔗 链接'].tolist()
                            hotspots_to_process = [h for h in st.session_state['hotspot_results'] if h['url'] in selected_urls]
                            for hotspot in hotspots_to_process:
                                try:
                                    res = requests.post(f"{API_BASE_URL}/api/hotspot/generate-from-link", json={"video_url": hotspot['url']}, proxies=get_proxy_settings()).json()
                                    for r in res.get("results", []):
                                        st.subheader(f"生成结果: `{r.get('saved_path')}`")
                                        st.info(f"🤖 **Gemini 视频摘要**: {r.get('video_summary')}")
                                        display_prompt(r.get("prompt_content"))
                                except Exception as e:
                                    st.error(f"分析 {hotspot['title']} 失败: {e}")

    # 其他标签页（简化版）
    # 获取可用的Prompt选项
    prompt_options = st.session_state.get('prompt_files', [])
    
    with tab_iterate:
        st.header("🔁 单视频迭代")
        st.markdown("基于现有Prompt和视频URL进行迭代优化")
        
        col1, col2 = st.columns(2)
        with col1:
            base_prompt = st.selectbox("选择基础Prompt", prompt_options, key="iterate_base")
            video_url = st.text_input("输入视频URL", placeholder="https://www.bilibili.com/video/BV...", key="iterate_url")
        
        with col2:
            max_comments = st.number_input("最大评论数", min_value=50, max_value=500, value=200, key="iterate_comments")
            top_deltas = st.number_input("采纳建议数", min_value=1, max_value=10, value=3, key="iterate_deltas")
        
        if st.button("🚀 开始迭代", key="iterate_btn"):
            if base_prompt and video_url:
                try:
                    with st.spinner("正在迭代中..."):
                        response = requests.post(f"{API_BASE_URL}/api/iterate/from-video", 
                                              json={"base_prompt_path": base_prompt, "video_url": video_url},
                                              proxies=get_proxy_settings())
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"迭代完成！新版本: {result.get('new_prompt_path', 'N/A')}")
                            if result.get('report_path'):
                                st.info(f"详细报告: {result.get('report_path')}")
                        else:
                            st.error(f"迭代失败: {response.text}")
                except Exception as e:
                    st.error(f"迭代出错: {e}")
            else:
                st.warning("请填写完整信息")

    with tab_refine:
        st.header("✍️ 交互式优化")
        st.markdown("基于用户反馈优化现有Prompt")
        
        col1, col2 = st.columns(2)
        with col1:
            refine_prompt = st.selectbox("选择要优化的Prompt", prompt_options, key="refine_prompt")
            feedback = st.text_area("输入优化建议", placeholder="例如：让它更温馨一些，增加一些暖色调...", key="refine_feedback")
        
        with col2:
            model_choice = st.selectbox("选择优化模型", ["deepseek-chat", "deepseek-reasoner"], key="refine_model")
        
        if st.button("🔧 开始优化", key="refine_btn"):
            if refine_prompt and feedback:
                try:
                    with st.spinner("正在优化中..."):
                        response = requests.post(f"{API_BASE_URL}/api/prompt/refine", 
                                              json={"prompt_path": refine_prompt, "feedback": feedback},
                                              proxies=get_proxy_settings())
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"优化完成！新版本: {result.get('new_prompt_path', 'N/A')}")
                        else:
                            st.error(f"优化失败: {response.text}")
                except Exception as e:
                    st.error(f"优化出错: {e}")
            else:
                st.warning("请填写完整信息")

    with tab_expand:
        st.header("💡 创意扩展")
        st.markdown("基于现有Prompt生成创意变体")
        
        col1, col2 = st.columns(2)
        with col1:
            expand_prompt = st.selectbox("选择基础Prompt", prompt_options, key="expand_prompt")
            num_expansions = st.number_input("扩展数量", min_value=1, max_value=10, value=3, key="expand_num")
        
        with col2:
            user_hint = st.text_input("创意提示（可选）", placeholder="例如：更梦幻的风格", key="expand_hint")
        
        if st.button("✨ 开始扩展", key="expand_btn"):
            if expand_prompt:
                try:
                    with st.spinner("正在扩展中..."):
                        payload = {"prompt_path": expand_prompt, "num_expansions": num_expansions}
                        if user_hint:
                            payload["user_hint"] = user_hint
                        
                        response = requests.post(f"{API_BASE_URL}/api/prompt/expand", 
                                              json=payload,
                                              proxies=get_proxy_settings())
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"扩展完成！生成了 {len(result.get('generated_prompts', []))} 个变体")
                            for i, prompt in enumerate(result.get('generated_prompts', [])):
                                st.info(f"变体 {i+1}: {prompt.get('saved_path', 'N/A')}")
                        else:
                            st.error(f"扩展失败: {response.text}")
                except Exception as e:
                    st.error(f"扩展出错: {e}")
            else:
                st.warning("请选择基础Prompt")

    with tab_generate:
        st.header("🎬 视频生成")
        st.markdown("使用Flow或Veo生成视频")
        
        col1, col2 = st.columns(2)
        with col1:
            generation_method = st.selectbox("生成方式", ["Flow (浏览器自动化)", "Veo 3 API"], key="generate_method")
            
            # 根据生成方式选择prompt选择器
            if generation_method == "Flow (浏览器自动化)":
                generate_prompt = st.multiselect("选择Prompt（可多选）", prompt_options, key="generate_prompt_multiselect")
            else:
                generate_prompt = st.selectbox("选择Prompt", prompt_options, key="generate_prompt_single")
        
        with col2:
            if generation_method == "Flow (浏览器自动化)":
                flow_url = st.text_input("Flow页面URL（可选）", placeholder="https://labs.google.com/flow/...", key="flow_url")
                debug_port = st.number_input("调试端口", min_value=9222, max_value=9230, value=9222, key="debug_port")
            else:
                st.info("Veo 3 API生成")
        
        if st.button("🎬 开始生成", key="generate_btn"):
            # 根据生成方式获取选中的prompt
            if generation_method == "Flow (浏览器自动化)":
                selected_prompts = st.session_state.get("generate_prompt_multiselect", [])
            else:
                selected_prompts = [st.session_state.get("generate_prompt_single")]
            
            if selected_prompts and any(selected_prompts):
                try:
                    with st.spinner("正在生成中..."):
                        if generation_method == "Flow (浏览器自动化)":
                            payload = {"prompt_paths": selected_prompts}
                            if flow_url:
                                payload["flow_url"] = flow_url
                            payload["debugging_port"] = debug_port
                            
                            response = requests.post(f"{API_BASE_URL}/api/generate/video", 
                                                  json=payload,
                                                  proxies=get_proxy_settings())
                        else:
                            # Veo API 仍然只支持单个prompt
                            response = requests.post(f"{API_BASE_URL}/api/generate/veo", 
                                                  json={"prompt_path": selected_prompts[0]},
                                                  proxies=get_proxy_settings())
                        
                        if response.status_code == 200:
                            result = response.json()
                            if generation_method == "Flow (浏览器自动化)":
                                # 处理多个prompt的结果
                                if "results" in result:
                                    st.success(f"批量生成任务已提交！总计: {result.get('total', 0)} 个")
                                    st.info(f"成功: {result.get('successful', 0)} 个, 失败: {result.get('failed', 0)} 个")
                                    
                                    # 显示详细结果
                                    for i, res in enumerate(result.get('results', [])):
                                        if res.get('success'):
                                            st.success(f"✅ {res.get('prompt_path', 'N/A')}: {res.get('message', '成功')}")
                                        else:
                                            st.error(f"❌ {res.get('prompt_path', 'N/A')}: {res.get('error', '失败')}")
                                else:
                                    st.success(f"生成任务已提交！{result.get('message', '')}")
                            else:
                                st.success(f"生成任务已提交！{result.get('message', '')}")
                            
                            if result.get('task_id'):
                                st.info(f"任务ID: {result.get('task_id')}")
                        else:
                            st.error(f"生成失败: {response.text}")
                except Exception as e:
                    st.error(f"生成出错: {e}")
            else:
                st.warning("请选择Prompt")

# --- 右侧对话区域 ---
with right_col:
    st.header("🧠 AI 助手")
    
    # 大脑设置
    with st.expander("⚙️ 大脑设置", expanded=True):
        st.selectbox("选择大模型供应商", ["Gemini","DeepSeek"], key='llm_provider')
        if st.session_state.llm_provider == "Gemini":
            st.selectbox("选择具体模型 (Gemini)", ["gemini-2.5-flash","gemini-2.5-pro"], key='gemini_model')
            model_name = st.session_state.gemini_model
        else:
            st.selectbox("选择具体模型 (DeepSeek)", ["deepseek-chat","deepseek-reasoner"], key='deepseek_model')
            model_name = st.session_state.deepseek_model
        st.info(f"当前大脑: **{st.session_state.llm_provider} ({model_name})**")
        
        # 流式输出设置
        st.markdown("##### 流式输出设置")
        show_detailed = st.checkbox("显示详细思考过程", value=st.session_state.show_detailed_thinking, 
                                   help="启用后将实时显示AI的思考过程和工具调用")
        st.session_state.show_detailed_thinking = show_detailed

    # 对话历史
    st.markdown("##### 💬 对话历史")
    
    # 创建可滚动的对话容器
    chat_container = st.container()
    
    with chat_container:
        # 显示所有对话消息
        for i, message in enumerate(st.session_state.agent_messages):
            with st.chat_message(message["role"]):
                st.markdown(message.get("content",""))
        
        # 添加自动滚动到底部的JavaScript
        if st.session_state.agent_messages:
            st.markdown("""
            <script>
            // 自动滚动到对话底部
            window.scrollTo(0, document.body.scrollHeight);
            </script>
            """, unsafe_allow_html=True)

    # 输入框
    if prompt := st.chat_input("例如: 帮我把这两个prompt都用浏览器生成视频"):
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        
        # 创建对话消息
        with st.chat_message("assistant"):
            # 创建多个占位符用于不同类型的输出
            message_placeholder = st.empty()
            thinking_placeholder = st.empty()
            tool_placeholder = st.empty()
            full_response = ""
            
            # 准备请求数据
            cleaned_msgs = [{"role": m.get("role","user"), "content": m.get("content","")} for m in st.session_state.agent_messages]
            payload = {"messages": cleaned_msgs, "llm_provider": st.session_state.llm_provider, "model_name": model_name}
            
            try:
                with requests.post(f"{API_BASE_URL}/api/agent/chat_stream", json=payload, stream=True, timeout=None, proxies=get_proxy_settings()) as r:
                    r.raise_for_status()
                    
                    # 根据设置决定是否显示详细思考过程
                    if st.session_state.show_detailed_thinking:
                        # 显示初始思考状态
                        thinking_placeholder.info("🤔 AI正在思考中...")
                    
                    for line in r.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                try:
                                    event_data = json.loads(decoded_line[5:])
                                    event_type = event_data.get("type")
                                    
                                    if event_type == "thinking_start":
                                        # 显示开始思考
                                        if st.session_state.show_detailed_thinking:
                                            thinking_placeholder.info("🤔 AI正在分析您的请求...")
                                        
                                    elif event_type == "thought":
                                        # 清除思考状态，显示实际思考内容
                                        if st.session_state.show_detailed_thinking:
                                            thinking_placeholder.empty()
                                        content = event_data.get("content", "")
                                        full_response += content
                                        message_placeholder.markdown(full_response + "▌")
                                        
                                    elif event_type == "tool_start":
                                        tool_name = event_data.get('tool_name')
                                        tool_args = event_data.get('tool_args', {})
                                        
                                        if st.session_state.show_detailed_thinking:
                                            # 显示工具调用信息
                                            tool_info = f"""
                                            **🛠️ 正在调用工具:** `{tool_name}`
                                            
                                            **参数:** `{json.dumps(tool_args, indent=2, ensure_ascii=False)}`
                                            """
                                            tool_placeholder.info(tool_info)
                                        
                                        # 在思考内容中添加工具调用记录
                                        full_response += f"\n\n**🛠️ 调用工具:** `{tool_name}`\n\n"
                                        message_placeholder.markdown(full_response + "▌")
                                        
                                    elif event_type == "tool_end":
                                        tool_name = event_data.get('tool_name')
                                        tool_output = event_data.get('output', "")
                                        
                                        if st.session_state.show_detailed_thinking:
                                            # 清除工具调用信息
                                            tool_placeholder.empty()
                                        
                                        # 格式化工具输出 - 显示完整内容
                                        if isinstance(tool_output, dict):
                                            # 如果是字典，显示关键信息
                                            if 'success' in tool_output:
                                                status_icon = "✅" if tool_output['success'] else "❌"
                                                tool_output_display = f"{status_icon} {tool_output.get('message', '')}"
                                                if 'task_id' in tool_output:
                                                    tool_output_display += f"\n任务ID: {tool_output['task_id']}"
                                                if 'prompt_path' in tool_output:
                                                    tool_output_display += f"\n文件路径: {tool_output['prompt_path']}"
                                            else:
                                                tool_output_display = json.dumps(tool_output, indent=2, ensure_ascii=False)
                                        elif isinstance(tool_output, str):
                                            # 如果是字符串，显示完整内容（不截断）
                                            tool_output_display = tool_output
                                        else:
                                            tool_output_display = str(tool_output)
                                        
                                        # 在思考内容中添加工具返回记录
                                        full_response += f"**✅ 工具返回:**\n```\n{tool_output_display}\n```\n\n"
                                        message_placeholder.markdown(full_response + "▌")
                                        
                                    elif event_type == "thinking_end":
                                        # 显示思考完成
                                        if st.session_state.show_detailed_thinking:
                                            thinking_placeholder.success("✅ 分析完成！")
                                        
                                    elif event_type == "error":
                                        error_content = event_data.get('content', "未知错误")
                                        full_response += f"\n\n**❌ 错误**: {error_content}"
                                        if st.session_state.show_detailed_thinking:
                                            thinking_placeholder.error(f"❌ 发生错误: {error_content}")
                                        break
                                        
                                    elif event_type == "done":
                                        if st.session_state.show_detailed_thinking:
                                            thinking_placeholder.success("✅ 任务完成！")
                                        break
                                        
                                except json.JSONDecodeError:
                                    pass
                    
                    # 最终显示完整响应
                    message_placeholder.markdown(full_response)
                    st.session_state.agent_messages.append({"role": "assistant", "content": full_response})
                    
                    # 自动滚动到对话底部
                    st.experimental_rerun()
                    
            except requests.exceptions.RequestException as e:
                if st.session_state.show_detailed_thinking:
                    thinking_placeholder.error(f"❌ 连接后端流式接口失败: {e}")
                st.error(f"连接后端流式接口失败: {e}")

# --- 页面底部 ---
st.markdown("---")
st.markdown("### 📊 系统状态")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("API状态", "🟢 正常" if requests.get(f"{API_BASE_URL}/api/health", proxies=get_proxy_settings()).status_code == 200 else "🔴 异常")
with col2:
    st.metric("Prompt数量", len(st.session_state.get('prompt_files', [])))
with col3:
    st.metric("对话消息", len(st.session_state.get('agent_messages', [])))
