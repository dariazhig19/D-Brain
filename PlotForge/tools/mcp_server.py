# -*- coding: utf-8 -*-
"""
BimOn-PlotForge MCP 서버 — 순수 Python 3.8 stdio JSON-RPC (외부 의존성 없음).
PlotForge (대지 배치 자동화, Site Layout Automation) — BimOn MCP 스위트 편입.

연결 모델: BimOn-Revit/AutoCAD/Forma 와 동일한 "라이브 앱" 방식.
  - 이 서버가 WebSocket 브리지(ws://localhost:5179)를 백그라운드로 호스팅한다.
  - 열려 있는 PlotForge 앱(브라우저, http://localhost:5178)이 클라이언트로 접속한다.
  - 도구 호출 → 브리지로 코드를 보내 살아있는 앱 컨텍스트에서 실행 → 결과를 동기 회수.
  (Revit 애드인은 앱 안에서 리스너를 열지만 브라우저는 소켓을 못 열어 방향만 반대다.
   사용자에겐 동일: 앱을 열어두면 Claude가 실시간 조작 — 헤드리스도 파일 폴링도 버튼도 없음.)

기본 도구 plotforge_execute_script 는 스위트의 execute_script 대응(앱에서 JS 실행).
시맨틱 도구들은 앱 상태(window.__pf.dump/load)를 읽고 되돌려 써서 조작하며,
plotforge_run_layout 은 앱의 실제 엔진(autoPlace/generateRoads)을 그대로 구동한다.

등록: 프로젝트 루트 .mcp.json → {"mcpServers":{"BimOn-PlotForge":{"command":"python","args":["tools/mcp_server.py"]}}}
"""
import base64
import hashlib
import json
import os
import socket
import struct
import sys
import threading
import time

WS_PORT = int(os.environ.get('PLOTFORGE_WS_PORT', '5179'))
APP_URL = os.environ.get('PLOTFORGE_APP_URL', 'http://localhost:5178')
_WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
NO_APP = ('PlotForge 앱이 연결되어 있지 않습니다. 브라우저에서 %s 를 여세요 '
          '(실행.bat). 앱이 자동으로 이 서버에 접속합니다.' % APP_URL)

PALETTE = ['#e57373', '#64b5f6', '#81c784', '#ffb74d', '#ba68c8',
           '#4db6ac', '#f06292', '#a1887f', '#90a4ae', '#dce775']
DIRS = {'N': 0, 'NE': 45, 'E': 90, 'SE': 135, 'S': 180, 'SW': 225, 'W': 270, 'NW': 315}
RULE_KINDS = ['nearRoad', 'setback', 'distanceTo', 'adjacentCount', 'directionOf',
              'sameRowCol', 'openSide', 'windSide', 'centerOf', 'between', 'distanceToAnchor']
CATS = ['building', 'equipment', 'block', 'road', 'rack', 'tunnel', 'conduit']

_seq = [0]


def uid(prefix):
    _seq[0] += 1
    return '%s_m%d_%d' % (prefix, int(time.time()) % 100000, _seq[0])


# ---------- WebSocket 브리지 (순수 파이썬 — hashlib/base64/struct/socket만) ----------

class Bridge:
    """MCP 서버가 호스팅하는 로컬 WS 서버. 라이브 앱 1개와 요청/응답을 중계한다."""

    def __init__(self):
        self._client = None            # 현재 접속 소켓
        self._cli_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._pending = {}             # id -> {'ev': Event, 'box': [msg]}
        self._pend_lock = threading.Lock()
        self._counter = 0

    def start(self, port):
        threading.Thread(target=self._serve, args=(port,), daemon=True).start()

    # --- 접속 수락 ---
    def _serve(self, port):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('127.0.0.1', port))
            srv.listen(1)
        except Exception as e:  # 포트 점유 등 — 브리지 없이도 서버는 살아있게(도구가 NO_APP 반환)
            sys.stderr.write('PlotForge 브리지 기동 실패(:%d): %s\n' % (port, e))
            return
        while True:
            try:
                conn, _ = srv.accept()
            except Exception:
                continue
            try:
                if self._handshake(conn):
                    with self._cli_lock:
                        old, self._client = self._client, conn
                    if old:
                        try:
                            old.close()
                        except Exception:
                            pass
                    threading.Thread(target=self._reader, args=(conn,), daemon=True).start()
                else:
                    conn.close()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def _handshake(self, conn):
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = conn.recv(1024)
            if not chunk:
                return False
            data += chunk
            if len(data) > 65536:
                return False
        key = None
        for line in data.decode('latin1').split('\r\n'):
            if line.lower().startswith('sec-websocket-key:'):
                key = line.split(':', 1)[1].strip()
                break
        if not key:
            return False
        accept = base64.b64encode(
            hashlib.sha1((key + _WS_GUID).encode()).digest()).decode()
        conn.sendall((
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\nConnection: Upgrade\r\n'
            'Sec-WebSocket-Accept: %s\r\n\r\n' % accept).encode())
        return True

    # --- 프레임 수신 ---
    def _reader(self, conn):
        try:
            while True:
                msg = self._recv_message(conn)
                if msg is None:
                    break
                self._on_message(msg)
        finally:
            with self._cli_lock:
                if self._client is conn:
                    self._client = None
            try:
                conn.close()
            except Exception:
                pass

    @staticmethod
    def _recv_exact(conn, n):
        buf = b''
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_message(self, conn):
        """연속 프레임을 재조립해 하나의 텍스트 메시지를 돌려준다. 종료 시 None."""
        chunks = []
        while True:
            hdr = self._recv_exact(conn, 2)
            if hdr is None:
                return None
            b0, b1 = hdr[0], hdr[1]
            fin = b0 & 0x80
            opcode = b0 & 0x0f
            masked = b1 & 0x80
            length = b1 & 0x7f
            if length == 126:
                ext = self._recv_exact(conn, 2)
                if ext is None:
                    return None
                length = struct.unpack('>H', ext)[0]
            elif length == 127:
                ext = self._recv_exact(conn, 8)
                if ext is None:
                    return None
                length = struct.unpack('>Q', ext)[0]
            mask = self._recv_exact(conn, 4) if masked else b''
            if masked and mask is None:
                return None
            payload = self._recv_exact(conn, length) if length else b''
            if length and payload is None:
                return None
            if masked and payload:
                payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
            if opcode == 0x8:            # close
                return None
            if opcode == 0x9:            # ping → pong
                self._send_frame(conn, payload, 0xA)
                continue
            if opcode == 0xA:            # pong
                continue
            chunks.append(payload)       # text(1)/binary(2)/continuation(0)
            if fin:
                return b''.join(chunks).decode('utf-8', 'replace')

    def _send_frame(self, conn, data, opcode=0x1):
        if isinstance(data, str):
            data = data.encode('utf-8')
        n = len(data)
        if n < 126:
            header = struct.pack('>BB', 0x80 | opcode, n)
        elif n < 65536:
            header = struct.pack('>BBH', 0x80 | opcode, 126, n)
        else:
            header = struct.pack('>BBQ', 0x80 | opcode, 127, n)
        with self._send_lock:
            conn.sendall(header + data)

    def _on_message(self, text):
        try:
            msg = json.loads(text)
        except Exception:
            return
        if not isinstance(msg, dict):
            return
        rid = msg.get('id')
        with self._pend_lock:
            p = self._pending.pop(rid, None)
        if p:
            p['box'].append(msg)
            p['ev'].set()

    # --- 요청/응답 ---
    def call(self, code, timeout=25):
        with self._cli_lock:
            conn = self._client
        if conn is None:
            raise RuntimeError(NO_APP)
        with self._pend_lock:
            self._counter += 1
            rid = 'c%d' % self._counter
            ev = threading.Event()
            box = []
            self._pending[rid] = {'ev': ev, 'box': box}
        try:
            self._send_frame(conn, json.dumps({'id': rid, 'code': code}, ensure_ascii=False))
        except Exception as e:
            with self._pend_lock:
                self._pending.pop(rid, None)
            raise RuntimeError('앱 전송 실패(연결 끊김?): %s' % e)
        if not ev.wait(timeout):
            with self._pend_lock:
                self._pending.pop(rid, None)
            raise RuntimeError('앱 응답 시간 초과(%ss). 앱이 열려 있고 응답 가능한지 확인하세요.' % timeout)
        res = box[0]
        if res.get('error'):
            raise RuntimeError('앱 오류: %s' % res['error'])
        return res.get('result')


BRIDGE = Bridge()


# ---------- 프로젝트 상태 (라이브 앱이 단일 진실) ----------

def load():
    """현재 앱의 프로젝트를 객체로 회수 (window.__pf.dump)."""
    d = BRIDGE.call('return __pf.dump()')
    if not isinstance(d, dict):
        raise RuntimeError('앱에서 프로젝트를 읽지 못했습니다.')
    return d


def save(d):
    """프로젝트를 앱에 통째로 반영 (undo 1스텝, 화면 즉시 갱신)."""
    BRIDGE.call('return __pf.load(%s)' % json.dumps(d, ensure_ascii=False))


def type_by_name(d, name):
    for t in d['buildingTypes']:
        if t['name'] == name:
            return t
    raise RuntimeError('타입 없음: %s (등록: %s)' % (name, ', '.join(x['name'] for x in d['buildingTypes'])))


def cells(m, cell_size, mode='ceil'):
    import math
    v = m / cell_size
    return max(1, math.ceil(v - 1e-9) if mode == 'ceil' else round(v))


# ---------- 도구 구현 ----------

def t_new_project(a):
    w, h = float(a['width_m']), float(a['height_m'])
    cs = float(a.get('cell_size_m', 2))
    d = {
        'schemaVersion': 2,
        'site': [{'x': 0, 'y': 0}, {'x': w, 'y': 0}, {'x': w, 'y': h}, {'x': 0, 'y': h}],
        'cellSize': cs, 'maxCoverage': a.get('max_coverage_pct'),
        'roadNetwork': [], 'roadPattern': a.get('road_pattern', 'loop'), 'entryCell': None,
        'windDir': None, 'anchors': [], 'corridors': [], 'clearances': [],
        'roadParams': {'widthM': None, 'ringOffsetM': None},
        'buildingTypes': [], 'rules': [], 'sequence': [],
        'alternatives': [], 'activeAltId': None,
    }
    save(d)
    return '프로젝트 생성: %.0f×%.0fm, 셀 %.1fm (%d×%d셀) → 앱에 반영됨' % (
        w, h, cs, int(w / cs), int(h / cs))


def t_add_type(a):
    d = load()
    name = a['name']
    if any(t['name'] == name for t in d['buildingTypes']):
        raise RuntimeError('이미 존재하는 타입: ' + name)
    cs = d['cellSize']
    w, h = cells(float(a['width_m']), cs), cells(float(a['height_m']), cs)
    t = {'id': uid('t'), 'name': name, 'w': w, 'h': h,
         'category': a.get('category', 'building'),
         'color': a.get('color') or PALETTE[len(d['buildingTypes']) % len(PALETTE)]}
    d['buildingTypes'].append(t)
    save(d)
    return '타입 추가: %s %s×%sm → %d×%d셀 (%s)' % (name, a['width_m'], a['height_m'], w, h, t['category'])


def t_add_block(a):
    d = load()
    name = a['name']
    if any(t['name'] == name for t in d['buildingTypes']):
        raise RuntimeError('이미 존재하는 타입: ' + name)
    cs = d['cellSize']
    members = []
    for m in a['members']:
        mt = type_by_name(d, m['type'])
        members.append({'typeId': mt['id'],
                        'dc': cells(float(m['dx_m']), cs, 'round') if m['dx_m'] else 0,
                        'dr': cells(float(m['dy_m']), cs, 'round') if m['dy_m'] else 0,
                        'w': mt['w'], 'h': mt['h']})
    # dc/dr은 0 기준 정규화 + bbox 산출
    minc = min(m['dc'] for m in members)
    minr = min(m['dr'] for m in members)
    for m in members:
        m['dc'] -= minc
        m['dr'] -= minr
    w = max(m['dc'] + m['w'] for m in members)
    h = max(m['dr'] + m['h'] for m in members)
    # 멤버 겹침 검사
    occ = set()
    for m in members:
        for rr in range(m['dr'], m['dr'] + m['h']):
            for cc in range(m['dc'], m['dc'] + m['w']):
                if (cc, rr) in occ:
                    raise RuntimeError('멤버 겹침: %s 위치를 조정하세요' % a['members'][members.index(m)]['type'])
                occ.add((cc, rr))
    d['buildingTypes'].append({'id': uid('t'), 'name': name, 'kind': 'block',
                               'w': w, 'h': h, 'color': '#546e7a', 'members': members})
    save(d)
    return '블록 추가: %s — 멤버 %d개, bbox %d×%d셀 (%.0f×%.0fm)' % (name, len(members), w, h, w * cs, h * cs)


def t_add_rule(a):
    d = load()
    kind = a['kind']
    if kind not in RULE_KINDS:
        raise RuntimeError('kind는 %s 중 하나' % '/'.join(RULE_KINDS))
    t = type_by_name(d, a['type'])
    r = {'id': uid('r'), 'buildingTypeId': t['id'], 'kind': kind,
         'mode': a.get('mode', 'hard')}
    if r['mode'] == 'soft':
        r['weight'] = int(a.get('weight', 20))
    if kind in ('distanceTo', 'adjacentCount', 'directionOf', 'sameRowCol', 'between'):
        r['targetType'] = type_by_name(d, a['target'])['id']
    if kind == 'between':
        r['targetType2'] = type_by_name(d, a['target2'])['id']
    if kind == 'distanceToAnchor':
        anc = next((x for x in d['anchors'] if x['name'] == a['anchor']), None)
        if not anc:
            raise RuntimeError('앵커 없음: %s' % a.get('anchor'))
        r['anchorId'] = anc['id']
    if kind in ('nearRoad', 'setback'):
        r['basis'] = a.get('basis', 'any')
    if kind == 'openSide' or kind == 'directionOf':
        r['dir'] = a.get('dir', 'S')
    if kind == 'sameRowCol':
        r['axis'] = a.get('axis', 'row')
    if kind == 'windSide':
        r['side'] = a.get('side', 'down')
    if 'gap_m' in a and a['gap_m'] is not None:
        r['gapM'] = float(a['gap_m'])
    elif kind in ('nearRoad', 'setback', 'openSide', 'directionOf', 'adjacentCount',
                  'windSide', 'centerOf', 'between'):
        r['gapM'] = 0.0 if kind == 'windSide' else float(a.get('gap_m', 0) or 0)
    if kind in ('distanceTo', 'distanceToAnchor'):
        r['minM'] = float(a.get('min_m', 0) or 0)
        r['maxM'] = None if a.get('max_m') is None else float(a['max_m'])
        if r['maxM'] is not None and r['minM'] > r['maxM']:
            raise RuntimeError('min_m > max_m')
    if kind == 'adjacentCount':
        r['min'] = int(a.get('min_count', 0))
        r['max'] = None if a.get('max_count') is None else int(a['max_count'])
    d['rules'].append(r)
    save(d)
    return '규칙 추가(%s): %s — %s' % (r['mode'], t['name'], kind)


def t_set_sequence(a):
    d = load()
    d['sequence'] = [type_by_name(d, n)['id'] for n in a['types']]
    save(d)
    return '배치 순서 %d개 설정: %s' % (len(d['sequence']), ' → '.join(a['types']))


def t_set_wind(a):
    d = load()
    v = a['direction'].upper()
    d['windDir'] = None if v in ('NONE', '없음') else DIRS[v]
    save(d)
    return '풍향: %s' % ('없음' if d['windDir'] is None else v)


def t_add_anchor(a):
    d = load()
    cs = d['cellSize']
    c, r = int(float(a['x_m']) / cs), int(float(a['y_m']) / cs)
    d['anchors'].append({'id': uid('a'), 'name': a['name'], 'c': c, 'r': r})
    save(d)
    return '앵커 추가: %s @(%sm, %sm) → 셀(%d,%d)' % (a['name'], a['x_m'], a['y_m'], c, r)


def t_add_clearance(a):
    d = load()
    if a['a'] not in CATS or a['b'] not in CATS:
        raise RuntimeError('카테고리는 %s 중' % '/'.join(CATS))
    d['clearances'].append({'id': uid('cl'), 'a': a['a'], 'b': a['b'], 'minM': float(a['min_m'])})
    save(d)
    return '클리어런스: %s ↔ %s ≥ %sm' % (a['a'], a['b'], a['min_m'])


def t_set_roads(a):
    d = load()
    if 'pattern' in a and a['pattern']:
        if a['pattern'] not in ('comb', 'grid', 'loop'):
            raise RuntimeError('pattern은 comb/grid/loop')
        d['roadPattern'] = a['pattern']
    if 'width_m' in a:
        d['roadParams']['widthM'] = None if a['width_m'] is None else float(a['width_m'])
    if 'ring_offset_m' in a:
        d['roadParams']['ringOffsetM'] = None if a['ring_offset_m'] is None else float(a['ring_offset_m'])
    d['roadNetwork'] = []  # 파라미터 변경 → 다음 run_layout에서 재생성
    save(d)
    return '도로 설정: %s, 폭 %s, 링 %s' % (d['roadPattern'], d['roadParams']['widthM'], d['roadParams']['ringOffsetM'])


def t_run_layout(a):
    seed = int(a.get('seed', 1))
    roads = bool(a.get('roads', True))
    res = BRIDGE.call('return __pf.runLayout(%s)' % json.dumps({'seed': seed, 'roads': roads}),
                      timeout=int(a.get('timeout_seconds', 120)))
    lines = ['배치 실행 완료 (시드 %d, %dms)' % (seed, res['ms']),
             '배치: %d/%d동, 충전율 %.1f%%, 점수 %d, hard 위반 %d' % (
                 res['placed'], res['target'], res['fillRatePct'], res['score'], res['hardViolations'])]
    if res.get('unplaced'):
        lines.append('미배치: ' + ', '.join(res['unplaced']))
    lines.append('앱 화면에 바로 반영되었습니다 (%s, 되돌리기 Ctrl+Z).' % APP_URL)
    return '\n'.join(lines)


def t_execute_script(a):
    code = a['code']
    res = BRIDGE.call(code, timeout=int(a.get('timeout_seconds', 25)))
    if res is None:
        return '(결과 없음 — return 문으로 값을 돌려주세요)'
    if isinstance(res, str):
        return res
    return json.dumps(res, ensure_ascii=False, indent=1)


def t_status(_a):
    res = BRIDGE.call('return __pf.status()')
    return json.dumps(res, ensure_ascii=False, indent=1)


def t_summary(_a):
    d = load()
    byid = {t['id']: t['name'] for t in d['buildingTypes']}
    blocks = [t for t in d['buildingTypes'] if t.get('kind') == 'block']
    site = d.get('site') or [{'x': 0}, {}, {'x': 0, 'y': 0}]
    lines = [
        '부지: %.0f×%.0fm, 셀 %.1fm' % (site[2]['x'], site[2]['y'], d['cellSize']),
        '타입 %d개 (블록 %d): %s' % (len(d['buildingTypes']), len(blocks),
                                     ', '.join(t['name'] for t in d['buildingTypes'][:15])
                                     + ('…' if len(d['buildingTypes']) > 15 else '')),
        '규칙 %d개, 앵커 %d, 클리어런스 %d' % (len(d['rules']), len(d['anchors']), len(d['clearances'])),
        '풍향: %s / 도로: %s 폭%s 링%s' % (d['windDir'], d['roadPattern'],
                                            d['roadParams']['widthM'], d['roadParams']['ringOffsetM']),
        '순서(%d): %s' % (len(d['sequence']), ' → '.join(byid.get(i, i) for i in d['sequence'])),
    ]
    for alt in d.get('alternatives', []):
        lines.append('대안 "%s": %d동 배치' % (alt.get('name', '?'), len(alt.get('placements', []))))
    return '\n'.join(lines)


# ---------- MCP 프로토콜 (stdio, 줄 단위 JSON-RPC 2.0) ----------

def S(desc, props, req):
    return {'description': desc,
            'inputSchema': {'type': 'object', 'properties': props, 'required': req}}


P = lambda t, d: {'type': t, 'description': d}  # noqa: E731

TOOLS = {
    'plotforge_new_project': (t_new_project, S(
        '새 프로젝트 생성 (직사각 부지). 앱의 현재 작업을 덮어씀 (앱을 먼저 열어둘 것)',
        {'width_m': P('number', '부지 가로(m)'), 'height_m': P('number', '부지 세로(m)'),
         'cell_size_m': P('number', '셀 크기(m/셀), 기본 2'),
         'road_pattern': P('string', 'comb|grid|loop (기본 loop)'),
         'max_coverage_pct': P('number', '건폐율 상한 % (선택)')},
        ['width_m', 'height_m'])),
    'plotforge_add_type': (t_add_type, S(
        '건물 타입 추가 (치수는 m — 셀로 올림 환산)',
        {'name': P('string', '고유 이름'), 'width_m': P('number', '가로 m'),
         'height_m': P('number', '세로 m'),
         'category': P('string', 'building|equipment (클리어런스 카테고리, 기본 building)'),
         'color': P('string', '#rrggbb (선택)')},
        ['name', 'width_m', 'height_m'])),
    'plotforge_add_block': (t_add_block, S(
        '블록(복합 타입) 추가 — 기존 타입들을 상대좌표(m)로 묶음. 내부 레이아웃 고정',
        {'name': P('string', '블록 이름'),
         'members': {'type': 'array', 'description': '멤버 목록',
                     'items': {'type': 'object', 'properties': {
                         'type': P('string', '기존 타입 이름'),
                         'dx_m': P('number', '블록 내 x 오프셋(m)'),
                         'dy_m': P('number', '블록 내 y 오프셋(m)')},
                         'required': ['type', 'dx_m', 'dy_m']}}},
        ['name', 'members'])),
    'plotforge_add_rule': (t_add_rule, S(
        '배치 규칙 추가. kind: nearRoad(도로/경계 인접)|setback(이격)|distanceTo(거리범위)|'
        'adjacentCount(인접개수)|directionOf(방향배치)|sameRowCol(정렬)|openSide(방위개방)|'
        'windSide(풍향)|centerOf(중앙)|between(중간)|distanceToAnchor(앵커거리). 거리는 전부 m',
        {'type': P('string', '규칙 대상 타입/블록 이름'), 'kind': P('string', '규칙 종류'),
         'target': P('string', '기준 타입 이름 (distanceTo/adjacentCount/directionOf/sameRowCol/between)'),
         'target2': P('string', 'between의 두 번째 기준'),
         'anchor': P('string', 'distanceToAnchor의 앵커 이름'),
         'basis': P('string', 'nearRoad/setback 기준: any|road|fence'),
         'side': P('string', 'windSide: down(불어가는쪽)|up'),
         'dir': P('string', 'openSide/directionOf: N|S|E|W'),
         'axis': P('string', 'sameRowCol: row|col'),
         'gap_m': P('number', '거리(m) — kind별 의미 참조'),
         'min_m': P('number', 'distanceTo/anchor 최소(m)'),
         'max_m': P('number', 'distanceTo/anchor 최대(m), 생략=무제한'),
         'min_count': P('integer', 'adjacentCount 최소 개수'),
         'max_count': P('integer', 'adjacentCount 최대 개수'),
         'mode': P('string', 'hard|soft (기본 hard)'), 'weight': P('integer', 'soft 가중치 1~100')},
        ['type', 'kind'])),
    'plotforge_set_sequence': (t_set_sequence, S(
        '자동배치 순서 설정 (타입/블록 이름 배열 — 중복 허용)',
        {'types': {'type': 'array', 'items': {'type': 'string'}}}, ['types'])),
    'plotforge_set_wind': (t_set_wind, S(
        '풍향 설정 (바람이 불어오는 방위)',
        {'direction': P('string', 'N|NE|E|SE|S|SW|W|NW|NONE')}, ['direction'])),
    'plotforge_add_anchor': (t_add_anchor, S(
        '앵커(Tie-in/정문 기준점) 추가 — 부지 좌상단 원점 기준 m 좌표',
        {'name': P('string', '앵커 이름'), 'x_m': P('number', 'x(m)'), 'y_m': P('number', 'y(m)')},
        ['name', 'x_m', 'y_m'])),
    'plotforge_add_clearance': (t_add_clearance, S(
        '클리어런스 매트릭스 추가 (카테고리 간 최소 이격)',
        {'a': P('string', '|'.join(CATS)), 'b': P('string', '〃'), 'min_m': P('number', '최소 이격 m')},
        ['a', 'b', 'min_m'])),
    'plotforge_set_roads': (t_set_roads, S(
        '도로망 파라미터 (다음 run_layout에서 재생성)',
        {'pattern': P('string', 'comb|grid|loop'), 'width_m': P('number', '도로 폭 m'),
         'ring_offset_m': P('number', '루프형: 경계 이격 m')}, [])),
    'plotforge_run_layout': (t_run_layout, S(
        '도로망 생성 + 자동배치 실행 — 열려 있는 앱의 실제 엔진을 구동(수 초 소요). '
        '결과가 화면에 즉시 반영되고 지표를 반환. 시드를 바꾸면 다른 대안',
        {'seed': P('integer', '난수 시드 (기본 1)'),
         'roads': P('boolean', '도로망이 없으면 먼저 생성 (기본 true)'),
         'timeout_seconds': P('integer', '대형 격자 대비 타임아웃(기본 120)')}, [])),
    'plotforge_execute_script': (t_execute_script, S(
        '열려 있는 PlotForge 앱 컨텍스트에서 JS를 실행하고 결과를 반환 (Revit/AutoCAD execute_script 대응). '
        'return 문으로 값을 돌려줄 것. 앱 표면: window.__pf(dump/load/runLayout/status), window.__app, '
        '모듈 내부 함수/변수(store, serialize, restore, autoPlace, placeGrid 등)도 직접 접근 가능.',
        {'code': P('string', '실행할 JavaScript (return으로 값 반환)'),
         'timeout_seconds': P('integer', '기본 25')}, ['code'])),
    'plotforge_status': (t_status, S(
        '앱 연결/프로젝트 현황 (연결 확인용 — get_document_info 대응)', {}, [])),
    'plotforge_summary': (t_summary, S('프로젝트 요약 (타입/규칙/순서/대안 현황)', {}, [])),
}


def main():
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', newline='\n')
    BRIDGE.start(WS_PORT)  # 라이브 앱용 WS 브리지 기동 (백그라운드)

    def send(obj):
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + '\n')
        sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid = msg.get('id')
        method = msg.get('method', '')
        if method == 'initialize':
            send({'jsonrpc': '2.0', 'id': mid, 'result': {
                'protocolVersion': msg.get('params', {}).get('protocolVersion', '2024-11-05'),
                'capabilities': {'tools': {}},
                'serverInfo': {'name': 'BimOn-PlotForge', 'version': '2.0.0'}}})
        elif method == 'notifications/initialized':
            continue
        elif method == 'ping':
            send({'jsonrpc': '2.0', 'id': mid, 'result': {}})
        elif method == 'tools/list':
            send({'jsonrpc': '2.0', 'id': mid, 'result': {'tools': [
                dict(name=k, **v[1]) for k, v in TOOLS.items()]}})
        elif method == 'tools/call':
            name = msg['params']['name']
            args = msg['params'].get('arguments') or {}
            try:
                fn = TOOLS[name][0]
                text = fn(args)
                send({'jsonrpc': '2.0', 'id': mid, 'result': {
                    'content': [{'type': 'text', 'text': text}], 'isError': False}})
            except Exception as e:  # 도구 오류는 isError로
                send({'jsonrpc': '2.0', 'id': mid, 'result': {
                    'content': [{'type': 'text', 'text': '오류: %s' % e}], 'isError': True}})
        elif mid is not None:
            send({'jsonrpc': '2.0', 'id': mid,
                  'error': {'code': -32601, 'message': 'method not found: ' + method}})


if __name__ == '__main__':
    main()
