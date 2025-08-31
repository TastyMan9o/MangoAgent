# app.py (Streamlit Frontend - 带复制按钮版)
    # -*- coding: utf-8 -*-
    import streamlit as st
    import requests, io, time, json, pandas as pd
    from datetime import datetime
    import qrcode

    st.set_page_config(page_title="VideoAgent 控制台", page_icon="🤖", layout="wide")
    API_BASE_URL = "http://127.0.0.1:8001"

    def display_prompt(prompt_content: dict):
        '''
用于显示Prompt的统一函数，使用带复制按钮的code
block。'''
        st.code(json.dumps(prompt_content, indent=2, ensure_ascii=False), language='json')

    # ... (后续代码不变，仅将 st.json(...) 替换为 display_prompt(...)) ...
    # Full content is included below.

    for key in ['cookie_str', 'hotspot_results', 'prompt_files', 'selected_prompt', 
                'refined_result', 'expansion_results', 'iteration_result']:
        if key not in st.session_state:
            st.session_state[key] = None if key not in ['hotspot_results', 'expansion_results'] else []

    st.title("🤖 VideoAgent 控制台")
    st.caption("您的自动化视频灵感助手")

    @st.cache_data(ttl=600)
    def fetch_hotspots(keywords, weights):
        response = requests.post(f"{API_BASE_URL}/api/hotspot/search", json={"keywords": keywords, "weights": weights})
        response.raise_for_status(); return response.json()

    tab_login, tab_hotspot, tab_iterate, tab_refine, tab_expand = st.tabs(["🔑 授权登录", "🔥 热点发现 & 生成", "🔁 单视频迭代", "✍️ 交互式优化", "💡 创意扩展"])

    with tab_login:
        st.header("Bilibili 授权登录")
        if st.session_state['cookie_str']: st.success("🎉 您已登录成功！")
        else:
            st.info("为了使用B站相关功能，请先授权登录。")
            if st.button("1. 获取B站登录二维码"):
                try:
                    with st.spinner("请求二维码..."):
                        response = requests.get(f"{API_BASE_URL}/api/auth/get-qr-code"); response.raise_for_status()
                        data = response.json(); st.session_state['qrcode_key'] = data.get("qrcode_key"); login_url = data.get("url")
                    qr = qrcode.QRCode(box_size=10, border=4); qr.add_data(login_url); img = qr.make_image()
                    buf = io.BytesIO(); img.save(buf, format='PNG')
                    st.image(buf.getvalue(), caption="请在 2 分钟内使用手机B站APP扫描")
                    st.session_state['login_active'] = True
                except Exception as e: st.error(f"连接后端服务失败: {e}")
            if st.session_state.get('login_active', False):
                status_placeholder = st.empty(); status_placeholder.info("⏳ 等待扫码...")
                for i in range(60):
                    try:
                        poll_resp = requests.get(f"{API_BASE_URL}/api/auth/poll-qr-code", params={"qrcode_key": st.session_state['qrcode_key']})
                        poll_data = poll_resp.json(); code = poll_data.get("code")
                        if code == 86090: status_placeholder.info("👍 已扫码...")
                        elif code == 0:
                            st.session_state['cookie_str'] = poll_data.get("cookie_str"); st.session_state['login_active'] = False
                            status_placeholder.success("✅ 登录成功！"); time.sleep(2); st.rerun(); break
                        elif code == 86038: status_placeholder.error("❌ 二维码已过期。"); st.session_state['login_active'] = False; break
                        time.sleep(2)
                    except Exception as e: status_placeholder.error(f"轮询失败: {e}"); st.session_state['login_active'] = False; break
                else: st.session_state['login_active'] = False

    with tab_hotspot:
        st.header("热点发现 -> Gemini分析 -> 生成 v1 Prompt")
        if not st.session_state['cookie_str']: st.warning("请先在“授权登录”标签页完成登录。")
        else:
            with st.expander("⚙️ 调整排序算法权重"):
                weights = {}
                c1,c2,c3 = st.columns(3)
                with c1: weights['likes'] = st.slider("👍 点赞", 0.0, 2.0, 1.0, 0.05); weights['favorites'] = st.slider("⭐ 收藏", 0.0, 2.0, 1.2, 0.05)
                with c2: weights['shares'] = st.slider("🚀 分享", 0.0, 2.0, 1.5, 0.05); weights['comments'] = st.slider("💬 评论", 0.0, 2.0, 0.8, 0.05)
                with c3: weights['danmaku'] = st.slider("🎞️ 弹幕", 0.0, 2.0, 0.5, 0.05); weights['gravity'] = st.slider("⏳ 时间衰减", 1.0, 2.5, 1.8, 0.05)
                weights['views'] = 0.1
            c1, c2 = st.columns([2,1])
            with c1:
                keywords = st.text_input("搜索关键词 (用逗号分隔)", "猫,ASMR,解压", key="hotspot_keywords")
                if st.button("🔍 搜索热点视频"):
                    with st.spinner("正在搜索B站热点视频..."):
                        st.session_state['hotspot_results'] = fetch_hotspots([k.strip() for k in keywords.split(",")], weights)
            with c2:
                manual_url = st.text_input("或直接输入B站视频URL")
                if st.button("🎯 直接分析此链接"):
                    with st.spinner("正在处理手动链接..."):
                        try:
                            response = requests.post(f"{API_BASE_URL}/api/hotspot/generate-from-link", json={"video_url": manual_url})
                            response.raise_for_status(); result_data = response.json()
                            st.success("分析完成！")
                            for res in result_data.get("results", []):
                                st.subheader(f"生成结果: `{res.get('saved_path')}`"); st.info(f"🤖 **Gemini 视频摘要**: {res.get('video_summary')}")
                                display_prompt(res.get("prompt_content"))
                        except Exception as e: st.error(f"处理链接失败: {e}")
            if st.session_state['hotspot_results']:
                st.subheader("搜索结果")
                df = pd.DataFrame(st.session_state['hotspot_results'])
                stats_df = df['stats'].apply(pd.Series); df = pd.concat([df.drop('stats', axis=1), stats_df], axis=1)
                df['pubdate_str'] = pd.to_datetime(df['pubdate'], unit='s').dt.strftime('%Y-%m-%d %H:%M')
                display_cols = {'title': '🎬 标题','score': '🔥 热度分','likes': '👍 点赞','favorites': '⭐ 收藏','shares': '🚀 分享','comments': '💬 评论','pubdate_str': '📅 发布时间','url': '🔗 链接'}
                df_display = df[list(display_cols.keys())].rename(columns=display_cols); df_display['select'] = False
                column_config={"🔗 链接": st.column_config.LinkColumn("视频链接", display_text="跳转")}
                edited_df = st.data_editor(df_display, hide_index=True, column_order=('select', '🎬 标题', '🔥 热度分', '👍 点赞', '⭐ 收藏', '🚀 分享', '💬 评论', '📅 发布时间', '🔗 链接'), column_config=column_config, height=350, use_container_width=True)
                selected_rows = edited_df[edited_df.select]
                if not selected_rows.empty:
                    st.write("已选择的热点:")
                    st.dataframe(selected_rows[['🎬 标题', '🔥 热度分']], hide_index=True)
                    if st.button("🧠 对所选项进行Gemini分析"):
                        with st.spinner("正在下载视频并进行Gemini分析..."):
                            try:
                                selected_urls = selected_rows['🔗 链接'].tolist()
                                hotspots_to_process = [h for h in st.session_state['hotspot_results'] if h['url'] in selected_urls]
                                response = requests.post(f"{API_BASE_URL}/api/hotspot/generate", json={"hotspots": hotspots_to_process})
                                response.raise_for_status(); result_data = response.json()
                                st.success("分析完成！")
                                for res in result_data.get("results", []):
                                    st.subheader(f"生成结果: `{res.get('saved_path')}`"); st.info(f"🤖 **Gemini 视频摘要**: {res.get('video_summary')}")
                                    display_prompt(res.get("prompt_content"))
                            except Exception as e: st.error(f"Gemini分析失败: {e}")

    with tab_iterate:
        st.header("从单个视频迭代 (分步可视化)")
        if not st.session_state['cookie_str']: st.warning("请先登录。")
        else:
            with st.form("iterate_form"):
                base_prompt = st.text_input("基础Prompt文件路径", "prompts/generated/...")
                video_url = st.text_input("目标B站视频URL", "https://www.bilibili.com/video/...")
                iterate_button = st.form_submit_button("🔁 开始迭代")
            if iterate_button:
                st.session_state['iteration_result'] = None
                with st.spinner("第1步/3步: 正在获取视频评论..."):
                    try:
                        payload = {"video_url": video_url}; response = requests.post(f"{API_BASE_URL}/api/iterate/step1_fetch_comments", json=payload)
                        response.raise_for_status(); st.session_state['comments_data'] = response.json()
                    except Exception as e: st.error(f"获取评论失败: {e}")
                if st.session_state.get('comments_data'):
                    with st.expander("✅ 第1步完成：查看获取到的评论", expanded=True): st.dataframe(pd.DataFrame(st.session_state['comments_data'].get('comments', [])), use_container_width=True)
                    with st.spinner("第2步/3步: 正在进行AI分析..."):
                        try:
                            response = requests.post(f"{API_BASE_URL}/api/iterate/step2_analyze_comments", json=st.session_state['comments_data'])
                            response.raise_for_status(); st.session_state['analysis_result'] = response.json()
                        except Exception as e: st.error(f"分析评论失败: {e}")
                if st.session_state.get('analysis_result'):
                    with st.expander("✅ 第2步完成：查看AI洞察", expanded=True): st.write("AI提炼的可执行修改建议:"); display_prompt(st.session_state['analysis_result'].get('deltas', []))
                    with st.spinner("第3步/3步: 正在应用修改..."):
                        try:
                            payload = {"base_prompt_path": base_prompt, "deltas": st.session_state['analysis_result'].get('deltas', [])}
                            response = requests.post(f"{API_BASE_URL}/api/iterate/step3_apply_changes", json=payload)
                            response.raise_for_status(); st.session_state['iteration_result'] = response.json()
                        except Exception as e: st.error(f"应用修改失败: {e}")
            if st.session_state.get('iteration_result'):
                st.success("迭代完成！")
                final_data = st.session_state['iteration_result']
                st.subheader(f"新Prompt: `{final_data.get('new_prompt_path')}`"); display_prompt(final_data.get('new_content'))
                with st.expander("🔍 查看具体变更"): st.text("\n".join(final_data.get("diffs", ["无变更"])))

    with tab_refine:
        st.header("交互式优化 Prompt")
        if not st.session_state['cookie_str']: st.warning("请先登录。")
        else:
            if st.button("🔄 刷新Prompt列表"):
                try:
                    response = requests.get(f"{API_BASE_URL}/api/prompt/list"); response.raise_for_status()
                    st.session_state['prompt_files'] = response.json(); st.toast("列表已刷新")
                except Exception as e: st.error(f"获取列表失败: {e}")
            if st.session_state.get('prompt_files'):
                selected_file = st.selectbox("选择一个要优化的Prompt文件", options=st.session_state['prompt_files'])
                if selected_file:
                    st.session_state['selected_prompt'] = selected_file
                    try:
                        with open(selected_file, 'r', encoding='utf-8') as f: prompt_content = json.load(f)
                        display_prompt(prompt_content)
                    except Exception as e: st.error(f"读取文件失败: {e}")
            if st.session_state.get('selected_prompt'):
                with st.form("refine_form"):
                    feedback = st.text_area("输入你的优化指令", height=100)
                    refine_button = st.form_submit_button("🤖 开始优化")
                if refine_button and feedback:
                    with st.spinner("正在调用模型进行优化..."):
                        try:
                            payload = {"prompt_path": st.session_state['selected_prompt'], "feedback": feedback}
                            response = requests.post(f"{API_BASE_URL}/api/prompt/refine", json=payload)
                            response.raise_for_status(); st.session_state['refined_result'] = response.json()
                        except Exception as e: st.error(f"优化失败: {e}")
            if st.session_state.get('refined_result'):
                st.success("优化完成!")
                res = st.session_state['refined_result']
                st.subheader(f"新版本已保存: `{res.get('new_prompt_path')}`"); display_prompt(res.get('new_content'))
                with st.expander("🔍 查看具体变更"): st.text("\n".join(res.get("diffs", ["无变更"])))

    with tab_expand:
        st.header("💡 创意扩展 Prompt")
        if not st.session_state.get('prompt_files'):
            st.info("请先在“交互式优化”标签页点击“刷新Prompt列表”来加载文件。")
        else:
            c1, c2 = st.columns([2,1])
            with c1: base_expand_prompt = st.selectbox("选择一个基础Prompt进行扩展", options=st.session_state['prompt_files'], key="expand_select")
            with c2: num_expansions = st.number_input("扩展数量", min_value=1, max_value=10, value=3)
            use_hint = st.checkbox("自定义扩展方向")
            user_hint = ""
            if use_hint: user_hint = st.text_area("输入你的灵感方向 (例如: 改成赛博朋克风格, 主角换成柯基犬)")
            if st.button("🚀 开始扩展"):
                with st.spinner(f"正在生成 {num_expansions} 个创意变体..."):
                    try:
                        payload = {"prompt_path": base_expand_prompt, "num_expansions": num_expansions, "user_hint": user_hint if use_hint else None}
                        response = requests.post(f"{API_BASE_URL}/api/prompt/expand", json=payload)
                        response.raise_for_status()
                        st.session_state['expansion_results'] = response.json().get("results", [])
                    except Exception as e: st.error(f"扩展失败: {e}")
        if st.session_state.get('expansion_results'):
            st.success("扩展完成！")
            for result in st.session_state['expansion_results']:
                with st.expander(f"✨ 新变体: `{result.get('saved_path')}`"):
                    display_prompt(result.get("prompt_content"))