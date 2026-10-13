# 台股 Beta 研究室

- 本機工具，僅綁定 127.0.0.1，不含交易或推播；未經使用者確認不發布。
- Python 標準函式庫；執行 `python server.py`，測試 `python -m unittest discover -s tests -v`。
- `beta.py` 負責純計算；`server.py` 負責行情、輸入驗證及 HTTP；`web/` 負責介面。
- 計算口徑、資料限制與驗證紀錄見 README.md 與 HANDOFF.md。
- 禁止以展示資料冒充真實行情；不得靜默改變價格口徑或基準。
