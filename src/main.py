import machine
import utime
from machine import Pin
class DisplayDriver:
    """
    Naive MicroPython driver for 2 one-digit 7-segment displays with only 8 outputs, using transistor/driver logic on the select line and sacrificing the DP.

    It just has
      show_pattern(digit_select, pattern)
      allOff()
    methods, for lighting an arbitrary set of segments on a single digit.


    Wiring assumption:
      seg_start_pin     -> segment a
      seg_start_pin + 1 -> segment b
      ...
      seg_start_pin + 6 -> segment g
      seg_start_pin + 7 -> digit select pin
                        (LOW  = left digit / MSB  active)
                        (HIGH = right digit / LSB active)
                        
    this is how the TT demoboard PMODs are wired, so you can just pass, e.g. uo_out0 pin and the rest just wires itself up grandly.
    """
    
    def __init__(self, seg_start_pin: int):
        self.seg_pins = [
            machine.Pin(seg_start_pin + i, machine.Pin.OUT)
            for i in range(7)  # a through g
        ]
        self.select_pin = machine.Pin(seg_start_pin + 7, machine.Pin.OUT)

        # Start with both digits off
        self._off()

    def _set_segments(self, pattern: int):
        for i in range(7):
            self.seg_pins[i].value((pattern >> i) & 1)

    def _off(self):
        """Turn all segments and both digits off (no ghosting)."""
        self._set_segments(0)
        self.select_pin.value(0)  
        
    def allOff(self):
        self._off()

    def show_pattern(self, digit_select: int, pattern: int):
        """
        Light exactly the segments set in pattern on one digit; all other segments off.

        digit_select: 0 = left digit, 1 = right digit
        pattern: bitmask, bit 0=a, bit 1=b, ..., bit 6=g
        """
        self.select_pin.value(digit_select)
        self._set_segments(pattern)


class SingleDigitDriver:
    """
    Drives a single onboard 7-segment digit (with decimal point), wired
    directly with no digit-select multiplexing (only one digit, so no
    sharing of segment lines needed).

    Wiring assumption:
      seg_start_pin     -> segment a
      seg_start_pin + 1 -> segment b
      ...
      seg_start_pin + 6 -> segment g
      seg_start_pin + 7 -> decimal point
    """

    def __init__(self, seg_start_pin: int):
        self.seg_pins = [
            machine.Pin(seg_start_pin + i, machine.Pin.OUT)
            for i in range(8)  # a through g, then dp
        ]
        self.allOff()

    def show_pattern(self, pattern: int):
        """pattern: bitmask, bit 0=a, bit 1=b, ..., bit 6=g, bit 7=dp"""
        for i in range(8):
            self.seg_pins[i].value((pattern >> i) & 1)

    def allOff(self):
        self.show_pattern(0)


ResetPress = False

tt_uio0_pin = 25
tt_uo_out0_pin = 33
tt_ui_in0_pin = 17

display = DisplayDriver(tt_uio0_pin)
onboard = SingleDigitDriver(tt_uo_out0_pin)

def segment_test(on_ms: int = 150, off_ms: int = 150, flash_count: int = 4):
    global ResetPress
    for digit_select in (1, 0):    # right digit, then left digit
        display.allOff()
        pattern = 0
        for seg in range(7):        # a..g, each stays lit as the next is added
            if ResetPress:
                return
            pattern |= (1 << seg)
            display.show_pattern(digit_select, pattern)
            utime.sleep_ms(on_ms)

        for _ in range(flash_count):  # all segments lit: flash together
            if ResetPress:
                return
            display.allOff()
            utime.sleep_ms(off_ms)
            display.show_pattern(digit_select, pattern)
            utime.sleep_ms(on_ms)

    display.allOff()


# --- rotary encoder chase, on the onboard digit ---
# Segments a..f (bits 0..5) form the outer ring of the digit, in physical
# clockwise order, so the chase position doubles as the bit index directly.
# Segment g (bit 6) is the middle bar, toggled by the encoder's button.

RING_SIZE = 6      # segments a..f
GEAR = 4           # encoder steps per segment (geared down for controllability)

enc_counter = 0     # raw encoder step count, geared down into chase_pos
middle_on = False   # toggled by encoder button (segment g)

def _redraw_onboard():
    chase_pos = (enc_counter // GEAR) % RING_SIZE
    pattern = (1 << chase_pos)
    if middle_on:
        pattern |= (1 << 6)
    onboard.show_pattern(pattern)

pin_enc_a = Pin(tt_ui_in0_pin, Pin.IN, Pin.PULL_UP)
pin_enc_b = Pin(tt_ui_in0_pin + 1, Pin.IN, Pin.PULL_UP)
pin_enc_btn = Pin(tt_ui_in0_pin + 2, Pin.IN, Pin.PULL_UP)

# Standard quadrature decode: keyed by (previous 2-bit state << 2) | new
# 2-bit state, giving +/-1 only for valid single steps and ignoring bounce.
_QUAD_STEP = {
    0b0001: 1, 0b0111: 1, 0b1110: 1, 0b1000: 1,
    0b0010: -1, 0b1011: -1, 0b1101: -1, 0b0100: -1,
}
_quad_state = (pin_enc_a.value() << 1) | pin_enc_b.value()

def _encoder_irq(pin):
    global _quad_state, enc_counter
    new_state = (pin_enc_a.value() << 1) | pin_enc_b.value()
    step = _QUAD_STEP.get((_quad_state << 2) | new_state, 0)
    if step:
        enc_counter = (enc_counter + step) % (GEAR * RING_SIZE)
        _redraw_onboard()
    _quad_state = new_state

pin_enc_a.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_encoder_irq)
pin_enc_b.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=_encoder_irq)

_btn_last_ms = 0

def _encoder_btn_irq(pin):
    global middle_on, _btn_last_ms
    now = utime.ticks_ms()
    if utime.ticks_diff(now, _btn_last_ms) < 50:  # debounce
        return
    _btn_last_ms = now
    middle_on = not middle_on
    _redraw_onboard()

pin_enc_btn.irq(trigger=Pin.IRQ_FALLING, handler=_encoder_btn_irq)

_redraw_onboard()


def reset_pressed(pin):
    global ResetPress, enc_counter, middle_on
    ResetPress = True
    enc_counter = 0
    middle_on = False
    _redraw_onboard()

rst = Pin(14, Pin.IN)
rst.irq(trigger=Pin.IRQ_FALLING, handler=reset_pressed)

def routine():
    global ResetPress
    while True:
        ResetPress = False
        segment_test()

if __name__ == "__main__":
    routine()
