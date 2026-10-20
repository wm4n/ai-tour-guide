"""語助詞安全清單的測試句庫與判定規則（#16）。

每個候選詞 3 個自然的口語句 × 3 個 seed，用驗收器（Whisper CER）看會不會跑成類粵語腔／聽不懂。
"""

CASES: dict[str, list[str]] = {
    "哇": [
        "哇，這條老街的磚牆保存得真完整。",
        "哇，抬頭就看到好大一棵老榕樹。",
        "哇，這間店的招牌已經掛了快一百年。",
    ],
    "對了": [
        "對了，旁邊那間茶行也很有名。",
        "對了，這裡以前是進出口貨物的碼頭。",
        "對了，前面轉角還有一間老藥房。",
    ],
    "而且": [
        "這棟樓不只好看，而且還是市定古蹟。",
        "這裡的巷子很窄，而且兩邊都是紅磚牆。",
        "茶葉很香，而且價格也很親切。",
    ],
    "其實": [
        "其實這條街以前是河邊的貨運碼頭。",
        "其實這間店的招牌，是老闆的爺爺親手寫的。",
        "其實從這裡往前走，不用五分鐘就到廟口。",
    ],
    "你看": [
        "你看，二樓的窗花是手工雕刻的。",
        "你看，那面牆上還留著舊時代的廣告。",
        "你看，屋簷下有一排燕子窩。",
    ],
    "欸": [
        "欸，你有沒有聞到一股茶香？",
        "欸，那邊好像在辦什麼活動。",
        "欸，前面那棟房子特別好看。",
    ],
    "啊": [
        "這裡的夕陽真的很美啊。",
        "啊，原來這就是傳說中的老店。",
        "那時候的生意可是好得不得了啊。",
    ],
    "喔": [
        "前面有個小廣場，可以休息一下喔。",
        "這間店的紅豆餅很有名喔。",
        "喔，原來這裡以前是學校。",
    ],
    "吧": ["我們先往前走走看吧。", "這間老店應該有一百多年了吧。", "要不要進去喝杯茶吧。"],
    "啦": ["好啦，我們繼續往前走。", "這裡就是剛剛說的老碼頭啦。", "別擔心啦，這條路很好走。"],
    "一下下": [
        "我們在這裡停一下下，聽我說個故事。",
        "你可以先拍張照，等一下下再走。",
        "這個故事很短，只要一下下就講完。",
    ],
    "呢": [
        "你猜這棟老房子是做什麼用的呢？",
        "為什麼這條街叫做迪化街呢？",
        "接下來我們要去哪裡呢？",
    ],
}

SEEDS = (1234, 7, 42)

SAFE_PASS_RATE = 1.0
CAUTION_PASS_RATE = 0.75


def classify(cers: list[float], threshold: float) -> str:
    """全過＝safe；過關率 ≥ 75%＝caution（要搭配驗收重試）；其餘＝unsafe。"""
    passed = sum(c <= threshold for c in cers)
    rate = passed / len(cers)
    if rate >= SAFE_PASS_RATE:
        return "safe"
    if rate >= CAUTION_PASS_RATE:
        return "caution"
    return "unsafe"


def summarize(records: list[dict], threshold: float) -> dict[str, dict]:
    by_word: dict[str, list[float]] = {}
    for record in records:
        by_word.setdefault(record["word"], []).append(record["cer"])
    return {
        word: {
            "runs": len(cers),
            "passed": sum(c <= threshold for c in cers),
            "mean_cer": round(sum(cers) / len(cers), 3),
            "max_cer": round(max(cers), 3),
            "label": classify(cers, threshold),
        }
        for word, cers in by_word.items()
    }
