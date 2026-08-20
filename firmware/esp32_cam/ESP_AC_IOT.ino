#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "secrets.h"

// AI Thinker ESP32-CAM pin map
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

WebServer server(80);

// Output pins available in the supplied prototype.
const int led1Pin = 4;
const int led2Pin = 33;
// Commands E/F are intentionally reserved because a third LED was not wired.

bool isAuthenticated = false;

void handleSignIn();
void handleMessagePage();
void handleCapture();
void controlLEDs(char command);
void sendImageOverUART(const uint8_t *imageBuffer, size_t length);

void setup() {
  Serial.begin(115200);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_QVGA;   // 320x240 for lower UART payload
  config.jpeg_quality = 20;
  config.fb_count = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera initialization failed");
    return;
  }

  pinMode(led1Pin, OUTPUT);
  pinMode(led2Pin, OUTPUT);
  digitalWrite(led1Pin, LOW);
  digitalWrite(led2Pin, HIGH); // Active-low wiring in the supplied prototype.

  WiFi.softAP(AP_SSID, AP_PASSWORD);

  server.on("/", HTTP_ANY, handleSignIn);
  server.on("/message", HTTP_ANY, handleMessagePage);
  server.on("/capture", HTTP_GET, handleCapture);
  server.begin();

  Serial.println("CONFIG_COMPLETE");
}

void loop() {
  server.handleClient();
  if (Serial.available() > 0) {
    controlLEDs((char)Serial.read());
  }
}

void handleSignIn() {
  String username = server.arg("username");
  String password = server.arg("password");
  String botEnabled = server.arg("bot_enabled");

  if (username == WEB_USERNAME && password == WEB_PASSWORD) {
    isAuthenticated = true;
    if (botEnabled == "on") {
      Serial.println("Signed in! Telegram bot reading enabled!");
    } else {
      Serial.println("Signed in!");
    }
    server.sendHeader("Location", "/message");
    server.send(302, "text/plain", "Redirecting...");
    return;
  }

  String errorHtml = "";
  if (username.length() > 0 || password.length() > 0) {
    errorHtml = "<p style='color:#b00020'>Invalid credentials. Try again.</p>";
    Serial.println("Invalid credentials. Try again.");
  }

  String html =
      "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
      "<meta name='viewport' content='width=device-width,initial-scale=1'>"
      "<title>IoT Sign In</title></head><body>"
      "<h1>ESP32-CAM IoT Gateway</h1>" + errorHtml +
      "<form method='POST' action='/'>"
      "<label>Username <input name='username' required></label><br>"
      "<label>Password <input type='password' name='password' required></label><br>"
      "<label><input type='checkbox' name='bot_enabled'> Enable Telegram control</label><br>"
      "<button type='submit'>Sign in</button></form></body></html>";
  server.send(200, "text/html", html);
}

void handleMessagePage() {
  if (!isAuthenticated) {
    server.sendHeader("Location", "/");
    server.send(302, "text/plain", "Redirecting...");
    return;
  }

  String message = server.arg("message");
  if (message.length() > 0) {
    // The PC-side Python controller interprets this natural-language text.
    Serial.println(message);
  }

  String feedback = message.length() > 0
      ? "<p>Message sent to the PC controller.</p>"
      : "";

  String html =
      "<!DOCTYPE html><html><head><meta charset='UTF-8'>"
      "<meta name='viewport' content='width=device-width,initial-scale=1'>"
      "<title>IoT Control</title></head><body>"
      "<h1>ESP32-CAM Control</h1>" + feedback +
      "<form method='POST' action='/message'>"
      "<label>Natural-language command <input name='message' required></label>"
      "<button type='submit'>Send</button></form>"
      "<p><a href='/capture'>Capture image</a></p>"
      "</body></html>";
  server.send(200, "text/html", html);
}

void controlLEDs(char command) {
  switch (command) {
    case 'A': digitalWrite(led1Pin, HIGH); break;
    case 'B': digitalWrite(led1Pin, LOW); break;
    case 'C': digitalWrite(led2Pin, LOW); break;  // active-low ON
    case 'D': digitalWrite(led2Pin, HIGH); break; // active-low OFF
    case 'E': /* reserved: third LED not wired */ break;
    case 'F': /* reserved: third LED not wired */ break;
    default: break;
  }
}

void handleCapture() {
  if (!isAuthenticated) {
    server.sendHeader("Location", "/");
    server.send(302, "text/plain", "Redirecting...");
    return;
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }

  sendImageOverUART(fb->buf, fb->len);
  esp_camera_fb_return(fb);

  server.send(
      200,
      "text/html",
      "<!DOCTYPE html><html><body><h1>Image sent to PC over UART.</h1>"
      "<p><a href='/message'>Back</a></p></body></html>"
  );
}

void sendImageOverUART(const uint8_t *imageBuffer, size_t length) {
  Serial.println("Starting image transmission over UART...");
  Serial.write((const uint8_t *)"START_IMG", 9);

  // Fixed-width length field: matches the PC parser exactly.
  uint32_t length32 = (uint32_t)length;
  Serial.write((uint8_t *)&length32, sizeof(length32));
  Serial.write(imageBuffer, length);
  Serial.write((const uint8_t *)"END_IMG", 7);
  Serial.println("Image transmission complete.");
}
