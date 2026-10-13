# 台股 Beta 研究室

- 課程歸屬標示固定為「Freddy 投資課內容」；脈絡見 docs/course-context.md。

- 本機工具，僅綁定 127.0.0.1，不含交易或推播；使用者已於2026-10-13授權將此repo推送GitHub並設為public，網站服務部署另行授權。
- Python 標準函式庫；執行 `python server.py`，測試 `python -m unittest discover -s tests -v`。
- `beta.py` 負責純計算；`server.py` 負責行情、輸入驗證及 HTTP；`web/` 負責介面。
- 計算口徑、資料限制與驗證紀錄見 README.md 與 HANDOFF.md。
- 禁止以展示資料冒充真實行情；不得靜默改變價格口徑或基準。
