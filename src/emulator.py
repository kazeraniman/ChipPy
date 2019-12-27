import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s]:  %(message)s", stream=sys.stdout)
logger.disabled = "pydevd" not in sys.modules

UPPER_CHAR_MASK = 240
LOWER_CHAR_MASK = 15


class Emulator:
    def __init__(self):
        self.registers = bytearray(16)
        self.program_counter = 0

    # region Opcodes
    def run_opcode(self, opcode: bytes):
        self.program_counter += 2
        first_char = opcode[0] >> 4
        if first_char == 1:
            self.opcode_goto(opcode)
        elif first_char == 3:
            self.opcode_if_equal(opcode)
        elif first_char == 4:
            self.opcode_if_not_equal(opcode)
        else:
            logger.error(f"Unimplemented / Invalid Opcode: {opcode.hex()}.")

    def opcode_goto(self, opcode: bytes):
        address = ((opcode[0] & LOWER_CHAR_MASK) << 8) + opcode[1]
        self.program_counter = address
        logger.debug(f"Execute Opcode {opcode.hex}: Jump to address {hex(address)}")

    def opcode_if_equal(self, opcode: bytes):
        register = self.registers[opcode[0] & LOWER_CHAR_MASK]
        if register == opcode[1]:
            self.program_counter += 2

    def opcode_if_not_equal(self, opcode: bytes):
        register = self.registers[opcode[0] & LOWER_CHAR_MASK]
        if register != opcode[1]:
            self.program_counter += 2
    # endregion
