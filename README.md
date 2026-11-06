# qlc_dmx_bridge

DMX 卓のフェーダーで QLC+ 5 を操作するためのセット一式です。
Enttec Open DMX USB 互換機（FTDI FT232R）で受けた DMX512 を Art-Net に変換して QLC+ 5 に渡すブリッジ、
QLC+ 5 のワークスペース、フィクスチャ定義、udev ルール、診断ツールをまとめています。

Ubuntu 22.04 + QLC+ 5.3.1 で動作確認しています。

## 全体構成

```
DMX 卓 (192ch, 約48fps)
   │ XLR (終端抵抗 ON 必須)
   ▼
Open DMX USB 互換機 #1  (FTDI S/N BG01OIGN, 受信専用)
   │ /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_BG01OIGN-if00-port0  (ftdi_sio, 250kbaud 8N2)
   ▼
dmx2artnet  (systemd ユーザーサービス, BREAK 同期でフレーム復元 + チャンネル変換)
   │ Art-Net (ArtDMX) → 127.0.0.1:6454, universe 0
   ▼
QLC+ 5  (Universe 1: Input = ArtNet 127.0.0.1, Output = DMX USB)
   │ libftdi (Open TX)
   ▼
Open DMX USB 互換機 #2  (FTDI S/N AH02A40C, 送信)
   │ XLR
   ▼
HPAR64-9 (13ch, addr 1) → ムービングヘッド ×4 (全台 addr 14) → Stinger II (addr 25)
```

### なぜ QLC+ の「Open RX」を使わないのか

QLC+ の DMX USB プラグインには FTDI 受信用の「Open RX」モードがありますが、
DMX の BREAK を検出せず「USB の 1 回の read = 1 フレーム」とみなす実装のため、
この卓（194 バイト/フレーム、62 バイト単位の USB パケット）ではチャンネル番号が毎回ずれます。
そこで ftdi_sio 経由で tty を開き、`PARMRK` で BREAK を検出して確実にフレーム同期を取る
ブリッジを用意し、Art-Net で QLC+ に渡しています。チャンネル番号は卓と 1:1 で一致します。

## ファイル構成

| パス | 内容 |
|---|---|
| `bridge/dmx2artnet` | ブリッジ本体（Python 3 標準ライブラリのみ、依存なし） |
| `bridge/dmx2artnet.service` | systemd ユーザーサービス定義（変換オプション込み） |
| `bridge/dmx_diag.py` | FTDI から直接 DMX を読んで状態を診断するスクリプト |
| `qlcplus/stage1_5.qxw` | QLC+ 5 ワークスペース（フィクスチャ、Function、Virtual Console、入出力設定） |
| `fixtures/STAGE-EVO-HPAR64-9-7ch.qxf` | HPAR64-9 のフィクスチャ定義（7ch / 13ch モード） |
| `udev/z65-dmxusb.rules` | QLC+ 公式の udev ルール（FTDI デバイスの権限） |
| `install.sh` | 上記をホームディレクトリ配下へ配置してサービスを有効化するスクリプト |

## セットアップ

### 1. QLC+ 5 (AppImage)

公式サイト配布の QLC+ 5 AppImage は glibc 2.38 を要求するため Ubuntu 22.04 では起動しません。
GitHub Actions の CI（ubuntu-22.04 でビルド）の成果物 `build-v5-AppImage` を使います。

```bash
gh run list -R mcallegari/qlcplus -b master -L 5          # 成功した run の ID を確認
gh run download <RUN_ID> -R mcallegari/qlcplus -n build-v5-AppImage -D /tmp/qlc
mv /tmp/qlc/*.AppImage ~/Applications/QLC+_5.3.1_x86_64.AppImage
chmod +x ~/Applications/QLC+_5.3.1_x86_64.AppImage
ln -s ~/Applications/QLC+_5.3.1_x86_64.AppImage ~/.local/bin/qlcplus5
```

### 2. このリポジトリの配置

```bash
git clone https://github.com/hamataku/qlc_dmx_bridge.git
cd qlc_dmx_bridge
./install.sh
# 表示される sudo コマンドで udev ルールを入れ、Open DMX を抜き差しする
```

`install.sh` はブリッジを `~/.local/bin/dmx2artnet`、サービスを `~/.config/systemd/user/`、
フィクスチャ定義を `~/.qlcplus/fixtures/`、ワークスペースを `~/QLC+/stage1_5.qxw` に置き、
サービスをログイン時自動起動で有効化します。

受信側の FTDI は `bridge/dmx2artnet` 先頭の `DEFAULT_DEV`（シリアル番号入りのパス）で特定しています。
別の個体を使う場合は `ls /dev/serial/by-id/` で確認してサービスファイルに `--dev` を追加してください。

### 3. QLC+ 側

`~/QLC+/stage1_5.qxw` を開くだけで、入出力は名前照合で自動的に割り当たります。

- Universe 1 Input: ArtNet の `127.0.0.1`
- Universe 1 Output: DMX USB `FT232R USB UART (S/N: AH02A40C)`

**DMX USB プラグインの Input は必ず OFF のままにしてください。**
ON にすると QLC+ が libftdi で受信側 FTDI を掴み、ブリッジから見えなくなります
（掴まれた場合は USB を抜き差しすれば復帰します）。

フィクスチャ定義は QLC+ 起動時にしか読まれないので、`install.sh` の後は QLC+ を起動し直してください。

## 灯体のアドレス

| 灯体 | モード | DMX アドレス |
|---|---|---|
| STAGE EVO HPAR64-9 | 13ch | 1〜13 |
| UKing LED Spot Moving Head 100W ×4 | 11ch | 全台 14（QLC+ 上は 1 台として扱う） |
| American DJ Stinger II | 9ch | 25〜33 |

QLC+ はアドレスが重なるフィクスチャを読み込み時に拒否するため、
同じアドレスの 4 台はワークスペース上 1 台に統合しています。

## 卓のフェーダー割り当て

卓の ch1〜7 が、ブリッジでの変換を経て QLC+ の Virtual Console「DMX卓 1-7」フレームを動かします。

| フェーダー | 動作 | ブリッジでの変換 | QLC+ 側ウィジェット |
|---|---|---|---|
| 1 | PAR 赤 | なし | Level スライダー → HPAR Red |
| 2 | PAR 緑 | なし | Level スライダー → HPAR Green |
| 3 | PAR 青 | なし | Level スライダー → HPAR Blue |
| 4 | PAR ランダム色 | 10 以下 = 停止、11〜255 を ch4 (速度) と ch104 (ON/OFF) に分離 | Adjust スライダー → Chaser「PAR Random」、Speed Dial 2 秒〜0.08 秒 |
| 5 | ムービングヘッドの色 | 0〜10 消灯 / 11〜88 白 / 89〜166 赤 / 167〜244 青 / 245〜255 自動色替え。ch107 = Brightness 保持（5 が 10 超かつ 7 が 10 以下のとき 255） | Level スライダー → Color Select、Level スライダー → Brightness |
| 6 | ムービングヘッドの動き | 10 以下 = 停止、11〜255 を ch6 (速度) と ch106 (ON/OFF) に分離 | Adjust スライダー → EFX「MH Move」(円運動)、Speed Dial 20 秒〜2 秒 |
| 7 | PAR と MH のストロボ（ソフト制御、同期） | 10 以下 = 停止、11〜255 を ch7 (速度) に。ch108 = PAR 点滅 ON、ch109 = MH 点滅 ON（MH が点灯中のみ）、ch110 = PAR Dimmer 保持（点滅中は 0） | Adjust スライダー → Chaser「Strobe PAR」「Strobe MH」(Dimmer の ON/OFF 2 ステップ)、共通の Speed Dial 0.5 秒〜0.05 秒/ステップ |

### ブリッジの変換オプション

サービスファイルの `ExecStart` で指定しています。値はすべて卓の生の値に対する変換です。

| オプション | 意味 |
|---|---|
| `--deadzone CH:TH` | TH 以下を 0、TH+1〜255 を 1〜255 に引き伸ばす |
| `--gate CH:TH:OUT` | CH が TH 以下なら OUT チャンネルに 0、超えたら 255 を出す（元の CH はそのまま） |
| `--map CH:lo-hi=v/...` | 範囲ごとに固定値 `v`、または `a-b` で線形補間 |
| `--quantize CH:v1/v2/...` | 0〜255 を等分し各ゾーンを列挙値に置換 |
| `--logic OUT=式` | 式（`chN`、`> < <= >=`、`&` `\|` `!`）が真なら OUT チャンネルに 255、偽なら 0。生の値で判定 |

現在の指定:

```
--deadzone 4:10,6:10,7:10
--gate 4:10:104,6:10:106
--map 5:0-10=0/11-88=0/89-166=10/167-244=31/245-255=255
--logic "107=ch5>10&ch7<=10,108=ch7>10,109=ch7>10&ch5>10,110=ch7<=10"
```

変更したら `systemctl --user daemon-reload && systemctl --user restart dmx2artnet` で反映されます。

### 設計上の注意

- QLC+ の Flash ボタンは Scene にしか効きません（EFX や Chaser は起動しない）。
  そのため ON/OFF は Adjust スライダー（Intensity 属性、0 で停止）で行い、
  速度用の値とは別チャンネルに分けています。
- PAR の Red/Green/Blue は HTP 合成なので、ランダム色を綺麗に出すときは 1〜3 を下げてください。
- ストロボは灯体のハードウェアストロボではなく、QLC+ の Chaser で Dimmer を ON/OFF しています。
  灯体ごとにタイミングがばらつくハードストロボと違い、PAR と MH が同じ周期で点滅します。
  Dimmer は HTP なので、点滅中は「PAR Dimmer」「MH Dimmer」の保持スライダーをブリッジ側で 0 に落としています
  （そのため HPAR は Dimmer を持つ 13ch モードが必須です）。Stinger は対象外です。
- QLC+ の処理周期は 20 ms なので、ステップ 50 ms（10 Hz 点滅）あたりが実用上の上限です。

## 運用コマンド

```bash
systemctl --user status dmx2artnet      # 状態
journalctl --user -u dmx2artnet -f      # ログ（受信開始・信号喪失・再接続を記録）
systemctl --user restart dmx2artnet     # 再起動
```

ブリッジは受信側 FTDI の抜き差しに追従します。未接続時は 1 秒おきに待機し、
挿せば即座に受信を再開します。

## トラブルシューティング

| 症状 | 確認すること |
|---|---|
| QLC+ に何も入ってこない | `journalctl --user -u dmx2artnet` に `receiving DMX` が出ているか。出ていなければ下の診断へ |
| 診断で「輪郭しか見えない」 | 終端抵抗が OFF。ON にする（受信器がストップビットを拾えない典型症状） |
| 診断で「何も受信していない」 | XLR の 1-1 / 2-2 / 3-3 結線、卓の出力 |
| `/dev/ttyUSB0` が消えた | QLC+ の DMX USB Input が ON になっている。OFF にして USB を抜き差し |
| フィクスチャが不明扱い | QLC+ を再起動（定義は起動時読み込み） |

診断スクリプトは QLC+ とブリッジを止めた状態で実行します。

```bash
systemctl --user stop dmx2artnet
python3 -I ~/dmx_diag.py /dev/ttyUSB0 3
systemctl --user start dmx2artnet
```

ワークスペースを GUI で読み込まずに検証したいときは、ヘッドレスで起動してログを見られます。

```bash
timeout 15 ~/Applications/QLC+_5.3.1_x86_64.AppImage --platform minimal --open ~/QLC+/stage1_5.qxw 2>&1 | grep -E 'IOMAP|Mapping input|overlap'
```

## ワークスペースの更新について

QLC+ が実際に開いているのは `~/QLC+/stage1_5.qxw` です。
QLC+ で編集して保存したら、`cp ~/QLC+/stage1_5.qxw qlcplus/` でリポジトリに取り込んでからコミットしてください。
