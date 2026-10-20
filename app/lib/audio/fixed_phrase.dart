/// 事先合成好、打包進 App 的固定短句（設計文件 9.3）。
///
/// 編號沿用設計文件；5（額度用完）與 8（恢復）已取消，改成畫面提示與自動繼續。
enum FixedPhrase {
  thinkingLookup(1), // 好，我來查一下……（問答開頭）
  thinkingGoodQuestion(2), // 這個問題很好……（問答開頭替換）
  thinkingHowToPutIt(3), // 我想想怎麼說比較好（答案還沒好時補一句）
  thinkingWeb(4), // 我上網查一下……（需要上網查時）
  hostUnreachable(6), // 我連不上家裡的電腦了……
  startTour(7); // 好，我們出發吧！（按出發時）

  const FixedPhrase(this.number);

  final int number;

  /// 成品是用公眾人物的聲音複製出來的，不入 git：由 scripts/install-phrases.sh 從主機複製進來。
  String get assetPath => 'assets/phrases/$number.wav';
}
