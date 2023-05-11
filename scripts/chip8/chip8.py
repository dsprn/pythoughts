# CHIP-8 INFO
# https://chip-8.github.io/extensions/#chip-8
# https://chip-8.github.io/links/
#
# COMPATIBILITY QUIRKS TABLE
# https://games.gulrak.net/cadmium/chip8-opcode-table.html#quirk6
#
# MASTERING CHIP-8
# https://github.com/mattmikolay/chip-8/wiki/Mastering-CHIP%E2%80%908
#
# TEST SUITE
# https://github.com/Timendus/chip8-test-suite


import argparse
import random
import sys
from functools import wraps

import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "no welcome message"   # this env var disable pygame's welcome message when imported
import pygame
from pygame.locals import (
    K_0, K_1, K_2, K_3, 
    K_4, K_5, K_6, K_7, 
    K_8, K_9, K_a, K_b,
    K_c, K_d, K_e, K_f, 
)


# ******************** STATIC SECTION
C8_FONTS = [0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
            0x20, 0x60, 0x20, 0x20, 0x70,  # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
            0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
            0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
            0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
            0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
            0xF0, 0x80, 0xF0, 0x80, 0x80]  # F

KEY_MAPPINGS = {
    K_0: 0x0,
    K_1: 0x1,
    K_2: 0x2,
    K_3: 0x3,
    K_4: 0x4,
    K_5: 0x5,
    K_6: 0x6,
    K_7: 0x7,
    K_8: 0x8,
    K_9: 0x9,
    K_a: 0xA,
    K_b: 0xB,
    K_c: 0xC,
    K_d: 0xD,
    K_e: 0xE,
    K_f: 0xF,
}

ROM_START_ADDRESS = 0x200
DEBUG = True if int(os.getenv('DEBUG', 0)) >= 1 else False
SCREEN_HEIGHT = 32
SCREEN_WIDTH = 64
SCREEN_RESOLUTION = (SCREEN_WIDTH, SCREEN_HEIGHT)
SCREEN_FLAGS = pygame.SCALED            # if more than one use | to combine them
SCALE = 15
BLUE = pygame.Color(80,69,155,255)
LIGHT_BLUE = pygame.Color(136,126,203,255)


# ******************** UTILITIES SECTION
def asm(msg):
    """decorator to print out the ASM of the instruction being called"""
    def decorator(fn):
        @wraps(fn)
        def wrapper_fn(*args, **kwargs):
            mem_addr = args[0].pc       # args[0] equals self of the decorated method
            vals = fn(*args, **kwargs)  # use the locals() values of each decorated function in the print
            vals['mem_addr'] = mem_addr
            if DEBUG: print(msg.format(**vals))
        return wrapper_fn
    return decorator

def get_rom_arg():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True, help="input rom file")
    args = parser.parse_args()
    return args.file


# ******************** I/O SECTION
class Screen:
    def __init__(self, w=SCREEN_WIDTH, h=SCREEN_HEIGHT, s=SCALE, flgs=SCREEN_FLAGS, bg_color=BLUE, fg_color=LIGHT_BLUE):
        self.w, self.h, self.scale = w, h, s
        self.background = bg_color
        self.foreground = fg_color
        self.buffer = [0] * h * w
        self.surface = pygame.display.set_mode(
            (w * self.scale, h * self.scale),
        )
        self.surface.fill(self.background)

    def read_pixel(self, x, y):
        """return 1 if pixel is ON, return 0 if pixel is OFF"""
        p = self.surface.get_at((x * self.scale, y * self.scale))
        return 0 if p == self.background else 1

    def write_pixel(self, x, y, color):
        """
        set a pixel on the screen, being it a foreground pixel or a background one
        the change won't be immediatly visible because it'll require a call to the static method refresh
        """
        pygame.draw.rect(
            self.surface,
            self.background if color==0 else self.foreground,
            (x * self.scale, y * self.scale, self.scale, self.scale)
        )

    @staticmethod
    def refresh():
        pygame.display.flip()

    def clear(self):
        self.surface.fill(self.background)
        pygame.display.flip()

class Keypad:
    def __init__(self):
        self.pressed_keys = []

    def __getitem__(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
            return True
        return False

    def __setitem__(self, key, value):
        self.pressed_keys.append(key)

    def untouched(self):
        return len(self.pressed_keys) == 0
    
    def first(self):
        """get first button pressed present in the queue"""
        return self.pressed_keys.pop(0)


# ******************** MEMORY SECTION
# ********** WRAPS A LIST TO REPRESENT A STACK WITH A LIMITED SIZE OF 16 ADDRESSES
class Stack:
    def __init__(self):
        self.addr_list = []
        self.size = 0

    def append(self, address):
        if self.size >= 16:
            raise IndexError("The CHIP-8 stack can contain at most 16 addresses. Limit exceeded")
        self.addr_list.append(address)
        self.size += 1

    def pop(self):
        self.size -= 1
        return self.addr_list.pop()

# ********** WRAPS A LIST TO REPRESENT THE MAIN MEMORY WITH A LIMITED SIZE OF 4KB
class Memory:
    def __init__(self):
        self.inner = [0] * 4096
        self.inner[0x00:0x00+len(C8_FONTS)] = C8_FONTS

    def __setitem__(self, key, value):
        self.inner[key] = value

    def __getitem__(self, index):
        return self.inner[index]

    def load_rom(self, path=None):
        """load ROM file from user specified path if present, raise an exception otherwise"""
        with open(path, mode='rb') as f:
            rom = f.read()
        self.inner[ROM_START_ADDRESS:ROM_START_ADDRESS+len(rom)] = rom
        if DEBUG: print(f"The ROM at path {path} has been loaded successfully")


# ******************** CPU SECTION
class Chip8:
    def __init__(self, s=None, k=None):
        self.mem = Memory()
        self.stack = Stack()
        self.v_regs = [0] * 16
        self.pc = ROM_START_ADDRESS
        self.idx = 0    # specify where the sprites reside in memory
        self.dt = 0     # delay timer, active when non-zero
        self.st = 0     # sound timer, active when non-zero
        self.draw = False
        self.instructions = {
            0x00E0: self._clear_screen,
            0x00EE: self._return,
            0x1000: self._jump,
            0x2000: self._call_addr,
            0x3000: self._skip_if_eq,
            0x4000: self._skip_if_not_eq,
            0x5000: self._skip_if_eq_regs,
            0x6000: self._set_vk,
            0x7000: self._add_to_vk,
            0x8000: self._set_vx_to_vy,
            0x8001: self._set_vx_or_vy,
            0x8002: self._set_vx_and_vy,
            0x8003: self._set_vx_xor_vy,
            0x8004: self._add_vx_vy,
            0x8005: self._sub_vx_vy,
            0x8006: self._shr,
            0x8007: self._subn_vx_vy,
            0x800E: self._shl,
            0x9000: self._skip_if_not_eq_regs,
            0xA000: self._set_idx,
            0xB000: self._jump_plus,
            0xC000: self._random_byte_and,
            0xD000: self._to_screen,
            0xE09E: self._skip_if_pressed,
            0xE0A1: self._skip_if_not_pressed,
            0xF007: self._set_vx_dt,
            0xF00A: self._wait_keypress,
            0xF015: self._set_dt_vx,
            0xF018: self._set_st,
            0xF01E: self._add_to_idx,
            0xF029: self._select_char,
            0xF033: self._bcd_repr,
            0xF055: self._store_vregs,
            0xF065: self._load_vregs,
        }
        self.screen = s
        self.keypad = k

    def __str__(self):
        devices = ""
        if self.screen:
            devices += f"SCREEN:{self.screen}"
        if self.keypad:
            devices += " | "
            devices += f"KAYPAD:{self.keypad}"
        registers = f"PC_REGISTER:{self.pc} | IDX_REGISTER:{self.idx} | VARIABLE_REGISTERS:{self.v_regs}"
        stack = f"STACK:{self.stack}"
        flags = f"DRAW: {self.draw}"
        return f"{registers}\n{stack}\n{flags}"

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SKP V{x}")
    def _skip_if_pressed(self, opcode):
        """skip the following instruction if the key corresponding to the hex value stored in Vx is pressed"""
        x = (opcode & 0x0F00) >> 8
        key = self.v_regs[x]
        if self.keypad[key]:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SKNP V{x}")
    def _skip_if_not_pressed(self, opcode):
        """skip the following instruction if the key corresponding to the hex value stored in Vx is NOT pressed"""
        x = (opcode & 0x0F00) >> 8
        key = self.v_regs[x]
        if not self.keypad[key]:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, K")
    def _wait_keypress(self, opcode):
        """wait for a key press and store its value in Vx"""
        x = (opcode & 0x0F00) >> 8
        if self.keypad.untouched():
            self.pc -= 0x2      # stay on the same instruction until a key is pressed
        else:
            self.v_regs[x] = self.keypad.first()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, DT")
    def _set_vx_dt(self, opcode):
        """set Vx = DT (delay timer) value"""
        x = (opcode & 0x0F00) >> 8
        self.v_regs[x] = self.dt
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD DT, V{x}")
    def _set_dt_vx(self, opcode):
        """set DT (delay timer) = Vx"""
        x = (opcode & 0x0F00) >> 8
        self.dt = self.v_regs[x]
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: CLS")
    def _clear_screen(self, opcode):
        self.screen.clear()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: RET")
    def _return(self, opcode):
        """return from a subroutine"""
        self.pc = self.stack.pop()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: JP 0x{address:04x}")
    def _jump(self, opcode):
        address = opcode & 0x0FFF
        self.pc = address
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: CALL 0x{address:04x}")
    def _call_addr(self, opcode):
        address = opcode & 0x0FFF
        self.stack.append(self.pc)
        self.pc = address
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SE V{x}, {comparison_value}")
    def _skip_if_eq(self, opcode):
        x = (opcode & 0x0F00) >> 8
        comparison_value = opcode & 0x00FF
        if self.v_regs[x] == comparison_value:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SNE V{x}, {comparison_value}")
    def _skip_if_not_eq(self, opcode):
        x = (opcode & 0x0F00) >> 8
        comparison_value = opcode & 0x00FF
        if self.v_regs[x] != comparison_value:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SE V{x}, V{y}")
    def _skip_if_eq_regs(self, opcode):
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        if self.v_regs[x] == self.v_regs[y]:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SNE V{x}, V{y}")
    def _skip_if_not_eq_regs(self, opcode):
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        if self.v_regs[x] != self.v_regs[y]:
            self._goto_next_instruction()
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, {value}")
    def _set_vk(self, opcode):
        """set the value of one of the 16 variable registers, Vx"""
        x, value = (opcode & 0x0F00) >> 8, opcode & 0x00FF
        self.v_regs[x] = value
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, V{y}")
    def _set_vx_to_vy(self, opcode):
        """set the value of Vx equal to that of Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] = self.v_regs[y]
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: OR V{x}, V{y}")
    def _set_vx_or_vy(self, opcode):
        """set the value of Vx to Vx OR Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] |= self.v_regs[y]
        self.v_regs[0xF] = 0            # compatibility quirk 1
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: AND V{x}, V{y}")
    def _set_vx_and_vy(self, opcode):
        """set the value of Vx to Vx AND Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] &= self.v_regs[y]
        self.v_regs[0xF] = 0            # compatibility quirk 1
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: XOR V{x}, V{y}")
    def _set_vx_xor_vy(self, opcode):
        """set the value of Vx to Vx XOR Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] ^= self.v_regs[y]
        self.v_regs[0xF] = 0            # compatibility quirk 1
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: ADD V{x}, V{y}")
    def _add_vx_vy(self, opcode):
        """set the value of Vx to Vx + Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        sum = self.v_regs[x] + self.v_regs[y]
        self.v_regs[x] = sum & 0xFF     # keep only the lowest 8 bits from the result and store them in Vx
        self.v_regs[0xF] = 1 if sum > 255 else 0
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SUB V{x}, V{y}")
    def _sub_vx_vy(self, opcode):
        """set the value of Vx to Vx - Vy"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        if self.v_regs[x] > self.v_regs[y]:
            self.v_regs[x] = (self.v_regs[x] - self.v_regs[y]) & 0xFF   # keep only the lowest 8 bits from the result and store them in Vx
            self.v_regs[0xF] = 1
        else:
            self.v_regs[x] = (256 + self.v_regs[x] - self.v_regs[y]) & 0xFF
            self.v_regs[0xF] = 0
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SHR V{x} 1")
    def _shr(self, opcode):
        """set Vx equal to Vx SHR 1"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] = self.v_regs[y]     # compatibility quirk 2
        LSB = self.v_regs[x] & 0x1
        self.v_regs[x] = (self.v_regs[x] >> 1) & 0xFF   # divide by 2 and keep only the lowest 8 bits from the result
        self.v_regs[0xF] = LSB
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SUB V{x}, V{y}")
    def _subn_vx_vy(self, opcode):
        """set the value of Vx to Vy - Vx"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        if self.v_regs[y] > self.v_regs[x]:
            self.v_regs[x] = (self.v_regs[y] - self.v_regs[x]) & 0xFF   # keep only the lowest 8 bits from the result and store them in Vx
            self.v_regs[0xF] = 1
        else:
            self.v_regs[x] = (256 + self.v_regs[y] - self.v_regs[x]) & 0xFF
            self.v_regs[0xF] = 0
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: SHL V{x} 1")
    def _shl(self, opcode):
        """set Vx equal to Vx SHL 1"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] = self.v_regs[y]     # compatibility quirk 2
        MSB = (self.v_regs[x] & 0x80) >> 7
        self.v_regs[x] = (self.v_regs[x] << 1) & 0xFF   # multiply by 2 and keep only the lowest 8 bits from the result
        self.v_regs[0xF] = MSB
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: ADD V{x}, {value}")
    def _add_to_vk(self, opcode):
        """add to the value already present in one of the variable registers"""
        x, value = (opcode & 0x0F00) >> 8, opcode & 0x0FF
        self.v_regs[x] = (self.v_regs[x] + value) & 0xFF    # keep only the lowest 8 bits from the result and store them in Vx
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, V{y}")
    def _copy_reg(self, opcode):
        """store the value of register Vy in register Vx"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        self.v_regs[x] = self.v_regs[y]
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD I, {value}")
    def _set_idx(self, opcode):
        """set the value of the I register"""
        value = opcode & 0x0FFF
        self.idx = value
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: JP V0, 0x{address:04x}")
    def _jump_plus(self, opcode):
        address = opcode & 0x0FFF
        v0 = self.v_regs[0x0]
        self.pc = address + v0
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: RND V{x}, 0x{kk:04x}")
    def _random_byte_and(self, opcode):
        x, kk = (opcode & 0x0F00) >> 8, opcode & 0x00FF
        rnd = random.randint(0,255)
        self.v_regs[x] = rnd & kk
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD ST, V{register}")
    def _set_st(self, opcode):
        """set ST = Vx"""
        register = (opcode & 0x0F00) >> 8
        self.st = self.v_regs[register]
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: ADD I, V{register}")
    def _add_to_idx(self, opcode):
        """set I = I + Vx"""
        register = (opcode & 0x0F00) >> 8
        self.idx += self.v_regs[register]
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD F, V{register}")
    def _select_char(self, opcode):
        """set I to location of sprite for digit Vx"""
        register = (opcode & 0x0F00) >> 8
        self.idx = self.v_regs[register] * 5    # each character font is made of 5 bytes
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD [I], V{x}")
    def _store_vregs(self, opcode):
        """store registers V0 through Vx (included) in memory starting at location I"""
        x = (opcode & 0x0F00) >> 8
        self.mem[self.idx:self.idx+x+1] = self.v_regs[:x+1]
        self.idx += x + 1       # compatibility quirk 6
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD V{x}, [I]")
    def _load_vregs(self, opcode):
        """read registers V0 through Vx (included) from memory starting at location I"""
        x = (opcode & 0x0F00) >> 8
        self.v_regs[:x+1] = self.mem[self.idx:self.idx+x+1]
        self.idx += x + 1       # compatibility quirk 6
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: LD B, V{x}")
    def _bcd_repr(self, opcode):
        """takes the decimal value of Vx and the hundreds digit in memory at I, the tens digit at I+1, the ones digit at I+2"""
        x = (opcode & 0x0F00) >> 8
        ones = self.v_regs[x] % 10
        tens = int(self.v_regs[x] / 10) % 10
        hundreds = int(self.v_regs[x] / 100) % 100
        self.mem[self.idx], self.mem[self.idx+1], self.mem[self.idx+2] = hundreds, tens, ones
        return locals()

    @asm("mem_addr: 0x{mem_addr:04x}    instruction: DRW V{x}, V{y}, {n_bytes}")
    def _to_screen(self, opcode):
        """display n-byte sprite starting at memory location I at (Vx, Vy), set VF = collision"""
        x, y = (opcode & 0x0F00) >> 8, (opcode & 0x00F0) >> 4
        x, y = self.v_regs[x], self.v_regs[y]
        n_bytes = opcode & 0x000F
        self.v_regs[0xF] = 0
        # step through each sprite byte
        for i in range(n_bytes):
            sprite_byte = bin(self.mem[self.idx + i])   # get sprite's bytes one by one starting at self.idx
            sprite_byte = sprite_byte[2:].zfill(8)      # remove '0b' from the front and pad with 0 till it's a byte
            # increment y by one for each new sprite's byte read
            # this allows for wrap around of displayed sprites
            y_coordinate = (y + i) % self.screen.h
            for j, bit in enumerate(sprite_byte):       # step through each byte's bits
                x_coordinate = (x + j) % self.screen.w
                pixel_state = self.screen.read_pixel(x_coordinate, y_coordinate)
                # collision detection
                # sprites are XORed onto the existing screen and if this
                # causes any pixel to be erased then VF=1, otherwise VF=0
                # the only case when a pixel gets erased is when it was ON and is turned ON again
                if pixel_state==1 and int(bit)==1:
                    self.v_regs[0xF] = 1
                self.screen.write_pixel(x_coordinate, y_coordinate, pixel_state^int(bit))
        self.draw = True
        return locals()

    def not_implemented(self, opcode):
        """useful during development as a sort of placeholder/reminder"""
        raise NotImplementedError(f"The opcode for ({hex(opcode)}) has not been implemented yet")

    def _goto_next_instruction(self):
        self.pc += 0x2

    def decode(self, opcode):
        """decode opcodes using masks and return respective function"""
        # WATCH OUT: masks order is important!!!
        # as the for loop breaks out as soon as it finds a match
        mask = None
        masks = {
            0xF0FF: [0xE09E,0xE0A1,0xF007,0xF00A,0xF015,0xF018,0xF01E,0xF029,0xF033,0xF055,0xF065],
            0xF00F: [0x8000,0x8001,0x8002,0x8003,0x8004,0x8005,0x8006,0x8007,0x800E],
            0xF000: [0x1000,0x2000,0x3000,0x4000,0x5000,0x6000,0x7000,0x9000,0xA000,0xB000,0xC000,0xD000],
            0x00FF: [0x00EE],
            0x00F0: [0x00E0],
        }
        if DEBUG: print(f"opcode: 0x{opcode:04x}", end="    ")
        # get correct mask to decode the opcode
        for m, ops in list(masks.items()):
            if (opcode & m) in ops:
                mask = m
                break
        return self.instructions[opcode & mask]     # retrieve and return relative instruction

    def cycle(self):
        self.draw = False
        # fetch (each instruction is two bytes long)
        opcode = self.mem[self.pc] << 8 | self.mem[self.pc + 1]
        self._goto_next_instruction()
        # decode + execute
        instruction = self.decode(opcode)
        instruction(opcode)
        # refresh screen if needed
        if self.draw:
            self.screen.refresh()
        # delay/sound timers (dt/st)
        if self.dt > 0:
            self.dt -= 1
        if self.st > 0:
            self.st -= 1


# ******************** ENTRY POINT SECTION
def main(*args, **kwargs):
    # pygame initialization
    pygame.init()
    clock = pygame.time.Clock()
    rom_name = get_rom_arg()
    pygame.display.set_caption(rom_name.split('/')[-1])
    # IO
    s = Screen()
    k = Keypad()
    # CPU
    chip = Chip8(s, k)
    chip.mem.load_rom(rom_name)
    # emulation loop
    run = True
    while run:
        # frames per second
        clock.tick(300)
        try:
            # process user input
            # loop throught the event queue
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        run = False
                    elif event.key in KEY_MAPPINGS.keys():
                        chip.keypad[KEY_MAPPINGS[event.key]] = True     # register keypress
                elif event.type == pygame.QUIT:
                    run = False
            chip.cycle()        # emulate one machine cycle (fetch opcode, decode opcode, execute opcode, update timers)
        except NotImplementedError as nie:
            sys.exit(f"********** THE EMULATOR CRASHED WITH THE FOLLOWING STATE\n{chip}")


if __name__ == "__main__":
    main()
    pygame.quit()
