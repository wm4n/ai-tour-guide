# App 與主機的 JSON 契約

這裡是主機**實際輸出**的回應範例。兩邊各有測試讀同一份：

- 主機：`host/tests/qa/test_qa_api.py（`test_the_responses_match_the_contract…`）` 呼叫真的端點，把結果（id 與秒數正規化後）和這些檔案比對。
- App：`app/test/qa/contract_test.dart` 用這些檔案當主機的回應，確認 `HttpQaApi` 解得開。
- 聲音清單 `voices.json`：主機 `host/tests/test_voices_api.py`、App `app/test/voice/voice_api_test.dart`。

改了欄位名稱或型別，主機測試會先紅；照新的輸出更新這裡的檔案後，App 測試才會跟著紅，提醒你改 Dart。
