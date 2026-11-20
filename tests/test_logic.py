"""Checks the app logic without a screen or a real plug: tkinter, tinytuya and requests are
replaced by small fakes. Run:  python tests/test_logic.py"""
import sys, types, json, os, shutil, tempfile, importlib.util
from datetime import datetime, timedelta

# ---- fake tkinter ----
class W:
    def __init__(self, *a, **k): self.cfg = dict(k)
    def config(self, **k): self.cfg.update(k)
    configure = config
    def __getattr__(self, n): return lambda *a, **k: None
class Entry(W):
    def __init__(self, *a, **k): super().__init__(*a, **k); self.v = ''
    def insert(self, i, s): self.v = s
    def get(self): return self.v
class Root(W):
    def __init__(self): super().__init__(); self.jobs = {}; self.n = 0; self.cancelled = []
    def after(self, ms, fn, *args):
        if ms == 0: fn(*args); return None
        self.n += 1; self.jobs[self.n] = (ms, fn); return self.n
    def after_cancel(self, j): self.cancelled.append(j); self.jobs.pop(j, None)
    def winfo_width(self): return 1142
    def geometry(self, *a): return '1142x410'
tk = types.ModuleType('tkinter')
for n in ['Frame', 'Label', 'Button']: setattr(tk, n, W)
tk.Entry = Entry; tk.Tk = Root
for n in ['LEFT', 'TOP', 'RIDGE', 'FLAT']: setattr(tk, n, n)
tk.NORMAL, tk.DISABLED = 'normal', 'disabled'
font = types.ModuleType('tkinter.font'); font.Font = W
mb = types.ModuleType('tkinter.messagebox'); mb.calls = []
mb.showerror = lambda *a: mb.calls.append(('error',) + a); mb.showinfo = lambda *a: mb.calls.append(('info',) + a)
tk.font, tk.messagebox = font, mb
sys.modules.update({'tkinter': tk, 'tkinter.font': font, 'tkinter.messagebox': mb})
# ---- fake tinytuya / requests / threading start ----
class Dev:
    status_reply = {'dps': {'1': False, '19': 24000}}; turn_reply = {}; calls = []
    def __init__(self, *a): pass
    def set_version(self, v): pass
    def status(self): return Dev.status_reply
    def turn_on(self, switch): Dev.calls.append('on'); return Dev.turn_reply
    def turn_off(self, switch): Dev.calls.append('off'); return Dev.turn_reply
sys.modules['tinytuya'] = types.SimpleNamespace(OutletDevice=Dev)
sys.modules['requests'] = types.SimpleNamespace(get=None, exceptions=types.SimpleNamespace(RequestException=Exception))
import threading
threading.Thread.start = lambda self: None

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'AmberTuyaHotWaterAlarm.pyw')
def load(cfg_dir):
    os.chdir(cfg_dir)
    spec = importlib.util.spec_from_loader('app', loader=None); m = importlib.util.module_from_spec(spec)
    m.__file__ = os.path.join(cfg_dir, 'app.pyw')
    code = open(SRC).read().replace('if __name__ == "__main__":', 'if False:')
    exec(compile(code, SRC, 'exec'), m.__dict__)
    return m
ok = True
def check(c, msg):
    global ok; print(('ok:   ' if c else 'FAIL: ') + msg); ok &= bool(c)

base = json.load(open(os.path.join(os.path.dirname(SRC), 'config.example.json')))
def app_with(cfg):
    d = tempfile.mkdtemp(); json.dump(cfg, open(os.path.join(d, 'config.json'), 'w'))
    m = load(d); return m, m.AmberAlarmApp(Root())

# 0. first run creates config.json from the example and exits
d = tempfile.mkdtemp(); shutil.copy(os.path.join(os.path.dirname(SRC), 'config.example.json'), d)
try: load(d); check(False, 'first run exits')
except SystemExit as e: check(e.code == 0 and os.path.exists(os.path.join(d, 'config.json')) and mb.calls[-1][0] == 'info', 'first run copies config.example.json to config.json and says so')

# 1. not configured: toggle doesn't leave the button on "..."
m, a = app_with(dict(base, TUYA_DEVICE_ID=None))
a.toggle_hw_thread = None
a.btn_hw_toggle.config(text='...', state='disabled'); a._toggle_hw_thread()
check(a.btn_hw_toggle.cfg['text'] == 'NOT SET UP', 'unconfigured plug: button says NOT SET UP, not stuck on "..."')
a.update_gui(None, None, a.get_tuya_status())
check(a.btn_hw_toggle.cfg['text'] == 'NOT SET UP', 'status loop also shows NOT SET UP')

# 2. plug unreachable -> OFFLINE (was: stale ON)
m, a = app_with(dict(base, TUYA_DEVICE_ID='d', TUYA_IP_ADDRESS='1.2.3.4', TUYA_LOCAL_KEY='k'))
Dev.status_reply = {'dps': {'1': True, '19': 24000}}
a.update_gui(None, None, a.get_tuya_status())
check(a.btn_hw_toggle.cfg['text'] == 'ON' and a.lbl_power.cfg['text'] == '2.4 kW', 'reachable plug shows ON and 2.4 kW')
Dev.status_reply = {'Error': 'Network Error: Device Unreachable', 'Err': '905'}
a.update_gui(None, None, a.get_tuya_status())
check(a.btn_hw_toggle.cfg['text'] == 'OFFLINE' and a.hw_on is None, 'unreachable plug shows OFFLINE and forgets the old state')

# 3. unknown state + status read fails -> no command sent
Dev.calls = []; a.hw_on = None; a._toggle_hw_thread()
check(Dev.calls == [] and a.btn_hw_toggle.cfg['state'] == 'normal', 'unknown state and failed read: nothing switched, button usable')
# unknown state, read works (off) -> turns on
Dev.status_reply = {'dps': {'1': False}}; Dev.calls = []; a.lbl_power.config(text='2.4 kW'); a._toggle_hw_thread()
check(Dev.calls == ['on'] and a.btn_hw_toggle.cfg['text'] == 'ON', 'unknown state, read says OFF: turns ON')
check(a.lbl_power.cfg['text'] == '2.4 kW', 'power reading kept after a toggle')
# command error -> state unchanged
Dev.turn_reply = {'Error': 'timeout'}; Dev.calls = []; a._toggle_hw_thread()
check(Dev.calls == ['off'] and a.hw_on is True and a.btn_hw_toggle.cfg['text'] == 'ON' and a.btn_hw_toggle.cfg['state'] == 'normal', 'failed command keeps ON and re-enables the button')
Dev.turn_reply = {}

# 3b. a reply that leaves out the switch's reading is unknown, not OFF
Dev.status_reply = {'dps': {'19': 0}}; Dev.calls = []; a.hw_on = None; a._toggle_hw_thread()
check(Dev.calls == [], 'reply without the switch reading: no command sent (was: switched ON)')
a.update_gui(None, None, a.get_tuya_status())
check(a.btn_hw_toggle.cfg['text'] == 'OFFLINE', 'reply without the switch reading shows OFFLINE, not OFF')

# 4. night mute label switches on without a manual mute; only one timer at a time
m, a = app_with(dict(base, MUTE_START_HOUR=0, MUTE_END_HOUR=0))  # never night
a.root.jobs.clear(); a._mute_job = None
a.update_mute_status()
check(len(a.root.jobs) == 1 and list(a.root.jobs.values())[0][0] == 60000, 'alerts active: checks again in a minute')
now_h = datetime.now().hour; m.config['MUTE_START_HOUR'] = now_h; m.config['MUTE_END_HOUR'] = (now_h + 1) % 24
list(a.root.jobs.values())[0][1]()
check(a.lbl_mute_status.cfg['text'].startswith('Night Mute Active'), 'label switches to Night Mute when quiet hours start')
m.config['MUTE_START_HOUR'] = m.config['MUTE_END_HOUR'] = 0
for _ in range(5): a.set_mute(1)
check(len(a.root.jobs) == 1, 'five Mute presses leave one timer, not five')
check(a.mute_until > datetime.now() + timedelta(hours=4, minutes=59), 'five +1h presses add up to 5 hours')
print('ALL PASSED' if ok else 'SOME FAILED'); sys.exit(0 if ok else 1)
