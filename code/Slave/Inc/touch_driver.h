/**
 *
 * Driver for touch simulation
 * control shift register whose output make address of a capacity matrix
 *
 ******************************************************************************
 */

#ifndef __TOUCH_DRIVER__H__
#define __TOUCH_DRIVER__H__

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f1xx_hal.h"

#define TCHPAD_COLS 8
#define TCHPAD_ROWS 8
#define TCHBOARD_OUTPUT_BUF_SIZE (((TCHPAD_COLS) + (TCHPAD_ROWS)) / 8)

typedef struct _TCH_BOARD {
  // 74HC595 pins
  // 8-Bit Serial-Input/Serial or Parallel-Output ShiftRegister with Latched
  // 3-State Outputs RCLK: latch clock, SRCLK: shiftRegister clock
  GPIO_TypeDef *GPIO_group;
  uint16_t _OE_PIN, RCLK_PIN, SRCLK_PIN, _SRCLR_PIN, SER_PIN;
  uint8_t col_duty, row_duty;
  uint8_t *outputBufHi, *outputBufLo;
} TCH_BOARD;
extern TCH_BOARD tchBoard;

void TCH_Driver_Init(TCH_BOARD *board, GPIO_TypeDef *GPIOx, uint16_t _oe,
                     uint16_t rclk, uint16_t srclk, uint16_t _srclr,
                     uint16_t ser);
uint8_t TCH_Receive_Callback(uint8_t *Buf, uint32_t Len);
void TCH_Start();

#ifdef __cplusplus
}
#endif

#endif /* __TOUCH_DRIVER__H__ */