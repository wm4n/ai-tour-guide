import 'package:buddy_tour/tour/resume_point.dart';
import 'package:flutter_test/flutter_test.dart';

Duration s(double seconds) =>
    Duration(microseconds: (seconds * 1000000).round());

void main() {
  const starts = [0.0, 1.5, 3.5];

  test(
    'interrupted in the middle of a sentence goes back to its beginning',
    () {
      expect(resumePoint(s(2.0), starts), s(1.5));
      expect(resumePoint(s(1.6), starts), s(1.5));
      expect(resumePoint(s(5.0), starts), s(3.5));
    },
  );

  test(
    'interrupted exactly at a sentence boundary resumes at that boundary',
    () {
      expect(resumePoint(s(1.5), starts), s(1.5));
      expect(resumePoint(s(3.5), starts), s(3.5));
      expect(resumePoint(s(0.0), starts), s(0.0));
    },
  );

  test(
    'interrupted in the silence before a sentence resumes at that sentence',
    () {
      // 句子前面至少有 0.3 秒的靜音（主機偵測的門檻）：落在靜音裡就等於剛好在句界
      expect(resumePoint(s(3.3), starts), s(3.5));
      expect(resumePoint(s(1.25), starts), s(1.5));
    },
  );

  test('just before that silence it is still the previous sentence', () {
    expect(resumePoint(s(3.19), starts), s(1.5));
  });

  test('before the first sentence it starts at the first sentence', () {
    expect(resumePoint(s(0.1), const [0.4, 2.0]), s(0.4));
  });

  test('without sentence starts it resumes right where it was interrupted', () {
    expect(resumePoint(s(7.25), const []), s(7.25));
  });

  test('a single sentence always restarts from its beginning', () {
    expect(resumePoint(s(9.0), const [0.0]), s(0.0));
  });
}
