// Arduino actuator node for the IoT final project.
// Serial command alphabet: G..L at 115200 baud.

const int led1Pin = 2;
const int led2Pin = 4;
const int buzzerPin = 3;

void setup() {
  pinMode(led1Pin, OUTPUT);
  pinMode(led2Pin, OUTPUT);
  pinMode(buzzerPin, OUTPUT);

  digitalWrite(led1Pin, LOW);
  digitalWrite(led2Pin, LOW);
  digitalWrite(buzzerPin, LOW);

  Serial.begin(115200);
}

void loop() {
  if (Serial.available() <= 0) {
    return;
  }

  const char command = (char)Serial.read();
  switch (command) {
    case 'G': digitalWrite(led1Pin, HIGH); break;
    case 'H': digitalWrite(led1Pin, LOW); break;
    case 'I': digitalWrite(led2Pin, HIGH); break;
    case 'J': digitalWrite(led2Pin, LOW); break;
    case 'K': digitalWrite(buzzerPin, HIGH); break;
    case 'L': digitalWrite(buzzerPin, LOW); break;
    default: break;
  }
}
