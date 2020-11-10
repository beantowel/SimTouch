/**
 *
 * Driver for touch simulation
 * control shift register whose output make address of a capacity matrix
 *
 ******************************************************************************
 */

#include "touch_driver.h"
#include "usbd_def.h"
#include <stdlib.h>
#include <string.h>

#define RX_RING_SIZE 16 // APP_RX_DATA_SIZE
#define CONCAT_BYTE(lo, hi) ((uint16_t)((lo) + ((hi) << 8)))

#define SET 0xFF   // SET <buffer data>*2 <duty>*2
#define TOUCH 0xFE // TOUCH <duration>
#define SLEEP 0xFD // SLEEP <duration>
#define DRAW 0xFC  // DRAW <new duty>*2 <duration>

// <buffer data> 8-bit shift register chain:
// reverse(<Col_0>-...-<Col_n>-<Row_0>-...-<Row_n>)
static uint8_t receiveBufRing[RX_RING_SIZE][USB_FS_MAX_PACKET_SIZE];
static uint32_t receiveLenRing[RX_RING_SIZE];
static uint16_t ringBegin, ringEnd;
TCH_BOARD tchBoard;

void TCH_Parse_Command();
void flushPos(TCH_BOARD *board, uint8_t col_duty, uint8_t row_duty);
// void outputEnable(TCH_BOARD *board, uint8_t state);
void clearReg(TCH_BOARD *board);
void pwmTouch(TCH_BOARD *board, uint32_t duration);
void pwmDraw(TCH_BOARD *board, uint8_t ncol_duty, uint8_t nrow_duty,
             uint32_t duration);

void TCH_Driver_Init(TCH_BOARD *board, GPIO_TypeDef *GPIOx, uint16_t _oe,
                     uint16_t rclk, uint16_t srclk, uint16_t _srclr,
                     uint16_t ser) {
  board->GPIO_group = GPIOx;
  board->_OE_PIN = _oe;
  board->RCLK_PIN = rclk;
  board->SRCLK_PIN = srclk;
  board->_SRCLR_PIN = _srclr;
  board->SER_PIN = ser;
  board->col_duty = 0;
  board->row_duty = 0;
  board->outputBufHi =
      (uint8_t *)malloc(sizeof(uint8_t) * TCHBOARD_OUTPUT_BUF_SIZE);
  board->outputBufLo =
      (uint8_t *)malloc(sizeof(uint8_t) * TCHBOARD_OUTPUT_BUF_SIZE);
  ringBegin = 0;
  ringEnd = 0;
  memset(receiveBufRing, 0, sizeof(receiveBufRing));
  memset(receiveLenRing, 0, sizeof(receiveLenRing));
}

uint8_t TCH_Receive_Callback(uint8_t *Buf, uint32_t Len) {
  memcpy(receiveBufRing[ringEnd], Buf, Len);
  receiveLenRing[ringEnd] = Len;
  ringEnd = (ringEnd + 1) % RX_RING_SIZE;
  return 0;
}

void TCH_Start() { TCH_Parse_Command(); }

void TCH_Parse_Command() {
  while (ringBegin != ringEnd) {
    uint8_t *receiveBuf = receiveBufRing[ringBegin];
    uint32_t i = 0, len = receiveLenRing[ringBegin];
    uint16_t duration;
    TCH_BOARD *board = &tchBoard;
    while (i < len) {
      HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET); // led on
      switch (receiveBuf[i]) {
      case SET:
        memcpy(board->outputBufHi, &receiveBuf[i + 1],
               TCHBOARD_OUTPUT_BUF_SIZE);
        memcpy(board->outputBufLo,
               &receiveBuf[i + 1 + TCHBOARD_OUTPUT_BUF_SIZE],
               TCHBOARD_OUTPUT_BUF_SIZE);
        board->col_duty = receiveBuf[i + 1 + 2 * TCHBOARD_OUTPUT_BUF_SIZE];
        board->row_duty = receiveBuf[i + 1 + 2 * TCHBOARD_OUTPUT_BUF_SIZE + 1];
        i += 1 + 2 * TCHBOARD_OUTPUT_BUF_SIZE + 2;
        break;
      case TOUCH:
        duration = CONCAT_BYTE(receiveBuf[i + 1], receiveBuf[i + 2]);
        pwmTouch(board, duration);
        i += 1 + 2;
        break;
      case SLEEP:
        duration = CONCAT_BYTE(receiveBuf[i + 1], receiveBuf[i + 2]);
        HAL_Delay(duration);
        i += 1 + 2;
        break;
      case DRAW:
        duration = CONCAT_BYTE(receiveBuf[i + 3], receiveBuf[i + 4]);
        pwmDraw(board, receiveBuf[i + 1], receiveBuf[i + 2], duration);
        i += 1 + 2 + 2;
        break;
      default:
        i++;
        break;
      }
      HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET); // led off
    }
    ringBegin = (ringBegin + 1) % RX_RING_SIZE;
  }
}

void flushPos(TCH_BOARD *board, uint8_t col_duty, uint8_t row_duty) {
  for (uint16_t cycle = 0; cycle < 0xFF; cycle += 0x10) {
    clearReg(board);
    for (uint16_t i = 0; i < TCHBOARD_OUTPUT_BUF_SIZE; i++) {
      uint8_t byte;
      if (i < (TCHPAD_ROWS / 8)) {
        byte = cycle < row_duty ? board->outputBufHi[i] : board->outputBufLo[i];
      } else {
        byte = cycle < col_duty ? board->outputBufHi[i] : board->outputBufLo[i];
        // active-low output for column selection
        byte = ~byte;
      }
      // write to shift register
      for (uint16_t j = 0; j < 8; j++) {
        // flip bits for MSB order
        uint8_t bit = byte & (1 << (7 - j));
        HAL_GPIO_WritePin(board->GPIO_group, board->SRCLK_PIN,
                          GPIO_PIN_RESET); // CLK: 0
        HAL_GPIO_WritePin(board->GPIO_group, board->SER_PIN, bit);
        HAL_GPIO_WritePin(board->GPIO_group, board->SRCLK_PIN,
                          GPIO_PIN_SET); // CLK: ↑
      }
    }
    // add bubble because shift register state is one clock pulse ahead of the
    // storage(latch) register
    HAL_GPIO_WritePin(board->GPIO_group, board->RCLK_PIN,
                      GPIO_PIN_RESET); // CLK: 0
    HAL_GPIO_WritePin(board->GPIO_group, board->SER_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(board->GPIO_group, board->RCLK_PIN,
                      GPIO_PIN_SET); // CLK ↑
  }
}

void clearReg(TCH_BOARD *board) {
  HAL_GPIO_WritePin(board->GPIO_group, board->_SRCLR_PIN,
                    GPIO_PIN_RESET); // enable, clear reg
  HAL_GPIO_WritePin(board->GPIO_group, board->_SRCLR_PIN,
                    GPIO_PIN_SET); // disable
}

uint32_t deltaTick(uint32_t now, uint32_t pre) {
  if (now >= pre) {
    return now - pre;
  } else {
    // 24 bit sys tick
    return (1 << 24) - pre + now;
  }
}

void pwmTouch(TCH_BOARD *board, uint32_t duration) {
  uint32_t check_time = HAL_GetTick();
  while (deltaTick(HAL_GetTick(), check_time) < duration) {
    flushPos(board, board->col_duty, board->row_duty);
  }
  // close output
  clearReg(board);
  for (uint16_t i = 0; i < TCHPAD_COLS / 8; i++) {
    for (uint16_t j = 0; j < 8; j++) {
      HAL_GPIO_WritePin(board->GPIO_group, board->SRCLK_PIN,
                        GPIO_PIN_RESET); // CLK: 0
      HAL_GPIO_WritePin(board->GPIO_group, board->SER_PIN, 1);
      HAL_GPIO_WritePin(board->GPIO_group, board->SRCLK_PIN,
                        GPIO_PIN_SET); // CLK: ↑
    }
  }
  HAL_GPIO_WritePin(board->GPIO_group, board->RCLK_PIN,
                    GPIO_PIN_RESET); // CLK: 0
  HAL_GPIO_WritePin(board->GPIO_group, board->SER_PIN, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(board->GPIO_group, board->RCLK_PIN,
                    GPIO_PIN_SET); // CLK ↑
}

void pwmDraw(TCH_BOARD *board, uint8_t ncol_duty, uint8_t nrow_duty,
             uint32_t duration) {
  uint32_t check_time = HAL_GetTick();
  for (uint32_t dt = 0; dt < duration;
       dt = deltaTick(HAL_GetTick(), check_time)) {
    uint8_t col_duty =
        board->col_duty + (ncol_duty - board->col_duty) * dt / duration;
    uint8_t row_duty =
        board->row_duty + (nrow_duty - board->row_duty) * dt / duration;
    flushPos(board, col_duty, row_duty);
  }
}