// Replaces the default Flutter template test (it referenced a class called MyApp that this project does not have).
// Pure-logic checks for the offline chat engine: no device, no network.
import 'package:flutter_test/flutter_test.dart';
import '../lib/chat_engine.dart';

void main() {
  test('accents are folded and apostrophes removed', () {
    expect(ChatEngine.plain("Ng'ombe  Fièvre!"), 'ngombe fievre');
  });

  test('plural and -ing endings are stemmed like the server', () {
    expect(ChatEngine.stem('leaves'), 'leave');
    expect(ChatEngine.stem('wilting'), 'wilt');
  });

  test('pure greetings are small talk in every language, real questions are not', () async {
    for (final msg in ['Hello', 'Moni', 'Habari', 'Bonjour', 'Olá']) {
      expect(await ChatEngine.smalltalk(msg, 'en'), isNotNull, reason: msg);
    }
    expect(await ChatEngine.smalltalk('hello my maize has yellow spots', 'en'), isNull);
  });

  test('emergency rules work with no network and no downloaded pack', () async {
    expect(await ChatEngine.emergencyIfAny('I think it is anthrax', 'en', 'cattle'), isNotNull);
    expect(await ChatEngine.emergencyIfAny('many died suddenly', 'ny', 'chicken'), isNotNull);
    expect(await ChatEngine.emergencyIfAny('spots on my tomato leaves', 'en', 'tomato'), isNull);
  });
}
