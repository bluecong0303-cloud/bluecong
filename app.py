"""하루쉼 — streamlit run app.py (Python 3.10+)
GitHub 루트에 app.py와 requirements.txt를 업로드하고 Streamlit Cloud로 배포하세요.
설정 방법과 Supabase SQL은 앱의 '배포 설정 안내'에서 확인할 수 있습니다.
외부 DB 미설정 시 명시적인 체험 모드만 제공하며, 영속 저장을 가장하지 않습니다.
"""
import ast
import calendar
import html
import json
import math
import operator
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests
import streamlit as st

SQL = '''create table if not exists public.harushim_records (
  user_id uuid not null references auth.users(id) on delete cascade,
  entry_id text not null,
  payload jsonb not null default '{}'::jsonb,
  primary key (user_id, entry_id)
);
alter table public.harushim_records enable row level security;
create policy "own_select" on public.harushim_records for select to authenticated
using ((select auth.uid()) = user_id);
create policy "own_insert" on public.harushim_records for insert to authenticated
with check ((select auth.uid()) = user_id);
create policy "own_update" on public.harushim_records for update to authenticated
using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "own_delete" on public.harushim_records for delete to authenticated
using ((select auth.uid()) = user_id);'''

CSS = '''<style>
.stApp {background:#f5f8f4;color:#20372d;}
.block-container{padding-top:1.2rem;max-width:1500px;}
.hero{background:#203e32;color:white;border-radius:22px;padding:24px 30px;margin-bottom:18px;}
.hero h1{color:white;margin:0;font-size:2rem}.hero p{margin:6px 0;color:#dceadd}
.brand{font-size:72px;animation:bloom .7s ease-out;}@keyframes bloom{from{opacity:0;transform:scale(.8)}to{opacity:1;transform:scale(1)}}
.cal{width:100%;table-layout:fixed;border-collapse:separate;border-spacing:5px;}
.cal th{font-size:13px;color:#486451;padding:8px}.cal td{vertical-align:top;background:white;border:1px solid #dce6dc;border-radius:10px;height:98px;padding:8px;overflow-wrap:anywhere;}
.cal .free{background:#e0f3dc}.cal .today{border:2px solid #3e7552}.cal .blank{background:transparent;border:0}
.cal small{display:block;margin-top:6px;font-size:11px;color:#385341}.cal b{font-size:14px}
[data-testid="stSidebar"]{background:#eaf0e8;}
.stButton>button{border-radius:12px;}div[data-testid="stMetric"]{background:white;padding:14px;border-radius:14px;}
@media(max-width:650px){.cal td{height:76px;padding:4px}.cal small{font-size:9px}.block-container{padding:1rem .5rem}.hero{padding:18px}}
</style>'''


def now():
    return datetime.now(ZoneInfo('Asia/Seoul'))


def config():
    try:
        return str(st.secrets.get('SUPABASE_URL', '')).rstrip('/'), str(st.secrets.get('SUPABASE_ANON_KEY', ''))
    except Exception:
        return '', ''


def api(path, method='GET', body=None, params=None, auth=True):
    url, key = config()
    headers = {'apikey': key, 'Content-Type': 'application/json'}
    if auth:
        session = st.session_state.auth
        if datetime.now().timestamp() >= session.get('expires_at', 0) - 90:
            r = requests.post(url + '/auth/v1/token?grant_type=refresh_token',
                              headers=headers, json={'refresh_token': session['refresh_token']}, timeout=20)
            if not r.ok:
                raise RuntimeError('로그인이 만료되었습니다. 로그아웃 후 다시 로그인해 주세요.')
            session = r.json()
            session['expires_at'] = datetime.now().timestamp() + session.get('expires_in', 3600)
            st.session_state.auth = session
        headers['Authorization'] = 'Bearer ' + session['access_token']
        headers['Prefer'] = 'resolution=merge-duplicates,return=minimal'
    response = requests.request(method, url + path, headers=headers, json=body, params=params, timeout=20)
    if not response.ok:
        # Never expose access tokens or raw server responses.
        raise RuntimeError(f'연결 또는 인증에 실패했습니다 (HTTP {response.status_code}). 설정과 로그인 정보를 확인해 주세요.')
    return response.json() if response.content else None


def setup():
    with st.expander('⚙️ 배포 설정 안내 · 영구 저장 연결'):
        st.markdown('''1. GitHub 저장소에 **app.py, requirements.txt**를 올리고 Streamlit Community Cloud에서 배포합니다.
2. Supabase 프로젝트를 만든 뒤 SQL Editor에서 아래 SQL을 **처음 한 번** 실행합니다.
3. Supabase Authentication에서 Email 로그인을 활성화합니다. 회원가입 메일 확인을 사용할 경우 메일 링크로 확인한 뒤 앱에서 로그인합니다.
4. Streamlit 앱 **Settings → Secrets**에 아래 두 값을 입력합니다. 공개용 anon 키 또는 publishable 키만 사용하고, **service_role / secret 키는 넣지 마세요.**
5. 인증 사용자별 RLS 정책으로 개인 기록을 분리합니다. 이메일·비밀번호는 Supabase 인증으로 처리하며 GitHub에 저장하지 않습니다.

여러 기기에서 같은 기록을 동시에 수정하면 마지막 저장 내용이 적용됩니다. 공용 기기에서는 반드시 로그아웃하세요.''')
        st.code('SUPABASE_URL = "https://YOUR-PROJECT.supabase.co"\nSUPABASE_ANON_KEY = "YOUR-PUBLIC-ANON-OR-PUBLISHABLE-KEY"', language='toml')
        st.code(SQL, language='sql')


def load_records():
    if st.session_state.get('demo'):
        st.session_state.setdefault('records', {})
        return
    rows, offset = [], 0
    while True:
        batch = api('/rest/v1/harushim_records', params={
            'select': 'entry_id,payload', 'user_id': 'eq.' + st.session_state.auth['user']['id'],
            'order': 'entry_id', 'offset': offset, 'limit': 500})
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    st.session_state.records = {r['entry_id']: r['payload'] for r in rows}


def save_record(key, payload):
    payload = dict(st.session_state.records.get(key, {}), **payload)
    payload['updated_at'] = now().isoformat()
    try:
        if not st.session_state.get('demo'):
            api('/rest/v1/harushim_records', 'POST', {
                'user_id': st.session_state.auth['user']['id'], 'entry_id': key, 'payload': payload})
        st.session_state.records[key] = payload
        st.session_state.saved = now().strftime('%H:%M:%S')
        st.session_state.pop('save_error', None)
    except Exception as exc:
        st.session_state.save_error = str(exc) + ' 입력값은 화면에 남아 있습니다. 연결 복구 후 다시 저장하세요.'


def autosave(key, mapping):
    save_record(key, {field: st.session_state[widget] for field, widget in mapping.items()})


def get_record(key):
    return st.session_state.records.get(key, {})


def text_editor(key, fields):
    record = get_record(key)
    mapping = {f: key + ':' + f for f, _, _ in fields}
    for field, label, multiline in fields:
        widget = mapping[field]
        st.session_state.setdefault(widget, record.get(field, ''))
        fn = st.text_area if multiline else st.text_input
        fn(label, key=widget, on_change=autosave, args=(key, mapping))
    st.caption('입력 후 다른 곳을 클릭하거나 Enter로 확정하면 자동 저장됩니다. 작성 중인 글은 저장 상태를 확인해 주세요.')
    if st.button('💾 지금 저장 / 다시 시도', key=key + ':save'):
        autosave(key, mapping)


def month_records(year, month):
    prefix = f'schedule:{year:04d}-{month:02d}-'
    return {k.split(':', 1)[1]: v for k, v in st.session_state.records.items() if k.startswith(prefix)}


def free_hours(rec):
    return max(0.0, 16 - float(rec.get('hours', 0)))


def calendar_html(year, month, records, analyze):
    parts = ['<table class="cal"><thead><tr>' + ''.join(f'<th>{x}</th>' for x in ['월','화','수','목','금','토','일']) + '</tr></thead><tbody>']
    for week in calendar.monthcalendar(year, month):
        parts.append('<tr>')
        for day in week:
            if not day:
                parts.append('<td class="blank"></td>')
                continue
            d = date(year, month, day)
            rec = records.get(d.isoformat(), {})
            # Unknown days must never be interpreted as free days.
            available = analyze and 'hours' in rec and free_hours(rec) >= 2
            cls = ('free ' if available else '') + ('today' if d == now().date() else '')
            title = html.escape(str(rec.get('title', ''))[:55])
            detail = f'<small>{title}</small>' if title else ''
            if available:
                detail += f'<small>🌱 여유 {free_hours(rec):g}h · 휴식/취미</small>'
            parts.append(f'<td class="{cls}"><b>{day}</b>{detail}</td>')
        parts.append('</tr>')
    return ''.join(parts) + '</tbody></table>'


def schedule():
    st.subheader('🗓️ 일정 · 나만의 한 달')
    today = now().date()
    a, b = st.columns(2)
    year = a.number_input('연도', 2000, 2100, today.year)
    month = b.selectbox('월', list(range(1, 13)), index=today.month - 1)
    month_key = f'{year}-{month}'
    analyze = st.session_state.get('analyzed_month') == month_key
    records = month_records(year, month)
    st.markdown(calendar_html(year, month, records, analyze), unsafe_allow_html=True)
    st.caption('달력 날짜는 표시용입니다. 아래에서 작성할 날짜를 선택하세요. 연한 초록색은 기록된 일정에서 추정한 여유 시간입니다.')
    selected = st.date_input('작성할 날짜', value=date(year, month, min(today.day, calendar.monthrange(year, month)[1])),
                             min_value=date(year, month, 1), max_value=date(year, month, calendar.monthrange(year, month)[1]), key=f'day:{month_key}')
    key = 'schedule:' + selected.isoformat()
    rec = get_record(key)
    mapping = {f: key + ':' + f for f in ['title', 'hours', 'details']}
    defaults = {'title': '', 'hours': 0.0, 'details': ''}
    for field, widget in mapping.items():
        st.session_state.setdefault(widget, rec.get(field, defaults[field]))
    st.text_input('오늘 할 일 (여러 일은 쉼표로 구분)', key=mapping['title'], on_change=autosave, args=(key, mapping))
    st.number_input('식사·이동·학교·일 등을 포함한 총 사용 시간', 0.0, 16.0, step=0.5, key=mapping['hours'], on_change=autosave, args=(key, mapping))
    st.text_area('일정 상세 메모', key=mapping['details'], on_change=autosave, args=(key, mapping))
    st.caption('입력 확정 시 자동 저장 · 하루 24시간에서 수면 8시간을 제외한 16시간을 기준으로 여유 시간을 계산합니다.')
    if st.button('💾 일정 저장 / 재시도'):
        autosave(key, mapping)
        st.rerun()
    if st.button('🌱 날짜 분석', type='primary', use_container_width=True):
        st.session_state.analyzed_month = month_key
        st.rerun()
    if analyze:
        known = [r for r in records.values() if 'hours' in r]
        free = sum(free_hours(r) for r in known)
        st.success(f'작성한 {len(known)}일 기준, 추정 여유 시간은 총 {free:g}시간입니다. 미작성 날짜는 분석에서 제외했습니다.')
        st.write('2시간 이상 여유가 있는 날짜를 연한 초록색으로 표시했습니다. 몸이 피곤하면 휴식, 괜찮다면 가벼운 산책·취미·학습에 활용해 보세요. 실제 생활에 따라 달라지는 단순 추정입니다.')


def health_advice(text, severe=False, persistent=False):
    if severe:
        return '응급 도움', '흉통, 심한 호흡곤란, 갑작스러운 마비·말 어눌함, 의식 저하, 큰 외상 등은 잠으로 해결하려 하지 말고 119 또는 응급실 도움을 받으세요.'
    department = '가정의학과 또는 내과'
    if any(w in text for w in ['손', '손목', '허리', '목', '무릎', '근육', '관절']):
        department = '정형외과 또는 재활의학과'
    if any(w in text for w in ['눈', '시력']):
        department = '안과'
    if persistent:
        return '진료 상담 권장', f'통증이 심하거나 지속·악화되거나 일상을 방해한다면 무리한 작업을 멈추고 {department}에서 상담하세요. 마비·심한 외상 등 응급 증상은 즉시 도움을 받으세요.'
    return '휴식과 관찰', f'반복 작업과 무리한 활동을 줄이고 편한 자세로 쉬어 보세요. 호전되지 않거나 악화되면 {department} 상담이 좋습니다. 글만으로 원인이나 근무 가능 여부를 판단할 수는 없습니다.'


def bedtime(wake, hours):
    minutes = wake.hour * 60 + wake.minute - round(hours * 60)
    return ('전날 ' if minutes < 0 else '당일 ') + f'{(minutes % 1440)//60:02d}:{minutes % 60:02d}'


def health():
    st.subheader('💚 몸 상태 · 오늘은 괜찮으신가요?')
    st.info('의료 진단·처방 또는 근무 적합성 판정이 아닌 일반적인 참고 안내입니다. 실제 상황과 의료진의 판단이 우선입니다.')
    key = 'health:' + now().date().isoformat()
    text_editor(key, [('symptoms', '몸 상태를 적어 주세요 (예: 일을 오래 해서 손목과 허리가 아파요)', True)])
    severe = st.checkbox('지금 흉통·심한 호흡곤란·갑작스러운 마비/말 어눌함·의식 저하·큰 외상이 있어요')
    persistent = st.checkbox('통증이 심하거나 계속되거나 악화되어 일상에 지장이 있어요')
    symptoms = st.session_state.get(key + ':symptoms', '')
    if severe or symptoms.strip():
        heading, advice = health_advice(symptoms, severe, persistent)
        (st.error if severe else st.warning if persistent else st.success)(heading + ' — ' + advice)
        st.markdown('#### 🌙 오늘의 수면 계획')
        wake = st.time_input('내일 일어나야 하는 시각', value=time(7, 0), key='health_wake')
        age = st.radio('수면 안내 기준', ['청소년(13~17세)', '성인(18세 이상)'], horizontal=True, key='health_age')
        hours = 9 if age.startswith('청소년') else 8
        if severe:
            st.error('취침보다 응급 평가가 우선입니다. 잠들어 버티지 말고 즉시 도움을 받으세요.')
        else:
            st.write(f'규칙적인 수면을 위해 **{bedtime(wake, hours)} 취침**을 기준으로 잡아 보세요. 잠들기 30분 전부터 준비하면 좋습니다.')
            st.caption(f'{hours}시간을 확보하는 생활 계획 예시입니다. 청소년은 보통 8~10시간, 성인은 대체로 7~9시간이 필요하며 개인차가 있습니다. 아프다고 무조건 더 오래 자는 것이 치료가 되지는 않습니다.')


def vacation():
    st.subheader('🏖️ 휴가 · 쉬어 갈 계획')
    start = st.date_input('휴가 시작일', key='vac_start')
    end = st.date_input('휴가 종료일', value=start, min_value=start, key='vac_end:' + start.isoformat())
    key = 'vacation:' + start.isoformat()
    text_editor(key, [('title', '휴가 이름', False), ('memo', '휴식·여행 계획', True)])
    if st.button('휴가 기간 저장'):
        rec = dict(get_record(key), start=start.isoformat(), end=end.isoformat())
        save_record(key, rec)
    st.caption('휴가 시작일·종료일은 기간 저장 버튼으로 저장됩니다. 휴가 내용은 자동 저장됩니다.')
    for k, r in sorted(st.session_state.records.items()):
        if k.startswith('vacation:') and r.get('end'):
            st.write(f"🏖️ {r.get('start')} ~ {r.get('end')} · {r.get('title', '')}")


def sleep():
    st.subheader('🌙 잠 · 수면 기록')
    day = st.date_input('기상한 날짜', key='sleep_day')
    key = 'sleep:' + day.isoformat()
    rec = get_record(key)
    a, b = st.columns(2)
    bed = a.time_input('전날 잠든 시각', value=time.fromisoformat(rec.get('bed', '23:00')), key=key + ':bed')
    wake = b.time_input('일어난 시각', value=time.fromisoformat(rec.get('wake', '07:00')), key=key + ':wake')
    duration = ((wake.hour * 60 + wake.minute) - (bed.hour * 60 + bed.minute)) % 1440 / 60
    st.metric('추정 수면 시간', f'{duration:g}시간')
    st.caption('자정을 넘기는 수면을 기준으로 추정합니다. 같은 시각은 0시간으로 계산합니다.')
    quality = st.select_slider('일어났을 때 느낌', ['많이 피곤', '조금 피곤', '보통', '개운함'], key=key + ':quality')
    if st.button('수면 기록 저장'):
        save_record(key, {'bed': bed.strftime('%H:%M'), 'wake': wake.strftime('%H:%M'), 'hours': duration, 'quality': quality})
    st.markdown('#### 저장된 최근 수면')
    for k, r in sorted(st.session_state.records.items(), reverse=True):
        if k.startswith('sleep:'):
            st.write(f"{k.split(':')[1]} · {r.get('hours', 0):g}시간 · {r.get('quality', '')}")


OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Mod: operator.mod}


def calculate(expression):
    if not expression.strip() or len(expression) > 120:
        raise ValueError('수식을 1~120자로 입력하세요.')
    tree = ast.parse(expression, mode='eval')
    if len(list(ast.walk(tree))) > 70:
        raise ValueError('수식이 너무 복잡합니다.')
    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            value = OPS[type(node.op)](walk(node.left), walk(node.right))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = walk(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        else:
            raise ValueError('숫자, 괄호, + - * / % 만 사용할 수 있습니다.')
        if abs(value) > 1e15 or not math.isfinite(value):
            raise ValueError('계산 범위를 초과했습니다.')
        return value
    return walk(tree)


def notes():
    a, b = st.columns([4, 1])
    a.subheader('📝 메모 · 생각을 모으는 곳')
    with b.popover('🧮 계산기', use_container_width=True):
        expression = st.text_input('계산식', placeholder='(12000 + 3000) / 3')
        if st.button('계산'):
            try:
                st.success(f'결과: {calculate(expression):g}')
            except Exception as exc:
                st.error('0으로 나눌 수 없습니다.' if isinstance(exc, ZeroDivisionError) else '올바른 사칙연산 수식을 입력해 주세요.')
    categories = ['게임 관련', '일 관련', '생활 관련', '아이디어']
    categories += sorted({k.split(':', 1)[1] for k in st.session_state.records if k.startswith('note:')} - set(categories))
    category = st.selectbox('메모 분류', categories)
    new = st.text_input('새 분류 이름 (선택)', max_chars=40)
    if st.button('분류 추가') and new.strip():
        save_record('note:' + new.strip(), {'title': new.strip(), 'body': ''})
        st.rerun()
    text_editor('note:' + category, [('title', '제목', False), ('body', '메모', True)])


def login():
    st.markdown('<div class="hero"><div class="brand">🌿</div><h1>하루쉼</h1><p>일정부터 몸과 마음의 휴식까지, 나의 하루를 한곳에.</p></div>', unsafe_allow_html=True)
    setup()
    url, key = config()
    if url and key:
        mode = st.radio('계정', ['로그인', '회원가입'], horizontal=True)
        with st.form('login'):
            email = st.text_input('이메일')
            password = st.text_input('비밀번호', type='password')
            submitted = st.form_submit_button(mode, type='primary')
        if submitted:
            if not email.strip() or len(password) < 8:
                st.error('이메일과 8자 이상의 비밀번호를 입력해 주세요.')
            else:
                try:
                    path = '/auth/v1/token?grant_type=password' if mode == '로그인' else '/auth/v1/signup'
                    result = api(path, 'POST', {'email': email.strip(), 'password': password}, auth=False)
                    if result.get('access_token'):
                        result['expires_at'] = datetime.now().timestamp() + result.get('expires_in', 3600)
                        st.session_state.auth = result
                        st.session_state.demo = False
                        load_records()
                        st.rerun()
                    else:
                        st.success('가입 요청을 접수했습니다. 확인 메일이 있다면 확인 후 로그인해 주세요.')
                except Exception as exc:
                    st.error(str(exc))
    else:
        st.warning('영구 저장을 사용하려면 위 안내에 따라 Supabase를 연결해 주세요.')
    if st.button('둘러보기 · 저장되지 않는 체험 모드'):
        st.session_state.demo = True
        st.session_state.records = {}
        st.rerun()
    st.caption('체험 모드는 현재 세션에서만 동작합니다. 실제 건강 정보는 체험 모드에 입력하지 마세요.')


def main():
    st.set_page_config(page_title='하루쉼 · 나의 생활 관리', page_icon='🌿', layout='wide')
    st.markdown(CSS, unsafe_allow_html=True)
    if not st.session_state.get('auth') and not st.session_state.get('demo'):
        login()
        return
    if 'records' not in st.session_state:
        try:
            load_records()
        except Exception as exc:
            st.error(str(exc))
            if st.button('다시 연결'):
                st.rerun()
            if st.button('로그인 화면으로'):
                st.session_state.clear()
                st.rerun()
            return
    with st.sidebar:
        st.title('🌿 하루쉼')
        st.caption('나를 돌보는 다섯 가지 습관')
        page = st.radio('메뉴', ['🗓️ 일정', '💚 몸 상태', '🏖️ 휴가', '🌙 잠', '📝 메모'], label_visibility='collapsed')
        st.divider()
        st.caption('체험 모드 · 임시 저장' if st.session_state.get('demo') else '🔒 개인 계정 · 클라우드 저장')
        if st.button('🚪 로그아웃', use_container_width=True):
            if st.session_state.get('auth'):
                try:
                    api('/auth/v1/logout', 'POST')
                except Exception:
                    pass
            st.session_state.clear()
            st.rerun()
    title, refresh, helpcol = st.columns([8, 1, 1])
    title.markdown('<div class="hero"><h1>🌿 하루쉼</h1><p>일상을 정리하고, 쉴 시간을 발견하세요.</p></div>', unsafe_allow_html=True)
    if refresh.button('🔄', help='클라우드 기록 새로고침'):
        try:
            load_records()
            for k in list(st.session_state):
                if k.startswith(('schedule:', 'health:', 'note:', 'vacation:', 'sleep:')):
                    del st.session_state[k]
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    with helpcol.popover('❔'):
        st.write('왼쪽 메뉴에서 기능을 선택하세요. 오른쪽 도구에서 기록을 백업할 수 있습니다. 모바일에서는 좌측 상단 메뉴를 펼쳐 주세요.')
    if st.session_state.get('demo'):
        st.warning('체험 모드입니다. 재접속 시 기록이 사라질 수 있습니다. 영구 저장은 Supabase 연결 및 로그인 후 가능합니다.')
    if st.session_state.get('save_error'):
        st.error(st.session_state.save_error)
    elif st.session_state.get('saved'):
        st.caption('✓ 마지막 저장 ' + st.session_state.saved)
    center, tools = st.columns([6, 1.4], gap='large')
    with tools:
        st.markdown('#### 🧰 도구')
        st.write(now().strftime('%Y.%m.%d'))
        st.download_button('📥 내 기록 백업', json.dumps(st.session_state.records, ensure_ascii=False, indent=2),
                           'harushim_backup.json', 'application/json', use_container_width=True)
        st.caption('건강·개인 정보가 포함됩니다. 백업 파일을 안전하게 보관하세요.')
        with st.popover('⚙️ 연결 안내'):
            setup()
        st.markdown('---\n🌱 **오늘의 한마디**\n\n쉬는 시간도 중요한 일정입니다.')
    with center:
        {'🗓️ 일정': schedule, '💚 몸 상태': health, '🏖️ 휴가': vacation, '🌙 잠': sleep, '📝 메모': notes}[page]()


if __name__ == '__main__':
    main()
