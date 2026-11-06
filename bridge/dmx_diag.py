#!/usr/bin/env python3
"""DMX512 受信診断ツール (FTDI / ftdi_sio 経由, QLC+ 不要)

使い方:  python3 dmx_diag.py [/dev/ttyUSB0] [秒数]

250000 baud / 8N2 で開き、PARMRK により BREAK = <BRK>、フレーミングエラー = FE(xx)
として表示する。正常受信なら 1 フレームは  <BRK> 00(スタートコード) ch1 ch2 ...  の形になる。
"""
import os, sys, time, struct, fcntl, termios, select

DEV = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
DURATION = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
TCGETS2, TCSETS2, BOTHER, CBAUD = 0x802C542A, 0x402C542B, 0o10000, 0o10017
FMT = "IIIIB19sII"

fd = os.open(DEV, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
buf = bytearray(struct.calcsize(FMT)); fcntl.ioctl(fd, TCGETS2, buf)
_, _, cflag, _, line, cc, _, _ = struct.unpack(FMT, buf)
cflag &= ~(termios.CSIZE | termios.PARENB | CBAUD | termios.CRTSCTS)
cflag |= termios.CS8 | termios.CSTOPB | termios.CREAD | termios.CLOCAL | BOTHER
cc = bytearray(cc); cc[termios.VMIN] = 0; cc[termios.VTIME] = 0
fcntl.ioctl(fd, TCSETS2, struct.pack(FMT, termios.PARMRK, 0, cflag, 0, line, bytes(cc), 250000, 250000))
termios.tcflush(fd, termios.TCIOFLUSH)

def tokens(d):
    out = []; i = 0
    while i < len(d):
        b = d[i]
        if b == 0xFF and i + 1 < len(d):
            if d[i + 1] == 0xFF: out.append(("D", 0xFF)); i += 2; continue
            if d[i + 1] == 0x00 and i + 2 < len(d):
                out.append(("BRK", 0) if d[i + 2] == 0 else ("FE", d[i + 2])); i += 3; continue
        out.append(("D", b)); i += 1
    return out

def rle(toks):
    s = []; prev = None; n = 0
    for t in toks + [None]:
        name = None if t is None else (t[0] if t[0] != "D" else f"{t[1]:02x}") if t is None or t[0] != "FE" else f"FE({t[1]:02x})"
        if name == prev: n += 1
        else:
            if prev is not None: s.append(f"{prev}x{n}" if n > 1 else prev)
            prev, n = name, 1
    return " ".join(s)

stats = {"data0": 0, "dataNZ": 0, "BRK": 0, "FE": 0}; gaps = []; last = None
frames = 0; cur = None; good = None; shown = 0
t0 = time.time()
print(f"{DEV} を 250000 baud 8N2 で {DURATION:.0f} 秒間受信します...")
while time.time() - t0 < DURATION:
    r, _, _ = select.select([fd], [], [], 0.05)
    if not r: continue
    d = os.read(fd, 4096); t = time.time()
    if last is not None and t - last > 0.008: gaps.append(t - last)
    last = t
    toks = tokens(d)
    if shown < 6:
        print(f"  t={(t - t0) * 1000:7.1f}ms len={len(d):3d}: {rle(toks)[:160]}"); shown += 1
    for kind, v in toks:
        if kind == "BRK":
            stats["BRK"] += 1
            if cur is not None and len(cur) > 1: frames += 1; good = cur
            cur = []
        elif kind == "FE": stats["FE"] += 1
        else:
            stats["data0" if v == 0 else "dataNZ"] += 1
            if cur is not None: cur.append(v)
os.close(fd)

el = time.time() - t0
print("=== 集計 ===")
print(f"  0x00 データ: {stats['data0']}  非ゼロデータ: {stats['dataNZ']}  BREAK印: {stats['BRK']}  フレーミングエラー: {stats['FE']}")
if gaps: print(f"  フレーム周期: {sum(gaps) / len(gaps) * 1000:.2f} ms ({len(gaps) / sum(gaps):.1f} Hz)")
if stats["BRK"] + stats["data0"] + stats["dataNZ"] == 0:
    print("  → 何も受信していません。信号が来ていない (結線 / 卓の出力 / ケーブル) 可能性大")
elif good and frames and gaps and 0.5 < stats["BRK"] / (len(gaps) + 1) < 1.5 and stats["FE"] < frames:
    sc, ch = good[0], good[1:]
    nz = [(i + 1, v) for i, v in enumerate(ch) if v]
    print(f"  → 正常にデコードできています: スタートコード=0x{sc:02x} チャンネル数={len(ch)}")
    print("     ch1-16:", " ".join(f"{v:3d}" for v in ch[:16]))
    if nz: print("     非ゼロ:", ", ".join(f"ch{c}={v}" for c, v in nz[:30]))
else:
    if gaps: print(f"  1フレームあたりの BREAK 印: {stats['BRK'] / (len(gaps) + 1):.1f} (正常なら 1.0 付近)")
    print("  → 信号の『輪郭』は来ていますが、バイト単位ではデコードできていません。")
    print("     受信器が無効 (送信専用ハード) か、極性/GND の結線不良が疑われます。")
