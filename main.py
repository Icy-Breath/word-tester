import streamlit as st
import pandas as pd
import random
import os
import re
from datetime import datetime
import subprocess

def get_git_commit_time(file_path, data_dir):
    """파일의 마지막 git commit 시간을 반환 (Unix timestamp)"""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%aI', file_path],
            cwd=data_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # ISO 8601 형식의 시간을 파싱
            commit_time_str = result.stdout.strip()
            commit_datetime = datetime.fromisoformat(commit_time_str.replace('Z', '+00:00'))
            return commit_datetime.timestamp()
    except (subprocess.TimeoutExpired, Exception):
        pass
    # git 정보가 없으면 파일 시스템 시간 사용
    return os.path.getmtime(file_path)

# --- 페이지 기본 설정 ---
st.set_page_config(page_title="📝 나만의 단어 시험장", layout="wide")

# --- 상태 관리 ---
if "shuffle_seed" not in st.session_state:
    st.session_state.shuffle_seed = random.randint(0, 10000)
if "is_graded" not in st.session_state:
    st.session_state.is_graded = False

def reset_test():
    """다시 하기: 입력한 답과 채점 상태를 모두 초기화합니다."""
    st.session_state.is_graded = False
    st.session_state.shuffle_seed = random.randint(0, 10000)

def clear_answers():
    """입력값 초기화: 문서/시트 선택이 변경될 때 호출합니다."""
    st.session_state.is_graded = False

def grade_test():
    """채점 하기: 상태를 '채점됨(True)'으로 바꿉니다."""
    st.session_state.is_graded = True

# --- 기본 데이터 폴더 탐색 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(current_dir, "data")

available_files = {}
base_files_with_mtime = []  # (display_name, file_path, mtime) 튜플 저장

if os.path.exists(data_dir) and os.path.isdir(data_dir):
    for file_name in os.listdir(data_dir):
        # Excel 임시 파일 제외 (~$로 시작하는 파일)
        if file_name.startswith('~$'):
            continue
        if file_name.endswith('.xlsx') or file_name.endswith('.csv'):
            file_path = os.path.join(data_dir, file_name)
            # git commit 시간 또는 파일 시스템 시간 사용
            mtime = get_git_commit_time(file_path, data_dir)
            # 수정 시간을 표시 (테스트용)
            mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            display_name = f"[기본] {file_name} ({mtime_str})"
            base_files_with_mtime.append((display_name, file_path, mtime, file_name))
    
    # 수정 날짜 기준 최신순으로 정렬 (내림차순), 같으면 파일 이름으로 정렬 (앞->뒤)
    base_files_with_mtime.sort(key=lambda x: (-x[2], x[3]))
    
    # 정렬된 순서대로 available_files에 추가
    for display_name, file_path, _, _ in base_files_with_mtime:
        available_files[display_name] = file_path

# --- 메인 화면 ---
st.title("📝 나만의 단어 시험장")

with st.expander("새로운 단어장 파일 추가하기 (선택)"):
    uploaded_files = st.file_uploader("단어장 파일(Excel, CSV)을 끌어다 놓으세요", type=['xlsx', 'csv'], accept_multiple_files=True)
    if uploaded_files:
        # 새로운 파일을 추가한 경우, 업로드된 파일들을 먼저 표시
        # 나중에 추가한 것부터 앞에 오도록 역순 처리
        new_available_files = {}
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for f in reversed(uploaded_files):
            display_name = f"[업로드] {f.name} ({upload_time})"
            new_available_files[display_name] = f
        # 그 다음 기본 파일들(data/) 추가
        new_available_files.update(available_files)
        available_files = new_available_files

if available_files:
    available_files_list = list(available_files.keys())
    selected_file_name = st.selectbox("📚 시험 볼 문서를 선택하세요:", available_files_list, index=0, on_change=clear_answers)
    file_to_load = available_files[selected_file_name]
    
    df = None
    selected_sheet = None
    # display_name이 아닌 file_to_load(파일 경로)로 확장자 판단
    if str(file_to_load).endswith('.xlsx'):
        xls = pd.ExcelFile(file_to_load)
        sheet_names = xls.sheet_names
        selected_sheet = st.selectbox("📑 시트를 선택하세요:", sheet_names, on_change=clear_answers)
        df = pd.read_excel(file_to_load, sheet_name=selected_sheet)
    else:
        # CSV 파일 인코딩 자동 감지 및 읽기
        encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'iso-8859-1']
        df = None
        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(file_to_load, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        if df is None:
            st.error("CSV 파일을 읽을 수 없습니다. 지원되지 않는 인코딩입니다.")
            st.stop()
        selected_sheet = "csv"
        
    st.divider()
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        word_col = st.selectbox("단어가 있는 열(Column):", df.columns, index=0)
    with col_opt2:
        default_meaning_idx = 1 if len(df.columns) > 1 else 0
        meaning_col = st.selectbox("뜻이 있는 열(Column):", df.columns, index=default_meaning_idx)

    df = df.dropna(subset=[word_col, meaning_col])

    st.divider()

    col_list, col_test = st.columns([1, 2])

    # 파일/시트 정보를 포함한 고유한 키 프리픽스 생성 (위에서도 동일한 생성)
    safe_file = re.sub(r'[^a-zA-Z0-9]', '_', selected_file_name)[:15]
    safe_sheet = re.sub(r'[^a-zA-Z0-9]', '_', str(selected_sheet))[:15]
    key_prefix = f"{safe_file}_{safe_sheet}"

    # 🔥 현재 파일/시트의 사용자가 텍스트 칸에 입력한 모든 단어를 수집 (대소문자 무시, 공백 제거)
    # shuffle_seed를 포함한 현재 라운드의 키만 수집
    entered_words = set()
    current_key_pattern = f"q_{key_prefix}_{st.session_state.shuffle_seed}_"
    for key, value in st.session_state.items():
        if key.startswith(current_key_pattern) and isinstance(value, str) and value.strip():
            entered_words.add(value.strip().lower())

    # --- 왼쪽: 단어 목록 ---
    with col_list:
        st.subheader("📖 단어 목록")
        with st.container(height=700):
            words = df[word_col].astype(str).tolist()
            num_words = len(words)
            
            # 행 단위로 3개씩 표시하여 높이 정렬
            for row_idx in range(0, num_words, 3):
                c1, c2, c3 = st.columns(3)
                
                # 첫 번째 열
                if row_idx < num_words:
                    clean_word = words[row_idx].strip()
                    if clean_word.lower() in entered_words:
                        display_text = f"<span style='color:lightgray;'><strike>{clean_word}</strike></span>"
                    else:
                        display_text = clean_word
                    c1.markdown(display_text, unsafe_allow_html=True)
                
                # 두 번째 열
                if row_idx + 1 < num_words:
                    clean_word = words[row_idx + 1].strip()
                    if clean_word.lower() in entered_words:
                        display_text = f"<span style='color:lightgray;'><strike>{clean_word}</strike></span>"
                    else:
                        display_text = clean_word
                    c2.markdown(display_text, unsafe_allow_html=True)
                
                # 세 번째 열
                if row_idx + 2 < num_words:
                    clean_word = words[row_idx + 2].strip()
                    if clean_word.lower() in entered_words:
                        display_text = f"<span style='color:lightgray;'><strike>{clean_word}</strike></span>"
                    else:
                        display_text = clean_word
                    c3.markdown(display_text, unsafe_allow_html=True)
                
                # 마지막 행이 아니면 구분선 표시
                if row_idx + 3 < num_words:
                    st.markdown('<hr style="margin: 2px 0; border: 1px solid #333;">', unsafe_allow_html=True)

    # --- 오른쪽: 단어 시험 영역 ---
    with col_test:
        # 상단 제목 및 버튼 2개
        header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
        with header_col1:
            st.subheader("🎯 단어 시험")
        with header_col2:
            st.button("💯 채점하기", on_click=grade_test, key="top_grade", use_container_width=True, type="primary")
        with header_col3:
            st.button("🔄 다시 하기", on_click=reset_test, key="top_retry", use_container_width=True)
            
        shuffled_df = df.sample(frac=1, random_state=st.session_state.shuffle_seed)
        total_q = len(shuffled_df)
        
        st.write(f"뜻을 보고 알맞은 단어를 빈칸에 적어보세요. (총 **{total_q}문제**)")
        
        # 파일/시트 정보를 포함한 고유한 키 프리픽스 생성 (각 파일/시트마다 다른 키)
        safe_file = re.sub(r'[^a-zA-Z0-9]', '_', selected_file_name)[:15]
        safe_sheet = re.sub(r'[^a-zA-Z0-9]', '_', str(selected_sheet))[:15]
        key_prefix = f"{safe_file}_{safe_sheet}"
        
        user_answers = {}
        
        with st.container(height=550):
            for idx, (original_index, row) in enumerate(shuffled_df.iterrows(), 1):
                meaning = str(row[meaning_col])
                correct_word = str(row[word_col]).strip()
                
                # 입력 칸 - shuffle_seed를 포함한 고유한 키 사용
                # (shuffle_seed가 바뀔 때마다 완전히 다른 키가 생성됨 = 새로운 입력칸)
                current_key = f"q_{key_prefix}_{st.session_state.shuffle_seed}_{original_index}"
                user_input = st.text_input(
                    f"Q{idx}. {meaning}",
                    key=current_key
                )
                user_answers[original_index] = {"input": user_input.strip(), "correct": correct_word, "meaning": meaning}
                
                # 채점 버튼이 눌렸다면 정답/오답 표시
                if st.session_state.is_graded:
                    if user_input.strip().lower() == correct_word.lower():
                        st.markdown("✅ <span style='color:green; font-weight:bold;'>정답!</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"❌ <span style='color:red; font-weight:bold;'>땡! (정답: {correct_word})</span>", unsafe_allow_html=True)
            
        st.write("") 
        
        # 하단 버튼 2개
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            st.button("💯 채점하기", on_click=grade_test, key="bottom_grade", use_container_width=True, type="primary")
        with btn_col2:
            st.button("🔄 다시 하기", on_click=reset_test, key="bottom_retry", use_container_width=True)
            
        # 하단 채점 결과 요약
        if st.session_state.is_graded:
            score = sum(1 for data in user_answers.values() if data["input"].lower() == data["correct"].lower())
            
            st.divider()
            st.subheader("📝 결과 요약")
                    
            if score == total_q and total_q > 0:
                st.balloons()
                st.success(f"🎉 완벽해요! {total_q}문제 중 {score}문제를 맞혔습니다!")
            else:
                st.warning(f"👍 잘했어요! {total_q}문제 중 {score}문제를 맞혔습니다. 위에서 틀린 문제를 확인하고 다시 도전해 보세요.")
else:
    st.info("📂 시작하려면 'data' 폴더에 단어장 파일을 넣거나, 아래에 파일을 직접 끌어다 놓으세요!")