# -*- coding: utf-8 -*-
"""
PlotForge 런처 — 콘솔(cmd) 없이 '시스템 트레이(알림 영역)'에 상주.
정적 서버(http.server)를 백그라운드로 돌리고, 트레이 아이콘만 띄운다.
  · 아이콘 더블클릭 → 브라우저 열기
  · 아이콘 우클릭   → 메뉴(브라우저 열기 / 종료)
  · 종료를 누르면 서버도 함께 종료된다.

의존성 없음 — 표준 라이브러리만(ctypes로 Win32 Shell_NotifyIcon 직접 호출). Python 3.7+ / Windows.
실행: PlotForge.pyw 더블클릭(pythonw 연결 시 콘솔 안 뜸). 포트 변경: 인자로 지정.
자가검증: pythonw 없이  python PlotForge.pyw <port> --selftest
"""
import functools
import http.server
import os
import socket
import struct
import sys
import threading
import time
import webbrowser
import ctypes
from ctypes import wintypes

ROOT = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(ROOT, 'plotforge.ico')

_args = [a for a in sys.argv[1:] if not a.startswith('--')]
SELFTEST = '--selftest' in sys.argv
PORT = int(_args[0]) if _args else 5178
URL = 'http://localhost:%d' % PORT


# ---------- 정적 서버 ----------

class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass  # 트레이 모드에선 콘솔 로그 억제


def port_in_use(port):
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
        return False
    except OSError:
        return True
    finally:
        s.close()


class Server:
    def __init__(self, root, port):
        handler = functools.partial(_Handler, directory=root)
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass


# ---------- 트레이 아이콘(.ico) 생성 (없으면) ----------

def ensure_icon(path):
    """32x32 32bpp 트레이 아이콘을 코드로 생성 (청록 바탕 + 2x2 필지 격자 모티프)."""
    if os.path.exists(path):
        return
    W = H = 32
    teal = (0xac, 0xb6, 0x4d, 0xff)   # BGRA (#4db6ac)
    edge = (0x22, 0x2b, 0x2a, 0xff)
    plot = (0xea, 0xf1, 0xf3, 0xff)

    def px(x, y):
        if x < 2 or y < 2 or x >= 30 or y >= 30:
            return edge
        gx, gy = x - 5, y - 5
        in_col = (0 <= gx <= 9) or (12 <= gx <= 21)
        in_row = (0 <= gy <= 9) or (12 <= gy <= 21)
        if 0 <= gx <= 21 and 0 <= gy <= 21 and in_col and in_row:
            return plot
        return teal

    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            row += bytes(px(x, y))
        rows.append(bytes(row))
    xor = b''.join(reversed(rows))                 # BMP는 bottom-up
    and_mask = b'\x00' * (4 * H)                    # 1bpp, 전부 불투명
    bih = struct.pack('<IiiHHIIiiII', 40, W, H * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    dib = bih + xor + and_mask
    icondir = struct.pack('<HHH', 0, 1, 1)
    entry = struct.pack('<BBBBHHII', W, H, 0, 0, 1, 32, len(dib), 22)
    try:
        with open(path, 'wb') as f:
            f.write(icondir + entry + dib)
    except Exception:
        pass


# ---------- Win32 트레이 ----------

WM_DESTROY = 0x0002
WM_COMMAND = 0x0111
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x01, 0x02, 0x04, 0x10
IMAGE_ICON = 1
LR_LOADFROMFILE, LR_DEFAULTSIZE = 0x0010, 0x0040
IDI_APPLICATION = 32512
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100
MF_STRING, MF_SEPARATOR, MF_GRAYED = 0x0000, 0x0800, 0x0001
PM_REMOVE = 0x0001
ID_OPEN, ID_QUIT = 1001, 1002

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM)


class GUID(ctypes.Structure):
    _fields_ = [('Data1', wintypes.DWORD), ('Data2', wintypes.WORD),
                ('Data3', wintypes.WORD), ('Data4', ctypes.c_byte * 8)]


class NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD), ('hWnd', wintypes.HWND), ('uID', wintypes.UINT),
        ('uFlags', wintypes.UINT), ('uCallbackMessage', wintypes.UINT), ('hIcon', wintypes.HICON),
        ('szTip', ctypes.c_wchar * 128), ('dwState', wintypes.DWORD), ('dwStateMask', wintypes.DWORD),
        ('szInfo', ctypes.c_wchar * 256), ('uVersion', wintypes.UINT),
        ('szInfoTitle', ctypes.c_wchar * 64), ('dwInfoFlags', wintypes.DWORD),
        ('guidItem', GUID), ('hBalloonIcon', wintypes.HICON)]


class WNDCLASS(ctypes.Structure):
    _fields_ = [('style', wintypes.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', ctypes.c_int),
                ('cbWndExtra', ctypes.c_int), ('hInstance', wintypes.HINSTANCE),
                ('hIcon', wintypes.HICON), ('hCursor', wintypes.HANDLE),
                ('hbrBackground', wintypes.HBRUSH), ('lpszMenuName', wintypes.LPCWSTR),
                ('lpszClassName', wintypes.LPCWSTR)]


u = ctypes.windll.user32
k = ctypes.windll.kernel32
sh = ctypes.windll.shell32

u.DefWindowProcW.restype = LRESULT
u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM, LPARAM]
u.CreateWindowExW.restype = wintypes.HWND
u.LoadImageW.restype = wintypes.HANDLE
u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
u.LoadIconW.restype = wintypes.HICON
u.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
u.CreatePopupMenu.restype = wintypes.HMENU
u.TrackPopupMenu.restype = ctypes.c_int
u.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, wintypes.HWND, ctypes.c_void_p]
sh.Shell_NotifyIconW.restype = wintypes.BOOL
sh.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]

_STATE = {'nid': None, 'hwnd': None, 'server': None, 'wndproc': None, 'wc': None}


def _load_icon():
    ensure_icon(ICON_PATH)
    h = u.LoadImageW(None, ICON_PATH, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
    if not h:
        h = u.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))
    return h


def _show_menu(hwnd):
    menu = u.CreatePopupMenu()
    u.AppendMenuW(menu, MF_STRING, ID_OPEN, '브라우저 열기')
    u.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, '실행 중 · 포트 %d' % PORT)
    u.AppendMenuW(menu, MF_SEPARATOR, 0, None)
    u.AppendMenuW(menu, MF_STRING, ID_QUIT, '종료')
    pt = wintypes.POINT()
    u.GetCursorPos(ctypes.byref(pt))
    u.SetForegroundWindow(hwnd)
    cmd = u.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, pt.x, pt.y, 0, hwnd, None)
    u.DestroyMenu(menu)
    if cmd == ID_OPEN:
        webbrowser.open(URL)
    elif cmd == ID_QUIT:
        _quit(hwnd)


def _quit(hwnd):
    if _STATE['nid'] is not None:
        sh.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(_STATE['nid']))
    if _STATE['server']:
        _STATE['server'].stop()
    u.DestroyWindow(hwnd)


def _wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_TRAY:
        if lparam == WM_LBUTTONDBLCLK:
            webbrowser.open(URL)
        elif lparam == WM_RBUTTONUP:
            _show_menu(hwnd)
        return 0
    if msg == WM_COMMAND:
        cid = wparam & 0xFFFF
        if cid == ID_OPEN:
            webbrowser.open(URL)
        elif cid == ID_QUIT:
            _quit(hwnd)
        return 0
    if msg == WM_DESTROY:
        u.PostQuitMessage(0)
        return 0
    return u.DefWindowProcW(hwnd, msg, wparam, lparam)


def _create_tray():
    hinst = k.GetModuleHandleW(None)
    cls = WNDCLASS()
    cls.lpfnWndProc = WNDPROC(_wndproc)
    cls.hInstance = hinst
    cls.lpszClassName = 'PlotForgeTrayWnd'
    _STATE['wndproc'] = cls.lpfnWndProc         # 콜백 GC 방지 (필수)
    _STATE['wc'] = cls
    if not u.RegisterClassW(ctypes.byref(cls)):
        raise ctypes.WinError()
    hwnd = u.CreateWindowExW(0, cls.lpszClassName, 'PlotForge', 0, 0, 0, 0, 0,
                             None, None, hinst, None)
    if not hwnd:
        raise ctypes.WinError()
    _STATE['hwnd'] = hwnd

    nid = NOTIFYICONDATA()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
    nid.hWnd = hwnd
    nid.uID = 1
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAY
    nid.hIcon = _load_icon()
    nid.szTip = 'PlotForge · %s' % URL
    _STATE['nid'] = nid
    if not sh.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
        raise ctypes.WinError()

    # 시작 풍선 알림
    nid.uFlags = NIF_INFO
    nid.szInfoTitle = 'PlotForge 실행 중'
    nid.szInfo = '트레이 아이콘 더블클릭=열기, 우클릭=메뉴'
    nid.dwInfoFlags = 0
    sh.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
    return hwnd


def _message_loop(hwnd, timeout=None):
    msg = wintypes.MSG()
    if timeout is None:
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
    else:  # selftest: 잠깐 펌프 후 정리
        end = time.time() + timeout
        while time.time() < end:
            if u.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                u.TranslateMessage(ctypes.byref(msg))
                u.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.02)


def main():
    if port_in_use(PORT):
        webbrowser.open(URL)          # 이미 실행 중 — 브라우저만 열고 종료(중복 트레이 방지)
        if SELFTEST:
            print('ALREADY-RUNNING (트레이 생성 생략)')
        return
    _STATE['server'] = Server(ROOT, PORT)
    _STATE['server'].start()
    hwnd = _create_tray()
    if SELFTEST:
        _message_loop(hwnd, timeout=1.2)
        _quit(hwnd)
        print('TRAY OK')
        return
    webbrowser.open(URL)              # 서버 뜬 뒤 브라우저 자동 오픈
    _message_loop(hwnd)


if __name__ == '__main__':
    main()
