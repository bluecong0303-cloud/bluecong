"""Streamlit Community Cloud: app.py / requirements.txt. Python 3.10+.
Run locally: streamlit run app.py
No API keys, external services, or persistent student data storage required.
"""
from bisect import bisect_right
from decimal import Decimal, ROUND_FLOOR
import math
import streamlit as st

SEMESTERS = ('1학년 1학기', '1학년 2학기', '2학년 1학기', '2학년 2학기', '3학년 1학기')
FIVE = (1., 2., 3., 4., 5.)
PCT5 = (5., 22., 50., 78., 95.)
PCT9 = (2., 7.5, 17., 31.5, 50., 68.5, 83., 92.5, 98.)
NINE = tuple(float(i) for i in range(1, 10))


def interpolate(value, xs, ys):
    value = min(max(float(value), xs[0]), xs[-1])
    i = min(max(bisect_right(xs, value) - 1, 0), len(xs) - 2)
    t = (value - xs[i]) / (xs[i + 1] - xs[i])
    return ys[i] + t * (ys[i + 1] - ys[i])


def to_nine(grade):
    return interpolate(interpolate(grade, FIVE, PCT5), PCT9, NINE)


def to_five(grade):
    return interpolate(interpolate(grade, NINE, PCT9), PCT5, FIVE)


def required_average(grades, target):
    return (5 * to_five(target) - sum(grades)) / (5 - len(grades))


def roadmap(required, count, mode):
    """Bounded profiles with the exact requested average, before display rounding."""
    if count == 0:
        return []
    if mode == 'balanced' or count == 1:
        return [required] * count
    # Grades get smaller as performance improves. Fixed 0.40 span is not a user input.
    offsets = [0.4 * (i / (count - 1) - 0.5) for i in range(count)]
    if mode == 'rising':
        offsets.reverse()
    lo, hi = -6., 6.
    for _ in range(100):
        shift = (lo + hi) / 2
        values = [min(5., max(1., required + shift + d)) for d in offsets]
        if sum(values) / count < required:
            lo = shift
        else:
            hi = shift
    return [min(5., max(1., required + (lo + hi) / 2 + d)) for d in offsets]


def safe_display(values):
    # Lower numeric grades are better: floor to 2dp so following the shown plan
    # never silently misses the target due to ordinary nearest rounding.
    return [float(Decimal(str(round(v, 10))).quantize(Decimal('0.01'), rounding=ROUND_FLOOR)) for v in values]


def main():
    st.set_page_config(page_title='GRADE PATH | 내신 로드맵', page_icon='🎯', layout='wide')
    st.markdown("""<style>
    .stApp {background:#f5f7fc; color:#17243b;}
    .block-container {max-width:1120px; padding-top:2rem;}
    .hero {position:fixed; top:3.75rem; left:50%; transform:translateX(-50%);
      width:min(1080px,calc(100% - 3rem)); z-index:990; background:#142b50;
      color:white; padding:16px 24px; border-radius:18px;
      box-shadow:0 8px 24px #142b5022; display:flex; justify-content:space-between;
      gap:12px; align-items:center;}
    .hero small {color:#cbdaf2;} .hero strong {font-size:1.8rem;}
    .hero-space {height:125px;}
    .step {background:#edf3ff; border-left:4px solid #456bea;
      padding:14px 16px; margin:10px 0; border-radius:8px;}
    .step b {color:#243d74;} .step small {color:#52617b;}
    [data-testid="stMetric"] {background:white; padding:16px; border-radius:12px;}
    @media(max-width:640px){.hero{top:3.6rem;padding:12px 16px;}
      .hero strong{font-size:1.35rem;} .hero-space{height:130px;}}
    </style>""", unsafe_allow_html=True)

    # Render this placeholder after inputs, but retain its top-of-page position.
    header = st.empty()
    st.markdown('<div class="hero-space"></div>', unsafe_allow_html=True)
    st.title('내 목표까지, GRADE PATH')
    st.caption('5등급제 학기 평균 → 9등급제 참고 환산 → 3학년 1학기까지의 학습 계획')
    st.info('정확한 입시 환산기가 아닌 계획용 시뮬레이터입니다. 모든 학기를 동일 비중으로 계산하며, 낮은 등급 숫자일수록 좋은 성적입니다.')

    with st.container(border=True):
        st.subheader('01 · 성적과 목표 입력')
        completed = st.selectbox('성적이 나온 마지막 학기', options=range(1, 6),
            format_func=lambda n: SEMESTERS[n-1], index=1,
            help='해당 학기까지 연속으로 입력합니다. 이후 학기의 성적은 입력받지 않습니다.')
        columns = st.columns(min(completed, 3))
        grades = []
        for i in range(completed):
            with columns[i % len(columns)]:
                value = st.number_input(SEMESTERS[i] + ' 평균 · 5등급제', min_value=1.0,
                    max_value=5.0, value=None, step=0.01, format='%.2f',
                    placeholder='1.00 ~ 5.00', key=f'grade_{i}')
                grades.append(value)
        target = st.number_input('최종 목표 평균 · 9등급제 참고 환산 기준', min_value=1.0,
            max_value=9.0, value=None, step=0.01, format='%.2f',
            placeholder='예: 3.00', key='target',
            help='3학년 1학기까지의 전체 학기 평균을 환산한 값입니다. 목표 숫자 이하가 되면 달성으로 봅니다.')

    valid = all(g is not None for g in grades)
    current = sum(grades) / completed if valid else None
    number = f'{to_nine(current):.2f}등급' if valid else '성적 입력 대기'
    detail = f'현재 {completed}개 학기 평균 · 5등급제 {current:.2f}' if valid else '완료한 모든 학기의 평균을 입력해 주세요'
    header.markdown(f'<div class="hero"><div><small>현재 성적 · 9등급제 참고 추정</small><br><strong>{number}</strong></div><div><small>{detail}<br>공식·대학별 환산 결과가 아닙니다</small></div></div>', unsafe_allow_html=True)

    if not valid:
        st.warning('선택한 마지막 학기까지 모든 성적을 입력하면 현재 성적과 로드맵이 표시됩니다.')
    elif target is None:
        st.info('최종 목표등급을 입력하면 세 가지 로드맵을 동시에 비교할 수 있습니다.')
    else:
        render_results(grades, target)

    with st.expander('환산 방식 · 계산 기준 · 한계 확인'):
        st.markdown("""
**공식 환산표는 아닙니다.** 학기 평균만으로는 과목별 석차, 수강 인원, 이수학점을 알 수 없으므로 정확한 9등급제 평균을 복원할 수 없습니다.

- 5등급제 비율은 **10·24·32·24·10%**, 9등급제 비율은 **4·7·12·17·20·17·12·7·4%**를 기준으로 삼았습니다.
- 각 구간의 대표 백분위(상위 누적 비율의 구간 중간값)를 사용합니다. 5등급제는 **5·22·50·78·95%**, 9등급제는 **2·7.5·17·31.5·50·68.5·83·92.5·98%**입니다.
- 5등급 평균 → 대표 백분위 선형 보간 → 9등급 대표값 선형 보간 순서로 추정합니다. 학기 평균에 이 방식을 적용하는 것 자체가 단순화 가정입니다.
- 따라서 5등급제 1.00은 약 **1.55**, 3.00은 **5.00**, 5.00은 약 **8.45**로 추정됩니다. 9등급제 1.00을 정확히 만들 수 있는 모형이 아닙니다.
- 전체 성적은 **5등급제 학기 평균들을 먼저 평균낸 후 환산**합니다. 학기별 환산값의 평균이 아닙니다.
- 필요 남은 평균 = (목표의 5등급제 역환산값 × 5 − 완료 학기 성적 합) ÷ 남은 학기 수.
- 상승/선공 모드는 기본적으로 첫 학기와 마지막 학기에 0.40등급 차이를 두되, 1~5 범위에서 조정하며 필요한 평균을 보존합니다. 경계에서는 차이가 줄거나 동일해질 수 있습니다.
- 학기 목표는 소수 둘째 자리에서 보수적으로 내림하여 보여줍니다. 따라서 표시된 계획을 지키면 계산상 목표보다 조금 더 좋아질 수 있습니다. 9등급제 추정 표시는 반올림한 참고값입니다.
- 성적 입력값을 앱에서 파일·데이터베이스에 저장하거나 외부 API로 전송하지 않습니다. 공개 앱에는 이름·학교 등 개인정보를 입력하지 마세요.

**비율 참고:** [EBS 입시자료집](https://www.kyobit.com/news/download.php?filename=2028대비+EBSi+설명회+자료집.pdf&idxno=641&savefilename=1486_641.pdf&subUploadDir=202508%2F) · [5·9등급 구간 비교](https://smithlab.co.kr/calculator/naesin-grade-calculator/)

**배포:** 두 파일을 GitHub 저장소 최상위에 올리고 Streamlit Community Cloud에서 해당 저장소를 연결한 뒤 시작 파일을 `app.py`로 지정하세요. 의존성 파일명은 반드시 **requirements.txt**(s 포함)입니다. Python 3.10 이상을 사용하세요.
""")


def render_results(grades, target):
    remaining = 5 - len(grades)
    best = to_nine((sum(grades) + remaining) / 5)
    worst = to_nine((sum(grades) + 5 * remaining) / 5)
    st.subheader('02 · 목표 달성 진단')
    a, b, c = st.columns(3)
    a.metric('최종 목표 · 9등급제', f'{target:.2f}')
    b.metric('남은 학기', f'{remaining}개')
    c.metric('가능한 최선 · 9등급제 추정', f'{best:.2f}')
    if remaining == 0:
        result = to_nine(sum(grades) / 5)
        if result <= target + 1e-9:
            st.success(f'5개 학기가 모두 완료되었습니다. 최종 추정 {result:.2f}등급으로 목표를 달성했습니다.')
        else:
            st.warning(f'5개 학기가 모두 완료되었습니다. 최종 추정 {result:.2f}등급으로 목표에 미달합니다. 남은 학기가 없어 로드맵은 생성하지 않습니다.')
        return
    if target < best - 1e-9:
        st.error(f'현재 입력과 이 추정 모형에서는 목표를 달성하기 어렵습니다. 남은 {remaining}개 학기를 모두 5등급제 1.00로 받아도 최종 추정은 {best:.2f}등급입니다.')
        st.caption('등급 숫자가 낮을수록 좋은 성적입니다. 목표 숫자를 높이거나 입력 성적을 확인하세요. 실제 입시 가능 여부를 뜻하지는 않습니다.')
        return
    if target >= worst - 1e-9:
        required = 5.0
        st.success('남은 학기가 모두 5.00이어도 이 모형에서는 목표 이내입니다. 세 모드는 최대 허용 성적인 5.00으로 같아집니다. 이는 학습을 줄이라는 권고가 아닙니다.')
    else:
        required = min(5., max(1., required_average(grades, target)))
        st.success(f'계산상 달성 가능합니다. 남은 학기 평균을 5등급제 {required:.3f}등급 이하로 맞추세요.')
    st.subheader('03 · 나에게 맞는 세 가지 페이스')
    st.caption('굵은 수치는 실제 입력 기준인 5등급제 학기 평균 목표입니다. 각 계획은 별개의 대안이며 동시에 수행하는 계획이 아닙니다.')
    modes = [('balanced', '⚖️ 균형 페이스', '매 학기 비슷하게, 흔들림 없이'),
             ('rising', '📈 꾸준한 상승', '시작은 현실적으로, 뒤로 갈수록 성적 향상'),
             ('front', '🚀 선공후여유', '초반에 집중하고, 뒤에는 부담 완화')]
    cols = st.columns(3)
    for col, (key, title, description) in zip(cols, modes):
        plan = safe_display(roadmap(required, remaining, key))
        with col:
            with st.container(border=True):
                st.subheader(title)
                st.caption(description)
                for semester, grade in zip(SEMESTERS[len(grades):], plan):
                    st.markdown(f'<div class="step">{semester}<br><b>5등급제 {grade:.2f} 이하</b><br><small>9등급제 추정 {to_nine(grade):.2f}</small></div>', unsafe_allow_html=True)
                final = to_nine((sum(grades) + sum(plan)) / 5)
                st.metric('계획대로 받았을 때 · 최종 추정', f'{final:.2f}등급')
                st.caption('목표 달성 ✓' if final <= target + 1e-8 else '계산값을 확인해 주세요')
    if remaining == 1:
        st.caption('남은 학기가 하나이므로 세 모드의 목표 성적이 동일합니다.')


if __name__ == '__main__':
    main()
