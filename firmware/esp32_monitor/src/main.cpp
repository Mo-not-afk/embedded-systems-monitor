// Hardware-targeted PlatformIO sketch. It is not compiled or hardware-tested in this environment.
#include <Arduino.h>
#include <math.h>
#include <SPI.h>
#include <Wire.h>

namespace {
constexpr uint8_t kMpuAddress = 0x68;
constexpr uint8_t kMcp3008ChipSelect = 5;
constexpr uint8_t kDataReadyPin = 4;
constexpr float kVibrationBiasVolts = 1.65f;
constexpr float kVibrationSensitivityVoltsPerG = 0.300f;  // Calibrate for the selected analog sensor.

volatile bool g_sample_ready = false;
uint32_t g_sequence = 0;

void IRAM_ATTR onDataReady() { g_sample_ready = true; }

uint16_t crc16Ccitt(const uint8_t* bytes, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(bytes[i]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
                           : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

bool readMpuRegister(uint8_t reg, uint8_t* destination, size_t length) {
  Wire.beginTransmission(kMpuAddress);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(kMpuAddress, static_cast<uint8_t>(length)) != length) return false;
  for (size_t i = 0; i < length; ++i) destination[i] = Wire.read();
  return true;
}

bool writeMpuRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(kMpuAddress);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

int16_t readSignedWord(const uint8_t* bytes) {
  return static_cast<int16_t>((static_cast<uint16_t>(bytes[0]) << 8) | bytes[1]);
}

bool readMpu(int16_t* accel_x, float* temperature_c) {
  uint8_t accel_bytes[2];
  uint8_t temp_bytes[2];
  if (!readMpuRegister(0x3B, accel_bytes, sizeof(accel_bytes))) return false;
  if (!readMpuRegister(0x41, temp_bytes, sizeof(temp_bytes))) return false;
  *accel_x = readSignedWord(accel_bytes);
  *temperature_c = readSignedWord(temp_bytes) / 340.0f + 36.53f;
  return true;
}

bool readMcp3008(uint8_t channel, uint16_t* result) {
  if (channel > 7) return false;
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(kMcp3008ChipSelect, LOW);
  SPI.transfer(0x01);
  const uint8_t high = SPI.transfer(static_cast<uint8_t>(0x80 | (channel << 4)));
  const uint8_t low = SPI.transfer(0x00);
  digitalWrite(kMcp3008ChipSelect, HIGH);
  SPI.endTransaction();
  *result = static_cast<uint16_t>(((high & 0x03) << 8) | low);
  return true;
}

void putLe16(uint8_t* bytes, size_t offset, uint16_t value) {
  bytes[offset] = static_cast<uint8_t>(value & 0xFF);
  bytes[offset + 1] = static_cast<uint8_t>(value >> 8);
}

void putLe32(uint8_t* bytes, size_t offset, uint32_t value) {
  for (uint8_t i = 0; i < 4; ++i) bytes[offset + i] = static_cast<uint8_t>(value >> (8 * i));
}

void sendTelemetry(float temperature_c, float vibration_g) {
  // Frame layout matches Python's <2sIhH payload followed by a little-endian CRC-16.
  uint8_t frame[12] = {'S', 'M'};
  putLe32(frame, 2, g_sequence++);
  const int16_t temperature_centi = static_cast<int16_t>(lroundf(temperature_c * 100.0f));
  const uint16_t vibration_milli = static_cast<uint16_t>(lroundf(vibration_g * 1000.0f));
  putLe16(frame, 6, static_cast<uint16_t>(temperature_centi));
  putLe16(frame, 8, vibration_milli);
  putLe16(frame, 10, crc16Ccitt(frame, 10));
  Serial.write(frame, sizeof(frame));  // UART byte stream; receiver verifies each frame's CRC.
}
}  // namespace

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, 16, 17);  // Diagnostics use a separate UART from binary telemetry.
  Wire.begin();
  SPI.begin();
  pinMode(kMcp3008ChipSelect, OUTPUT);
  digitalWrite(kMcp3008ChipSelect, HIGH);
  pinMode(kDataReadyPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(kDataReadyPin), onDataReady, RISING);

  // Wake the MPU6050; check the I2C acknowledgement before entering the sampling loop.
  if (!writeMpuRegister(0x6B, 0x00)) {
    Serial2.println("ERR:MPU6050_NOT_FOUND");
  } else if (!writeMpuRegister(0x1A, 0x03) || !writeMpuRegister(0x19, 9) || !writeMpuRegister(0x38, 0x01)) {
    Serial2.println("ERR:MPU6050_CONFIG");
  }
}

void loop() {
  if (!g_sample_ready) return;
  noInterrupts();
  g_sample_ready = false;
  interrupts();

  int16_t accel_x_raw = 0;
  uint16_t vibration_adc = 0;
  float temperature_c = 0;
  if (!readMpu(&accel_x_raw, &temperature_c) || !readMcp3008(0, &vibration_adc)) {
    Serial2.println("ERR:SENSOR_READ");
    return;
  }

  const float adc_volts = vibration_adc * (3.3f / 1023.0f);
  const float vibration_g = fabsf(adc_volts - kVibrationBiasVolts) / kVibrationSensitivityVoltsPerG;
  (void)accel_x_raw;  // Kept available for calibration experiments alongside the external vibration sensor.
  sendTelemetry(temperature_c, vibration_g);
}
