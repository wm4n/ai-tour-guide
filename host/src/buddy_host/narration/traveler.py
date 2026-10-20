"""使用者裝置回報的即時狀態（怎麼移動、跟誰一起、幾點），讓夥伴依情況調整說法。"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class TravelMode(StrEnum):
    WALKING = "walking"
    DRIVING = "driving"


class Companions(StrEnum):
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"


_COMPANIONS = {
    Companions.SOLO: "他一個人，可以用比較貼近、像說悄悄話的口吻。",
    Companions.COUPLE: "他們兩個人一起。",
    Companions.FAMILY: "他和家人一起。",
    Companions.FRIENDS: "他和朋友一起。",
}
_MODE = {
    TravelMode.WALKING: "他正在走路，看得到周圍，可以請他看一下、想一下。",
    TravelMode.DRIVING: (
        "他正在開車：不要請他停下來、低頭或轉頭看，只說「等一下會經過」「路過時可以瞄一眼」，"
        "而且講短一點。"
    ),
}
_CHILDREN = (
    "有小朋友同行：用簡單有趣的說法，可以出個小問題讓大家一起找；"
    "不要講鬼怪、死亡、酒或其他大人的話題。"
)


def time_of_day(moment: datetime) -> str:
    hour = moment.hour
    if hour < 5:
        return "深夜"
    for limit, name in ((11, "早上"), (13, "中午"), (17, "下午"), (19, "傍晚"), (24, "晚上")):
        if hour < limit:
            return name
    return "晚上"


@dataclass(frozen=True)
class TravelerContext:
    mode: TravelMode | None = None
    companions: Companions | None = None
    with_children: bool = False
    local_time: datetime | None = None

    def describe(self) -> list[str]:
        lines: list[str] = []
        if self.local_time:
            lines.append(f"現在是{time_of_day(self.local_time)}{self.local_time:%H:%M}。")
        if self.mode:
            lines.append(_MODE[self.mode])
        if self.companions:
            lines.append(_COMPANIONS[self.companions])
        if self.with_children:
            lines.append(_CHILDREN)
        return lines

    def key(self) -> str:
        """快取用：只看會改變稿子內容的部分，幾點幾分的差別不算。"""
        part = time_of_day(self.local_time) if self.local_time else ""
        return f"{self.mode}|{self.companions}|{self.with_children}|{part}"
