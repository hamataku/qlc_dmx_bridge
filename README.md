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
dmx2artnet  (systemd ユーザーサービス, BREAK 同期でフレーム復元 + 50Hz でチャンネル変換・ランダム色・ストロボ生成)
   │ Art-Net (ArtDMX) → 127.0.0.1:6454, universe 0
   ▼
QLC+ 5  (Universe 1: Input = ArtNet 127.0.0.1, Output = DMX USB)
   │ libftdi (Open TX)
   ▼
Open DMX USB 互換機 #2  (FTDI S/N AH02A40C, 送信)
   │ XLR
   ▼
HPAR64-9 (7ch, addr 1) → ムービングヘッド ×4 (全台 addr 8) → Stinger II (addr 19)
```

### なぜ QLC+ の「Open RX」を使わないのか

QLC+ の DMX USB プラグインには FTDI 受信用の「Open RX」モードがありますが、
DMX の BREAK を検出せず「USB の 1 回の read = 1 フレーム」とみなす実装のため、
この卓（194 バイト/フレーム、62 バイト単位の USB パケット）ではチャンネル番号が毎回ずれます。
そこで ftdi_sio 経由で tty を開き、`PARMRK` で BREAK を検出して確実にフレーム同期を取る
ブリッジを用意し、Art-Net で QLC+ に渡しています。チャンネル番号は卓と 1:1 で一致します。

### なぜランダム色とストロボをブリッジ側で作るのか

QLC+ では RGB や Dimmer などの強度系チャンネルが HTP（大きい方優先）で合成されるため、
フェーダーで色を上げたまま QLC+ の Function で「暗くする」ことができません。
PAR を 7ch モード（Dimmer なし）で使う以上、点滅やランダム色を QLC+ 側で作ると HTP に阻まれます。
そこでブリッジが 50 Hz のタイマーでランダム色・ストロボを計算し、最終的な RGB 値を QLC+ に渡します。
QLC+ の Virtual Console は「入力をそのまま灯体チャンネルに流す Level スライダー」と
ムービングヘッドの EFX だけで済み、PAR と MH のストロボも同じタイマーなので完全に同期します。

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
| STAGE EVO HPAR64-9 | 7ch | 1〜7 |
| UKing LED Spot Moving Head 100W ×4 | 11ch | 全台 8（QLC+ 上は 1 台として扱う） |
| American DJ Stinger II | 9ch | 19〜27 |

QLC+ はアドレスが重なるフィクスチャを読み込み時に拒否するため、
同じアドレスの 4 台はワークスペース上 1 台に統合しています。

## 卓のフェーダー割り当て

卓の ch1〜7 が、ブリッジでの変換を経て QLC+ の Virtual Console「DMX卓 1-7」フレームを動かします。

| フェーダー | 動作 | ブリッジでの変換 | QLC+ 側ウィジェット |
|---|---|---|---|
| 1 | PAR 赤 | そのまま（ランダム・ストロボ中はブリッジが上書き） | Level スライダー → HPAR Red |
| 2 | PAR 緑 | 同上 | Level スライダー → HPAR Green |
| 3 | PAR 青 | 同上 | Level スライダー → HPAR Blue |
| 4 | PAR の色揺らぎ | 10 以下 = なし（1〜3 の色そのまま）。11〜255 で 1〜3 の色を HSV で揺らす。上げるほど色相の振れ幅（最大 ±180°）・彩度の注入・速度（周期 20 秒 → 1.5 秒）が増える。明度は固定 | なし（1〜3 のスライダーに乗る） |
| 5 | ムービングヘッドの色 | 0〜10 消灯 / 11〜88 白 / 89〜166 赤 / 167〜244 青 / 245〜255 自動色替え。ch107 = Brightness（5 が 10 超なら 255） | Level スライダー → Color Select、Level スライダー → Brightness |
| 6 | ムービングヘッドの動き | 10 以下 = 停止、11〜255 を ch6 (速度) と ch106 (ON/OFF) に分離 | Adjust スライダー → EFX「MH Move」(円運動)、Speed Dial 20 秒〜2 秒 |
| 7 | PAR と MH のストロボ（同期） | 10 以下 = なし。11〜255 で ch1〜3 と ch107 を同じタイマーで周期的に 0 にする。半周期 0.5 秒 → 0.05 秒 | なし（1〜3 と MH Dimmer のスライダーに乗る） |
| 8 | Stinger II | 10 以下 = 0（消灯）、11〜255 = 255（内蔵の Random Show） | Level スライダー → Stinger ch1「Show Mode」 |

### ブリッジの変換オプション

サービスファイルの `ExecStart` で指定しています。値はすべて卓の生の値に対する変換です。適用順は logic → gate → deadzone → map → random → colormod → strobe です。

| オプション | 意味 |
|---|---|
| `--deadzone CH:TH` | TH 以下を 0、TH+1〜255 を 1〜255 に引き伸ばす |
| `--gate CH:TH:OUT` | CH が TH 以下なら OUT チャンネルに 0、超えたら 255 を出す（元の CH はそのまま） |
| `--map CH:lo-hi=v/...` | 範囲ごとに固定値 `v`、または `a-b` で線形補間 |
| `--logic OUT=式` | 式（`chN`、`> < <= >=`、`&` `\|` `!`）が真なら OUT チャンネルに 255、偽なら 0。生の値で判定 |
| `--random CH:TH:T1-T2:O1/O2/O3` | CH が TH 超のとき O1〜O3 に 8 色パレットのランダム色。切替周期は TH+1 で T1 ms、255 で T2 ms |
| `--colormod CH:TH:T1-T2:O1/O2/O3` | CH が TH 超のとき O1〜O3 の色を HSV で滑らかに揺らす。明度は固定、色相の振れ幅と彩度の注入量と速度が CH に比例。周期は TH+1 で T1 ms、255 で T2 ms |
| `--strobe CH:TH:T1-T2:O1/O2/...` | CH が TH 超のとき O1〜 を周期的に 0 にする。半周期は TH+1 で T1 ms、255 で T2 ms |

現在の指定:

```
--deadzone 6:10
--gate 6:10:106
--map 5:0-10=0/11-88=0/89-166=10/167-244=31/245-255=255,8:0-10=0/11-255=255
--logic 107=ch5>10
--colormod 4:10:20000-1500:1/2/3
--strobe 7:10:500-50:1/2/3/107
```

変更したら `systemctl --user daemon-reload && systemctl --user restart dmx2artnet` で反映されます。

### 設計上の注意

- QLC+ の Flash ボタンは Scene にしか効きません（EFX や Chaser は起動しない）。
  そのため EFX の ON/OFF は Adjust スライダー（Intensity 属性、0 で停止）で行い、
  速度用の値とは別チャンネル（ch106）に分けています。
- フェーダー 4 の色揺らぎは HSV 空間で計算しています。明度 V は基準色のまま、色相 H を周期の異なる 2 つの正弦波の和で
  揺らし（フェーダー量に比例した振れ幅）、彩度 S はフェーダー量に応じて注入します。
  白（彩度 0）は色相が無いので、ゆっくり回る基準色相に乗せて「白 → パステル → 鮮やか」と変化させます。
  速度を変えても色が飛ばないよう、位相は毎ティック積算しています。
- 色揺らぎとストロボはブリッジが生成するので、QLC+ 側に Chaser はありません。
  点滅の最速は半周期 50 ms（10 Hz）です。ブリッジは 50 Hz で送信し、QLC+ の処理周期も 20 ms なので、
  これより速くしても粗くなるだけです。
- Stinger は Dimmer を持たないためストロボ同期の対象外です（必要なら `--strobe` の出力に
  Stinger のチャンネルを足してください）。

### Stinger II の DMX 制御（9ch モード、ADJ マニュアル 2023 年版より）

| ch | 機能 | 値 |
|---|---|---|
| 1 | Show Mode | 0〜9 なし / 10〜219 内蔵ショー 1〜6（35 刻み） / 220〜255 Random Show |
| 2 | Color Macro | 0〜9 なし / 10〜198 色（15 色） / 199〜225 Color Fade 1 / 226〜255 Color Fade 2 |
| 3 | LED Strobe | 0〜9 なし / 10〜244 遅→速 / 245〜255 音声同期 |
| 4 | UV LEDs | 0〜134 消灯 / 135〜255 UV チェイス |
| 5 | UV Strobe & Chase Speed | 0〜127 チェイス速度（ストロボなし） / 128〜255 チェイス速度（ストロボあり） |
| 6 | Lasers | 0〜9 消灯 / 10〜49 赤 / 50〜89 緑 / 90〜129 赤+緑 / 130〜249 各種フリッカー / 250〜255 交互フリッカー |
| 7 | Laser Strobe | 0〜9 なし / 10〜244 遅→速 / 245〜255 音声同期 |
| 8 | LED Rotation | 0〜9 停止 / 10〜127 時計回り 遅→速 / 128〜255 反時計回り 遅→速 |
| 9 | Laser Rotation | 0〜127 パターン固定 / 128〜255 パターンチェイス 遅→速 |

ch1 を 10 以上にすると内蔵ショーが走り、他のチャンネルは効かなくなる前提です（2ch モードは
「ショー番号 + 速度」だけで構成されているため）。9ch モードではショーの速度は変えられません。
ch1 を 0 にして ch2〜9 を直接指定すれば、色・ストロボ・レーザー・回転を個別に組み合わせられます
（去年の「ST Strobe 1/2」シーンはこの方式）。

**安全上の注意**: Stinger II のレーザーは Class 3R で、観客に向けて照射することは禁止されています。
マニュアルは床から 3 m 以上の高さで、人のいる方向に向けないよう求めています。
UV LED も Risk Group 3（3.3 m 以内で直視・直射を避ける）です。

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
