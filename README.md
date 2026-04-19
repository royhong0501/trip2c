# trip2c — ASCII Art 終端機工具

用 Python + OpenCV 把圖片或影片轉成 ASCII 字元畫，直接顯示在終端機上。
整套在 Docker 容器內跑，不會污染主機 Python 環境。

## 快速開始

```bash
# 建置 image（第一次，或修改 Dockerfile / requirements.txt 後）
docker compose build

# 把圖片放到 samples/，例如 samples/test.jpg
# 然後：
docker compose run --rm ascii image samples/test.jpg
```

## 使用方式

```bash
# 圖片：自動貼合終端寬度
docker compose run --rm ascii image samples/test.jpg

# 圖片：指定寬度、用方塊字元集、輸出成 PNG
docker compose run --rm ascii image samples/test.jpg \
    --width 80 --charset blocks --output output/test.png

# 影片：以接近原 FPS 播放 ASCII 串流
docker compose run --rm ascii video samples/clip.mp4

# 影片：縮小寬度，方塊字元
docker compose run --rm ascii video samples/clip.mp4 --width 100 --charset blocks
```

按 `Ctrl+C` 可在影片模式中斷播放。

## 參數

| 參數 | 預設 | 說明 |
|---|---|---|
| `--width N` | 終端機欄位數 | ASCII 輸出寬度（字元數） |
| `--charset NAME` | `default` | 字元密度集（見下表） |
| `--halfblock` | 關 | 使用 Unicode 半形方塊把**垂直解析度翻倍**（二元，忽略 `--charset`） |
| `--output PATH` | 無 | *(image 模式專用)* 把結果渲染成 PNG 存檔 |

字元集內容：

- `default` — Paul Bourke 70 階灰階 ramp，細節最豐富（**新預設**）
- `classic` — `@%#*+=-:. `（從暗到亮，10 階，傳統 ASCII 風格）
- `blocks`  — `█▓▒░ `（Unicode 方塊，5 階）
- `simple`  — `#. `（極簡，3 階）

## 提高解析度的三個方向

想要更高解析度時，可以組合使用：

1. **加大 `--width`** — 直接把字元數拉大，例如 `--width 200`
2. **用 `default` charset**（預設就是）— 70 階灰階比 10 階過渡柔和
3. **開 `--halfblock`** — 每個字元代表 2 個垂直像素，細節翻倍，
   但變成**二元黑白**（沒有灰階）。適合對比強烈的畫面。

範例：

```bash
# 高解析度、細灰階
docker compose run --rm ascii image samples/photo.jpg --width 200

# 垂直細節翻倍（二元），邊緣最銳利
docker compose run --rm ascii image samples/photo.jpg --width 160 --halfblock
```

## 檔案結構

```
trip2c/
├── ascii_art.py          # 主程式
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── samples/              # 放輸入圖片 / 影片（唯讀掛載進容器）
└── output/               # PNG 輸出（可寫掛載）
```

## 開發技巧

- `ascii_art.py` 以 bind mount 掛進容器，**改完程式不用重新 build**，
  直接 `docker compose run --rm ascii ...` 就會看到變化。
- 修改 `requirements.txt` 或 `Dockerfile` 後要 `docker compose build`。
- 輸出的 PNG 檔會同步出現在主機的 `output/` 目錄。

## 核心原理

1. `cv2.imread` / `cv2.VideoCapture` 讀取影像
2. `cv2.cvtColor(..., COLOR_BGR2GRAY)` 轉灰階
3. `cv2.resize` 縮到目標尺寸（高度有除以 2 修正字元長寬比）
4. numpy 向量化把像素亮度 0–255 映射到字元密度集的索引
5. 影片模式用 ANSI escape `\033[H` 把游標移回左上角重繪，避免整片滾動

## 已知限制

- **Webcam 模式不支援**：Docker Desktop for Windows 存取 USB 鏡頭需要
  `usbipd-win` 手動 attach，設定繁瑣，因此本工具只支援圖片與影片檔。
- 終端機需支援 ANSI escape（Windows Terminal、大多數 Linux/macOS 終端都 OK；
  舊版 cmd.exe 可能需要 Windows 10+）。
