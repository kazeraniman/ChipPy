from unittest import mock

from src.emulator import Emulator


class TestIndividualOpcodes:
    def setup_method(self):
        self.emulator = Emulator()

    def test_opcode_goto(self):
        assert self.emulator.program_counter == 0, "Program counter starting at an unexpected value."

        self.emulator.opcode_goto(bytes.fromhex("14e5"))
        assert self.emulator.program_counter == int("4e5", 16), "Program counter incorrect after jump opcode."

    def test_opcode_if_equal(self):
        assert self.emulator.program_counter == 0, "Program counter starting at an unexpected value."
        assert self.emulator.registers[6] == 0, "Register starting at an unexpected value."

        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == 0, "Program counter was changed despite register value not matching."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == 2, "Next instruction was not skipped when it should have been."

    def test_opcode_if_not_equal(self):
        assert self.emulator.program_counter == 0, "Program counter starting at an unexpected value."

        self.emulator.registers[6] = int("98", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == 0, "Program counter was changed despite register value matching."

        self.emulator.registers[6] = int("ff", 16)
        self.emulator.opcode_if_not_equal(bytes.fromhex("3698"))
        assert self.emulator.program_counter == 2, "Next instruction was not skipped when it should have been."


class TestOpcodeRouting:
    @classmethod
    def setup_class(cls):
        cls.emulator = Emulator()

    def run_opcode(self, opcode: bytes, bad_opcode: bytes, mock_method: mock.patch.object):
        self.emulator.run_opcode(bad_opcode)
        mock_method.assert_not_called()

        self.emulator.run_opcode(opcode)
        mock_method.assert_called_with(opcode)

    @mock.patch.object(Emulator, "opcode_goto")
    def test_goto(self, mock_method):
        opcode = bytes.fromhex("132a")
        bad_opcode = bytes.fromhex("332a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_equal")
    def test_if_equal(self, mock_method):
        opcode = bytes.fromhex("332a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)

    @mock.patch.object(Emulator, "opcode_if_not_equal")
    def test_if_not_equal(self, mock_method):
        opcode = bytes.fromhex("432a")
        bad_opcode = bytes.fromhex("132a")
        self.run_opcode(opcode, bad_opcode, mock_method)
