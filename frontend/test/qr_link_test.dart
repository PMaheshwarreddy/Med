import 'package:flutter_test/flutter_test.dart';
import 'package:medora/api/api_client.dart';

void main() {
  test('a kiosk opened as localhost puts the network address in its QR', () {
    final kiosk = Uri.parse('http://localhost:8090/#/kiosk/phone');
    // Started without the address (VS Code's Run button): the server's.
    expect(
      publicBase(kiosk, '', '192.168.29.114').toString(),
      'http://192.168.29.114:8090/',
    );
    // An address baked in at start that went stale: the server's wins.
    expect(
      publicBase(kiosk, 'http://192.168.1.5:8090', '192.168.29.114').host,
      '192.168.29.114',
    );
    // Not known yet: what was baked in.
    expect(
      publicBase(kiosk, 'http://192.168.1.5:8090', '').toString(),
      'http://192.168.1.5:8090',
    );
    // A real domain always wins.
    expect(
      publicBase(
        kiosk,
        'https://medora.example.com',
        '192.168.29.114',
      ).toString(),
      'https://medora.example.com',
    );
    // Opened on the network already (a phone, another screen): as opened.
    expect(
      publicBase(
        Uri.parse('http://192.168.29.114:8080/?x=1'),
        '',
        '10.0.0.2',
      ).toString(),
      'http://192.168.29.114:8080/',
    );
  });

  test('the server serving the app gives one fixed address for phones', () {
    // Whatever port or mode the kiosk was started with, the QR points at the
    // server (port 8100), which serves the built app.
    for (final opened in [
      'http://localhost:46265/#/kiosk/phone',
      'http://localhost:8090/#/kiosk/phone',
      'http://192.168.100.152:46265/',
    ]) {
      expect(
        publicBase(
          Uri.parse(opened),
          '',
          '192.168.100.152',
          phone: 'http://192.168.100.152:8100',
        ).replace(fragment: '/phone/AB12').toString(),
        'http://192.168.100.152:8100/#/phone/AB12',
      );
    }
    // A real domain still wins.
    expect(
      publicBase(
        Uri.parse('http://localhost:46265/'),
        'https://medora.example.com',
        '192.168.100.152',
        phone: 'http://192.168.100.152:8100',
      ).host,
      'medora.example.com',
    );
  });
}
