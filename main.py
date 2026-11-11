
import streamlit as st
import pandas as pd
import requests
from io import StringIO


# ----------------------------------------
# 1. 기본 설정
# ----------------------------------------
st.set_page_config(
    page_title="서울 연평균 기온 분석",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ 서울 연평균 기온 분석")
st.write(
    "서울의 일별 기온 데이터를 불러와 "
    "연도별 평균 기온을 계산합니다."
)

CSV_URL = (
    "https://raw.githubusercontent.com/greatsong/"
    "modudata/refs/heads/main/data/seoul_daily.csv"
)

MIN_DAYS = 350


# ----------------------------------------
# 2. CSV 데이터 불러오기
# ----------------------------------------
@st.cache_data(ttl=3600)
def load_data():
    response = requests.get(CSV_URL, timeout=20)
    response.raise_for_status()

    text = response.content.decode("utf-8-sig")
    return pd.read_csv(StringIO(text))


try:
    df = load_data()

except requests.exceptions.Timeout:
    st.error(
        "데이터 서버가 20초 이내에 응답하지 않았습니다. "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException:
    st.error(
        "CSV 파일을 불러오지 못했습니다. "
        "인터넷 연결이나 파일 주소를 확인해 주세요."
    )
    st.stop()

except (UnicodeError, pd.errors.ParserError):
    st.error(
        "CSV 파일을 읽을 수 없습니다. "
        "파일 형식과 인코딩을 확인해 주세요."
    )
    st.stop()


if df.empty:
    st.warning("CSV 파일에 데이터가 없습니다.")
    st.stop()


# ----------------------------------------
# 3. 열 이름 확인
# ----------------------------------------
st.subheader("데이터 기본 정보")

st.write("**CSV 열 이름**")
st.write(", ".join(df.columns.tolist()))

required_columns = ["날짜", "평균기온"]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    st.error(
        "필요한 열이 없습니다: "
        + ", ".join(missing_columns)
    )
    st.stop()

st.write(f"**전체 기록 수:** {len(df):,}개")


# ----------------------------------------
# 4. 날짜와 평균 기온 변환
# ----------------------------------------
df["날짜"] = pd.to_datetime(
    df["날짜"],
    format="%Y-%m-%d",
    errors="coerce",
)

df["평균기온"] = pd.to_numeric(
    df["평균기온"],
    errors="coerce",
)

invalid_dates = int(df["날짜"].isna().sum())
missing_temps = int(df["평균기온"].isna().sum())

st.write(f"**날짜 변환 실패:** {invalid_dates:,}개")
st.write(f"**평균 기온 결측값:** {missing_temps:,}개")

valid_dates = df["날짜"].dropna()

if valid_dates.empty:
    st.error("유효한 날짜가 없어 분석할 수 없습니다.")
    st.stop()

start_date = valid_dates.min().strftime("%Y-%m-%d")
end_date = valid_dates.max().strftime("%Y-%m-%d")

col1, col2 = st.columns(2)

col1.metric("기록 시작 날짜", start_date)
col2.metric("기록 마지막 날짜", end_date)


# ----------------------------------------
# 5. 날짜 중복 확인 및 처리
# ----------------------------------------
st.subheader("중복 날짜 확인")

# 날짜가 없는 기록은 중복 비교에서 제외
valid_df = df.dropna(subset=["날짜"]).copy()

duplicate_mask = valid_df.duplicated(
    subset=["날짜"],
    keep=False,
)

duplicate_dates = int(
    valid_df.loc[duplicate_mask, "날짜"].nunique()
)

duplicate_rows = int(
    valid_df.duplicated("날짜").sum()
)

st.write(
    f"**중복된 날짜 수:** {duplicate_dates:,}일"
)
st.write(
    f"**중복으로 제거할 행 수:** {duplicate_rows:,}개"
)

st.info(
    "같은 날짜의 기록이 중복되어 있다면 "
    "평균 기온이 유효한 기록을 우선해 "
    "한 건만 남깁니다. "
    "중복 기록을 모두 평균에 포함하지 않습니다."
)

# 평균 기온이 있는 기록 우선
valid_df["기온유효"] = valid_df["평균기온"].notna()

valid_df = valid_df.sort_values(
    "기온유효",
    ascending=False,
    kind="stable",
)

valid_df = valid_df.drop_duplicates(
    subset=["날짜"],
    keep="first",
).copy()

valid_df = valid_df.drop(columns=["기온유효"])


# ----------------------------------------
# 6. 연도별 유효 날짜 수 계산
# ----------------------------------------
valid_df["연도"] = valid_df["날짜"].dt.year

# 평균 기온이 존재하는 날짜만 유효 날짜로 계산
yearly = (
    valid_df.groupby("연도")
    .agg(
        유효날짜수=("평균기온", "count"),
        연평균기온=("평균기온", "mean"),
    )
    .reset_index()
)

# 350일 이상인 연도만 포함
yearly["분석여부"] = yearly["유효날짜수"].apply(
    lambda count: (
        "포함" if count >= MIN_DAYS else "제외"
    )
)

included = yearly.loc[
    yearly["유효날짜수"] >= MIN_DAYS
].copy()

excluded = yearly.loc[
    yearly["유효날짜수"] < MIN_DAYS
].copy()


# ----------------------------------------
# 7. 분석 대상 요약
# ----------------------------------------
st.subheader("연도별 데이터 검증 결과")

col1, col2, col3 = st.columns(3)

col1.metric("전체 연도", len(yearly))
col2.metric("분석 포함 연도", len(included))
col3.metric("분석 제외 연도", len(excluded))

st.write(
    "**분석 기준:** 평균 기온이 기록된 날짜가 "
    f"연간 {MIN_DAYS}일 이상"
)

st.dataframe(
    yearly[
        ["연도", "유효날짜수", "분석여부"]
    ].rename(
        columns={"유효날짜수": "유효 날짜 수"}
    ),
    hide_index=True,
    use_container_width=True,
)


# ----------------------------------------
# 8. 제외한 연도 확인
# ----------------------------------------
st.subheader("분석에서 제외한 연도")

if excluded.empty:
    st.success("분석에서 제외된 연도가 없습니다.")
else:
    st.warning(
        f"유효 날짜가 {MIN_DAYS}일 미만인 "
        f"{len(excluded)}개 연도를 제외했습니다."
    )

    st.dataframe(
        excluded[
            ["연도", "유효날짜수"]
        ].rename(
            columns={"유효날짜수": "유효 날짜 수"}
        ),
        hide_index=True,
        use_container_width=True,
    )


# ----------------------------------------
# 9. 연평균 기온 계산 결과
# ----------------------------------------
st.subheader("서울 연도별 평균 기온")

if included.empty:
    st.info(
        "유효 날짜가 350일 이상인 연도가 없어 "
        "연평균 기온 결과를 표시할 수 없습니다."
    )
else:
    result = included[
        ["연도", "유효날짜수", "연평균기온"]
    ].copy()

    result = result.rename(
        columns={
            "유효날짜수": "유효 날짜 수",
            "연평균기온": "연평균 기온(℃)",
        }
    )

    result = result.sort_values("연도")

    st.dataframe(
        result,
        hide_index=True,
        use_container_width=True,
        column_config={
            "연도": st.column_config.NumberColumn(
                format="%d"
            ),
            "유효 날짜 수": st.column_config.NumberColumn(
                format="%d"
            ),
            "연평균 기온(℃)": st.column_config.NumberColumn(
                format="%.2f"
            ),
        },
    )

st.caption(
    "연평균 기온은 중복 날짜를 제거한 뒤 "
    "평균 기온이 기록된 날짜만 사용해 계산했습니다. "
    "유효 날짜가 연간 350일 미만인 연도는 제외했습니다."
)
