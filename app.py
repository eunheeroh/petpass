# =============================================================================
# 펫패스(PetPass) — 반려동물 동반 출입 사전 확인 Streamlit 웹앱
# =============================================================================
#
# [이 앱이 하는 일]
#   내 반려동물의 무게·크기를 입력하면, 한국관광공사 '반려동물 동반여행 정보'
#   공공데이터를 불러와서, 가려는 장소의 동반 조건과 비교해
#   🟢가능 / 🟡조건부 / 🔴불가 를 신호등처럼 판정해 줍니다.
#
# -----------------------------------------------------------------------------
# [실행 전 준비] 아래 라이브러리를 먼저 설치하세요. (터미널에 복사해서 실행)
#
#   pip install streamlit requests pandas folium streamlit-folium
#
# [실행 방법] 터미널에서 아래 명령을 입력하면 브라우저가 자동으로 열립니다.
#
#   streamlit run app.py
#
# =============================================================================

# --- 필요한 도구(라이브러리) 불러오기 -----------------------------------------
import re                       # 정규식: 글자 속에서 숫자(무게 상한 등)를 뽑아낼 때 사용
import requests                 # 인터넷(API)에서 데이터를 가져올 때 사용
import pandas as pd             # 표(엑셀 같은 형태)로 데이터를 정리·필터링할 때 사용
import streamlit as st          # 웹 화면(UI)을 만드는 도구
import folium                   # 지도를 그리는 도구
from streamlit_folium import st_folium  # folium 지도를 Streamlit 화면에 붙여주는 도구


# =============================================================================
# 0. 기본 설정 (인증키, 주소 등)
# =============================================================================

# [중요] 공공데이터포털 인증키(서비스키) — 보안을 위해 '비밀값(Secrets)'으로 관리합니다.
#   - 코드에 직접 넣지 않으므로, GitHub 등에 올려도 키가 노출되지 않습니다.
#   - 인증키는 Decoding 키(순수 글자/숫자)를 권장합니다. requests 가 자동으로 인코딩합니다.
#
#   [로컬 실행]  프로젝트 안에  .streamlit/secrets.toml  파일을 만들고 아래처럼 적으세요:
#       SERVICE_KEY = "여기에_발급받은_Decoding_키"
#   [클라우드 배포]  Streamlit Community Cloud 앱의  Settings > Secrets  칸에 같은 내용을 붙여넣으세요.

def _load_service_key():
    """st.secrets 에서 인증키를 읽습니다. 없으면 빈 문자열."""
    try:
        return st.secrets.get("SERVICE_KEY", "")
    except Exception:
        # secrets.toml 이 아예 없을 때 st.secrets 접근이 예외를 낼 수 있어 방어합니다.
        return ""

SERVICE_KEY = _load_service_key()

# 한국관광공사 반려동물 동반여행 정보(KorPetTourService)의 기본 주소
#   [주의] 구버전 'KorPetTourService/areaBasedList' 경로는 폐기되어 404가 납니다.
#          현재는 버전 '2'가 붙은 경로(KorPetTourService2/areaBasedList2 등)를 사용합니다.
BASE_URL = "http://apis.data.go.kr/B551011/KorPetTourService2"

# API를 부를 때 우리 앱이 어떤 서비스인지 알려주는 이름(공공데이터 규칙상 아무 값이나 넣어도 됩니다)
MOBILE_OS = "ETC"       # 운영체제 구분 (ETC = 기타)
MOBILE_APP = "PetPass"  # 서비스(앱) 이름


# =============================================================================
# 1. 페이지 기본 모양 설정
# =============================================================================
st.set_page_config(
    page_title="펫패스(PetPass) — 반려동물 동반 출입 확인",
    page_icon="🐾",
    layout="wide",  # 화면을 넓게 사용
    # "auto": PC 넓은 화면에서는 사이드바(검색 필터)를 펼치고,
    #         모바일 좁은 화면에서는 자동으로 접어줍니다. (스트림릿 기본 반응형)
    initial_sidebar_state="auto",
)

# -----------------------------------------------------------------------------
# 다국어(한국어/English) 지원 헬퍼
# -----------------------------------------------------------------------------
# t("한국어 문구", "English text") 처럼 두 언어를 함께 넘기면,
# 사이드바에서 고른 언어(st.session_state["lang"])에 맞는 문구를 돌려줍니다.
# 언어 선택 위젯은 사이드바 맨 위에 있고, 값은 자동으로 session_state에 저장됩니다.
def t(ko, en):
    """현재 선택된 언어에 맞는 문구를 반환합니다. (기본값: 한국어)"""
    return en if st.session_state.get("lang") == "English" else ko

# -----------------------------------------------------------------------------
# 그린 계열 배경 테마 (CSS 주입)
# -----------------------------------------------------------------------------
# 앱 전체 배경을 부드러운 연두/초록 톤으로 바꾸고, 카드·버튼도 그린 계열로 통일합니다.
st.markdown(
    """
    <style>
    /* 구글 폰트 불러오기 — 전체 Gothic A1 (단정한 한글 고딕) */
    @import url('https://fonts.googleapis.com/css2?family=Gothic+A1:wght@400;500;700;800&display=swap');

    /* 앱 전체 기본 글꼴을 Gothic A1 로 */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        font-family: 'Gothic A1', sans-serif;
    }
    /* 위젯 내부 요소까지 글꼴 적용 */
    [data-testid="stAppViewContainer"] *, [data-testid="stSidebar"] * {
        font-family: 'Gothic A1', sans-serif;
    }
    /* -------------------------------------------------------------------
       [중요] 아이콘 폰트 복구
       위의 'Gothic A1 전체 적용'이 아이콘(사이드바 펼침 » 버튼 등)의
       전용 폰트(Material Symbols)까지 덮어써서, 아이콘이 글자로 깨져
       보이는 문제를 되돌립니다. 아이콘 요소만 원래 폰트로 되돌립니다.
       ------------------------------------------------------------------- */
    [data-testid="stIconMaterial"],
    [data-testid="stAppViewContainer"] [data-testid="stIconMaterial"],
    [data-testid="stSidebar"] [data-testid="stIconMaterial"],
    span.material-icons, span.material-symbols-outlined,
    span.material-symbols-rounded,
    [class*="material-symbols"], [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                     'Material Icons' !important;
    }
    /* 제목(h1~h3)은 굵게 강조 */
    h1, h2, h3 {
        font-family: 'Gothic A1', sans-serif !important;
        font-weight: 800;
    }

    /* -------------------------------------------------------------------
       모든 글자를 검정으로 (다크모드 폰에서도 확실히 잘 보이도록)
       - 제목/본문/캡션/입력라벨/푸터까지 전부 검정
       - 단, 초록 배경 버튼의 흰 글자는 아래에서 예외 처리
       ------------------------------------------------------------------- */
    [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    [data-testid="stAppViewContainer"] p,
    [data-testid="stAppViewContainer"] span,
    [data-testid="stAppViewContainer"] li,
    [data-testid="stAppViewContainer"] label,
    [data-testid="stSidebar"] label,
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] *,
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *,
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"],
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }
    /* 예외: 진한 초록 primary 버튼(검색하기)의 글자는 흰색 유지 */
    .stButton > button[kind="primary"],
    .stButton > button[kind="primary"] * {
        color: #ffffff !important;
    }

    /* 메인 화면 배경 — 위에서 아래로 연한 초록 그라데이션 */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #e8f5e9 0%, #f1f8f2 45%, #ffffff 100%);
    }
    /* 사이드바 배경 — 조금 더 진한 연초록 */
    [data-testid="stSidebar"] {
        background-color: #dcefdc;
    }
    /* 상단 헤더 바를 투명하게 해서 배경 그라데이션이 이어지도록 */
    [data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0);
    }
    /* 테두리 카드(st.container(border=True))를 흰 카드 + 초록 테두리로 */
    [data-testid="stContainer"] {
        background-color: #ffffff;
        border-color: #b7dfb9 !important;
    }
    /* 일반 버튼('상세 보기 ▶' 등): 흰 배경 + 진한 초록 글자로 확실히 보이게.
       (전체 글자를 검정으로 만드는 규칙에 덮여 버튼 글자가 안 보이던 문제 해결)
       primary(검색하기) 버튼은 :not 으로 제외해 초록 배경을 유지합니다. */
    .stButton > button:not([kind="primary"]) {
        background-color: #ffffff !important;
        border-color: #2e7d32 !important;
        color: #1b5e20 !important;
    }
    /* 버튼 안쪽 라벨 글자까지 초록으로 강제 (검정 규칙 방지) */
    .stButton > button:not([kind="primary"]) p,
    .stButton > button:not([kind="primary"]) span,
    .stButton > button:not([kind="primary"]) div {
        color: #1b5e20 !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background-color: #eaf5ea !important;
        border-color: #1b5e20 !important;
        color: #1b5e20 !important;
    }
    /* primary 버튼(검색하기)은 진한 초록 배경 */
    .stButton > button[kind="primary"] {
        background-color: #2e7d32;
        border-color: #2e7d32;
        color: #ffffff;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #1b5e20;
        border-color: #1b5e20;
    }

    /* =====================================================================
       반응형(Responsive) — 스마트폰/태블릿 대응
       ---------------------------------------------------------------------
       화면 폭에 따라 여백·글자크기를 줄이고, 지도/이미지가 화면을 넘지
       않도록 합니다. (스트림릿은 좁은 화면에서 컬럼을 자동으로 세로로 쌓습니다.)
       ===================================================================== */

    /* 이미지가 항상 컨테이너 폭 안에 들어오도록 (세로 비율 유지) */
    img {
        max-width: 100% !important;
        height: auto;
    }
    /* 지도 등 iframe이 화면을 넘지 않도록 (높이는 건드리지 않음) */
    iframe {
        max-width: 100% !important;
    }
    /* 고정 폭 이미지(상단 강아지·고양이)가 좁은 화면에서도 가운데 오도록 */
    [data-testid="stImage"] img {
        margin-left: auto;
        margin-right: auto;
    }

    /* 메인 콘텐츠 기본 여백 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* 태블릿 이하 (가로 768px 이하) */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
        }
        h1 { font-size: 1.6rem !important; }
        h2 { font-size: 1.3rem !important; }
        h3 { font-size: 1.1rem !important; }
        /* 지표(metric) 카드가 좁을 때 숫자가 잘리지 않도록 */
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
    }

    /* 스마트폰 (가로 480px 이하) */
    @media (max-width: 480px) {
        .block-container {
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        h1 { font-size: 1.35rem !important; }
        h2 { font-size: 1.15rem !important; }
        /* 3개짜리 지표 행이 좁아도 숫자가 잘리지 않도록 */
        [data-testid="stMetricValue"] { font-size: 1.05rem; }
        /* 버튼을 손가락으로 누르기 쉽게 살짝 키움 */
        .stButton > button { padding: 0.5rem 0.75rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# 2. 신호등 판정 로직 (이 앱의 핵심!)
# =============================================================================
#
# 사용자의 반려동물 정보(user)와 장소의 동반 조건(place)을 비교해
# (신호 문구, 색상코드, 사유 리스트)를 돌려주는 함수입니다.
#
#   - user  : {"weight": 무게(kg), "size": 크기, "breed": 종류} 형태의 딕셔너리
#   - place : API에서 받아온 한 장소의 정보(딕셔너리)
#
# =============================================================================

def extract_weight_limit(text):
    """
    글자(text) 안에서 '허용 무게 상한'을 숫자로 뽑아냅니다.
    예) '20kg 이하 동반 가능' -> 20.0 을 반환
        무게 정보가 없으면 -> None 반환

    (비전공자용 설명)
      정규식(re)은 "글자 패턴 찾기" 도구입니다.
      여기서는 '숫자 + kg' 형태를 찾아서 그 숫자만 꺼냅니다.
    """
    if not text:
        return None

    # 'kg', '킬로', 'kg이하' 등 앞에 오는 숫자를 찾습니다. (소수점도 허용: 5.5kg)
    # 예: "10kg", "20 kg 이하", "무게 15킬로그램" 등에서 숫자를 추출
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kg|킬로|㎏)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def judge_pet(user, place):
    """
    반려동물(user)과 장소(place)를 대조해 신호등 판정을 내립니다.

    반환값(3가지를 한 번에 돌려줌):
      1) signal : 화면에 보여줄 신호 문구 (예: "🟢 가능")
      2) color  : 지도 마커/뱃지에 쓸 색상 코드 (green / orange / red)
      3) reasons: 판정 이유를 담은 리스트 (예: ["무게 15kg ≤ 상한 20kg", "이동장 필요"])
    """
    reasons = []  # 판정 근거를 하나씩 담을 빈 리스트

    # -------------------------------------------------------------------------
    # (A) 장소의 동반 조건 텍스트들을 하나로 합칩니다.
    #     -> 아래 place.get("...") 의 키 이름은 '실제 API 필드명'으로 바꿔야 합니다.
    #     -> 지금은 어떤 필드가 오든 최대한 잡아내도록 여러 후보를 합쳐 둡니다.
    #
    # 【여기를 실제 필드명으로 바꾸세요】 ↓↓↓
    # 예상되는 조건 관련 필드(실제 응답을 보고 정확한 이름으로 교체):
    #   acmpyPsblCpam : 동반 가능 반려동물
    #   etcAcmpyInfo  : 기타 동반 정보
    #   acmpyNeedMtr  : 반려동물 필수 준비물
    #   acmpyTypeCd   : 동반 유형
    #   (detailPetTour2 응답에서 확인한 실제 필드명으로 반영)
    condition_texts = " ".join([
        str(place.get("acmpyTypeCd", "")),       # 동반 유형 (예: "전구역 동반가능", "동반 불가")
        str(place.get("acmpyPsblCpam", "")),     # 동반 가능 반려동물 (예: "20kg 이하 소형견")
        str(place.get("etcAcmpyInfo", "")),       # 기타 동반 정보
        str(place.get("acmpyNeedMtr", "")),       # 필수 준비물 (예: "목줄 착용")
        str(place.get("relaAcdntRiskMtr", "")),   # 관련 사고 위험 요소/유의사항
    ])
    # 【여기까지】 ↑↑↑

    # 제약(조건부) 사유만 따로 셉니다. '무게 통과' 같은 긍정 근거는 제약이 아니므로 제외.
    # (신호 문구는 내부적으로 항상 한국어로 두고, 화면에 보일 때만 번역합니다.)
    constraint_count = 0  # 조건부로 볼 제약이 몇 개인지 세는 카운터

    # -------------------------------------------------------------------------
    # (B) 조건 정보가 아예 비어 있으면 -> 판단 불가 -> '조건부 + 현장 확인 권장'
    if not condition_texts.strip():
        return "🟡 조건부", "orange", [t(
            "동반 조건 정보가 없어 판단이 어렵습니다. 현장 확인을 권장합니다.",
            "No accompaniment info available, so it's hard to judge. Please check on-site.",
        )]

    # -------------------------------------------------------------------------
    # (C) '명시적으로 불가'인지 먼저 확인합니다. (가장 강한 신호)
    #     '동반 불가', '출입 불가', '반려동물 금지' 같은 표현이 있으면 바로 빨강.
    forbidden_keywords = ["동반불가", "동반 불가", "출입불가", "출입 불가", "불가능", "금지", "반입불가"]
    if any(word in condition_texts for word in forbidden_keywords):
        reasons.append(t(
            "장소 안내에 '동반 불가/금지' 문구가 있습니다.",
            "The listing states pets are not allowed / prohibited.",
        ))
        return "🔴 불가", "red", reasons

    # -------------------------------------------------------------------------
    # (D) 무게 조건을 비교합니다.
    weight_limit = extract_weight_limit(condition_texts)  # 장소가 허용하는 무게 상한
    user_weight = user.get("weight")                       # 내 반려동물 무게

    if weight_limit is not None and user_weight is not None:
        if user_weight > weight_limit:
            # 무게 초과 -> 불가
            reasons.append(t(
                f"내 반려동물 {user_weight}kg > 허용 상한 {weight_limit}kg (무게 초과)",
                f"Your pet {user_weight}kg > limit {weight_limit}kg (over the weight limit)",
            ))
            return "🔴 불가", "red", reasons
        else:
            # 무게는 통과 -> 근거로 기록 (제약은 아님)
            reasons.append(t(
                f"무게 {user_weight}kg ≤ 허용 상한 {weight_limit}kg (통과)",
                f"Weight {user_weight}kg ≤ limit {weight_limit}kg (OK)",
            ))

    # -------------------------------------------------------------------------
    # (E) '조건부'로 볼 만한 제약이 있는지 확인합니다.
    #     이동장, 목줄, 추가요금, 야외만 가능 등은 '가능은 하지만 조건이 있음'.
    #     각 항목: 검색 키워드 -> (한국어 안내, 영어 안내)
    conditional_keywords = {
        "이동장": ("이동장(케이지)이 필요할 수 있습니다.", "A carrier (crate) may be required."),
        "케이지": ("케이지가 필요할 수 있습니다.", "A crate may be required."),
        "목줄": ("목줄 착용이 필요합니다.", "A leash is required."),
        "리드줄": ("리드줄 착용이 필요합니다.", "A lead is required."),
        "입마개": ("입마개가 필요할 수 있습니다.", "A muzzle may be required."),
        "야외": ("야외(테라스 등) 공간만 동반 가능할 수 있습니다.", "Pets may be allowed only in outdoor areas (e.g. terrace)."),
        "테라스": ("테라스 등 일부 공간만 동반 가능할 수 있습니다.", "Pets may be allowed only in some areas such as the terrace."),
        "추가요금": ("추가 요금이 발생할 수 있습니다.", "An extra fee may apply."),
        "추가 요금": ("추가 요금이 발생할 수 있습니다.", "An extra fee may apply."),
        "예약": ("사전 예약이 필요할 수 있습니다.", "Advance reservation may be required."),
        "소형견": ("소형견만 동반 가능할 수 있습니다.", "Only small dogs may be allowed."),
    }
    seen_messages = set()  # 같은 안내가 중복 추가되는 것을 막습니다.
    for keyword, (ko_msg, en_msg) in conditional_keywords.items():
        if keyword in condition_texts:
            msg = t(ko_msg, en_msg)
            if msg not in seen_messages:
                seen_messages.add(msg)
                reasons.append(msg)
                constraint_count += 1

    # -------------------------------------------------------------------------
    # (F) 최종 판정
    #  - 조건부 제약이 하나라도 있으면 -> 🟡 조건부
    #  - 무게도 통과했고 별다른 제약도 없으면 -> 🟢 가능
    #  - 무게 상한 정보 자체가 없으면(불명확) -> 🟡 조건부 + 현장 확인 권장
    if constraint_count > 0:
        return "🟡 조건부", "orange", reasons

    if weight_limit is None:
        # 무게 상한 정보가 없어서 확실히 가능하다고 말하기 어려운 경우
        reasons.append(t(
            "무게 제한 정보가 명확하지 않습니다. 현장 확인을 권장합니다.",
            "Weight limit info is unclear. Please check on-site.",
        ))
        return "🟡 조건부", "orange", reasons

    # 여기까지 왔다면: 무게 통과 + 별다른 제약 없음 -> 가능
    if not reasons:
        reasons.append(t(
            "특별한 제한 조건이 확인되지 않았습니다.",
            "No special restrictions were found.",
        ))
    return "🟢 가능", "green", reasons


# =============================================================================
# 3. 공공데이터 API 호출 함수들
# =============================================================================
#
# @st.cache_data : 같은 검색 조건이면 결과를 '기억'해 두었다가 재사용합니다.
#                  -> API를 불필요하게 여러 번 부르지 않아 빠르고, 호출 수도 아낍니다.
# =============================================================================

# 지역(시/도)을 코드 번호로 바꾸는 표입니다. (KorService 계열 표준 areaCode)
# API 명세에 맞는 실제 코드로, 필요하면 값을 수정하세요.
AREA_CODES = {
    "전체": None,
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5,
    "부산": 6, "울산": 7, "세종": 8, "경기": 31, "강원": 32,
    "충북": 33, "충남": 34, "경북": 35, "경남": 36,
    "전북": 37, "전남": 38, "제주": 39,
}

# 유형(콘텐츠 타입)을 코드 번호로 바꾸는 표입니다. (KorService 계열 표준 contenttypeid)
# "전체"는 None 이며, 이 경우 유형 필터를 적용하지 않습니다.
CONTENT_TYPE_CODES = {
    "전체": None,
    "관광지": "12",
    "문화시설": "14",
    "축제/공연/행사": "15",
    "여행코스": "25",
    "레포츠": "28",
    "숙박": "32",
    "쇼핑": "38",
    "음식점": "39",
}

# 코드 -> 이름 역방향 표 (카드에 숫자 코드 대신 사람이 읽을 이름을 보여줄 때 사용)
CONTENT_TYPE_NAMES = {
    code: name for name, code in CONTENT_TYPE_CODES.items() if code is not None
}

# -----------------------------------------------------------------------------
# 다국어: 지역/유형/크기/신호 이름의 영어 대응표
# -----------------------------------------------------------------------------
# 셀렉트박스는 한국어 키(예: "서울")를 그대로 값으로 쓰되, 화면 표시만 아래 표로
# 번역합니다. (format_func 사용) 그래서 AREA_CODES 등의 매핑 로직은 그대로 동작합니다.
AREA_NAMES_EN = {
    "전체": "All", "서울": "Seoul", "인천": "Incheon", "대전": "Daejeon",
    "대구": "Daegu", "광주": "Gwangju", "부산": "Busan", "울산": "Ulsan",
    "세종": "Sejong", "경기": "Gyeonggi", "강원": "Gangwon", "충북": "Chungbuk",
    "충남": "Chungnam", "경북": "Gyeongbuk", "경남": "Gyeongnam",
    "전북": "Jeonbuk", "전남": "Jeonnam", "제주": "Jeju",
}
TYPE_NAMES_EN = {
    "전체": "All", "관광지": "Attraction", "문화시설": "Cultural facility",
    "축제/공연/행사": "Festival/Event", "여행코스": "Travel course",
    "레포츠": "Leisure sports", "숙박": "Lodging", "쇼핑": "Shopping",
    "음식점": "Restaurant",
}
SIZE_NAMES_EN = {"소형": "Small", "중형": "Medium", "대형": "Large"}

# 견종/종류 선택 목록 — (한국어, English) 쌍. 마지막은 '직접 입력' 옵션.
BREED_OPTIONS = [
    ("말티즈", "Maltese"),
    ("푸들", "Poodle"),
    ("포메라니안", "Pomeranian"),
    ("시츄", "Shih Tzu"),
    ("치와와", "Chihuahua"),
    ("웰시코기", "Welsh Corgi"),
    ("비글", "Beagle"),
    ("진돗개", "Jindo"),
    ("골든리트리버", "Golden Retriever"),
    ("코리안숏헤어", "Korean Shorthair"),
    ("페르시안", "Persian"),
    ("러시안블루", "Russian Blue"),
    ("기타(직접 입력)", "Other (type it)"),
]
# 직접 입력 옵션을 식별하기 위한 한국어 키 (내부 값은 항상 한국어)
BREED_OTHER_KO = "기타(직접 입력)"
# 견종 한국어 -> 영어 표시용 (직접 입력한 값은 그대로 보여줌)
BREED_NAMES_EN = {ko: en for ko, en in BREED_OPTIONS}


def breed_display(breed):
    """견종 내부값(한국어)을 현재 언어에 맞게 표시용으로 바꿉니다."""
    if st.session_state.get("lang") == "English":
        return BREED_NAMES_EN.get(breed, breed)  # 목록에 없으면(직접 입력) 그대로
    return breed
# 신호 문구(내부는 한국어)를 화면 표시용으로 번역
SIGNAL_NAMES_EN = {"🟢 가능": "🟢 OK", "🟡 조건부": "🟡 Conditional", "🔴 불가": "🔴 Not allowed"}


def signal_display(signal):
    """내부 신호 문구('🟢 가능' 등)를 현재 언어에 맞게 표시용으로 바꿉니다."""
    if st.session_state.get("lang") == "English":
        return SIGNAL_NAMES_EN.get(signal, signal)
    return signal


@st.cache_data(ttl=3600, show_spinner="공공데이터를 불러오는 중입니다...")
def fetch_area_based_list(area_code=None, sigungu_code=None, num_rows=100, page_no=1):
    """
    [1단계 API] 지역기반 목록(areaBasedList)을 불러옵니다.
    반려동물 동반이 가능한 장소들의 '기본 목록'을 가져오는 역할입니다.

    - area_code    : 시/도 코드(숫자). None이면 전국.
    - sigungu_code : 시군구 코드(숫자). None이면 시/도 전체.
    - num_rows     : 한 번에 가져올 개수
    - page_no      : 페이지 번호

    반환값: (성공 여부, 데이터 리스트 또는 에러메시지)
    """
    # API에 함께 보낼 조건(파라미터)들을 딕셔너리로 준비합니다.
    params = {
        "serviceKey": SERVICE_KEY,   # 인증키
        "MobileOS": MOBILE_OS,
        "MobileApp": MOBILE_APP,
        "_type": "json",             # 응답을 JSON 형태로 받겠다는 뜻
        "numOfRows": num_rows,
        "pageNo": page_no,
        "arrange": "A",              # 정렬 기준 (A=제목순 등, 명세에 따라 조정)
    }
    # 지역이 지정된 경우에만 areaCode 조건을 추가합니다.
    if area_code is not None:
        params["areaCode"] = area_code
        # 시군구는 시/도가 지정됐을 때만 의미가 있습니다.
        if sigungu_code is not None:
            params["sigunguCode"] = sigungu_code

    try:
        # 실제로 인터넷에 요청을 보냅니다. timeout=10 -> 10초 안에 응답 없으면 실패 처리.
        response = requests.get(f"{BASE_URL}/areaBasedList2", params=params, timeout=10)
        response.raise_for_status()  # 200(정상)이 아니면 여기서 오류를 발생시킴
        data = response.json()       # 받은 내용을 JSON(파이썬 딕셔너리)으로 변환
    except requests.exceptions.RequestException as e:
        # 인터넷 오류, 서버 오류, 시간 초과 등 모든 요청 관련 문제를 여기서 처리
        return False, f"데이터를 불러오지 못했습니다. (원인: {e})"
    except ValueError:
        # 응답이 JSON이 아닐 때(예: 인증키 오류로 XML 에러가 올 때)
        return False, "응답 형식이 올바르지 않습니다. 인증키(SERVICE_KEY)를 확인해 주세요."

    # -------------------------------------------------------------------------
    # JSON 구조를 '견고하게' 파싱합니다. (키가 없어도 앱이 죽지 않도록 .get 사용)
    # 공공데이터 표준 응답 구조:  response > body > items > item(리스트)
    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
    )
    # items 가 빈 문자열("")로 오는 경우도 있으므로 방어합니다.
    if not items or not isinstance(items, dict):
        return True, []  # 정상 호출이지만 결과가 0건인 경우

    item_list = items.get("item", [])

    # 결과가 1건이면 리스트가 아니라 딕셔너리 하나로 올 수 있어, 리스트로 통일합니다.
    if isinstance(item_list, dict):
        item_list = [item_list]

    return True, item_list


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sigungu_codes(area_code):
    """
    선택한 시/도(area_code)에 속한 시군구 목록을 불러옵니다. (areaCode2 API)
    반환값: [(코드, 이름), ...] 형태의 리스트. 실패하거나 없으면 빈 리스트.

    - 예) 서울(area_code=1) -> [("1","종로구"), ("2","중구"), ...]
    - 하루(86400초) 캐시 — 시군구 목록은 거의 바뀌지 않습니다.
    """
    if area_code is None:
        return []  # '전체' 지역이면 시군구를 나눌 수 없음

    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": MOBILE_OS,
        "MobileApp": MOBILE_APP,
        "_type": "json",
        "numOfRows": 100,
        "pageNo": 1,
        "areaCode": area_code,
    }
    try:
        response = requests.get(f"{BASE_URL}/areaCode2", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return []  # 실패하면 시군구 없이 진행 (전체만 표시)

    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
    )
    if not items or not isinstance(items, dict):
        return []

    item_list = items.get("item", [])
    if isinstance(item_list, dict):
        item_list = [item_list]

    # (코드, 이름) 쌍으로 정리해서 돌려줍니다.
    return [(str(it.get("code")), str(it.get("name"))) for it in item_list if it.get("code")]


def _request_detail_item(content_id):
    """
    [내부 공용] 한 장소(content_id)의 상세 동반조건을 실제로 API에서 가져옵니다.
    캐시를 붙이지 않은 '순수' 함수라 여러 스레드에서 동시에 불러도 안전합니다.

    반환값: (성공 여부, 상세정보 딕셔너리 또는 에러메시지)
    """
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": MOBILE_OS,
        "MobileApp": MOBILE_APP,
        "_type": "json",
        "contentId": content_id,   # 어떤 장소의 상세정보를 원하는지 지정
    }

    try:
        response = requests.get(f"{BASE_URL}/detailPetTour2", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        return False, f"상세 정보를 불러오지 못했습니다. (원인: {e})"
    except ValueError:
        return False, "상세 응답 형식이 올바르지 않습니다."

    items = (
        data.get("response", {})
            .get("body", {})
            .get("items", {})
    )
    if not items or not isinstance(items, dict):
        return True, {}

    item = items.get("item", {})
    if isinstance(item, list):
        item = item[0] if item else {}  # 리스트로 오면 첫 번째 것을 사용

    return True, item


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_detail_pet_tour(content_id):
    """
    [2단계 API] 반려동물 상세 조건(detailPetTour)을 불러옵니다.
    상세 카드에서 '한 장소'의 동반 상세 조건을 가져올 때 사용합니다.

    - content_id : 장소를 구분하는 고유 번호 (1단계 목록에서 얻음)

    반환값: (성공 여부, 상세정보 딕셔너리 또는 에러메시지)
    """
    return _request_detail_item(content_id)


@st.cache_data(ttl=3600, show_spinner="장소별 동반조건을 확인하는 중입니다...")
def fetch_conditions_for_ids(content_ids):
    """
    [목록 보강용] 여러 장소의 동반조건을 '한꺼번에' 가져옵니다.
    목록 카드에서도 무게/조건 신호등을 정확히 보여주려면, 각 장소의 상세조건이
    미리 필요합니다. 장소가 수십 곳이라 하나씩 순차 호출하면 느리므로,
    스레드로 '동시에' 여러 건을 불러 속도를 높입니다.

    - content_ids : 장소 고유번호들의 튜플 (캐시가 되도록 리스트가 아닌 튜플 권장)

    반환값: {content_id: 상세조건딕셔너리} 형태의 딕셔너리
            (실패하거나 정보가 없는 장소는 빈 딕셔너리 {})
    """
    from concurrent.futures import ThreadPoolExecutor

    results = {}

    def worker(cid):
        ok, detail = _request_detail_item(cid)
        return cid, (detail if ok and isinstance(detail, dict) else {})

    # max_workers=8 : 동시에 최대 8건까지 호출 (서버 부담과 속도의 균형)
    with ThreadPoolExecutor(max_workers=8) as executor:
        for cid, detail in executor.map(worker, content_ids):
            results[cid] = detail

    return results


# =============================================================================
# 4. 사이드바 — 사용자 입력 & 검색 필터
# =============================================================================

with st.sidebar:
    # --- (0) 언어 선택 — 이 값(st.session_state["lang"])에 따라 전체 문구가 바뀝니다 --
    #   key="lang" 을 주면 선택값이 자동으로 st.session_state["lang"] 에 저장됩니다.
    st.radio(
        "🌐 Language / 언어",
        options=["한국어", "English"],
        horizontal=True,
        key="lang",
    )

    st.header(t("🐶 내 반려동물", "🐶 My Pet"))

    # --- (1) 내 반려동물 정보 입력 -------------------------------------------
    # 입력값은 st.session_state 에 저장해 두면, 화면이 새로고침돼도 값이 유지됩니다.
    #
    # 견종/종류: 목록에서 고르되, '기타(직접 입력)'를 고르면 자유롭게 타이핑할 수 있습니다.
    # 내부값(breed)은 항상 한국어로 저장하고, 화면 표시만 언어에 맞게 번역합니다.
    breed_keys = [ko for ko, en in BREED_OPTIONS]
    breed_en = {ko: en for ko, en in BREED_OPTIONS}
    selected_breed = st.selectbox(
        t("견종 / 종류", "Breed / Type"),
        options=breed_keys,
        index=0,
        format_func=lambda b: breed_en[b] if st.session_state.get("lang") == "English" else b,
    )
    if selected_breed == BREED_OTHER_KO:
        # '기타'를 고른 경우에만 직접 입력칸을 보여줍니다.
        breed = st.text_input(
            t("견종/종류 직접 입력", "Enter breed / type"),
            value=st.session_state.get("breed_custom", ""),
            placeholder=t("예: 사모예드, 벵갈고양이", "e.g. Samoyed, Bengal cat"),
        )
        st.session_state["breed_custom"] = breed
    else:
        breed = selected_breed
    weight = st.number_input(
        t("무게 (kg)", "Weight (kg)"),
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get("weight", 5.0),
        step=0.5,
        help=t(
            "반려동물의 몸무게를 입력하세요. 신호등 판정의 핵심 기준입니다.",
            "Enter your pet's weight. It's the key factor for the traffic-light result.",
        ),
    )
    # 크기: 내부값은 한국어("소형"/"중형"/"대형") 그대로 두고, 표시만 번역합니다.
    size = st.radio(
        t("크기", "Size"),
        options=["소형", "중형", "대형"],
        index=["소형", "중형", "대형"].index(st.session_state.get("size", "소형")),
        horizontal=True,
        format_func=lambda s: SIZE_NAMES_EN[s] if st.session_state.get("lang") == "English" else s,
    )

    # 입력한 값을 session_state에 저장 (다른 곳에서도 꺼내 쓰기 위함)
    st.session_state["breed"] = breed
    st.session_state["weight"] = weight
    st.session_state["size"] = size

    st.divider()  # 구분선

    # --- (2) 검색 필터 -------------------------------------------------------
    st.header(t("🔎 검색 필터", "🔎 Search Filters"))

    # 지역: 내부값은 한국어 키("서울" 등), 표시만 영어로 번역 (AREA_CODES 매핑 유지)
    selected_area = st.selectbox(
        t("지역 (시/도)", "Region (Province/City)"),
        options=list(AREA_CODES.keys()),  # 위에서 만든 지역표의 이름들
        index=0,
        format_func=lambda a: AREA_NAMES_EN[a] if st.session_state.get("lang") == "English" else a,
    )

    # 시군구: 위에서 고른 시/도에 속한 시군구 목록을 API로 불러와 보여줍니다.
    #   - '전체' 지역이면 시군구를 나눌 수 없으므로 '전체'만 표시합니다.
    #   - sigungu_map: 표시이름 -> 시군구코드 (필터에 사용)
    _area_code_for_sgg = AREA_CODES.get(selected_area)
    sigungu_list = fetch_sigungu_codes(_area_code_for_sgg)  # [(코드, 이름), ...]
    sigungu_map = {t("전체", "All"): None}
    for _code, _name in sigungu_list:
        sigungu_map[_name] = _code
    selected_sigungu = st.selectbox(
        t("시군구", "District"),
        options=list(sigungu_map.keys()),
        index=0,
        disabled=(_area_code_for_sgg is None),  # 시/도가 '전체'면 비활성화
        help=t("먼저 시/도를 선택하면 시군구를 고를 수 있습니다.",
               "Select a province/city first to choose a district."),
    )
    sigungu_code = sigungu_map.get(selected_sigungu)  # 선택한 시군구 코드(없으면 None)

    # 유형(관광지/음식점 등) — API의 contenttypeid(콘텐츠 타입 표준 코드)로 필터링합니다.
    # 한국관광공사 표준 코드:
    #   12=관광지, 14=문화시설, 15=축제/공연/행사, 25=여행코스,
    #   28=레포츠, 32=숙박, 38=쇼핑, 39=음식점
    selected_type = st.selectbox(
        t("유형", "Type"),
        options=list(CONTENT_TYPE_CODES.keys()),  # 아래 CONTENT_TYPE_CODES 표의 이름들
        index=0,
        format_func=lambda ty: TYPE_NAMES_EN[ty] if st.session_state.get("lang") == "English" else ty,
    )

    # '🟢만 보기' 토글 — 켜면 '가능' 판정 장소만 보여줍니다.
    only_green = st.toggle(t("🟢 가능만 보기", "🟢 Show only 'OK'"), value=False)

    st.divider()

    # --- (3) 디버그 옵션 -----------------------------------------------------
    # 실제 API 응답의 '진짜 필드명'을 확인할 때 켜는 스위치입니다.
    debug_mode = st.toggle(
        t("🛠️ 디버그: API 원본 응답 보기", "🛠️ Debug: show raw API response"),
        value=False,
        help=t(
            "켜면 API가 돌려준 원본 데이터를 화면에 그대로 보여줍니다. 실제 필드명 확인용입니다.",
            "When on, shows the raw API data as-is. Useful for checking real field names.",
        ),
    )

    # 검색 실행 버튼
    search_clicked = st.button(
        t("🔍 장소 검색하기", "🔍 Search places"),
        type="primary",
        use_container_width=True,
    )


# =============================================================================
# 5. 메인 화면 — 제목 & 데이터 불러오기
# =============================================================================

# --- 제일 위쪽: 강아지·고양이 대표 이미지 -------------------------------------
# 이미지 파일 경로를 '이 코드 파일이 있는 폴더' 기준으로 잡아, 실행 위치가 달라도
# 항상 찾을 수 있게 합니다.
#   - 배경(흰색)을 투명 처리한 '강아지고양이_투명.png'를 우선 사용해, 앱의 초록
#     배경이 그림 뒤로 자연스럽게 비치도록 합니다. (없으면 원본 png 사용)
from pathlib import Path  # 파일 경로 처리를 위한 표준 라이브러리
_img_dir = Path(__file__).parent
PET_IMG_PATH = _img_dir / "강아지고양이_투명.png"
if not PET_IMG_PATH.exists():
    PET_IMG_PATH = _img_dir / "강아지고양이.png"

if PET_IMG_PATH.exists():
    # 화면 가운데에 작게 배치 (양옆 여백을 크게 줘서 가운데 칸을 좁힘 → 이미지 축소)
    _left, _center, _right = st.columns([2, 1, 2])
    with _center:
        st.image(str(PET_IMG_PATH), width=130)  # 고정 폭 130px (더 작게 하려면 값을 줄이세요)

st.title("🐾 " + t("펫패스(PetPass)", "PetPass"))
st.caption(t(
    "반려동물과 함께 갈 수 있는지, 미리 신호등으로 확인하세요! 🟢가능 · 🟡조건부 · 🔴불가",
    "Check whether you can bring your pet — with a simple traffic light! 🟢 OK · 🟡 Conditional · 🔴 Not allowed",
))

# 인증키가 설정되지 않았으면(배포 시 secrets 누락 등) 먼저 안내합니다.
if not SERVICE_KEY:
    st.error(t(
        "🔑 인증키(SERVICE_KEY)가 설정되지 않았습니다. "
        "로컬은 .streamlit/secrets.toml, 배포 시에는 앱 설정의 Secrets 에 키를 등록하세요.",
        "🔑 SERVICE_KEY is not set. Add it to .streamlit/secrets.toml locally, "
        "or to the app's Secrets settings when deploying.",
    ))

# 검색 결과를 session_state에 저장해 두면, 다른 버튼을 눌러도 목록이 사라지지 않습니다.
if search_clicked and SERVICE_KEY:
    area_code = AREA_CODES.get(selected_area)  # 선택한 지역의 코드 번호
    success, result = fetch_area_based_list(area_code=area_code, sigungu_code=sigungu_code)

    if not success:
        # 실패 시 친절한 에러 메시지 (result 안에 사유가 들어 있음)
        st.error(f"😢 {result}")
        st.session_state["places"] = []
    else:
        st.session_state["places"] = result  # 성공하면 목록 저장

        # --- 디버그: 원본 응답 첫 번째 항목을 그대로 보여주기 --------------------
        if debug_mode and result:
            st.subheader(t("🛠️ 디버그 — API 원본 응답(첫 번째 장소)",
                           "🛠️ Debug — raw API response (first place)"))
            st.info(t(
                "아래에 보이는 '키 이름(field name)'이 실제 API 필드명입니다. "
                "이 이름들을 코드의 judge_pet / 상세 카드 부분에 반영하세요.",
                "The 'key names' shown below are the real API field names. "
                "Reflect them in judge_pet / the detail card in the code.",
            ))
            st.write(result[0])  # 원본 딕셔너리를 그대로 출력


# 저장된 장소 목록을 가져옵니다. (없으면 빈 리스트)
places = st.session_state.get("places", [])


# =============================================================================
# 6. 데이터 정리 (pandas DataFrame) & 신호등 판정
# =============================================================================

if places:
    # --- (사전작업) 각 장소의 '상세 동반조건'을 미리 병합 ----------------------
    #   목록 API에는 동반조건 텍스트가 거의 비어 있어서, 이대로 판정하면 대부분
    #   '🟡 조건부(정보 없음)'가 됩니다. 그래서 상세 API로 각 장소의 조건을 미리
    #   가져와 목록에도 반영해, 목록 단계에서부터 정확한 신호등을 보여줍니다.
    content_ids = tuple(
        str(p.get("contentid") or p.get("contentId") or "")
        for p in places
    )
    # 빈 id는 조회할 필요가 없으니 제외합니다.
    valid_ids = tuple(cid for cid in content_ids if cid)
    conditions_map = fetch_conditions_for_ids(valid_ids) if valid_ids else {}

    # 각 장소 딕셔너리에 상세조건을 합친 '보강된 장소' 목록을 만듭니다.
    enriched_places = []
    for p in places:
        cid = str(p.get("contentid") or p.get("contentId") or "")
        detail = conditions_map.get(cid, {})
        enriched_places.append({**p, **detail})  # 목록정보 + 상세조건 병합

    # 리스트(딕셔너리들)를 표(DataFrame)로 변환 -> 필터링·정렬이 쉬워집니다.
    df = pd.DataFrame(enriched_places)

    # 현재 사용자의 반려동물 정보를 딕셔너리로 묶습니다.
    user = {"weight": weight, "size": size, "breed": breed}

    # 각 장소마다 신호등 판정을 실행해서 새 열(column)로 추가합니다.
    #   (상세조건이 병합된 enriched_places 로 판정해야 목록에서도 정확합니다.)
    signals, colors, reasons_list = [], [], []
    for place in enriched_places:
        signal, color, reasons = judge_pet(user, place)
        signals.append(signal)
        colors.append(color)
        reasons_list.append(reasons)

    df["신호"] = signals
    df["색상"] = colors
    df["사유"] = reasons_list

    # --- '🟢만 보기' 필터 적용 ------------------------------------------------
    if only_green:
        df = df[df["신호"].str.contains("가능")]

    # --- 유형 필터 적용 (선택했을 때만) --------------------------------------
    # 선택한 유형 이름을 표준 코드(contenttypeid)로 바꿔서 정확히 일치하는 행만 남깁니다.
    type_code = CONTENT_TYPE_CODES.get(selected_type)  # "전체"면 None
    if type_code is not None and "contenttypeid" in df.columns:
        df = df[df["contenttypeid"].astype(str) == type_code]

    # 신호등 순서(가능 -> 조건부 -> 불가)로 정렬하면 보기 좋습니다.
    signal_order = {"🟢 가능": 0, "🟡 조건부": 1, "🔴 불가": 2}
    df["_정렬"] = df["신호"].map(signal_order).fillna(3)
    df = df.sort_values("_정렬").reset_index(drop=True)


# =============================================================================
# 7. 메인 영역 — 왼쪽: 결과 목록 / 오른쪽: 지도
# =============================================================================

if not places:
    # 아직 검색하지 않았거나 결과가 없을 때 안내 문구
    st.info(t(
        "👈 왼쪽 사이드바에서 반려동물 정보를 입력하고 **[장소 검색하기]** 를 눌러보세요.",
        "👈 Enter your pet's info in the left sidebar and press **[Search places]**.",
    ))
else:
    # 화면을 왼쪽(목록)과 오른쪽(지도) 두 칸으로 나눕니다. (비율 5:5)
    left_col, right_col = st.columns([5, 5])

    # -------------------------------------------------------------------------
    # (왼쪽) 검색 결과 목록
    # -------------------------------------------------------------------------
    with left_col:
        st.subheader(t(f"📋 검색 결과 ({len(df)}곳)", f"📋 Results ({len(df)})"))

        if len(df) == 0:
            st.warning(t(
                "조건에 맞는 장소가 없습니다. 필터를 바꿔보세요.",
                "No places match your filters. Try changing them.",
            ))

        # 한 곳씩 카드 형태로 보여줍니다.
        for idx, row in df.iterrows():
            place_name = row.get("title", t("이름 없음", "No name"))
            place_addr = row.get("addr1", t("주소 정보 없음", "No address"))
            # contenttypeid(숫자 코드)를 사람이 읽을 유형 이름으로 바꿔서 보여줍니다.
            type_code = str(row.get("contenttypeid", ""))
            place_type_ko = CONTENT_TYPE_NAMES.get(type_code, "유형 미상")
            # 유형 이름도 영어면 번역 (없으면 원래 값)
            place_type = TYPE_NAMES_EN.get(place_type_ko, place_type_ko) \
                if st.session_state.get("lang") == "English" else place_type_ko
            signal = row.get("신호", "🟡 조건부")

            # 컨테이너로 묶되 테두리 대신 얇은 구분선으로 카드를 나눕니다.
            with st.container(border=False):
                st.markdown(f"**{signal_display(signal)}  {place_name}**")
                st.write(f"📍 {place_addr}")
                st.caption(t(f"유형: {place_type}", f"Type: {place_type}"))

                # '상세 보기' 버튼 — 누르면 어떤 장소를 골랐는지 session_state에 저장
                if st.button(t("상세 보기 ▶", "View details ▶"), key=f"detail_{idx}"):
                    st.session_state["selected_place"] = row.to_dict()

            # 카드 사이를 얇은 구분선으로 구분합니다.
            st.markdown(
                "<hr style='margin:6px 0; border:none; border-top:1px solid #d4e6d4;'>",
                unsafe_allow_html=True,
            )

    # -------------------------------------------------------------------------
    # (오른쪽) 지도 — folium 마커를 신호등 색상으로 표시
    # -------------------------------------------------------------------------
    with right_col:
        st.subheader(t("🗺️ 지도", "🗺️ Map"))

        # 지도의 중심 좌표. 결과 중 첫 장소가 있으면 그 위치를, 없으면 서울시청 기준.
        # 【여기를 실제 위경도 필드명으로 바꾸세요】: mapy(위도), mapx(경도) 가 표준
        try:
            center_lat = float(df.iloc[0].get("mapy", 37.5665))
            center_lon = float(df.iloc[0].get("mapx", 126.9780))
        except (ValueError, TypeError, IndexError):
            center_lat, center_lon = 37.5665, 126.9780  # 서울시청 기본값

        m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

        # 각 장소를 지도에 마커로 찍습니다. 마커 색은 신호등 색을 그대로 사용.
        for _, row in df.iterrows():
            try:
                lat = float(row.get("mapy"))
                lon = float(row.get("mapx"))
            except (ValueError, TypeError):
                continue  # 좌표가 없는 장소는 지도에 표시하지 않고 건너뜁니다.

            folium.Marker(
                location=[lat, lon],
                popup=f"{signal_display(row.get('신호', ''))} {row.get('title', '')}",
                tooltip=row.get("title", ""),
                # folium 마커 색: green / orange / red 를 그대로 사용
                icon=folium.Icon(color=row.get("색상", "gray"), icon="paw", prefix="fa"),
            ).add_to(m)

        # folium 지도를 Streamlit 화면에 실제로 그립니다.
        #  - returned_objects=[] : 지도 조작(이동/확대) 값을 되돌려주지 않게 하여
        #    '계속 로딩중(무한 새로고침)' 문제를 막습니다.
        #  - key="place_map" : 지도에 고정 키를 줘서 재실행 시 위젯을 안정적으로 재사용합니다.
        st_folium(
            m,
            width=None,          # 컨테이너 폭에 맞춤(반응형)
            height=450,
            returned_objects=[],
            key="place_map",
        )

    # -------------------------------------------------------------------------
    # (아래) 검색 결과 분석 & 추천 — 지도/목록 밑에 전체 폭으로 표시
    # -------------------------------------------------------------------------
    st.divider()
    st.subheader(t("📊 검색 결과 분석 & 추천", "📊 Analysis & Recommendations"))

    # 신호등 색상별 개수를 셉니다. ('색상' 열: green / orange / red)
    total = len(df)
    green = int((df["색상"] == "green").sum())
    orange = int((df["색상"] == "orange").sum())
    red = int((df["색상"] == "red").sum())

    if total == 0:
        st.warning(t(
            "표시할 결과가 없어 분석을 만들 수 없습니다. 지역이나 유형 필터를 바꿔보세요.",
            "No results to analyze. Try changing the region or type filter.",
        ))
    else:
        # --- (1) 한눈에 보는 지표 --------------------------------------------
        col_a, col_b, col_c = st.columns(3)
        col_a.metric(t("🟢 가능", "🟢 OK"), t(f"{green}곳", f"{green}"))
        col_b.metric(t("🟡 조건부", "🟡 Conditional"), t(f"{orange}곳", f"{orange}"))
        col_c.metric(t("🔴 불가", "🔴 Not allowed"), t(f"{red}곳", f"{red}"))

        # 화면에 쓸 반려동물 표현 (견종이 비어 있으면 무게/크기만 사용)
        size_disp = SIZE_NAMES_EN[size] if st.session_state.get("lang") == "English" else size
        breed_disp = breed_display(breed)
        pet_label = f"{breed_disp} " if breed_disp else ""
        pet_desc = f"{pet_label}({size_disp}, {weight}kg)"
        # 지역 표시(전체 -> 전국 / All regions), 영어면 지역명도 번역
        if selected_area == "전체":
            area_label = t("전국", "all regions")
        else:
            area_label = AREA_NAMES_EN[selected_area] if st.session_state.get("lang") == "English" else selected_area
        green_ratio = round(green / total * 100)

        # --- (2) 분석 설명 글 (자동 생성) ------------------------------------
        analysis_lines = [
            t(
                f"**{area_label}** 지역에서 **{total}곳**을 확인했어요. "
                f"내 반려동물 **{pet_desc}** 기준으로 판정한 결과입니다.",
                f"Checked **{total}** places in **{area_label}**. "
                f"Results are based on your pet **{pet_desc}**.",
            ),
        ]
        if green > 0:
            analysis_lines.append(t(
                f"- 🟢 **바로 갈 수 있는 곳이 {green}곳**({green_ratio}%) 있습니다. "
                f"무게·조건을 모두 통과한 장소예요.",
                f"- 🟢 **{green} places ({green_ratio}%) you can visit right away** — "
                f"they pass both the weight and other conditions.",
            ))
        else:
            analysis_lines.append(t(
                "- 🟢 조건을 모두 통과한 곳은 아직 없어요. "
                "아래 🟡 조건부 장소를 살펴보고 현장 조건을 확인해 보세요.",
                "- 🟢 No place passes every condition yet. "
                "Check the 🟡 conditional places below and confirm on-site.",
            ))
        if orange > 0:
            analysis_lines.append(t(
                f"- 🟡 **조건부가 {orange}곳**입니다. 목줄·이동장·예약 등 "
                "약간의 준비가 필요하거나, 정보가 부족해 현장 확인이 필요한 곳이에요.",
                f"- 🟡 **{orange} conditional places** — they need a bit of preparation "
                "(leash, carrier, reservation) or lack info, so check on-site.",
            ))
        if red > 0:
            analysis_lines.append(t(
                f"- 🔴 **동반 불가가 {red}곳**입니다. 무게 초과이거나 "
                "'동반 불가/금지' 안내가 있는 곳이라 피하는 게 좋아요.",
                f"- 🔴 **{red} not-allowed places** — over the weight limit or marked "
                "'not allowed / prohibited', so best avoided.",
            ))
        st.markdown("\n".join(analysis_lines))

        # --- (3) 추천 글 -----------------------------------------------------
        st.markdown(t("#### 💡 추천", "#### 💡 Recommendations"))

        # df는 이미 '가능 → 조건부 → 불가' 순으로 정렬돼 있습니다.
        # 추천 후보: 가능(green)이 있으면 그 중 상위 3곳, 없으면 조건부 상위 3곳.
        if green > 0:
            recommend_df = df[df["색상"] == "green"].head(3)
            st.markdown(t(
                f"**{pet_desc}** 와(과) 함께라면 아래 **{len(recommend_df)}곳**을 "
                "가장 먼저 추천해요! 👇",
                f"With **{pet_desc}**, we recommend these **{len(recommend_df)}** places first! 👇",
            ))
        elif orange > 0:
            recommend_df = df[df["색상"] == "orange"].head(3)
            st.markdown(t(
                "조건을 모두 만족하는 곳은 없지만, 아래 **조건부 장소**라면 "
                "약간의 준비로 방문할 수 있어요. 방문 전 조건을 꼭 확인하세요. 👇",
                "No place meets every condition, but you can visit these **conditional places** "
                "with a little preparation. Please check the conditions before visiting. 👇",
            ))
        else:
            recommend_df = df.iloc[0:0]  # 빈 표 (추천할 곳 없음)
            st.info(t(
                "이 조건에서는 추천할 만한 곳이 없어요. 😢 "
                "지역을 넓히거나 유형 필터를 바꿔서 다시 검색해 보세요.",
                "No places to recommend under these filters. 😢 "
                "Try a wider region or a different type and search again.",
            ))

        # 추천 장소를 카드로 하나씩 보여줍니다. (판정 사유 1줄 포함)
        for _, row in recommend_df.iterrows():
            r_name = row.get("title", t("이름 없음", "No name"))
            r_addr = row.get("addr1", t("주소 정보 없음", "No address"))
            r_signal = row.get("신호", "")
            r_reasons = row.get("사유", [])
            # 사유 리스트 중 첫 번째를 대표 사유로 보여줍니다.
            reason_text = r_reasons[0] if isinstance(r_reasons, list) and r_reasons else ""
            with st.container(border=False):
                st.markdown(f"**{signal_display(r_signal)} {r_name}**")
                st.caption(f"📍 {r_addr}")
                if reason_text:
                    st.caption(f"✅ {reason_text}")
            # 추천 카드 사이도 얇은 구분선으로 구분합니다.
            st.markdown(
                "<hr style='margin:6px 0; border:none; border-top:1px solid #d4e6d4;'>",
                unsafe_allow_html=True,
            )


# =============================================================================
# 8. 상세 카드 — 선택한 장소의 동반 조건 & 준비물 체크리스트
# =============================================================================

selected = st.session_state.get("selected_place")

if selected:
    st.divider()
    st.header(t(f"📑 상세 정보 — {selected.get('title', '')}",
               f"📑 Details — {selected.get('title', '')}"))

    # 선택한 장소의 고유번호로 '상세 조건' API를 한 번 더 호출합니다.
    content_id = selected.get("contentid") or selected.get("contentId")

    detail = {}
    if content_id:
        ok, detail_result = fetch_detail_pet_tour(content_id)
        if ok:
            detail = detail_result
        else:
            st.warning(detail_result)

    # 디버그 모드면 상세 응답 원본도 보여줍니다.
    if debug_mode and detail:
        st.subheader(t("🛠️ 디버그 — 상세 API 원본 응답", "🛠️ Debug — raw detail API response"))
        st.write(detail)

    # 목록 정보(selected)와 상세 정보(detail)를 합쳐서 하나로 봅니다.
    merged = {**selected, **detail}

    # 상세 카드도 신호등 판정을 다시 계산해 맨 위에 보여줍니다.
    user = {"weight": weight, "size": size, "breed": breed}
    signal, color, reasons = judge_pet(user, merged)

    st.markdown(f"## {signal_display(signal)}")
    # 판정 사유들을 목록으로 출력
    for reason in reasons:
        st.write(f"- {reason}")

    st.divider()

    # 두 칸으로 나눠서 왼쪽은 조건 정보, 오른쪽은 사진 & 체크리스트
    info_col, extra_col = st.columns([6, 4])

    no_info = t("정보 없음", "No info")
    with info_col:
        st.subheader(t("🐾 동반 조건", "🐾 Accompaniment Conditions"))
        # detailPetTour2 응답에서 확인한 실제 필드명 사용
        st.write(t("**동반 가능 반려동물:**", "**Pets allowed:**"),
                 merged.get("acmpyPsblCpam") or no_info)
        st.write(t("**필수 준비물:**", "**Required items:**"),
                 merged.get("acmpyNeedMtr") or no_info)
        st.write(t("**동반 유형:**", "**Accompaniment type:**"),
                 merged.get("acmpyTypeCd") or no_info)
        st.write(t("**기타 안내:**", "**Other info:**"),
                 merged.get("etcAcmpyInfo") or no_info)
        st.write(t("**유의사항:**", "**Cautions:**"),
                 merged.get("relaAcdntRiskMtr") or no_info)

    with extra_col:
        st.subheader(t("🖼️ 사진", "🖼️ Photo"))
        # firstimage(대표이미지) 가 표준
        image_url = merged.get("firstimage")
        if image_url:
            st.image(image_url, use_container_width=True)
        else:
            st.caption(t("등록된 사진이 없습니다.", "No photo available."))

        st.subheader(t("✅ 준비물 체크리스트", "✅ Packing Checklist"))
        st.caption(t("외출 전에 하나씩 확인하세요!", "Check off each item before you head out!"))
        # 기본 준비물 목록 — (한국어, 영어) 쌍. key는 언어와 무관하게 고정(인덱스).
        checklist = [
            ("목줄/리드줄", "Leash / lead"),
            ("배변봉투", "Poop bags"),
            ("이동장(케이지)", "Carrier (crate)"),
            ("물/급수기", "Water / dispenser"),
            ("예방접종 확인", "Vaccination check"),
            ("간식", "Treats"),
        ]
        for i, (ko_item, en_item) in enumerate(checklist):
            st.checkbox(t(ko_item, en_item), key=f"check_{i}")


# =============================================================================
# 9. 푸터 (데이터 출처 & 제작자 표기)
# =============================================================================

st.divider()
st.markdown(
    "<p style='text-align:center; color:gray; font-size:0.85rem;'>"
    + t(
        "데이터 출처: 한국관광공사 반려동물 동반여행 정보(공공데이터포털)",
        "Data source: Korea Tourism Organization — Pet-friendly travel info (data.go.kr)",
    )
    + "</p>",
    unsafe_allow_html=True,
)
