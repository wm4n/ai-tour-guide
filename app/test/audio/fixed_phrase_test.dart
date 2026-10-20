import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('編號沿用設計文件 9.3：5（額度用完）與 8（恢復）已取消', () {
    expect(FixedPhrase.values.map((p) => p.number), [1, 2, 3, 4, 6, 7]);
  });

  test('按「出發」播放的是短句 7', () {
    expect(FixedPhrase.startTour.number, 7);
  });

  test('音檔路徑是 assets/phrases/<編號>.wav', () {
    expect(FixedPhrase.startTour.assetPath, 'assets/phrases/7.wav');
    expect(FixedPhrase.hostUnreachable.assetPath, 'assets/phrases/6.wav');
  });
}
