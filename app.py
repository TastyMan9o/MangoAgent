# app.py (Final, Streaming & Parallel Version)
# -*- coding: utf-8 -*-
import streamlit as st
import requests, io, time, json, pandas as pd
from datetime import datetime
import qrcode
import os

# --- App Setup ---
st.set_page_config(page_title="VideoAgent 控制台", page_icon="🤖", layout="wide")
API_BASE_URL = "http://127.0.0.1:8001"

# --- Reusable Functions ---
def display_prompt(prompt_content: dict):
    st.code(json.dumps(prompt_content, indent=2, ensure_ascii=False), language='json')

def refresh_prompt_list():
    try:
        resp = requests.get(f"{API_BASE_URL}/api/prompt/list", timeout=30, proxies={"http": None, "https": None})
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
st.session_state.setdefault("agent_messages", [{"role":"assistant","content":"你好！我是VideoAgent大脑，请问有什么可以帮您？"}])
st.session_state.setdefault('llm_provider', "Gemini")
st.session_state.setdefault('gemini_model', "gemini-2.5-flash")
st.session_state.setdefault('deepseek_model', "deepseek-chat")

# --- Sidebar Agent Brain UI ---
with st.sidebar:
    st.header("🧠 终极大脑")
    st.markdown("##### 大脑设置")
    st.selectbox("选择大模型供应商", ["Gemini","DeepSeek"], key='llm_provider')
    if st.session_state.llm_provider == "Gemini":
        st.selectbox("选择具体模型 (Gemini)", ["gemini-2.5-flash","gemini-2.5-pro"], key='gemini_model')
        model_name = st.session_state.gemini_model
    else:
        st.selectbox("选择具体模型 (DeepSeek)", ["deepseek-chat","deepseek-reasoner"], key='deepseek_model')
        model_name = st.session_state.deepseek_model
    st.info(f"当前大脑: **{st.session_state.llm_provider} ({model_name})**")
    st.markdown("---")
    for message in st.session_state.agent_messages:
        with st.chat_message(message["role"]):
            st.markdown(message.get("content",""))

    if prompt := st.chat_input("例如: 帮我把 “颜料果冻动物_v1.json” 和 “猫咪抢鸡块_v1.json” 这两个prompt都用浏览器生成视频"):
        st.session_state.agent_messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            cleaned_msgs = [{"role": m.get("role","user"), "content": m.get("content","")} for m in st.session_state.agent_messages]
            payload = {"messages": cleaned_msgs, "llm_provider": st.session_state.llm_provider, "model_name": model_name}
            try:
                with requests.post(f"{API_BASE_URL}/api/agent/chat_stream", json=payload, stream=True, timeout=None, proxies={"http": None, "https": None}) as r:
                    r.raise_for_status()
                    for line in r.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                try:
                                    event_data = json.loads(decoded_line[5:])
                                    event_type = event_data.get("type")
                                    if event_type == "thought":
                                        full_response += event_data.get("content", "")
                                        message_placeholder.markdown(full_response + "▌")
                                    elif event_type == "tool_start":
                                        tool_name = event_data.get('tool_name')
                                        tool_args = json.dumps(event_data.get('tool_args', {}), ensure_ascii=False)
                                        full_response += f"\\n\\n**✨ 调用工具:** `{tool_name}`\\n\\n**参数:** `{tool_args}`\\n\\n"
                                        message_placeholder.markdown(full_response + "▌")
                                    elif event_type == "tool_end":
                                        tool_output_str = str(event_data.get('output', ""))
                                        full_response += f"**✅ 工具返回:** `{tool_output_str}`\\n\\n"
                                        message_placeholder.markdown(full_response + "▌")
                                    elif event_type == "error":
                                        full_response += f"\\n\\n**❌ 错误**: {event_data.get('content')}"
                                        break
                                except json.JSONDecodeError:
                                    pass
                message_placeholder.markdown(full_response)
                st.session_state.agent_messages.append({"role": "assistant", "content": full_response})
            except requests.exceptions.RequestException as e:
                st.error(f"连接后端流式接口失败: {e}")

# --- Main Page Content ---
st.title("🤖 VideoAgent 控制台")
st.caption("您的自动化视频灵感助手")

with st.expander("🔑 API 密钥管理 (API Key Management)"):
    try:
        response = requests.get(f"{API_BASE_URL}/api/keys/get", proxies={"http": None, "https": None})
        if response.status_code == 200:
            current_keys = response.json()
        else:
            current_keys = {}
            st.error(f"加载API密钥状态失败: {response.status_code}")
    except Exception as e:
        st.error(f"无法连接后端加载API密钥状态: {e}")
        current_keys = {}
    with st.form("api_key_form"):
        st.info("在此处输入您的API密钥，将被安全地存储在项目的 .env 文件中。")
        deepseek_key = st.text_input("DeepSeek API Key", value=current_keys.get("deepseek_api_key", ""), type="password")
        gemini_keys_str = current_keys.get("gemini_api_keys", "")
        gemini_keys_display = "\\n".join([k.strip() for k in gemini_keys_str.split(',') if k.strip()])
        gemini_keys_multiline = st.text_area("Gemini API Keys (每行一个，用于轮询)", value=gemini_keys_display, height=150, help="当一个Key达到速率限制时会自动切换到下一个。")
        veo_key = st.text_input("Veo API Key", value=current_keys.get("veo_api_key", ""), type="password")
        if st.form_submit_button("保存所有密钥"):
            with st.spinner("正在保存..."):
                payload = {"deepseek_api_key": deepseek_key, "veo_api_key": veo_key, "gemini_api_keys": gemini_keys_multiline}
                try:
                    response = requests.post(f"{API_BASE_URL}/api/keys/update", json=payload, proxies={"http": None, "https": None})
                    response.raise_for_status()
                    st.success("保存成功！")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败: {e}")

if not st.session_state['prompt_files']:
    refresh_prompt_list()

tab_login, tab_manage, tab_hotspot, tab_iterate, tab_refine, tab_expand, tab_generate = st.tabs(
    ["🔑 授权登录", "🗂️ Prompt 管理", "🔥 热点发现 & 生成", "🔁 单视频迭代", "✍️ 交互式优化", "💡 创意扩展", "🎬 视频生成"])

with tab_login:
    st.header("Bilibili 授权登录")
    if st.session_state.get('cookie_str'):
        st.success("🎉 您已登录成功！")
    else:
        st.info("为了使用B站相关功能，请先授权登录。")
        if st.button("1. 获取B站登录二维码"):
            try:
                with st.spinner("请求二维码..."):
                    response = requests.get(f"{API_BASE_URL}/api/auth/get-qr-code", proxies={"http": None, "https": None})
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
                    poll_resp = requests.get(f"{API_BASE_URL}/api/auth/poll-qr-code", params={"qrcode_key": st.session_state['qrcode_key']}, proxies={"http": None, "https": None})
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
                            response = requests.delete(f"{API_BASE_URL}/api/prompt/delete", json=payload, proxies={"http": None, "https": None})
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

with tab_hotspot:
    st.header("🔥 热点发现 & 生成")
    st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_hotspot")
    if not st.session_state.get('cookie_str'):
        st.warning("请先在“授权登录”标签页完成登录。")
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
                    response = requests.post(f"{API_BASE_URL}/api/hotspot/search", json={"keywords": [k.strip() for k in keywords_input.split(",")], "weights": weights}, proxies={"http": None, "https": None})
                    if response.status_code == 200: st.session_state['hotspot_results'] = response.json()
                    else: st.error(f"搜索失败: {response.text}")
        with c2:
            manual_url = st.text_input("或直接输入B站视频URL", key="manual_url_hotspot")
            if st.button("🎯 直接分析此链接"):
                with st.spinner("正在处理手动链接..."):
                    try:
                        response = requests.post(f"{API_BASE_URL}/api/hotspot/generate-from-link", json={"video_url": manual_url}, proxies={"http": None, "https": None})
                        response.raise_for_status()
                        result_data = response.json()
                        st.success("分析完成！")
                        for res in result_data.get("results", []):
                            st.subheader(f"生成结果: `{res.get('saved_path')}`"); st.info(f"🤖 **Gemini 视频摘要**: {res.get('video_summary')}"); display_prompt(res.get("prompt_content"))
                    except Exception as e:
                        st.error(f"处理链接失败: {e}")
        if st.session_state.get('hotspot_results'):
            st.subheader("搜索结果")
            df = pd.DataFrame(st.session_state['hotspot_results']); df['pubdate_str'] = pd.to_datetime(df['pubdate'], unit='s', errors='coerce').dt.strftime('%Y-%m-%d %H:%M'); df['duration_str'] = df['duration'].apply(format_duration); df['likes'] = df['stats'].apply(lambda x: x.get('likes', 0)); df['comments'] = df['stats'].apply(lambda x: x.get('comments', 0)); display_cols = {'title': '🎬 标题', 'score': '🔥 热度分', 'likes': '👍 点赞', 'comments': '💬 评论', 'duration_str': '⏱️ 时长', 'pubdate_str': '📅 发布时间', 'url': '🔗 链接'}; df_display = df[list(display_cols.keys())].rename(columns=display_cols); df_display['select'] = False; column_config = {"🔗 链接": st.column_config.LinkColumn("视频链接", display_text="跳转")}; edited_df = st.data_editor(df_display, hide_index=True, column_order=('select', '🎬 标题', '🔥 热度分', '⏱️ 时长', '👍 点赞', '💬 评论', '📅 发布时间', '🔗 链接'), column_config=column_config, height=350, use_container_width=True)
            selected_rows = edited_df[edited_df.select]
            if not selected_rows.empty:
                st.write("已选择的热点:"); st.dataframe(selected_rows[['🎬 标题', '🔥 热度分']], hide_index=True, use_container_width=True)
                if st.button("🧠 对所选项进行Gemini分析"):
                    with st.spinner("正在下载视频并进行Gemini分析..."):
                        selected_urls = selected_rows['🔗 链接'].tolist()
                        hotspots_to_process = [h for h in st.session_state['hotspot_results'] if h['url'] in selected_urls]
                        payload = {"hotspots": hotspots_to_process, "series": "Gemini Hotspot Series"}
                        # This should be a POST to generate-from-link in a loop, or a new batch endpoint
                        # For now, let's process one by one
                        for hotspot in hotspots_to_process:
                            try:
                                res = requests.post(f"{API_BASE_URL}/api/hotspot/generate-from-link", json={"video_url": hotspot['url']}, proxies={"http": None, "https": None}).json()
                                for r in res.get("results", []):
                                    st.subheader(f"生成结果: `{r.get('saved_path')}`"); st.info(f"🤖 **Gemini 视频摘要**: {r.get('video_summary')}"); display_prompt(r.get("prompt_content"))
                            except Exception as e:
                                st.error(f"分析 {hotspot['title']} 失败: {e}")

with tab_iterate:
    st.header("🔁 单视频迭代")
    st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_iterate")
    if not st.session_state.get('cookie_str'):
        st.warning("请先在“授权登录”标签页完成登录。")
    else:
        st.markdown("##### 1. 选择基础Prompt")
        selected_prompt = st.selectbox(
            "选择一个Prompt文件作为迭代基础",
            options=st.session_state.get('prompt_files', []),
            key="iter_select",
            label_visibility="collapsed"
        )
        with st.form("iterate_form"):
            st.markdown("##### 2. 提供用于分析的视频链接")
            video_url = st.text_input("输入目标B站视频URL", placeholder="https://www.bilibili.com/video/...", label_visibility="collapsed")
            st.markdown("---")
            iterate_button = st.form_submit_button("🔁 开始迭代")
        if iterate_button:
            if selected_prompt and video_url and "..." not in video_url:
                with st.spinner("正在分析评论并生成新版本..."):
                    try:
                        payload = {"base_prompt_path": selected_prompt, "video_url": video_url}
                        response = requests.post(f"{API_BASE_URL}/api/iterate/from-video", json=payload, proxies={"http": None, "https": None})
                        response.raise_for_status()
                        st.session_state['iteration_result'] = response.json()
                        st.rerun()
                    except Exception as e:
                        st.error(f"迭代失败: {e}")
            else:
                st.warning("请确保已选择一个Prompt并输入了有效的视频URL。")
        if st.session_state.get('iteration_result'):
            data = st.session_state['iteration_result']
            st.success("迭代完成！")
            st.subheader(f"新Prompt已生成: `{data.get('new_prompt_path')}`")
            display_prompt(data.get('new_content'))
            with st.expander("🔍 查看具体变更"):
                st.text("\\n".join(data.get("diffs", ["无变更"])))
            st.session_state['iteration_result'] = None

with tab_refine:
    st.header("✍️ 交互式优化")
    st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_refine")
    selected_file = st.selectbox("1. 选择一个要优化的Prompt文件", options=st.session_state.get('prompt_files', []), key="refine_select")
    if selected_file:
        try:
            with open(selected_file, 'r', encoding='utf-8') as f:
                prompt_content = json.load(f)
            display_prompt(prompt_content)
            with st.form("refine_form"):
                feedback = st.text_area("2. 输入你的优化指令", height=100)
                refine_button = st.form_submit_button("🤖 开始优化")
            if refine_button and feedback:
                with st.spinner("正在调用模型进行优化..."):
                    try:
                        payload = {"prompt_path": selected_file, "feedback": feedback}
                        response = requests.post(f"{API_BASE_URL}/api/prompt/refine", json=payload, proxies={"http": None, "https": None})
                        response.raise_for_status()
                        st.session_state['refined_result'] = response.json()
                    except Exception as e:
                        st.error(f"优化失败: {e}")
        except Exception as e:
            st.error(f"读取文件失败: {e}")
    if st.session_state.get('refined_result'):
        res = st.session_state['refined_result']
        st.success("优化完成!"); st.subheader(f"新版本已保存: `{res.get('new_prompt_path')}`"); display_prompt(res.get('new_content'))
        with st.expander("🔍 查看具体变更"): st.text("\\n".join(res.get("diffs", ["无变更"])))

with tab_expand:
    st.header("💡 创意扩展")
    st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_expand")
    if not st.session_state.get('prompt_files'):
        st.warning("请先刷新或生成一个Prompt。")
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            base_expand_prompt = st.selectbox("选择一个基础Prompt进行扩展", options=st.session_state['prompt_files'], key="expand_select")
        with c2:
            num_expansions = st.number_input("扩展数量", min_value=1, max_value=10, value=3)
        use_hint = st.checkbox("自定义扩展方向")
        user_hint = ""
        if use_hint:
            user_hint = st.text_area("输入你的灵感方向", placeholder="例如: 改成赛博朋克风格, 主角换成柯基犬")
        if st.button("🚀 开始扩展"):
            with st.spinner(f"正在生成 {num_expansions} 个创意变体..."):
                try:
                    payload = {"prompt_path": base_expand_prompt, "num_expansions": num_expansions, "user_hint": user_hint if use_hint else None}
                    response = requests.post(f"{API_BASE_URL}/api/prompt/expand", json=payload, proxies={"http": None, "https": None})
                    response.raise_for_status()
                    st.session_state['expansion_results'] = response.json().get("results", [])
                except Exception as e:
                    st.error(f"扩展失败: {e}")
    if st.session_state.get('expansion_results'):
        st.success("扩展完成！")
        for result in st.session_state['expansion_results']:
            with st.expander(f"✨ 新变体: `{result.get('saved_path')}`"):
                display_prompt(result.get("prompt_content"))

with tab_generate:
    st.header("🎬 视频生成")
    st.button("🔄 刷新Prompt列表", on_click=refresh_prompt_list, key="refresh_btn_generate")
    generation_method = st.radio("选择生成方式", ["浏览器自动化 (Flow)", "Veo 3 API"], horizontal=True)
    st.markdown("---")
    if not st.session_state.get('prompt_files'):
        st.warning("请先刷新或生成一个Prompt。")
    else:
        selected_file_gen = st.selectbox("1. 选择一个基础Prompt", options=st.session_state.get('prompt_files', []), key="gen_select")
        prompt_content_obj = {}
        if selected_file_gen:
            try:
                with open(selected_file_gen, 'r', encoding='utf-8') as f:
                    prompt_content_obj = json.load(f)
            except Exception as e:
                st.error(f"读取文件失败: {e}")
        edited_prompt_str = st.text_area("2. (可选) 修改您的Prompt JSON内容", value=json.dumps(prompt_content_obj, indent=2, ensure_ascii=False) if prompt_content_obj else "", height=300, key="gen_prompt_area")
        if generation_method == "浏览器自动化 (Flow)":
            st.info("此方式将自动操作本地浏览器，在Flow网页中提交任务。")
            c1, c2 = st.columns(2)
            with c1:
                debugging_port = st.number_input("Chrome调试端口", value=9222, min_value=1024, max_value=65535)
            with c2:
                flow_url = st.text_input("Flow页面URL (可选)", placeholder="留空则不自动打开新页面")
            if st.button("🚀 在Flow中生成"):
                if not edited_prompt_str:
                    st.error("Prompt内容不能为空！")
                else:
                    with st.spinner("正在连接浏览器并提交任务..."):
                        try:
                            payload = {
                                "prompt_content": edited_prompt_str,
                                "debugging_port": debugging_port,
                                "flow_url": flow_url if flow_url else ""
                            }
                            response = requests.post(f"{API_BASE_URL}/api/generate/video", json=payload,
                                                     proxies={"http": None, "https": None})
                            response.raise_for_status()
                            result = response.json()
                            if result.get("success"):
                                st.success(result.get("message"))
                            else:
                                st.error(result.get("message"))
                        except Exception as e:
                            st.error(f"Flow任务提交失败: {e}")
