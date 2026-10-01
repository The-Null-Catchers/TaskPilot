import 'package:flutter_test/flutter_test.dart';
import 'package:taskpilot_mobile/src/features/onboarding/onboarding_screen.dart';

void main() {
  test('onboarding recommends a useful template for every use case', () {
    expect(suggestedTemplateForUseCase('Personal'), 'Personal Productivity');
    expect(suggestedTemplateForUseCase('Software development'), 'Software Development');
    expect(suggestedTemplateForUseCase('Business'), 'Product Launch');
    expect(suggestedTemplateForUseCase('School'), 'University Project');
    expect(suggestedTemplateForUseCase('Other'), 'Blank Project');
    expect(suggestedTemplateForUseCase('unknown'), 'Blank Project');
  });
}
