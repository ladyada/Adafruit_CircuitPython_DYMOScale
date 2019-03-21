import board
import pulseio
import digitalio
import time

led = digitalio.DigitalInOut(board.D13)
led.direction = digitalio.Direction.OUTPUT

class ScaleReading:
    OUNCES = const(0x0B)   # data in weight is in ounces
    GRAMS = const(0x02)    # data in weight is in grams
    units = None           # what units we're measuring
    stable = None          # is the measurement stable?
    weight = None          # the weight!

def get_scale_data(pin, timeout=1.0):
    """Read a pulse of SPI data on a pin that corresponds to DYMO scale
    output protocol (12 bytes of data at about 14KHz), timeout is in seconds"""
    timestamp = time.monotonic()
    with pulseio.PulseIn(pin, maxlen=96, idle_state=True) as pulses:
        pulses.pause()
        pulses.clear()
        pulses.resume()

        while len(pulses) < 35:
            if (time.monotonic() - timestamp) > timeout:
                raise RuntimeError("Timed out waiting for data")
        pulses.pause()
        bits = [0] * 96   # there are 12 bytes = 96 bits of data
        bit_idx = 0       # we will count a bit at a time
        bit_val = False   # first pulses will be LOW
        print(pulses[1])
        for i in range(len(pulses)):
            if pulses[i] == 65535:     # This is the pulse between transmits
                break
            num_bits = int(pulses[i] / 75 + 0.5)  # ~14KHz == ~7.5us per clock
            #print("%d (%d)," % (pulses[i], num_bits), end='')
            for bit in range(num_bits):
                #print("bit #", bit_idx)
                bits[bit_idx] = bit_val
                bit_idx += 1
                if bit_idx == 96:      # we have read all the data we wanted
                    #print("DONE")
                    break
            bit_val = not bit_val
        #print(bits)
        data_bytes = [0] * 12
        for byte_n in range(12):
            thebyte = 0
            for bit_n in range(8):
                thebyte <<= 1
                thebyte |= bits[byte_n*8 + bit_n]
            data_bytes[byte_n] = thebyte
        print([hex(i) for i in data_bytes])
        # do some very basic data checking
        if data_bytes[0] != 3 or data_bytes[1] != 3 or data_bytes[7] != 4 \
           or data_bytes[8] != 0x1C or data_bytes[9] != 0 or data_bytes[10] \
           or data_bytes[11] != 0:
              raise RuntimeError("Bad data capture")
        reading = ScaleReading()

        reading.stable = data_bytes[2] & 0x4
        reading.units = data_bytes[3]
        reading.weight = data_bytes[5] + (data_bytes[6] << 8)
        if data_bytes[2] & 0x1:
            reading.weight *= -1
        if reading.units == ScaleReading.OUNCES:
            # oi no easy way to cast to int8_t
            if data_bytes[4] & 0x80:
                data_bytes[4] -= 0x100
            reading.weight *= 10 ** data_bytes[4]
        return reading


while True:
    try:
        reading = get_scale_data(board.MISO)
        if reading.units == ScaleReading.OUNCES:
            print(reading.weight, "oz")
        if reading.units == ScaleReading.GRAMS:
            print(reading.weight, "g")
    except RuntimeError:
        print("Failed to read data, is scale on?")
