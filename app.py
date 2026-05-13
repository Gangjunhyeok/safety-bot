import streamlit as st
import requests
import json
import pandas as pd
import io
from datetime import datetime

# 1. 웹 앱 기본 설정 (브라우저 탭 이름, 아이콘, 레이아웃 등)
st.set_page_config(page_title="유해위험요인 추출기", page_icon="🛡️", layout="centered")

# 2. 메인 타이틀 및 설명
st.title("🛡️ 스마트 위험성평가 AI 봇")
st.markdown("현장 설비 및 작업명을 입력하면 **기술사 수준의 유해위험요인과 공학적 대책**을 즉시 추출합니다.")

# 3. 사이드바 (API 키 자동 적용 및 입력란)
with st.sidebar:
    st.header("⚙️ 환경 설정")
    
    # 비밀 금고(Secrets)에 키가 있으면 그걸 자동으로 꺼내 씀!
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ 서버에 등록된 API 키가 자동 적용되었습니다!")
    # 금고에 없으면 예전처럼 직접 입력창을 띄움
    else:
        api_key = st.text_input("구글 API 키를 입력하세요", type="password")
        
    st.markdown("---")
    st.info("💡 **사용 팁**\n\n'압력용기', '지게차', '밀폐공간 용접' 등 단어만 간단히 입력하세요.")

# 4. 사용자 입력창
user_input = st.text_input("▶ 평가할 장소, 설비 또는 작업명을 입력하세요:")

# 5. 시스템 프롬프트 (최고 전문가 페르소나)
system_instruction = """
당신은 20년 차 산업안전보건 최고 권위자이자, '화공안전기술사', '기계안전기술사', '산업안전지도사(화공)', '위험물기능장' 자격을 모두 보유한 공정안전관리(PSM) 및 위험성평가 전문가입니다.
사용자가 특정 '장소', '설비', 또는 '작업명'을 입력하면, 발생 가능한 유해위험요인을 분석하여 아래 규칙에 따라 표 형식으로만 출력해 주세요.

[출력 규칙]
1. 반드시 마크다운(Markdown) 표 형식으로 출력할 것.
2. 테이블 헤더: | 대상/설비명 | 세부 작업(노드) | 위험요인 분류 | 세부 유해위험요인 | 위험성 감소 대책 (공학적 대책 위주) |
3. KOSHA GUIDE 등의 명칭은 기재하지 말고 실제 '조치 내용'만 작성할 것.
4. [중요] '세부 유해위험요인' 및 '위험성 감소 대책' 열에서 여러 항목(1., 2., 3. 등)을 나열할 때는, 각 항목 사이에 반드시 <br> 태그를 삽입하여 줄바꿈을 할 것.
5. 표 이외의 인사말이나 부연 설명은 철저히 생략할 것.
"""

# 6. '분석 시작' 버튼을 눌렀을 때의 동작
if st.button("분석 시작 🚀", use_container_width=True):
    if not api_key:
        st.warning("👈 왼쪽 사이드바에 API 키를 먼저 입력해 주세요!")
    elif not user_input:
        st.warning("분석할 대상을 입력해 주세요!")
    else:
        # 진행 상태를 보여주는 스피너 애니메이션
        with st.spinner(f"'{user_input}'(을)를 분석 중입니다. 잠시만 기다려주세요..."):
            
            URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            data = {
                "systemInstruction": {"parts": [{"text": system_instruction}]},
                "contents": [{"parts": [{"text": user_input}]}]
            }
            
            try:
                # API 호출
                response = requests.post(URL, headers=headers, data=json.dumps(data), timeout=30)
                response.raise_for_status()
                
                result = response.json()
                ai_text = result['candidates'][0]['content']['parts'][0]['text']
                
                # 마크다운 표를 판다스 데이터프레임(엑셀 형태)으로 변환
                lines = ai_text.strip().split('\n')
                table_data = []
                for line in lines:
                    line = line.strip()
                    if '|' in line:
                        row = [cell.strip() for cell in line.split('|')][1:-1]
                        if not row or all(c.replace('-', '').strip() == '' for c in row):
                            continue
                        table_data.append(row)
                
                if len(table_data) > 1:
                    # 첫 줄을 헤더(열 이름)로, 나머지를 데이터로 설정
                    df = pd.DataFrame(table_data[1:], columns=table_data[0])
                    
                    # [1차 변환] AI가 넣은 <br> 태그를 실제 줄바꿈(\n)으로 교체
                    df = df.replace({'<br>': '\n', '<br/>': '\n'}, regex=True)
                    
                    # [2차 강제 변환] AI가 태그를 빼먹고 '문장 1.1.2. 문장' 처럼 썼을 경우, 번호 앞에서 강제로 줄바꿈!
                    df = df.replace({r'(?<=[^\s])\s+(?=\d+(?:\.\d+)*\.)': '\n'}, regex=True)
                    
                    st.success("✅ 분석이 완료되었습니다!")
                    
                    # 글자가 잘리지 않고 줄바꿈이 다 보이도록 st.table() 사용
                    st.table(df)

                    
                    
                    # 엑셀 파일로 변환하여 메모리에 저장
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='위험성평가')
                    excel_data = output.getvalue()
                    
                    # 스마트폰/PC로 즉시 다운로드할 수 있는 버튼 생성
                    current_time = datetime.now().strftime('%y%m%d_%H%M')
                    st.download_button(
                        label="📥 엑셀 파일로 다운로드",
                        data=excel_data,
                        file_name=f"위험성평가_{user_input}_{current_time}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                else:
                    st.error("표 형태의 결과를 받아오지 못했습니다. 다시 시도해 주세요.")
                    
            # 이 except 구문이 지워지거나 들여쓰기가 안 맞아서 났던 에러입니다!
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
