import streamlit as st
import pandas as pd
import random
import os

# 페이지 기본 설정
st.set_page_config(page_title="📝 나만의 단어 시험장", layout="wide")

# --- 상태 관리 (문제 섞기 & 초기화 용도) ---
if "shuffle_seed" not in st.session_state:
    st.session_state.shuffle_seed = random.randint(0, 10000)

def reset_test():
    """다시 하기 버튼을 누르면 랜덤 시드를 바꾸고, 입력했던 정답을 모두 지웁니다."""
    st.session_state.shuffle_seed = random.randint(0, 10000)
    for key in list(st.session_state.keys()):
        if key.startswith("q_"):
            del st.session_state[key]

# --- 기본 데이터 폴더 탐색 ---
# 현재 app.py가 있는 폴더 경로를 찾고, 그 안의 'data' 폴더 경로를 지정합니다.
current_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(current_dir, "data")

available_files = {} # { "화면에 보일 이름": "실제 파일 경로 또는 객체" }

# 1. data 폴더가 있고 그 안에 파일이 있다면 목록에 추가
if os.path.exists(data_dir) and os.path.isdir(data_dir):
    for file_name in os.listdir(data_dir):
        if file_name.endswith('.xlsx') or file_name.endswith('.csv'):
            file_path = os.path.join(data_dir, file_name)
            available_files[f"[기본] {file_name}"] = file_path

# --- 메인 화면 ---
st.title("📝 나만의 단어 시험장")

# 2. 추가 업로드 기능 (선택 사항)
with st.expander("새로운 단어장 파일 추가하기 (선택)"):
    uploaded_files = st.file_uploader("단어장 파일(Excel, CSV)을 끌어다 놓으세요", type=['xlsx', 'csv'], accept_multiple_files=True)
    if uploaded_files:
        for f in uploaded_files:
            available_files[f"[업로드] {f.name}"] = f

# 파일이 하나라도 인식되었을 때만 아래 로직 실행
if available_files:
    # 파일 선택 드롭다운
    selected_file_name = st.selectbox("📚 시험 볼 문서를 선택하세요:", list(available_files.keys()))
    file_to_load = available_files[selected_file_name]
    
    df = None
    
    # 엑셀 파일 처리
    if selected_file_name.endswith('.xlsx'):
        xls = pd.ExcelFile(file_to_load)
        sheet_names = xls.sheet_names
        selected_sheet = st.selectbox("📑 시트를 선택하세요:", sheet_names)
        df = pd.read_excel(file_to_load, sheet_name=selected_sheet)
    # CSV 파일 처리
    else:
        df = pd.read_csv(file_to_load)
        
    st.divider()
    
    # 열 선택 UI
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        word_col = st.selectbox("단어가 있는 열(Column):", df.columns, index=0)
    with col_opt2:
        default_meaning_idx = 1 if len(df.columns) > 1 else 0
        meaning_col = st.selectbox("뜻이 있는 열(Column):", df.columns, index=default_meaning_idx)

    # 빈칸이 있는 줄은 제외 (에러 방지)
    df = df.dropna(subset=[word_col, meaning_col])

    st.divider()

    # 화면 좌우 1:2 분할
    col_list, col_test = st.columns([1, 2])

    # --- 왼쪽: 꽉 찬 3열 단어 목록 ---
    with col_list:
        st.subheader("📖 단어 목록")
        # 왼쪽 영역 독립 스크롤
        with st.container(height=700):
            words = df[word_col].astype(str).tolist()
            
            c1, c2, c3 = st.columns(3)
            for i, word in enumerate(words):
                if i % 3 == 0:
                    c1.write(word)
                elif i % 3 == 1:
                    c2.write(word)
                else:
                    c3.write(word)

    # --- 오른쪽: 단어 시험 영역 ---
    with col_test:
        # 상단 제목 및 '다시 하기' 버튼
        header_col1, header_col2 = st.columns([4, 1])
        with header_col1:
            st.subheader("🎯 단어 시험")
        with header_col2:
            st.button("🔄 다시 하기", on_click=reset_test, key="top_retry", use_container_width=True)
            
        # 섞인 문제 만들기
        shuffled_df = df.sample(frac=1, random_state=st.session_state.shuffle_seed)
        total_q = len(shuffled_df)
        
        st.write(f"뜻을 보고 알맞은 단어를 빈칸에 적어보세요. (총 **{total_q}문제** / Tab 키로 다음 칸 이동)")
        
        user_answers = {}
        
        # 오른쪽 문제지 독립 스크롤
        with st.container(height=550):
            for idx, (original_index, row) in enumerate(shuffled_df.iterrows(), 1):
                meaning = str(row[meaning_col])
                correct_word = str(row[word_col]).strip()
                
                user_input = st.text_input(f"Q{idx}. {meaning}", key=f"q_{original_index}")
                user_answers[original_index] = {"input": user_input.strip(), "correct": correct_word, "meaning": meaning}
            
        st.write("") 
        
        # 하단 버튼
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            do_grade = st.button("💯 채점하기", use_container_width=True, type="primary")
        with btn_col2:
            st.button("🔄 다시 하기", on_click=reset_test, key="bottom_retry", use_container_width=True)
            
        # 채점 결과 보여주기
        if do_grade:
            score = 0
            
            st.divider()
            st.subheader("📝 결과 확인")
            
            for idx, (original_index, row) in enumerate(shuffled_df.iterrows(), 1):
                data = user_answers[original_index]
                if data["input"].lower() == data["correct"].lower():
                    score += 1
                    st.success(f"Q{idx}. {data['meaning']} → 정답! (입력: {data['input']})")
                else:
                    st.error(f"Q{idx}. {data['meaning']} → 땡! (입력: '{data['input']}' / 정답: '{data['correct']}')")
                    
            if score == total_q and total_q > 0:
                st.balloons()
                st.success(f"🎉 완벽해요! {total_q}문제 중 {score}문제를 맞혔습니다!")
            else:
                st.warning(f"👍 잘했어요! {total_q}문제 중 {score}문제를 맞혔습니다. 틀린 문제를 확인하고 '다시 하기'를 눌러보세요.")
else:
    st.info("📂 시작하려면 'data' 폴더에 단어장 파일을 넣거나, 아래에 파일을 직접 끌어다 놓으세요!")