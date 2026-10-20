import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

/// 沒辦法拍照（沒有相機、沒有權限）。[message] 可以直接顯示給使用者。
class PhotoUnavailable implements Exception {
  PhotoUnavailable(this.message);

  final String message;

  @override
  String toString() => 'PhotoUnavailable: $message';
}

/// 拍一張照片。
abstract class PhotoSource {
  /// 回傳 JPEG；使用者取消拍照時是 null。
  Future<Uint8List?> take();
}

/// 開系統相機拍照。縮到長邊 1600 像素、品質 80：上傳走 Tailscale，幾百 KB 就夠 Claude 認東西。
class CameraPhotoSource implements PhotoSource {
  CameraPhotoSource({ImagePicker? picker}) : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  @override
  Future<Uint8List?> take() async {
    try {
      final file = await _picker.pickImage(
        source: ImageSource.camera,
        maxWidth: 1600,
        maxHeight: 1600,
        imageQuality: 80,
        requestFullMetadata: false,
      );
      return file == null ? null : await file.readAsBytes();
    } on PlatformException catch (error) {
      throw PhotoUnavailable(
        error.code == 'camera_access_denied'
            ? '需要相機權限才能拍照，請到「設定」開啟'
            : '無法開啟相機：${error.message ?? error.code}',
      );
    }
  }
}

/// 開發用：不開相機，每次都「拍到」同一張照片。模擬器沒有相機，端到端測試用
/// `--dart-define=FAKE_PHOTO=true` 啟用（見 app/README.md）。
class FixedPhotoSource implements PhotoSource {
  /// 最小的合法 JPEG（1×1 像素）；主機只看檔頭，重播模式的假答案也不看內容。
  static final tinyJpeg = Uint8List.fromList(const [
    0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01, //
    0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
  ]);

  @override
  Future<Uint8List?> take() async => tinyJpeg;
}
