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


ResetPress = False

tt_uio0_pin = 25

display = DisplayDriver(tt_uio0_pin)

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


def reset_pressed(pin):
    global ResetPress
    ResetPress = True
    
rst = Pin(14, Pin.IN)
rst.irq(trigger=Pin.IRQ_FALLING, handler=reset_pressed)

def routine():
    global ResetPress
    while True:
        ResetPress = False
        segment_test()

if __name__ == "__main__":
    routine()
