import machine
import utime
from machine import Pin
class DisplayDriver:
    """
    Naive MicroPython driver for 2 one-digit 7-segment displays with only 8 outputs, using transistor/driver logic on the select line and sacrificing the DP.
    
    It just has
      set(NUMBER) # 0 <= NUMBER <= 0xff 
      show()
    methods.  Show will just loop a few times displaying each digit for "a little bit".
    
    
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
    
    # Segment patterns for 0-F (bit 0 = a, bit 1 = b, ..., bit 6 = g)
    _PATTERNS = [
        0b00111111,  # 0
        0b00000110,  # 1
        0b01011011,  # 2
        0b01001111,  # 3
        0b01100110,  # 4
        0b01101101,  # 5
        0b01111101,  # 6
        0b00000111,  # 7
        0b01111111,  # 8
        0b01101111,  # 9
        0b01110111,  # A
        0b01111100,  # b
        0b00111001,  # C
        0b01011110,  # d
        0b01111001,  # E
        0b01110001,  # F
        0b00000000   # off
    ]

    def __init__(self, seg_start_pin: int):
        self.seg_pins = [
            machine.Pin(seg_start_pin + i, machine.Pin.OUT)
            for i in range(7)  # a through g
        ]
        self.select_pin = machine.Pin(seg_start_pin + 7, machine.Pin.OUT)
        
        # Default to 00
        self.left_pattern = self._PATTERNS[0]
        self.right_pattern = self._PATTERNS[0]
        
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
       

    def set(self, value: int):
        """
        Set the value to display (0..255).
        Interpreted as two hex digits: high nibble = left digit, low nibble = right digit.
        """
        if not 0 <= value <= 255:
            raise ValueError("Value must be between 0 and 255 (00-FF hex)")
        
        high_nibble = (value >> 4) & 0x0F
        low_nibble = value & 0x0F
        
        self.left_pattern = self._PATTERNS[high_nibble]
        self.right_pattern = self._PATTERNS[low_nibble]

    def show(self, loops:int=30, delay_us:int=1200):
        """
        Multiplex one full cycle: left digit (select LOW) then right digit (select HIGH).
        Call this repeatedly in your main loop as fast as possible for flicker-free display.
        """
        
        for i in range(loops):
            # === LEFT DIGIT (MSB) - select LOW ===
            self.select_pin.value(0)          # activate left
            self._set_segments(self.left_pattern)
            utime.sleep_us(delay_us)               # ~800µs on time (adjust if needed)
            
            # Blank before switching to prevent ghosting
            self._off()
            
            # === RIGHT DIGIT (LSB) - select HIGH ===
            self.select_pin.value(1)          # activate right
            self._set_segments(self.right_pattern)
            utime.sleep_us(delay_us)               # ~800µs on time
            # Blank before switching to prevent ghosting
            self._off()


ResetPress = False

tt_uo_out0_pin = 33

display = DisplayDriver(tt_uo_out0_pin)

def flashit(upto:int=0xff+1, loops:int=60, delay:int=700):
    global ResetPress
    for i in range(upto):
        display.set(i)
        if ResetPress:
            return 
        display.show(loops=loops, delay_us=delay)
        

def wakeup(loops:int=200, delay:int=800):
    global ResetPress
    for i in range(16):
        if ResetPress:
            return 
        display.set(i*0x11)
        display.show(loops, delay)
        
    for i in range(8):
        if ResetPress:
            return 
        display.set(0x88) 
        display.show(60, 900)
        display.allOff()
        utime.sleep_ms(75)
        
        
def reset_pressed(pin):
    global ResetPress
    ResetPress = True
    
rst = Pin(14, Pin.IN)
rst.irq(trigger=Pin.IRQ_FALLING, handler=reset_pressed)

def routine():
    global ResetPress
    ResetPress = False
    while True:
        wakeup()
        flashit()
        if ResetPress:
            ResetPress = False

if __name__ == "__main__":
    routine()
